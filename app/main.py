from fastapi import FastAPI

from app.api.v1 import router as api_v1_router
from app.core.exception_handlers import register_exception_handlers
from app.core.lifespan import lifespan
from app.core.middleware import register_middleware


def create_app() -> FastAPI:
    app = FastAPI(title="LogScope", lifespan=lifespan)
    register_middleware(app)
    register_exception_handlers(app)
    app.include_router(api_v1_router)

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
