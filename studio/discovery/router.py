import sqlite3
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query

from .config import Settings
from .errors import DiscoveryError
from .schemas import HistoryResponse, SearchRequest, SearchResponse
from .service import DiscoveryService

router = APIRouter(prefix="/api/discovery", tags=["discovery"])


def public_error(error):
    return HTTPException(error.status, detail={"code": error.code, "message": error.message, "retryable": error.retryable},
                         headers={"Retry-After": "60"} if error.status == 429 else None)


@lru_cache(maxsize=1)
def get_service():
    try:
        settings = Settings.from_env()
        if not settings.enabled:
            raise DiscoveryError("discovery_disabled", "Set DISCOVERY_ENABLED=1 to enable this single-operator discovery service.", 503)
        return DiscoveryService(settings)
    except DiscoveryError as error:
        raise public_error(error) from None
    except (ValueError, OSError, sqlite3.Error):
        raise HTTPException(503, detail={"code": "discovery_configuration_error", "message": "Check discovery settings and writable SQLite storage.", "retryable": False}) from None


def invoke(operation):
    try:
        return operation()
    except DiscoveryError as error:
        raise public_error(error) from None
    except (sqlite3.Error, OSError):
        raise HTTPException(503, detail={"code": "discovery_storage_unavailable", "message": "Discovery storage is unavailable.", "retryable": True}) from None


# Synchronous endpoints run in FastAPI's threadpool: SQLite and HTTP never block the event loop.
@router.post("/search", response_model=SearchResponse)
def search(request: SearchRequest, service: DiscoveryService = Depends(get_service)):
    return invoke(lambda: service.search(request))


@router.get("/history", response_model=HistoryResponse)
def history(limit: int = Query(20, ge=1, le=100), before_id: int | None = Query(None, ge=1, le=2**63 - 1),
            service: DiscoveryService = Depends(get_service)):
    return invoke(lambda: service.history(limit, before_id))
