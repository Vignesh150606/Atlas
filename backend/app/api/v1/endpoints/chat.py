from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.core.deps import get_llm_provider
from app.core.errors import internal_error
from app.providers.base import LLMProvider
from app.schemas.chat import ChatRequest, ChatResponse, DeviceActionResultRequest, MessageSchema
from app.schemas.memory import MemoryCreate
from app.models.memory import MemoryType
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.memory_service import MemoryService

router = APIRouter()

@router.post("", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    provider: LLMProvider = Depends(get_llm_provider)
):
    try:
        service = ChatService(db=db, provider=provider)
        return await service.process_chat(request)
    except Exception as e:
        # Phase 12 / SECURITY_PLAN.md S10: generic detail, real exception
        # logged server-side with a correlation id (see app/core/errors.py).
        raise internal_error(e, context="POST /chat")


@router.post("/device-result", response_model=MessageSchema)
async def report_device_result(
    payload: DeviceActionResultRequest,
    db: AsyncSession = Depends(get_db),
):
    """Phase 8: closes the 'Android Tool -> Result -> Memory' loop from the
    mission's tool-architecture diagram. The Android app calls this after
    actually executing a ChatResponse.device_action locally (the backend
    has no way to know the outcome on its own) - the outcome is appended to
    the conversation as an assistant message and logged as an 'automation'
    memory so future turns can reference it (e.g. "did you open WhatsApp
    for me?"). This intentionally does not call the LLM again: the Android
    app already knows success/failure the instant the action completes, so
    round-tripping through a provider just to say "Done" would add latency
    for no benefit - see docs/Phase8_KnownLimitations.md.
    """
    try:
        conversation_service = ConversationService(db)
        memory_service = MemoryService(db)

        icon = "\u2705" if payload.success else "\u26a0\ufe0f"
        content = f"{icon} {payload.summary}"
        assistant_msg = await conversation_service.save_assistant_message(
            payload.conversation_id, content
        )

        await memory_service.create_memory(
            MemoryCreate(
                title=f"Device action: {payload.tool}.{payload.action}",
                content=payload.summary,
                memory_type=MemoryType.NOTE,
                category="automation",
                importance=2,
                source="device_action",
                tags=["device_action", payload.tool, payload.action],
                structured_data={"success": payload.success, **payload.details},
            ),
            # Each device action is a distinct event (e.g. "opened WhatsApp"
            # can legitimately happen many times) - not a fact to dedupe
            # against prior identical text the way chat-extracted memories are.
            allow_duplicate=True,
        )

        await db.commit()
        return assistant_msg
    except Exception as e:
        raise internal_error(e, context="POST /chat/device-result")
