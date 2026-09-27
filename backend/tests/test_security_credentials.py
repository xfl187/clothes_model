import asyncio
import base64
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from argon2.low_level import Type
from sqlalchemy import func, select

from clothes_model import operator
from clothes_model.core.config import Settings
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.infrastructure.database.models import (
    access_tokens,
    admin_sessions,
    security_audit_events,
)
from clothes_model.infrastructure.security import (
    AesGcmSecretCipher,
    Argon2TokenHasher,
    SecretCryptoError,
    generate_token,
    load_master_key,
    parse_token,
)
from clothes_model.modules.auth.application import AuditedSecretCipher, TokenService
from clothes_model.modules.auth.domain import AdminSession


def sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path.as_posix()}"


def fast_hasher(*, time_cost: int = 1) -> Argon2TokenHasher:
    return Argon2TokenHasher(
        PasswordHasher(
            time_cost=time_cost,
            memory_cost=8_192,
            parallelism=1,
            hash_len=16,
            salt_len=16,
            type=Type.ID,
        )
    )


def test_token_format_entropy_hashing_and_redaction() -> None:
    generated = generate_token("app")
    parsed = parse_token(generated.value)
    hasher = fast_hasher()
    encoded = hasher.hash(parsed.secret)

    assert generated.value.startswith("cm.app.")
    assert len(base64.urlsafe_b64decode(parsed.secret + "=")) == 32
    assert hasher.verify(encoded, parsed.secret)
    assert not hasher.verify(encoded, "wrong-secret")
    assert parsed.secret not in repr(generated)
    assert generated.value not in repr(generated)


def test_master_key_loading_and_aes_gcm_fail_closed(tmp_path: Path) -> None:
    key_path = tmp_path / "master.key"
    key = bytes(range(32))
    key_path.write_text(base64.urlsafe_b64encode(key).decode().rstrip("="), encoding="ascii")
    cipher = AesGcmSecretCipher(load_master_key(key_path))
    envelope = cipher.encrypt("provider-secret", purpose="provider.api-key", record_id="p1")

    assert cipher.decrypt(envelope, purpose="provider.api-key", record_id="p1") == "provider-secret"
    assert "provider-secret" not in envelope
    for operation in (
        lambda: AesGcmSecretCipher(bytes(reversed(key))).decrypt(
            envelope, purpose="provider.api-key", record_id="p1"
        ),
        lambda: cipher.decrypt(envelope, purpose="provider.api-key", record_id="p2"),
        lambda: cipher.decrypt(
            envelope.replace('"v":1', '"v":2'),
            purpose="provider.api-key",
            record_id="p1",
        ),
        lambda: load_master_key(None),
    ):
        with pytest.raises(SecretCryptoError):
            operation()

    modified = json.loads(envelope)
    modified["ciphertext"] = ("A" if modified["ciphertext"][0] != "A" else "B") + modified[
        "ciphertext"
    ][1:]
    with pytest.raises(SecretCryptoError):
        cipher.decrypt(json.dumps(modified), purpose="provider.api-key", record_id="p1")


def test_token_lifecycle_bootstrap_rotation_reset_and_audit(tmp_path: Path) -> None:
    database_url = sqlite_url(tmp_path / "security.db")
    upgrade_database(database_url, tmp_path / "migration.lock")

    async def exercise() -> None:
        runtime = create_database_runtime(database_url, 5000)

        def clock() -> datetime:
            return datetime(2026, 9, 26, 12, 0, tzinfo=UTC)

        service = TokenService(lambda: SqlAlchemyUnitOfWork(runtime.sessions), fast_hasher(), clock)
        try:
            issued = await service.bootstrap()
            assert {credential.scope for credential in issued} == {"app", "admin"}
            assert await service.bootstrap() == []
            app = next(item for item in issued if item.scope == "app")
            admin = next(item for item in issued if item.scope == "admin")
            assert await service.verify(app.value, "app") is not None
            assert await service.verify(app.value, "admin") is None
            assert await service.verify(admin.value, "admin") is not None
            assert await service.verify("malformed", "app") is None
            wrong_app = app.value[:-1] + ("A" if app.value[-1] != "A" else "B")
            assert await service.verify(wrong_app, "app") is None

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                app_record = await uow.access_tokens.get_by_public_id(app.public_id)
                assert app_record is not None
                await uow.access_tokens.replace(
                    replace(app_record, expires_at=clock() + timedelta(hours=1))
                )
                await uow.commit()
            expired_service = TokenService(
                lambda: SqlAlchemyUnitOfWork(runtime.sessions),
                fast_hasher(),
                lambda: clock() + timedelta(hours=2),
            )
            assert await expired_service.verify(app.value, "app") is None

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                admin_record = await uow.access_tokens.get_by_public_id(admin.public_id)
                assert admin_record is not None
                await uow.admin_sessions.add(
                    AdminSession(
                        id="session-lineage",
                        token_id=admin_record.id,
                        session_digest="a" * 64,
                        csrf_digest="b" * 64,
                        state="active",
                        created_at=clock(),
                        expires_at=clock() + timedelta(hours=1),
                    )
                )
                await uow.commit()

            replacement_admin = await service.reset_admin()
            assert await service.verify(admin.value, "admin") is None
            assert await service.verify(replacement_admin.value, "admin") is not None
            replacement_app = await service.rotate_app()
            assert await service.verify(app.value, "app") is None
            assert await service.verify(replacement_app.value, "app") is not None

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                rows = (await uow.session.execute(select(access_tokens))).mappings().all()
                database_text = "\n".join(str(dict(row)) for row in rows)
                assert app.value not in database_text
                assert admin.value not in database_text
                assert all(str(row["secret_hash"]).startswith("$argon2id$") for row in rows)
                session_state = await uow.session.scalar(
                    select(admin_sessions.c.state).where(admin_sessions.c.id == "session-lineage")
                )
                audit_count = await uow.session.scalar(
                    select(func.count()).select_from(security_audit_events)
                )
                assert session_state == "revoked"
                assert audit_count == 4
        finally:
            await runtime.close()

    asyncio.run(exercise())


def test_rehash_on_success_and_crypto_failure_audit(tmp_path: Path) -> None:
    database_url = sqlite_url(tmp_path / "rehash.db")
    upgrade_database(database_url, tmp_path / "migration.lock")

    async def exercise() -> None:
        runtime = create_database_runtime(database_url, 5000)
        weak_service = TokenService(
            lambda: SqlAlchemyUnitOfWork(runtime.sessions), fast_hasher(time_cost=1)
        )
        try:
            app = next(item for item in await weak_service.bootstrap() if item.scope == "app")
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                before = await uow.access_tokens.get_by_public_id(app.public_id)
                assert before is not None

            strong = fast_hasher(time_cost=2)
            strong_service = TokenService(lambda: SqlAlchemyUnitOfWork(runtime.sessions), strong)
            assert await strong_service.verify(app.value, "app") is not None
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                after = await uow.access_tokens.get_by_public_id(app.public_id)
                assert after is not None and after.secret_hash != before.secret_hash

            cipher = AuditedSecretCipher(
                AesGcmSecretCipher(bytes(range(32))),
                lambda: SqlAlchemyUnitOfWork(runtime.sessions),
            )
            envelope = await cipher.encrypt("safe", purpose="provider", record_id="p1")
            with pytest.raises(SecretCryptoError):
                await cipher.decrypt(envelope, purpose="provider", record_id="p2")
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                failed = await uow.session.scalar(
                    select(func.count())
                    .select_from(security_audit_events)
                    .where(security_audit_events.c.action == "secret.decrypt")
                )
                assert failed == 1
        finally:
            await runtime.close()

    asyncio.run(exercise())


def test_operator_bootstrap_displays_new_credentials_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    database_url = sqlite_url(tmp_path / "operator.db")
    settings = Settings(
        environment="test",
        database_url=database_url,
        instance_lock_path=tmp_path / "instance.lock",
    )
    monkeypatch.setattr(operator, "get_settings", lambda: settings)

    assert operator.run(["--database-url", database_url, "bootstrap"]) == 0
    first_output = capsys.readouterr().out
    assert first_output.count("shown once") == 2
    assert "cm.app." in first_output
    assert "cm.admin." in first_output

    assert operator.run(["--database-url", database_url, "bootstrap"]) == 0
    second_output = capsys.readouterr().out
    assert "no credential was displayed" in second_output
    assert "cm.app." not in second_output
    assert "cm.admin." not in second_output
