"""POST /api/v1/copilot/chat — SSE streaming chat endpoint."""

from typing import Annotated, Any, cast

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.common.auth import current_user
from app.core.config import Settings, get_settings
from app.modules.auth.models.user import User
from app.modules.copilot.schemas import ChatRequest
from app.modules.copilot.services.chat_service import ChatService

router = APIRouter()


def _validate_last_message_is_user(req: ChatRequest) -> ChatRequest:
    if req.messages[-1].role != "user":
        raise HTTPException(
            status_code=422,
            detail=[
                {
                    "loc": ["body", "messages", -1, "role"],
                    "msg": "last message must be from the user",
                    "type": "value_error",
                }
            ],
        )
    return req


async def get_chat_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ChatService:
    """Construct ChatService. Always builds a real AsyncAnthropic client; service
    short-circuits to error event when api key is unset."""
    client = anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key or "placeholder"
    )

    skill_models: dict[str, str] = {}
    if settings.llm_copilot_vrl_model:
        skill_models["vrl_generate"] = settings.llm_copilot_vrl_model
        skill_models["vrl_optimize"] = settings.llm_copilot_vrl_model
        skill_models["vrl_inline"] = settings.llm_copilot_vrl_model
        skill_models["vrl_fix"] = settings.llm_copilot_vrl_model

    return ChatService(
        anthropic_client=cast(Any, client),
        anthropic_api_key=settings.anthropic_api_key,
        default_model=settings.llm_copilot_model,
        skill_models=skill_models,
        max_history=settings.llm_copilot_max_history,
        max_log_lines_in_context=settings.llm_copilot_max_log_lines_in_context,
        max_vrl_chars_in_context=settings.llm_copilot_max_vrl_chars_in_context,
        max_library_products_in_context=settings.llm_copilot_max_library_products_in_context,
    )


@router.post("/chat")
async def chat(
    body: ChatRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
    _user: Annotated[User, Depends(current_user)],
) -> StreamingResponse:
    body = _validate_last_message_is_user(body)
    generator = service.stream(request=body)
    return StreamingResponse(generator, media_type="text/event-stream")
