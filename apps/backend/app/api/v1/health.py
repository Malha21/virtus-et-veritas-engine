from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def api_health() -> dict[str, object]:
    return {
        "success": True,
        "data": {
            "status": "ok",
            "service": "vve-engine",
            "version": "0.1.0",
        },
    }
