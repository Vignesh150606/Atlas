import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.conversation_service import ConversationService


@pytest.mark.asyncio
async def test_get_or_create_creates_new_when_no_id(db_session: AsyncSession):
    service = ConversationService(db_session)
    conv = await service.get_or_create(None)
    assert conv.id is not None
    assert conv.title == "New Conversation"


@pytest.mark.asyncio
async def test_get_or_create_returns_existing(db_session: AsyncSession):
    service = ConversationService(db_session)
    conv = await service.get_or_create(None)
    same = await service.get_or_create(conv.id)
    assert same.id == conv.id


@pytest.mark.asyncio
async def test_history_returns_most_recent_messages_in_order(db_session: AsyncSession):
    """Regression test: get_history_for_provider must return the MOST RECENT
    messages (trimmed to the limit), not the oldest ones, and in chronological
    order.
    """
    service = ConversationService(db_session)
    conv = await service.get_or_create(None)

    for i in range(5):
        await service.save_user_message(conv.id, f"user msg {i}")
        await service.save_assistant_message(conv.id, f"assistant msg {i}")

    history = await service.get_history_for_provider(conv.id, max_messages=4)

    assert len(history) == 4
    # Should be the last 4 of the 10 total messages, still chronological.
    assert [m["content"] for m in history] == [
        "user msg 3",
        "assistant msg 3",
        "user msg 4",
        "assistant msg 4",
    ]


@pytest.mark.asyncio
async def test_history_excludes_unsaved_current_message(db_session: AsyncSession):
    service = ConversationService(db_session)
    conv = await service.get_or_create(None)
    await service.save_user_message(conv.id, "earlier message")

    history = await service.get_history_for_provider(conv.id)
    assert len(history) == 1
    assert history[0]["content"] == "earlier message"
