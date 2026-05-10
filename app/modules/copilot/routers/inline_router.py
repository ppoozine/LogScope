"""POST /api/v1/copilot/inline/vrl — SSE streaming inline VRL completion."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.common.auth import current_user
from app.modules.auth.models.user import User
from app.modules.copilot.routers.chat_router import get_chat_service
from app.modules.copilot.schemas import InlineVrlRequest
from app.modules.copilot.services.chat_service import ChatService

router = APIRouter()


@router.post("/inline/vrl")
async def inline_vrl(
    body: InlineVrlRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
    _user: Annotated[User, Depends(current_user)],
) -> StreamingResponse:
    return StreamingResponse(
        service.stream_inline(request=body),
        media_type="text/event-stream",
    )
