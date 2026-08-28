import pytest
from datetime import datetime, timedelta
from app.utils.time import utc_now
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.reminder_service import ReminderService
from app.schemas.reminder import ReminderCreate, ReminderUpdate
from app.models.reminder import ReminderStatus, RecurrenceType


@pytest.mark.asyncio
async def test_create_direct_reminder(db_session: AsyncSession):
    service = ReminderService(db_session)
    due = utc_now() + timedelta(days=1)
    reminder = await service.create(ReminderCreate(title="Submit report", due_at=due))
    assert reminder.title == "Submit report"
    assert reminder.due_at == due
    assert reminder.status == ReminderStatus.PENDING.value
    assert reminder.source == "api"


@pytest.mark.asyncio
async def test_create_from_text_resolves_due_date(db_session: AsyncSession):
    service = ReminderService(db_session)
    reference = datetime(2026, 8, 5, 10, 0, 0)  # Wednesday
    reminder = await service.create_from_text(
        "remind me to submit the assignment tomorrow", reference_time=reference
    )
    assert reminder is not None
    assert reminder.title == "submit the assignment"
    assert reminder.due_at == datetime(2026, 8, 6, 9, 0)  # DEFAULT_REMINDER_HOUR
    assert reminder.raw_when_text == "tomorrow"


@pytest.mark.asyncio
async def test_create_from_text_with_time_and_recurrence(db_session: AsyncSession):
    service = ReminderService(db_session)
    reference = datetime(2026, 8, 5, 10, 0, 0)
    reminder = await service.create_from_text(
        "remind me to take my medicine every day at 8am", reference_time=reference
    )
    assert reminder is not None
    assert reminder.recurrence == RecurrenceType.DAILY.value
    assert reminder.due_at == datetime(2026, 8, 5, 8, 0)


@pytest.mark.asyncio
async def test_create_from_text_returns_none_for_unrelated_message(db_session: AsyncSession):
    service = ReminderService(db_session)
    result = await service.create_from_text("What time is it?")
    assert result is None


@pytest.mark.asyncio
async def test_create_from_text_with_unparseable_when_still_saves_task(db_session: AsyncSession):
    service = ReminderService(db_session)
    reminder = await service.create_from_text("remind me to call John by whenever works")
    assert reminder is not None
    assert reminder.title == "call John"
    assert reminder.due_at is None
    assert reminder.raw_when_text == "whenever works"


@pytest.mark.asyncio
async def test_complete_non_recurring_reminder(db_session: AsyncSession):
    service = ReminderService(db_session)
    reminder = await service.create(ReminderCreate(title="One-off", due_at=utc_now()))
    completed = await service.complete(reminder.id)
    assert completed.status == ReminderStatus.COMPLETED.value
    assert completed.completed_at is not None


@pytest.mark.asyncio
async def test_complete_recurring_reminder_advances_due_date_and_stays_pending(db_session: AsyncSession):
    service = ReminderService(db_session)
    reference = datetime(2026, 8, 5, 8, 0, 0)  # Wednesday
    reminder = await service.create(ReminderCreate(
        title="Daily standup", due_at=reference, recurrence=RecurrenceType.DAILY,
    ))
    original_due_at = reminder.due_at  # snapshot: SQLAlchemy's identity map means
    # `reminder` and `completed` below alias the same Python object once
    # re-fetched by id, so due_at must be captured before complete() mutates it.
    completed = await service.complete(reminder.id)
    assert completed.status == ReminderStatus.PENDING.value
    assert completed.completed_at is not None
    assert completed.due_at > original_due_at  # advanced, not deleted


@pytest.mark.asyncio
async def test_cancel_reminder(db_session: AsyncSession):
    service = ReminderService(db_session)
    reminder = await service.create(ReminderCreate(title="Skip this"))
    cancelled = await service.cancel(reminder.id)
    assert cancelled.status == ReminderStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_get_upcoming_and_overdue(db_session: AsyncSession):
    service = ReminderService(db_session)
    now = utc_now()
    past = await service.create(ReminderCreate(title="Overdue one", due_at=now - timedelta(hours=1)))
    soon = await service.create(ReminderCreate(title="Due soon", due_at=now + timedelta(hours=2)))
    far = await service.create(ReminderCreate(title="Far away", due_at=now + timedelta(days=10)))

    overdue = await service.get_overdue(reference=now)
    upcoming = await service.get_upcoming(timedelta(hours=24), reference=now)

    overdue_ids = {r.id for r in overdue}
    upcoming_ids = {r.id for r in upcoming}
    assert past.id in overdue_ids
    assert soon.id in upcoming_ids
    assert far.id not in upcoming_ids
    assert far.id not in overdue_ids


@pytest.mark.asyncio
async def test_update_reminder(db_session: AsyncSession):
    service = ReminderService(db_session)
    reminder = await service.create(ReminderCreate(title="Original"))
    updated = await service.update(reminder.id, ReminderUpdate(title="Updated title"))
    assert updated.title == "Updated title"


@pytest.mark.asyncio
async def test_update_unknown_reminder_returns_none(db_session: AsyncSession):
    service = ReminderService(db_session)
    result = await service.update("not-a-real-id", ReminderUpdate(title="x"))
    assert result is None


@pytest.mark.asyncio
async def test_list_filters_by_status(db_session: AsyncSession):
    service = ReminderService(db_session)
    r1 = await service.create(ReminderCreate(title="A"))
    r2 = await service.create(ReminderCreate(title="B"))
    await service.cancel(r2.id)

    pending = await service.list(status=ReminderStatus.PENDING.value)
    cancelled = await service.list(status=ReminderStatus.CANCELLED.value)
    assert {r.id for r in pending} == {r1.id}
    assert {r.id for r in cancelled} == {r2.id}
