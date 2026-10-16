from fastapi import APIRouter

from src.api.v1.routes.payments import router as payments_router

router = APIRouter(prefix="/api/v1")
router.include_router(payments_router)
