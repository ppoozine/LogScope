from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response

from app.common.auth import SESSION_COOKIE_NAME, current_user, get_auth_service
from app.common.schemas import DataResponse
from app.core.config import Settings, get_settings
from app.modules.auth.models.user import User
from app.modules.auth.schemas import LoginRequest, UserRead
from app.modules.auth.services.auth_service import AuthService

router = APIRouter()


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    auth: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DataResponse[dict]:
    session_id = await auth.login(email=body.email, password=body.password)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return DataResponse(data={"ok": True})


@router.post("/logout")
async def logout(
    response: Response,
    auth: Annotated[AuthService, Depends(get_auth_service)],
    session_cookie: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> DataResponse[dict]:
    if session_cookie:
        await auth.logout(session_cookie)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value="",
        max_age=0,
        path="/",
    )
    return DataResponse(data={"ok": True})


@router.get("/me", response_model=DataResponse[UserRead])
async def me(user: Annotated[User, Depends(current_user)]) -> DataResponse[UserRead]:
    return DataResponse(data=UserRead.model_validate(user))
