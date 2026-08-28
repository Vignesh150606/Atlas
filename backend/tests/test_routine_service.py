import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.routine_service import RoutineService
from app.schemas.routine import RoutineCreate, RoutineUpdate


@pytest.mark.asyncio
async def test_create_routine(db_session: AsyncSession):
    service = RoutineService(db_session)
    routine = await service.create(RoutineCreate(
        name="Morning Routine", steps=["Drink water", "Stretch", "Review timetable"]
    ))
    assert routine.name == "Morning Routine"
    assert routine.is_active is True
    assert len(routine.steps) == 3


@pytest.mark.asyncio
async def test_update_routine(db_session: AsyncSession):
    service = RoutineService(db_session)
    routine = await service.create(RoutineCreate(name="Study Routine", steps=["Review notes"]))
    updated = await service.update(routine.id, RoutineUpdate(steps=["Review notes", "Practice problems"]))
    assert len(updated.steps) == 2


@pytest.mark.asyncio
async def test_delete_routine(db_session: AsyncSession):
    service = RoutineService(db_session)
    routine = await service.create(RoutineCreate(name="Night Routine"))
    deleted = await service.delete(routine.id)
    assert deleted is not None
    assert await service.get(routine.id) is None


@pytest.mark.asyncio
async def test_search_by_name_fragment(db_session: AsyncSession):
    service = RoutineService(db_session)
    await service.create(RoutineCreate(name="Evening Wind-down Routine"))
    found = await service.search_by_name_fragment("evening")
    assert found is not None
    assert found.name == "Evening Wind-down Routine"


@pytest.mark.asyncio
async def test_get_active_around_matches_time_and_day(db_session: AsyncSession):
    service = RoutineService(db_session)
    # Wednesday 2026-08-05 is a Wednesday (weekday=2)
    reference = datetime(2026, 8, 5, 7, 30)
    await service.create(RoutineCreate(
        name="Weekday Morning", time_of_day="07:15", days_of_week=[0, 1, 2, 3, 4]
    ))
    await service.create(RoutineCreate(
        name="Weekend Only", time_of_day="07:15", days_of_week=[5, 6]
    ))
    await service.create(RoutineCreate(
        name="Late Night", time_of_day="23:00", days_of_week=[]
    ))

    matches = await service.get_active_around(reference, window_minutes=30)
    names = {r.name for r in matches}
    assert "Weekday Morning" in names
    assert "Weekend Only" not in names
    assert "Late Night" not in names


@pytest.mark.asyncio
async def test_get_active_around_matches_across_midnight(db_session: AsyncSession):
    # Regression test: get_active_around previously compared times-of-day
    # with a plain abs() difference in minutes-since-midnight, so a
    # routine at 23:50 checked 15 minutes later at 00:05 read as ~1430
    # minutes apart instead of the real 15, and never matched. The
    # distance must "wrap" across midnight.
    service = RoutineService(db_session)
    await service.create(RoutineCreate(name="Wind-down", time_of_day="23:50", days_of_week=[]))
    just_after_midnight = datetime(2026, 8, 6, 0, 5)  # 15 minutes after 23:50
    matches = await service.get_active_around(just_after_midnight, window_minutes=30)
    assert "Wind-down" in {r.name for r in matches}


@pytest.mark.asyncio
async def test_get_active_around_ignores_inactive_routines(db_session: AsyncSession):
    service = RoutineService(db_session)
    reference = datetime(2026, 8, 5, 7, 30)
    routine = await service.create(RoutineCreate(name="Deactivated", time_of_day="07:15", days_of_week=[]))
    await service.update(routine.id, RoutineUpdate(is_active=False))
    matches = await service.get_active_around(reference, window_minutes=30)
    assert routine.id not in {r.id for r in matches}
