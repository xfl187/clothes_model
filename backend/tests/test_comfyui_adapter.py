import asyncio
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx2
import pytest
from PIL import Image

from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.infrastructure.storage import WorkflowArtifactStorage
from clothes_model.modules.comfy.domain import ComfyNodeConfig
from clothes_model.modules.providers.domain import (
    ProviderCapabilities,
    ProviderError,
    ProviderInvocation,
    ProviderRequest,
)
from clothes_model.modules.providers.infrastructure import ComfyUIAdapter, ProviderRegistry
from clothes_model.modules.workflows.application import canonical_json
from clothes_model.modules.workflows.domain import WorkflowVersion

ADAPTER = "comfyui"


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color=(10, 20, 30)).save(buffer, "PNG")
    return buffer.getvalue()


def _workflow_payload() -> tuple[dict[str, object], dict[str, object]]:
    workflow = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "person.png"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": "garment.png"}},
        "3": {
            "class_type": "KSampler",
            "inputs": {"seed": 0, "candidate_index": 0, "person": ["1", 0]},
        },
        "4": {"class_type": "SaveImage", "inputs": {"images": ["3", 0]}},
    }
    manifest = {
        "schema_version": "1",
        "bindings": {
            "person": {"node_id": "1", "input": "image"},
            "garment": {"node_id": "2", "input": "image"},
            "seed": {"node_id": "3", "input": "seed"},
            "candidate_index": {"node_id": "3", "input": "candidate_index"},
        },
        "outputs": [{"node_id": "4", "output_index": 0}],
        "capabilities": ProviderCapabilities(
            multiple_candidates=False,
            manual_mask=False,
            max_candidates=1,
            source="workflow_declared",
            verification="verified",
        ).to_payload(),
    }
    return workflow, manifest


def _objects() -> dict[str, object]:
    return {
        "LoadImage": {"input": {"required": {"image": ["STRING"]}}},
        "KSampler": {"input": {"required": {"seed": ["INT"], "candidate_index": ["INT"]}}},
        "SaveImage": {},
    }


class _Harness:
    def __init__(self, tmp_path: Path) -> None:
        self.database_url = f"sqlite+aiosqlite:///{(tmp_path / 'comfy.db').as_posix()}"
        upgrade_database(self.database_url, tmp_path / "migration.lock")
        self.runtime = create_database_runtime(self.database_url, 5000)
        self.artifacts = WorkflowArtifactStorage(tmp_path / "storage")
        self.state: dict[str, Any] = {
            "objects": _objects(),
            "upload_calls": [],
            "prompt_calls": [],
            "cleanup_calls": [],
            "history": {},
            "queue": {"queue_pending": [], "queue_running": []},
            "prompt_response": {"prompt_id": "p1"},
            "view_content": _png(),
        }
        self.version_id = str(uuid4())
        self.workflow, self.manifest = _workflow_payload()
        self._seed()

    def _seed(self) -> None:
        workflow_bytes = canonical_json(self.workflow)
        manifest_bytes = canonical_json(self.manifest)
        stored = self.artifacts.publish(self.version_id, workflow_bytes, manifest_bytes)
        now = datetime.now(UTC)

        async def run() -> None:
            async with SqlAlchemyUnitOfWork(self.runtime.sessions) as uow:
                await uow.comfy_node.save(
                    ComfyNodeConfig(
                        id="default",
                        endpoint="https://comfy.example",
                        timeout_seconds=2,
                        enabled=True,
                        health_status="unchecked",
                        created_at=now,
                        updated_at=now,
                    )
                )
                await uow.workflows.add(
                    WorkflowVersion(
                        id=self.version_id,
                        workflow_id="try-on",
                        version=1,
                        mode="precise_try_on",
                        display_name="try-on",
                        state="active",
                        workflow_sha256=hashlib.sha256(workflow_bytes).hexdigest(),
                        workflow_path=stored.workflow_path,
                        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
                        manifest_path=stored.manifest_path,
                        bindings_schema_version="1",
                        manifest_json=manifest_bytes.decode(),
                        capabilities_json=json.dumps(self.manifest["capabilities"]),
                        created_at=now,
                        validated_at=now,
                        activated_at=now,
                    )
                )
                await uow.commit()

        asyncio.run(run())

    def uow_factory(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self.runtime.sessions)

    def invocation(self) -> ProviderInvocation:
        return ProviderInvocation(
            provider_id="logical-comfy",
            config_revision_id="revision-1",
            adapter_type=ADAPTER,
            endpoint="comfy://physical-node",
            model="try-on:1",
            timeout_seconds=2,
            vendor_parameters={"workflow_version_id": self.version_id},
        )

    def request(self, item_id: str = "item-1") -> ProviderRequest:
        return ProviderRequest(
            job_item_id=item_id,
            candidate_index=0,
            candidate_count=1,
            seed=7,
            person_bytes=_png(),
            garment_bytes=_png(),
        )

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        if path == "/system_stats":
            return httpx2.Response(200, json={"system": {"comfyui_version": "test"}})
        if path == "/object_info":
            if isinstance(self.state["objects"], Exception):
                raise self.state["objects"]
            return httpx2.Response(200, json=self.state["objects"])
        if path == "/upload/image":
            self.state["upload_calls"].append(request)
            index = len(self.state["upload_calls"])
            return httpx2.Response(200, json={"name": f"temp/remote-{index}.png"})
        if path == "/prompt":
            self.state["prompt_calls"].append(request)
            value = self.state["prompt_response"]
            if isinstance(value, BaseException):
                raise value
            if isinstance(value, httpx2.Response):
                return value
            return httpx2.Response(200, json=value)
        if path.startswith("/history/"):
            prompt_id = path.rsplit("/", 1)[-1]
            history = self.state["history"]
            if prompt_id in history:
                value = history[prompt_id]
                if isinstance(value, Exception):
                    raise value
                return httpx2.Response(200, json={prompt_id: value})
            return httpx2.Response(200, json={})
        if path == "/queue":
            if request.method == "POST":
                return httpx2.Response(200, json={})
            return httpx2.Response(200, json=self.state["queue"])
        if path == "/view":
            return httpx2.Response(
                200,
                content=self.state["view_content"],
                headers={"Content-Type": "image/png"},
            )
        if path == "/api/clothes-model/temp" and request.method == "DELETE":
            self.state["cleanup_calls"].append(json.loads(request.content.decode() or "{}"))
            return httpx2.Response(204)
        return httpx2.Response(404)

    def adapter(self) -> ComfyUIAdapter:
        client = httpx2.AsyncClient(transport=httpx2.MockTransport(self.handler))
        return ComfyUIAdapter(self.uow_factory, self.artifacts, None, client=client)

    def close(self) -> None:
        asyncio.run(self.runtime.close())


def _succeeded(prompt_id: str, filenames: list[str]) -> dict[str, object]:
    del prompt_id
    images = [{"filename": item, "subfolder": "", "type": "temp"} for item in filenames]
    return {
        "status": {"completed": True, "status_str": "success"},
        "outputs": {"4": {"images": images}},
    }


def test_comfy_adapter_uploads_binds_submits_queries_and_cleans_up(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    harness.state["history"]["p1"] = _succeeded("p1", ["out.png"])
    adapter = harness.adapter()
    invocation = harness.invocation()

    async def run() -> None:
        submission = await adapter.submit(invocation, harness.request())
        assert submission.state == "accepted"
        assert submission.external_execution_id == "p1"

        body = json.loads(harness.state["prompt_calls"][0].content.decode())
        prompt = body["prompt"]
        assert prompt["1"]["inputs"]["image"].endswith(".png")
        assert "temp/" not in prompt["1"]["inputs"]["image"]
        assert prompt["3"]["inputs"]["seed"] == 7
        assert prompt["3"]["inputs"]["candidate_index"] == 0

        # The stored artifact must remain untouched by binding.
        stored = json.loads(harness.artifacts.read(f"workflows/{harness.version_id}/workflow.json"))
        assert stored["1"]["inputs"]["image"] == "person.png"

        status = await adapter.query(invocation, "p1")
        assert status.state == "succeeded"
        outputs = await adapter.fetch_outputs(invocation, "p1")
        assert outputs and outputs[0].content.startswith(b"\x89PNG")
        assert outputs[0].actual_parameters["bindings_schema_version"] == "1"

        cleanup = harness.state["cleanup_calls"][-1]
        assert "out.png" in cleanup["files"]
        assert cleanup["prompt_id"] == "p1"

    asyncio.run(run())
    asyncio.run(adapter.close())
    harness.close()


def test_comfy_adapter_pending_deletion_and_running_interruption_limitation(
    tmp_path: Path,
) -> None:
    harness = _Harness(tmp_path)
    harness.state["queue"]["queue_pending"] = [[0, "pending-1", {}, {}, []]]
    harness.state["queue"]["queue_running"] = [[1, "running-1", {}, {}, []]]
    adapter = harness.adapter()
    invocation = harness.invocation()

    async def run() -> None:
        assert await adapter.cancel(invocation, "pending-1") is True
        assert await adapter.cancel(invocation, "running-1") is False
        assert await adapter.cancel(invocation, "unknown-1") is False

    asyncio.run(run())
    asyncio.run(adapter.close())
    harness.close()


def test_comfy_adapter_query_reports_running_then_unknown(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    adapter = harness.adapter()
    invocation = harness.invocation()

    async def run() -> None:
        harness.state["history"]["p1"] = {
            "status": {"completed": False},
            "outputs": {},
        }
        assert (await adapter.query(invocation, "p1")).state == "running"
        with pytest.raises(ProviderError) as unknown:
            await adapter.query(invocation, "missing")
        assert unknown.value.error_class == "externally_ambiguous"

    asyncio.run(run())
    asyncio.run(adapter.close())
    harness.close()


@pytest.mark.parametrize(
    ("scenario", "expected_class", "expected_code"),
    [
        ("auth", "invalid_configuration", "comfy_auth_failed"),
        ("rejected", "rejected_input", "comfy_prompt_rejected"),
        ("transient", "retryable_transient", "comfy_temporarily_unavailable"),
        ("timeout", "externally_ambiguous", "comfy_submit_outcome_unknown"),
        ("offline", "temporarily_offline", "comfy_connection_failed"),
    ],
)
def test_comfy_adapter_submit_error_mapping(
    tmp_path: Path, scenario: str, expected_class: str, expected_code: str
) -> None:
    harness = _Harness(tmp_path)
    if scenario == "auth":
        harness.state["prompt_response"] = _http_error(401)
    elif scenario == "rejected":
        harness.state["prompt_response"] = _http_error(400)
    elif scenario == "transient":
        harness.state["prompt_response"] = _http_error(503)
    elif scenario == "timeout":
        harness.state["prompt_response"] = httpx2.ReadTimeout("slow")
    elif scenario == "offline":
        harness.state["prompt_response"] = httpx2.ConnectError("refused")
    adapter = harness.adapter()

    async def run() -> None:
        with pytest.raises(ProviderError) as error:
            await adapter.submit(harness.invocation(), harness.request())
        assert error.value.error_class == expected_class
        assert error.value.code == expected_code

    asyncio.run(run())
    asyncio.run(adapter.close())
    harness.close()


def _http_error(status: int) -> httpx2.Response:
    return httpx2.Response(status, json={"error": {"code": f"http_{status}"}})


def test_comfy_adapter_rejects_incompatible_and_unbound_workflow(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    harness.state["objects"] = {"LoadImage": {}}
    adapter = harness.adapter()

    async def run() -> None:
        with pytest.raises(ProviderError) as incompatible:
            await adapter.submit(harness.invocation(), harness.request())
        assert incompatible.value.error_class == "temporarily_offline"
        assert incompatible.value.code == "comfy_workflow_incompatible"

    asyncio.run(run())
    asyncio.run(adapter.close())
    harness.close()

    unbound = _Harness(tmp_path / "unbound")
    unbound_adapter = unbound.adapter()
    invocation = ProviderInvocation(
        provider_id="logical-comfy",
        config_revision_id="revision-1",
        adapter_type=ADAPTER,
        endpoint="comfy://physical-node",
        model="try-on:1",
        timeout_seconds=2,
        vendor_parameters={},
    )

    async def run_unbound() -> None:
        with pytest.raises(ProviderError) as error:
            await unbound_adapter.submit(invocation, unbound.request())
        assert error.value.code == "comfy_workflow_unbound"

    asyncio.run(run_unbound())
    asyncio.run(unbound_adapter.close())
    unbound.close()


def test_comfy_adapter_output_must_be_declared_and_valid(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    escaping = {"filename": "../escape.png", "subfolder": "", "type": "temp"}
    harness.state["history"]["p1"] = {
        "status": {"completed": True, "status_str": "success"},
        "outputs": {"4": {"images": [escaping]}},
    }
    adapter = harness.adapter()

    async def run() -> None:
        await adapter.submit(harness.invocation(), harness.request())
        with pytest.raises(ProviderError) as error:
            await adapter.fetch_outputs(harness.invocation(), "p1")
        assert error.value.code == "comfy_output_invalid"

    asyncio.run(run())
    asyncio.run(adapter.close())
    harness.close()


def test_registry_accepts_comfy_and_rejects_fake_in_production(tmp_path: Path) -> None:
    harness = _Harness(tmp_path)
    adapter = harness.adapter()
    registry = ProviderRegistry([adapter], environment="production")
    assert registry.resolve(ADAPTER).adapter_type == ADAPTER
    from clothes_model.modules.providers.infrastructure import FakeImageEditAdapter

    guarded = ProviderRegistry([FakeImageEditAdapter()], environment="production")
    with pytest.raises(ProviderError):
        guarded.resolve("fake_image_edit")
    asyncio.run(adapter.close())
    harness.close()
