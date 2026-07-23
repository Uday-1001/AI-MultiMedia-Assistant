from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "AI Multimedia Knowledge Assistant",
        "version": "1.0.0"
    }
