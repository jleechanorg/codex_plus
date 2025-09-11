"""Thin test entrypoint.

This file re-exports the FastAPI `app` object from `main_sync_cffi.py` so that
test runners and deployment tools can import `app` from a stable module path
(`main:app`). Some CI and ASGI loaders rely on this convention. Keeping this
shim avoids import churn and makes PR tests simpler.
"""
from .main_sync_cffi import app

__all__ = ["app"]
