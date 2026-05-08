from fastapi import APIRouter

from app.modules.auth.routers.auth_router import router as auth_router
from app.modules.library.routers.field_schema_router import router as field_schema_router
from app.modules.library.routers.library_overview_router import router as library_overview_router
from app.modules.library.routers.log_type_router import router as log_type_router
from app.modules.library.routers.parse_rule_router import router as parse_rule_router
from app.modules.library.routers.product_router import router as product_router
from app.modules.library.routers.sample_log_router import router as sample_log_router
from app.modules.library.routers.vendor_router import router as vendor_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(library_overview_router, prefix="/library", tags=["library"])
router.include_router(vendor_router, prefix="/library/vendors", tags=["library:vendor"])
router.include_router(product_router, prefix="/library", tags=["library:product"])
router.include_router(log_type_router, prefix="/library", tags=["library:log_type"])
router.include_router(parse_rule_router, prefix="/library", tags=["library:parse_rule"])
router.include_router(field_schema_router, prefix="/library", tags=["library:field"])
router.include_router(sample_log_router, prefix="/library", tags=["library:sample"])
