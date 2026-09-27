import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from clothes_model.core.persistence import PersistenceConflict
from clothes_model.infrastructure.database import (
    SqlAlchemyUnitOfWork,
    create_database_runtime,
    models,
)
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.modules.comfy.domain import ComfyNodeConfig
from clothes_model.modules.workflows.domain import WorkflowValidationRun, WorkflowVersion


def sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path.as_posix()}"


def now() -> datetime:
    return datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def workflow(
    version_id: str,
    workflow_id: str,
    version: int,
    digest: str,
    *,
    state: str = "draft",
) -> WorkflowVersion:
    active = state in {"active", "retired"}
    return WorkflowVersion(
        id=version_id,
        workflow_id=workflow_id,
        version=version,
        mode="precise_try_on",
        display_name=f"Try-on v{version}",
        state=state,  # type: ignore[arg-type]
        workflow_sha256=digest * 64,
        workflow_path=f"workflows/{version_id}/workflow.json",
        manifest_sha256=chr(ord(digest) + 1) * 64,
        manifest_path=f"workflows/{version_id}/manifest.json",
        bindings_schema_version="1",
        manifest_json='{"schema_version":"1"}',
        capabilities_json='{"modes":["precise_try_on"]}',
        validation_json='{"status":"passed"}' if active else None,
        validated_at=now() if active else None,
        activated_at=now() if active else None,
        retired_at=now() if state == "retired" else None,
        created_at=now(),
    )


def test_comfy_singleton_and_workflow_constraints(tmp_path: Path) -> None:
    database_url = sqlite_url(tmp_path / "phase5.db")
    upgrade_database(database_url, tmp_path / "migration.lock")

    async def exercise() -> None:
        runtime = create_database_runtime(database_url, 5000)
        try:
            node = ComfyNodeConfig(
                id="default",
                endpoint="https://comfy.internal",
                timeout_seconds=60,
                enabled=True,
                health_status="unchecked",
                credential_envelope='{"ciphertext":"redacted"}',
                credential_updated_at=now(),
                created_at=now(),
                updated_at=now(),
            )
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.comfy_node.save(node)
                await uow.workflows.add(workflow("workflow-v1", "workflow", 1, "a"))
                await uow.workflows.add_validation(
                    WorkflowValidationRun(
                        id="validation-1",
                        workflow_version_id="workflow-v1",
                        status="passed",
                        result_json='{"status":"passed"}',
                        checked_node_fingerprint="node-a",
                        created_at=now(),
                    )
                )
                await uow.commit()

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                assert await uow.comfy_node.get() == node
                versions = await uow.workflows.list_versions("workflow")
                assert [item.version for item in versions] == [1]

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.workflows.add(workflow("active-v1", "active-a", 1, "c", state="active"))
                await uow.commit()
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                with pytest.raises(PersistenceConflict):
                    await uow.workflows.add(
                        workflow("active-v2", "active-b", 1, "e", state="active")
                    )

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                current = await uow.workflows.get("workflow-v1")
                assert current is not None
                with pytest.raises(IntegrityError, match="immutable"):
                    await uow.session.execute(
                        update(models.workflow_versions)
                        .where(models.workflow_versions.c.id == current.id)
                        .values(workflow_sha256="f" * 64)
                    )

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                current = await uow.workflows.get("active-v1")
                assert current is not None
                retired = replace(current, state="retired", retired_at=now())
                await uow.workflows.update_lifecycle(retired)
                await uow.commit()
                assert await uow.workflows.get_active("precise_try_on") is None
        finally:
            await runtime.close()

    asyncio.run(exercise())

