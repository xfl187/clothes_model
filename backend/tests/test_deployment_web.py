from pathlib import Path

from fastapi.testclient import TestClient

from clothes_model.api.application import create_app
from clothes_model.core.config import Settings


def test_configured_web_root_serves_spa_and_dev_cors(tmp_path: Path) -> None:
    web_root = tmp_path / "web"
    web_root.mkdir()
    (web_root / "index.html").write_text("<main>contract shell</main>", encoding="utf-8")
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        web_static_root=web_root,
        cors_allowlist=["http://localhost:5173"],
    )

    with TestClient(create_app(settings)) as client:
        shell = client.get("/contract-status")
        preflight = client.options(
            "/health/live",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert shell.status_code == 200
    assert "contract shell" in shell.text
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"
