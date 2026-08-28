import pytest
from datetime import datetime, timedelta
from app.utils.time import utc_now
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.daily_briefing_service import DailyBriefingService
from app.services.reminder_service import ReminderService
from app.services.task_service import TaskService
from app.services.routine_service import RoutineService
from app.services.memory_service import MemoryService
from app.schemas.reminder import ReminderCreate
from app.schemas.task import TaskCreate
from app.schemas.routine import RoutineCreate
from app.schemas.memory import MemoryCreate
from app.models.memory import MemoryType


@pytest.mark.asyncio
async def test_empty_briefing_has_empty_sections_and_neutral_narrative(db_session: AsyncSession):
    briefing = await DailyBriefingService(db_session).build()
    assert briefing.upcoming_reminders == []
    assert briefing.incomplete_tasks == []
    assert "Nothing pressing" in briefing.narrative


@pytest.mark.asyncio
async def test_briefing_includes_upcoming_and_overdue_reminders(db_session: AsyncSession):
    now = utc_now()
    reminder_service = ReminderService(db_session)
    await reminder_service.create(ReminderCreate(title="Overdue", due_at=now - timedelta(hours=1)))
    await reminder_service.create(ReminderCreate(title="Soon", due_at=now + timedelta(hours=2)))
    await reminder_service.create(ReminderCreate(title="Far off", due_at=now + timedelta(days=30)))

    briefing = await DailyBriefingService(db_session).build(reference=now)
    titles = {r.title for r in briefing.upcoming_reminders}
    assert "Overdue" in titles
    assert "Soon" in titles
    assert "Far off" not in titles
    assert "overdue" in briefing.narrative.lower()


@pytest.mark.asyncio
async def test_briefing_narrative_does_not_double_count_overdue_as_upcoming(db_session: AsyncSession):
    # Regression test: the narrative previously reported overdue reminders
    # both in the "N overdue" clause AND folded into "N reminders in the
    # next 24 hours" (since upcoming_reminders is the merged overdue+
    # upcoming list) - e.g. 1 overdue + 1 genuinely-soon read as "1
    # overdue reminder; 2 reminders in the next 24 hours" even though only
    # one reminder is actually upcoming. The second figure must exclude
    # anything already counted as overdue.
    now = utc_now()
    reminder_service = ReminderService(db_session)
    await reminder_service.create(ReminderCreate(title="Overdue", due_at=now - timedelta(hours=1)))
    await reminder_service.create(ReminderCreate(title="Soon", due_at=now + timedelta(hours=2)))

    briefing = await DailyBriefingService(db_session).build(reference=now)
    assert "1 overdue reminder" in briefing.narrative
    assert "1 reminder in the next 24 hours" in briefing.narrative
    assert "2 reminders in the next 24 hours" not in briefing.narrative


@pytest.mark.asyncio
async def test_briefing_includes_incomplete_tasks_only(db_session: AsyncSession):
    task_service = TaskService(db_session)
    pending = await task_service.create(TaskCreate(title="Pending task"))
    done = await task_service.create(TaskCreate(title="Done task"))
    await task_service.complete(done.id)

    briefing = await DailyBriefingService(db_session).build()
    titles = {t.title for t in briefing.incomplete_tasks}
    assert "Pending task" in titles
    assert "Done task" not in titles


@pytest.mark.asyncio
async def test_briefing_includes_routines_around_now(db_session: AsyncSession):
    reference = datetime(2026, 8, 5, 7, 30)  # Wednesday
    routine_service = RoutineService(db_session)
    await routine_service.create(RoutineCreate(name="Morning Routine", time_of_day="07:15", days_of_week=[]))
    await routine_service.create(RoutineCreate(name="Night Routine", time_of_day="22:00", days_of_week=[]))

    briefing = await DailyBriefingService(db_session).build(reference=reference)
    names = {r.name for r in briefing.routines_today}
    # A 12-hour window is exactly half of a 24-hour clock, so once the
    # time-distance check is circular (see RoutineService.get_active_around),
    # every time-of-day is within it - "routines_today" means every active
    # routine matching today's weekday, regardless of clock time. The old
    # exclusion of an evening routine from a morning briefing was a symptom
    # of a midnight-wraparound bug in the distance calculation, not an
    # intentional "only routines near now" filter - nothing in this
    # service ever documented the latter as the goal, and it wouldn't
    # explain a field named routines_today only surfacing some of today's
    # routines.
    assert "Morning Routine" in names
    assert "Night Routine" in names


@pytest.mark.asyncio
async def test_briefing_includes_pinned_memories(db_session: AsyncSession):
    memory_service = MemoryService(db_session)
    await memory_service.create_memory(MemoryCreate(
        title="Important fact", content="Allergic to peanuts",
        memory_type=MemoryType.FACT, is_pinned=True,
    ))
    briefing = await DailyBriefingService(db_session).build()
    titles = {m.title for m in briefing.important_memories}
    assert "Important fact" in titles
