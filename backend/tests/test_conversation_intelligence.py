import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.conversation_service import ConversationService
from app.services.conversation_intelligence import ConversationIntelligenceService


@pytest.mark.asyncio
async def test_summarize_empty_conversation_returns_none(db_session: AsyncSession):
    conv_service = ConversationService(db_session)
    intel = ConversationIntelligenceService(db_session)
    conv = await conv_service.get_or_create(None)
    summary = await intel.summarize(conv.id)
    assert summary is None


@pytest.mark.asyncio
async def test_summarize_returns_message_count_and_previews(db_session: AsyncSession):
    conv_service = ConversationService(db_session)
    intel = ConversationIntelligenceService(db_session)
    conv = await conv_service.get_or_create(None)
    await conv_service.save_user_message(conv.id, "I have a Math class at 9am")
    await conv_service.save_assistant_message(conv.id, "Got it, noted your class.")
    await conv_service.save_user_message(conv.id, "What is my next class?")

    summary = await intel.summarize(conv.id)
    assert summary.message_count == 3
    assert summary.first_message_preview.startswith("I have a Math class")
    assert "class" in summary.first_message_preview.lower()


@pytest.mark.asyncio
async def test_detect_topics_finds_recurring_keywords(db_session: AsyncSession):
    conv_service = ConversationService(db_session)
    intel = ConversationIntelligenceService(db_session)
    conv = await conv_service.get_or_create(None)
    await conv_service.save_user_message(conv.id, "I have a Math class at 9am")
    await conv_service.save_user_message(conv.id, "When is my next class?")
    await conv_service.save_user_message(conv.id, "Is class cancelled tomorrow?")

    metadata = await intel.get_session_metadata(conv.id)
    assert "class" in metadata.dominant_topics


@pytest.mark.asyncio
async def test_session_metadata_for_missing_conversation_returns_none(db_session: AsyncSession):
    intel = ConversationIntelligenceService(db_session)
    result = await intel.get_session_metadata(999999)
    assert result is None


@pytest.mark.asyncio
async def test_rollover_triggers_only_past_the_limit(db_session: AsyncSession):
    conv_service = ConversationService(db_session)
    intel = ConversationIntelligenceService(db_session)
    conv = await conv_service.get_or_create(None)

    for i in range(3):
        await conv_service.save_user_message(conv.id, f"message {i}")

    messages, rollover_note = await intel.get_history_with_rollover(conv.id, max_messages=10)
    assert len(messages) == 3
    assert rollover_note is None


@pytest.mark.asyncio
async def test_rollover_summarizes_dropped_messages(db_session: AsyncSession):
    conv_service = ConversationService(db_session)
    intel = ConversationIntelligenceService(db_session)
    conv = await conv_service.get_or_create(None)

    for i in range(8):
        await conv_service.save_user_message(conv.id, f"message about class number {i}")

    messages, rollover_note = await intel.get_history_with_rollover(conv.id, max_messages=3)
    assert len(messages) == 3
    assert rollover_note is not None
    assert "5 earlier messages" in rollover_note
    assert "class" in rollover_note


# --- Phase 9: follow-up detection -------------------------------------------
def test_detect_follow_up_recognizes_cue_word():
    history = [
        {"role": "user", "content": "What classes do I have tomorrow?"},
        {"role": "assistant", "content": "You have a Math class and a Physics lab."},
    ]
    result = ConversationIntelligenceService.detect_follow_up("What about Friday?", history)
    assert result is not None
    assert result.is_follow_up is True
    assert "class" in result.hint.lower() or "math" in result.hint.lower() or "physics" in result.hint.lower()


def test_detect_follow_up_recognizes_bare_pronoun_in_short_message():
    history = [
        {"role": "user", "content": "Remind me to submit the report"},
        {"role": "assistant", "content": "Got it - I'll remember that you need to submit the report."},
    ]
    result = ConversationIntelligenceService.detect_follow_up("cancel that", history)
    assert result is not None


def test_detect_follow_up_returns_none_with_no_history():
    result = ConversationIntelligenceService.detect_follow_up("What about Friday?", [])
    assert result is None


def test_detect_follow_up_returns_none_for_standalone_question():
    """A normal, fully-formed new question must not be flagged just because
    history exists - only explicit cues or short-message bare pronouns do."""
    history = [
        {"role": "user", "content": "What classes do I have tomorrow?"},
        {"role": "assistant", "content": "You have a Math class."},
    ]
    result = ConversationIntelligenceService.detect_follow_up(
        "What is the capital of France?", history
    )
    assert result is None


def test_detect_follow_up_returns_none_for_long_message_with_pronoun():
    """A long, substantive message containing 'it' somewhere is not a bare
    follow-up - only short (<=8 word) pronoun-only messages qualify."""
    history = [{"role": "user", "content": "Tell me about Project Atlas"}]
    long_message = (
        "It is interesting that you mention this, but I actually wanted to ask "
        "something completely different about my calendar for next month"
    )
    result = ConversationIntelligenceService.detect_follow_up(long_message, history)
    assert result is None


# --- Phase 9: ambiguity detection -------------------------------------------
@pytest.mark.parametrize("message", [
    "Remind me to",
    "remind me to.",
    "Remind me to?",
])
def test_detect_ambiguous_command_flags_incomplete_reminder(message):
    result = ConversationIntelligenceService.detect_ambiguous_command(message)
    assert result is not None
    assert "remind" in result.lower()


@pytest.mark.parametrize("message", [
    "Add an event",
    "add event:",
    "Schedule an event",
])
def test_detect_ambiguous_command_flags_incomplete_event(message):
    result = ConversationIntelligenceService.detect_ambiguous_command(message)
    assert result is not None
    assert "event" in result.lower()


def test_detect_ambiguous_command_returns_none_for_complete_reminder():
    result = ConversationIntelligenceService.detect_ambiguous_command(
        "Remind me to submit the report by Friday"
    )
    assert result is None


def test_detect_ambiguous_command_returns_none_for_unrelated_message():
    result = ConversationIntelligenceService.detect_ambiguous_command("What time is it?")
    assert result is None
