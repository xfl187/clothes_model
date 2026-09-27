import asyncio
import base64
from typing import Any, cast

import httpx2
import pytest

from clothes_model.modules.providers.domain import (
    ProviderError,
    ProviderInvocation,
    ProviderRequest,
)
from clothes_model.modules.providers.infrastructure.volcengine_ark import (
    ARK_ADAPTER_TYPE,
    ARK_BASE_URL,
    ARK_MODEL,
    PROMPT_TEMPLATE_VERSION,
    VolcengineArkSeedreamAdapter,
)

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
JPEG = b"\xff\xd8\xff\xd9"


def invocation(**changes: object) -> ProviderInvocation:
    values: dict[str, Any] = {
        "provider_id": "provider-1",
        "config_revision_id": "revision-1",
        "adapter_type": ARK_ADAPTER_TYPE,
        "endpoint": ARK_BASE_URL,
        "model": ARK_MODEL,
        "timeout_seconds": 30,
        "vendor_parameters": {},
        "credential": "ark-secret",
    }
    values.update(changes)
    return ProviderInvocation(**values)


def request() -> ProviderRequest:
    return ProviderRequest(
        job_item_id="item-1",
        candidate_index=0,
        candidate_count=1,
        seed=7,
        person_bytes=PNG,
        garment_bytes=JPEG,
    )


def test_seedream_request_and_immediate_output() -> None:
    captured: dict[str, object] = {}

    async def handler(http_request: httpx2.Request) -> httpx2.Response:
        captured["request"] = http_request
        return httpx2.Response(
            200,
            json={"data": [{"b64_json": base64.b64encode(PNG).decode("ascii")}]},
        )

    async def run() -> None:
        client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
        adapter = VolcengineArkSeedreamAdapter(client)
        assert await adapter.availability(invocation()) == "available"
        capabilities = await adapter.capabilities(invocation())
        assert capabilities.max_candidates == 1
        assert capabilities.multiple_candidates is False
        submission = await adapter.submit(invocation(), request())
        assert submission.state == "completed"
        assert submission.external_execution_id is None
        assert submission.outputs[0].content == PNG
        assert submission.outputs[0].actual_parameters["prompt_template_version"] == (
            PROMPT_TEMPLATE_VERSION
        )
        await client.aclose()

    asyncio.run(run())
    http_request = cast(httpx2.Request, captured["request"])
    assert str(http_request.url) == f"{ARK_BASE_URL}/images/generations"
    assert http_request.headers["authorization"] == "Bearer ark-secret"
    payload = cast(dict[str, Any], __import__("json").loads(http_request.content))
    assert payload["model"] == ARK_MODEL
    assert payload["response_format"] == "b64_json"
    assert payload["sequential_image_generation"] == "disabled"
    assert payload["stream"] is False
    assert payload["watermark"] is True
    images = cast(list[str], payload["image"])
    assert images[0].startswith("data:image/png;base64,")
    assert images[1].startswith("data:image/jpeg;base64,")


@pytest.mark.parametrize(
    ("status", "body", "error_class", "retryable"),
    [
        (400, {"error": {"code": "InvalidParameter"}}, "rejected_input", False),
        (401, {"error": {"code": "Unauthorized"}}, "invalid_configuration", False),
        (403, {"error": {"code": "Forbidden"}}, "invalid_configuration", False),
        (413, {"error": {"code": "TooLarge"}}, "rejected_input", False),
        (429, {"error": {"code": "RateLimit"}}, "retryable_transient", True),
        (500, {"error": {"code": "InternalError"}}, "retryable_transient", True),
    ],
)
def test_seedream_maps_safe_http_errors(
    status: int, body: dict[str, object], error_class: str, retryable: bool
) -> None:
    async def handler(_: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status, json=body)

    async def run() -> None:
        client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
        adapter = VolcengineArkSeedreamAdapter(client)
        with pytest.raises(ProviderError) as caught:
            await adapter.submit(invocation(), request())
        assert caught.value.error_class == error_class
        assert caught.value.retryable is retryable
        assert "ark-secret" not in caught.value.detail
        await client.aclose()

    asyncio.run(run())


def test_seedream_rejects_invalid_boundary_and_output() -> None:
    async def malformed(_: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"data": [{"b64_json": "not base64"}]})

    async def run() -> None:
        client = httpx2.AsyncClient(transport=httpx2.MockTransport(malformed))
        adapter = VolcengineArkSeedreamAdapter(client)
        with pytest.raises(ProviderError) as endpoint_error:
            await adapter.capabilities(invocation(endpoint="https://evil.example/api/v3"))
        assert endpoint_error.value.code == "ark_endpoint_invalid"
        with pytest.raises(ProviderError) as model_error:
            await adapter.capabilities(invocation(model="other-model"))
        assert model_error.value.code == "ark_model_unsupported"
        with pytest.raises(ProviderError) as response_error:
            await adapter.submit(invocation(), request())
        assert response_error.value.code == "ark_response_invalid"
        await client.aclose()

    asyncio.run(run())


def test_seedream_transport_failure_is_ambiguous_and_operations_are_conservative() -> None:
    async def failed(http_request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("lost response", request=http_request)

    async def run() -> None:
        client = httpx2.AsyncClient(transport=httpx2.MockTransport(failed))
        adapter = VolcengineArkSeedreamAdapter(client)
        with pytest.raises(ProviderError) as submit_error:
            await adapter.submit(invocation(), request())
        assert submit_error.value.error_class == "externally_ambiguous"
        with pytest.raises(ProviderError) as query_error:
            await adapter.query(invocation(), "unknown")
        assert query_error.value.error_class == "externally_ambiguous"
        assert await adapter.cancel(invocation(), "unknown") is False
        with pytest.raises(ProviderError):
            await adapter.fetch_outputs(invocation(), "unknown")
        await client.aclose()

    asyncio.run(run())
