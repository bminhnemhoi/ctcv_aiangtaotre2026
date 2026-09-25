"""ASGI entry point for servers that expect ``module:app`` (``uvicorn ctcv_api.asgi:app``)."""

from ctcv_api.main import create_app

app = create_app()
