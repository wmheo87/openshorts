"""Lightweight metadata-only ASGI entry point for Linux/Windows Docker hosts."""
from fastapi import FastAPI

from .router import router

app = FastAPI(title="OpenShorts Discovery", version="1.0.0")
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
