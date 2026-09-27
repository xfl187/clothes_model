"""Secure configuration and bounded health probing for the physical ComfyUI node."""

from __future__ import annotations

import ipaddress
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import urlsplit
from uuid import uuid4

import httpx2

from clothes_model.infrastructure.security import AesGcmSecretCipher, SecretCryptoError
from clothes_model.modules.auth.domain import SecurityAuditEvent
from clothes_model.modules.comfy.application.ports import ComfyUnitOfWork
from clothes_model.modules.comfy.domain import ComfyNodeConfig

SECRET_PURPOSE = "comfy_node_credential"
MAX_PROBE_BYTES = 2_000_000


class ComfyNodeError(RuntimeError):
    def __init__(self, code: str, detail: str, *, status: int = 409) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status


class ComfyNodeService:
    def __init__(
        self,
        uow_factory: Callable[[], ComfyUnitOfWork],
        cipher: AesGcmSecretCipher | None,
        client: httpx2.AsyncClient,
        *,
        environment: str,
        allowed_hosts: tuple[str, ...],
    ) -> None:
        self._uow_factory = uow_factory
        self._cipher = cipher
        self._client = client
        self._environment = environment
        self._allowed_hosts = {item.lower() for item in allowed_hosts}

    def validate_endpoint(self, endpoint: str) -> str:
        parsed = urlsplit(endpoint)
        host = (parsed.hostname or "").lower()
        if (
            not host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ComfyNodeError("comfy_endpoint_invalid", "ComfyUI 节点地址格式无效。", status=422)
        loopback = False
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = host == "localhost"
        if parsed.scheme != "https" and not (
            self._environment in {"development", "test"} and parsed.scheme == "http" and loopback
        ):
            raise ComfyNodeError(
                "comfy_endpoint_scheme_rejected",
                "ComfyUI 节点必须使用 HTTPS。",
                status=422,
            )
        if host not in self._allowed_hosts and not (
            self._environment in {"development", "test"} and loopback
        ):
            raise ComfyNodeError(
                "comfy_endpoint_host_rejected",
                "ComfyUI 节点主机不在部署允许列表中。",
                status=422,
            )
        return endpoint.rstrip("/")

    async def get(self) -> ComfyNodeConfig | None:
        async with self._uow_factory() as uow:
            return await uow.comfy_node.get()

    async def update(
        self,
        *,
        endpoint: str,
        timeout_seconds: int,
        enabled: bool,
        credential: str | None,
        actor_id: str,
    ) -> ComfyNodeConfig:
        endpoint = self.validate_endpoint(endpoint)
        timestamp = datetime.now(UTC)
        async with self._uow_factory() as uow:
            current = await uow.comfy_node.get()
            envelope = current.credential_envelope if current else None
            credential_updated_at = current.credential_updated_at if current else None
            if credential is not None:
                if not credential or len(credential) > 4096:
                    raise ComfyNodeError(
                        "comfy_credential_invalid", "节点凭据长度无效。", status=422
                    )
                if self._cipher is None:
                    raise ComfyNodeError(
                        "secret_store_unavailable", "加密主密钥不可用，无法保存节点凭据。"
                    )
                envelope = self._cipher.encrypt(
                    credential, purpose=SECRET_PURPOSE, record_id="default"
                )
                credential_updated_at = timestamp
            changed = current is None or any(
                (
                    current.endpoint != endpoint,
                    current.timeout_seconds != timeout_seconds,
                    current.enabled != enabled,
                    credential is not None,
                )
            )
            previous_health = current.health_status if current else "unchecked"
            previous_detail = current.health_detail if current else None
            previous_version = current.observed_server_version if current else None
            previous_capabilities = current.observed_capabilities_json if current else "{}"
            previous_checked_at = current.last_checked_at if current else None
            config = ComfyNodeConfig(
                id="default",
                endpoint=endpoint,
                timeout_seconds=timeout_seconds,
                enabled=enabled,
                health_status="unchecked" if changed else previous_health,
                credential_envelope=envelope,
                credential_updated_at=credential_updated_at,
                health_detail=None if changed else previous_detail,
                observed_server_version=None if changed else previous_version,
                observed_capabilities_json="{}" if changed else previous_capabilities,
                last_checked_at=None if changed else previous_checked_at,
                created_at=current.created_at if current else timestamp,
                updated_at=timestamp,
            )
            await uow.comfy_node.save(config)
            await uow.security_audit.add(
                SecurityAuditEvent(
                    id=str(uuid4()),
                    action="comfy_node.updated",
                    actor_kind="admin_session",
                    actor_id=actor_id,
                    outcome="succeeded",
                    context_json=json.dumps(
                        {"enabled": enabled, "credential_rotated": credential is not None},
                        separators=(",", ":"),
                    ),
                    created_at=timestamp,
                )
            )
            await uow.commit()
            return config

    async def probe(self, *, actor_id: str) -> tuple[ComfyNodeConfig, dict[str, object]]:
        timestamp = datetime.now(UTC)
        async with self._uow_factory() as uow:
            config = await uow.comfy_node.get()
        if config is None:
            raise ComfyNodeError("comfy_node_not_configured", "ComfyUI 节点尚未配置。", status=404)
        credential: str | None = None
        if config.credential_envelope is not None:
            if self._cipher is None:
                raise ComfyNodeError("secret_store_unavailable", "加密主密钥不可用。")
            try:
                credential = self._cipher.decrypt(
                    config.credential_envelope, purpose=SECRET_PURPOSE, record_id="default"
                )
            except SecretCryptoError as error:
                raise ComfyNodeError("secret_decryption_failed", "节点凭据无法解密。") from error
        headers = {"Accept": "application/json"}
        if credential:
            headers["Authorization"] = f"Bearer {credential}"
        health = "healthy"
        detail = "ComfyUI 节点连接正常。"
        version: str | None = None
        capabilities: dict[str, object] = {}
        try:
            system = await self._get_json(
                f"{config.endpoint}/system_stats", headers, config.timeout_seconds
            )
            objects = await self._get_json(
                f"{config.endpoint}/object_info", headers, config.timeout_seconds
            )
            system_data = system.get("system")
            if isinstance(system_data, dict):
                value = cast(dict[str, object], system_data).get("comfyui_version")
                version = value[:160] if isinstance(value, str) else None
            if not objects:
                health = "incompatible"
                detail = "节点未返回可用的 ComfyUI 节点元数据。"
            else:
                capabilities = {"node_count": len(objects)}
        except ComfyNodeError as error:
            health = "offline" if error.code != "comfy_response_invalid" else "incompatible"
            detail = error.detail
        updated = replace(
            config,
            health_status=cast(Any, health),
            health_detail=detail,
            observed_server_version=version,
            observed_capabilities_json=json.dumps(capabilities, separators=(",", ":")),
            last_checked_at=timestamp,
            updated_at=timestamp,
        )
        async with self._uow_factory() as uow:
            await uow.comfy_node.save(updated)
            await uow.security_audit.add(
                SecurityAuditEvent(
                    id=str(uuid4()),
                    action="comfy_node.probed",
                    actor_kind="admin_session",
                    actor_id=actor_id,
                    outcome="succeeded" if health == "healthy" else "failed",
                    context_json=json.dumps({"health": health}, separators=(",", ":")),
                    created_at=timestamp,
                )
            )
            await uow.commit()
        return updated, {
            "status": "passed" if health == "healthy" else "failed",
            "checked_at": timestamp,
            "detail": detail,
        }

    async def _get_json(
        self, url: str, headers: dict[str, str], timeout_seconds: int
    ) -> dict[str, object]:
        try:
            response = await self._client.get(url, headers=headers, timeout=timeout_seconds)
        except Exception as error:
            raise ComfyNodeError(
                "comfy_connection_failed", "无法连接 ComfyUI 节点。"
            ) from error
        if 300 <= response.status_code < 400:
            raise ComfyNodeError("comfy_redirect_rejected", "ComfyUI 节点返回了禁止的重定向。")
        if response.status_code < 200 or response.status_code >= 300:
            raise ComfyNodeError("comfy_connection_failed", "ComfyUI 节点连接测试失败。")
        if len(response.content) > MAX_PROBE_BYTES:
            raise ComfyNodeError("comfy_response_too_large", "ComfyUI 节点响应超过安全上限。")
        try:
            value: object = response.json()
        except (TypeError, ValueError) as error:
            raise ComfyNodeError(
                "comfy_response_invalid", "ComfyUI 节点响应格式不兼容。"
            ) from error
        if not isinstance(value, dict):
            raise ComfyNodeError("comfy_response_invalid", "ComfyUI 节点响应格式不兼容。")
        return cast(dict[str, object], value)
