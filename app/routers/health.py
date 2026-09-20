from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.health import readiness_status

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live():
    return {
        "status": "alive",
    }


@router.get("/health/ready")
def ready():
    result = readiness_status()

    if result["status"] != "ready":
        return JSONResponse(
            status_code=503,
            content=result,
        )

    return result
