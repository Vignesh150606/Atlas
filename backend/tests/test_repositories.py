import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository

@pytest.mark.asyncio
async def test_conversation_and_message_repositories(db_session: AsyncSession):
    conv_repo = ConversationRepository(db_session)
    msg_repo = MessageRepository(db_session)

    # Create conversation
    conv = await conv_repo.create({"title": "Test Conv"})
    assert conv.id is not None
    assert conv.title == "Test Conv"

    # Create user message
    msg1 = await msg_repo.create({
        "conversation_id": conv.id,
        "role": "user",
        "content": "Hello"
    })
    assert msg1.id is not None

    # Fetch messages
    messages = await msg_repo.get_by_conversation(conv.id)
    assert len(messages) == 1
    assert messages[0].content == "Hello"
