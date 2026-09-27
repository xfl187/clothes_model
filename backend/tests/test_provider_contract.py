import asyncio

import pytest

from clothes_model.modules.providers.domain import (
    ProviderError,
    ProviderInvocation,
    ProviderRequest,
)
from clothes_model.modules.providers.infrastructure.fake import FakeImageEditAdapter
from clothes_model.modules.providers.infrastructure.registry import ProviderRegistry
from clothes_model.modules.providers.infrastructure.volcengine_ark import (
    VolcengineArkSeedreamAdapter,
)


def invocation(scenario: str, **parameters: object) -> ProviderInvocation:
    return ProviderInvocation(
        provider_id="provider-1",
        config_revision_id="revision-1",
        adapter_type="fake_image_edit",
        endpoint="https://fake.local",
        model="fake-model",
        timeout_seconds=30,
        vendor_parameters={"scenario": scenario, **parameters},
        credential="secret",
    )


def request(item_id: str = "item-1") -> ProviderRequest:
    return ProviderRequest(
        job_item_id=item_id,
        candidate_index=0,
        candidate_count=1,
        seed=7,
        person_bytes=b"person",
        garment_bytes=b"garment",
    )


def exercise() -> None:
    adapter = FakeImageEditAdapter()

    async def run() -> None:
        success = invocation("success")
        assert await adapter.availability(success) == "available"
        capabilities = await adapter.capabilities(success)
        assert capabilities.multiple_candidates is True
        submission = await adapter.submit(success, request("success-item"))
        assert submission.external_execution_id == "fake-success-item"
        assert (await adapter.query(success, submission.external_execution_id)).state == "succeeded"
        outputs = await adapter.fetch_outputs(success, submission.external_execution_id)
        assert outputs and outputs[0].content.startswith(b"\x89PNG")
        assert await adapter.cancel(success, submission.external_execution_id) is True

        offline = invocation("offline")
        assert await adapter.availability(offline) == "temporarily_offline"
        with pytest.raises(ProviderError) as offline_error:
            await adapter.submit(offline, request("offline-item"))
        assert offline_error.value.error_class == "temporarily_offline"

        transient = invocation("transient", transient_failures=1)
        transient_submission = await adapter.submit(transient, request("transient-item"))
        first = await adapter.query(transient, transient_submission.external_execution_id)
        assert first.state == "failed"
        assert first.error is not None and first.error.error_class == "retryable_transient"
        second = await adapter.query(transient, transient_submission.external_execution_id)
        assert second.state == "succeeded"

        ambiguous = invocation("ambiguous")
        ambiguous_submission = await adapter.submit(ambiguous, request("ambiguous-item"))
        with pytest.raises(ProviderError) as ambiguous_error:
            await adapter.query(ambiguous, ambiguous_submission.external_execution_id)
        assert ambiguous_error.value.error_class == "externally_ambiguous"

        reject = invocation("reject")
        with pytest.raises(ProviderError) as reject_error:
            await adapter.submit(reject, request("reject-item"))
        assert reject_error.value.error_class == "rejected_input"

        invalid = invocation("invalid_config")
        assert await adapter.availability(invalid) == "unavailable_configuration"

        uncancellable = invocation("uncancellable")
        uncancellable_submission = await adapter.submit(
            uncancellable, request("uncancellable-item")
        )
        cancelled = await adapter.cancel(
            uncancellable, uncancellable_submission.external_execution_id
        )
        assert cancelled is False

    asyncio.run(run())


def test_fake_adapter_contract_scenarios() -> None:
    exercise()


def test_registry_rejects_fake_adapter_in_production() -> None:
    registry = ProviderRegistry([FakeImageEditAdapter()], environment="production")
    with pytest.raises(ProviderError) as error:
        registry.resolve("fake_image_edit")
    assert error.value.code == "fake_adapter_forbidden"

    development = ProviderRegistry([FakeImageEditAdapter()], environment="development")
    assert development.resolve("fake_image_edit").adapter_type == "fake_image_edit"


def test_registry_accepts_seedream_adapter_in_production() -> None:
    registry = ProviderRegistry([VolcengineArkSeedreamAdapter()], environment="production")
    assert registry.resolve("volcengine_ark_seedream").adapter_type == (
        "volcengine_ark_seedream"
    )
