"""ASGI entrypoint."""

from clothes_model.api.application import create_app

app = create_app()


def run() -> None:
    """Run the development server with the single-worker V1 constraint."""
    import uvicorn

    from clothes_model.core.config import get_settings

    settings = get_settings()
    uvicorn.run(
        "clothes_model.main:app",
        host=settings.bind_host,
        port=settings.bind_port,
        workers=1,
    )
