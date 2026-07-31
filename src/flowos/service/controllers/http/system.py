"""HTTP API Controllers — REST endpointi."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    """Provera da je servis živ."""
    return {"status": "ok"}


@router.get("/version")
async def version():
    """Verzija servisa i API-ja."""
    return {"version": "0.1.0", "api_version": 1}


@router.get("/runtime")
async def runtime():
    """Informacije o runtime-u servisa."""
    import os

    return {
        "pid": os.getpid(),
        "port": 9100,
        "started_at": "skeleton",
        "data_directory": "skeleton",
    }
