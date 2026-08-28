import pytest
from datetime import datetime, timedelta
from app.utils.time import utc_now
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.proactive_suggestion_service import ProactiveSuggestionService, STALE_MEMORY_SUGGESTION_THRESHOLD
from app.services.reminder_service import ReminderService
from app.services.routine_service import RoutineService
from app.services.memory_service import MemoryService
from app.schemas.reminder import ReminderCreate
from app.schemas.routine import RoutineCreate
from app.schemas.memory import MemoryCreate
from app.models.memory import MemoryType


@pytest.mark.asyncio
async def test_no_suggestions_when_nothing_pending(db_session: AsyncSession):
    result = await ProactiveSuggestionService(db_session).get_suggestions()
    assert result.suggestions == []


@pytest.mark.asyncio
async def test_overdue_reminder_produces_suggestion(db_session: AsyncSession):
    now = utc_now()
    reminder = await ReminderService(db_session).create(
        ReminderCreate(title="Pay rent", due_at=now - timedelta(hours=2))
    )
    result = await ProactiveSuggestionService(db_session).get_suggestions(reference=now)
    types = {s.suggestion_type for s in result.suggestions}
    assert "overdue_reminder" in types
    matching = [s for s in result.suggestions if s.suggestion_type == "overdue_reminder"]
    assert matching[0].related_id == reminder.id
    assert "Pay rent" in matching[0].message


@pytest.mark.asyncio
async def test_due_soon_reminder_produces_suggestion_not_overdue(db_session: AsyncSession):
    now = utc_now()
    await ReminderService(db_session).create(
        ReminderCreate(title="Team call", due_at=now + timedelta(minutes=10))
    )
    result = await ProactiveSuggestionService(db_session).get_suggestions(reference=now)
    types = [s.suggestion_type for s in result.suggestions]
    assert types.count("overdue_reminder") == 0
    assert "due_soon_reminder" in types


@pytest.mark.asyncio
async def test_far_future_reminder_produces_no_suggestion(db_session: AsyncSession):
    now = utc_now()
    await ReminderService(db_session).create(
        ReminderCreate(title="Distant", due_at=now + timedelta(days=5))
    )
    result = await ProactiveSuggestionService(db_session).get_suggestions(reference=now)
    assert result.suggestions == []


@pytest.mark.asyncio
async def test_routine_time_produces_suggestion(db_session: AsyncSession):
    reference = datetime(2026, 8, 5, 7, 15)  # Wednesday
    await RoutineService(db_session).create(
        RoutineCreate(name="Morning Routine", time_of_day="07:10", days_of_week=[])
    )
    result = await ProactiveSuggestionService(db_session).get_suggestions(reference=reference)
    types = {s.suggestion_type for s in result.suggestions}
    assert "routine_time" in types


@pytest.mark.asyncio
async def test_stale_memories_suggestion_only_above_threshold(db_session: AsyncSession):
    memory_service = MemoryService(db_session)
    distinct_facts = [
        ("Allergic to peanuts", "Mentioned a peanut allergy during a recipe conversation."),
        ("Prefers window seats", "Said they always try to book a window seat on flights."),
        ("Works remotely on Fridays", "Mentioned working from home every Friday."),
        ("Studying for the bar exam", "Talked about preparing for the bar exam next spring."),
        ("Has a dog named Biscuit", "Mentioned a dog named Biscuit who needs a walk twice a day."),
        ("Vegetarian diet", "Said they've been vegetarian for the last three years."),
    ][:STALE_MEMORY_SUGGESTION_THRESHOLD]
    for title, content in distinct_facts:
        m = await memory_service.create_memory(MemoryCreate(title=title, content=content, memory_type=MemoryType.FACT))
        m.verification_state = "stale"
    await db_session.flush()

    result = await ProactiveSuggestionService(db_session).get_suggestions()
    types = {s.suggestion_type for s in result.suggestions}
    assert "stale_memories" in types
