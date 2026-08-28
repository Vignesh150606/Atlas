from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.models.conversation import Conversation
from app.models.message import Message
from app.providers.base import ProviderMessage
from app.core.config import settings


class ConversationService:
    """Owns conversation lifecycle: get-or-create, message persistence, and
    preparing conversation history for a provider call.

    This is deliberately separate from ChatService: ChatService orchestrates
    a full chat turn (retrieval + prompt building + provider call), while
    ConversationService only knows about conversations and messages. Keeping
    them apart means the conversation/session logic can be reused later by
    something that isn't a simple request/response chat turn (e.g. a
    streaming endpoint) without dragging retrieval or prompting along.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.conversation_repo = ConversationRepository(db)
        self.message_repo = MessageRepository(db)

    async def get_or_create(self, conversation_id: Optional[int]) -> Conversation:
        if conversation_id:
            conversation = await self.conversation_repo.get(conversation_id)
            if conversation:
                return conversation
        return await self.conversation_repo.create({"title": "New Conversation"})

    async def get_history_for_provider(
        self, conversation_id: int, max_messages: Optional[int] = None
    ) -> List[ProviderMessage]:
        """Fetch prior turns for this conversation, trimmed to a context-window
        budget. This only returns messages that already existed before the
        current turn - the current user message is appended separately by
        the caller (see PromptBuilder.build), so history here never includes it.
        """
        limit = max_messages or settings.MAX_HISTORY_MESSAGES
        # Repository stores ascending by created_at; fetch a wide window then
        # trim to the most recent N so we keep the tail of the conversation,
        # not the head, once it grows past the budget.
        all_messages = await self.message_repo.get_by_conversation(conversation_id, limit=1000)
        trimmed = all_messages[-limit:] if len(all_messages) > limit else all_messages
        return [{"role": m.role, "content": m.content} for m in trimmed if m.role in ("user", "assistant")]

    async def save_user_message(self, conversation_id: int, content: str) -> Message:
        return await self.message_repo.create(
            {"conversation_id": conversation_id, "role": "user", "content": content}
        )

    async def save_assistant_message(self, conversation_id: int, content: str) -> Message:
        return await self.message_repo.create(
            {"conversation_id": conversation_id, "role": "assistant", "content": content}
        )
