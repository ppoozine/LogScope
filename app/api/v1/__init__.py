from fastapi import APIRouter

from app.modules.auth.routers.auth_router import router as auth_router
from app.modules.library.routers.vendor_router import router as vendor_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(vendor_router, prefix="/library/vendors", tags=["library:vendor"])
