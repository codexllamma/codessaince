"""API routes package."""
from api.routes.upload import router as upload_router
from api.routes.warmup import router as warmup_router

__all__ = ["upload_router", "warmup_router"]
