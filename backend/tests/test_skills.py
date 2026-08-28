import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.skills.time_skill import TimeSkill
from app.skills.weather_skill import WeatherSkill
from app.skills.search_skill import SearchSkill
from app.skills.notes_skill import NotesSkill
from app.skills.reminder_skill import ReminderSkill
from app.skills.calendar_skill import CalendarSkill
from app.skills.task_skill import TaskSkill
from app.skills.routine_skill import RoutineSkill
from app.skills.briefing_skill import BriefingSkill


# --- TimeSkill --------------------------------------------------------------
def test_time_skill_matches_time_question():
    assert TimeSkill().match("What time is it?") is not None


def test_time_skill_does_not_match_unrelated_message():
    assert TimeSkill().match("What is the capital of France?") is None


@pytest.mark.asyncio
async def test_time_skill_run_returns_formatted_time():
    result = await TimeSkill().run(message="What time is it?")
    assert result.success
    assert "server time" in result.output


@pytest.mark.asyncio
async def test_time_skill_date_only_question_omits_clock_time():
    result = await TimeSkill().run(message="What's today's date?")
    assert result.success
    assert "server date" in result.output


# --- WeatherSkill (unconfigured by default) ---------------------------------
def test_weather_skill_matches_weather_question():
    match = WeatherSkill().match("What's the weather usually like in April?")
    assert match is not None


def test_weather_skill_does_not_match_unrelated_message():
    assert WeatherSkill().match("What time is it?") is None


@pytest.mark.asyncio
async def test_weather_skill_honestly_reports_unconfigured():
    """No fabricated forecast - see app/providers/weather.py."""
    result = await WeatherSkill().run(location="Chennai")
    assert result.success is False
    assert "not configured" in result.error.lower() or "no weather provider" in result.error.lower()


# --- SearchSkill -------------------------------------------------------------
def test_search_skill_matches_search_for_phrasing():
    match = SearchSkill().match("search for my thesis notes")
    assert match is not None
    assert match.kwargs["query"] == "my thesis notes"


def test_search_skill_does_not_match_casual_use_of_find():
    """'find' alone (not 'find info/notes/documents about') shouldn't
    false-positive on ordinary statements like "I can't find my keys"."""
    assert SearchSkill().match("I can't find my keys anywhere") is None


@pytest.mark.asyncio
async def test_search_skill_requires_a_query():
    result = await SearchSkill().run(query="")
    assert result.success is False


# --- NotesSkill (confirmation only) ------------------------------------------
def test_notes_skill_matches_remember_that():
    assert NotesSkill().match("Remember that my wifi password is atlas123") is not None


def test_notes_skill_does_not_match_unrelated_message():
    assert NotesSkill().match("What time is it?") is None


@pytest.mark.asyncio
async def test_notes_skill_confirms_without_touching_db():
    """No db was passed to this instance at all - if run() tried to
    persist anything it would raise, not silently succeed."""
    result = await NotesSkill().run()
    assert result.success
    assert "remember" in result.output.lower()


# --- ReminderSkill (confirmation only, shares MemoryExtractor.parse_reminder) -
def test_reminder_skill_matches_and_extracts_task():
    match = ReminderSkill().match("Remind me to submit the report by Friday")
    assert match is not None
    assert match.kwargs["task"] == "submit the report"
    assert match.kwargs["due_date"] == "Friday"


def test_reminder_skill_does_not_match_unrelated_message():
    assert ReminderSkill().match("What time is it?") is None


@pytest.mark.asyncio
async def test_reminder_skill_confirmation_mentions_task_and_due_date():
    result = await ReminderSkill().run(task="submit the report", due_date="Friday")
    assert result.success
    assert "submit the report" in result.output
    assert "Friday" in result.output


@pytest.mark.asyncio
async def test_reminder_skill_confirmation_without_due_date():
    result = await ReminderSkill().run(task="call John", due_date=None)
    assert result.success
    assert "call John" in result.output


# --- CalendarSkill (confirmation only, shares MemoryExtractor.parse_event) ---
def test_calendar_skill_matches_add_event_phrasing():
    match = CalendarSkill().match("Add an event: Team offsite on Monday")
    assert match is not None
    assert match.kwargs["event"] == "Team offsite"
    assert match.kwargs["date"] == "Monday"


def test_calendar_skill_does_not_match_schedule_question():
    """Must not false-positive on 'what's my schedule tomorrow?' - see
    MemoryExtractor.parse_event's docstring."""
    assert CalendarSkill().match("What's my schedule tomorrow?") is None


@pytest.mark.asyncio
async def test_calendar_skill_confirms_event():
    result = await CalendarSkill().run(event="Team offsite", date="Monday")
    assert result.success
    assert "Team offsite" in result.output
    assert "Monday" in result.output


# --- Phase 10: ReminderSkill now persists a real Reminder when a db session
# is available (see app/skills/reminder_skill.py) ----------------------------
@pytest.mark.asyncio
async def test_reminder_skill_persists_real_reminder_when_db_available(db_session: AsyncSession):
    from app.repositories.reminder_repository import ReminderRepository

    result = await ReminderSkill(db=db_session).run(task="submit the report", due_date="Friday")
    assert result.success
    assert "submit the report" in result.output

    reminders = await ReminderRepository(db_session).get_filtered()
    assert len(reminders) == 1
    assert reminders[0].title == "submit the report"


@pytest.mark.asyncio
async def test_reminder_skill_without_db_still_confirms_only(db_session: AsyncSession):
    """Backward compatibility: db=None (e.g. a unit test constructing the
    skill directly, as every other test in this file does) falls back to
    exactly the Phase 9 confirmation-only behavior - no exception, no
    silent no-op that looks like success but isn't."""
    from app.repositories.reminder_repository import ReminderRepository

    result = await ReminderSkill().run(task="call John", due_date="Friday")
    assert result.success
    reminders = await ReminderRepository(db_session).get_filtered()
    assert reminders == []


# --- Phase 10: TaskSkill ------------------------------------------------------
def test_task_skill_matches_create():
    match = TaskSkill().match("create a task to buy groceries")
    assert match is not None
    assert match.kwargs["action"] == "create"
    assert match.kwargs["title"] == "buy groceries"


def test_task_skill_matches_complete():
    match = TaskSkill().match("complete task buy groceries")
    assert match is not None
    assert match.kwargs["action"] == "complete"
    assert match.kwargs["title"] == "buy groceries"


def test_task_skill_matches_mark_as_done_phrasing():
    match = TaskSkill().match("mark task buy groceries as done")
    assert match is not None
    assert match.kwargs["action"] == "complete"
    assert match.kwargs["title"] == "buy groceries"


def test_task_skill_matches_list():
    match = TaskSkill().match("what are my tasks")
    assert match is not None
    assert match.kwargs["action"] == "list"


def test_task_skill_does_not_match_unrelated_message():
    assert TaskSkill().match("What time is it?") is None


@pytest.mark.asyncio
async def test_task_skill_create_persists_task(db_session: AsyncSession):
    result = await TaskSkill(db=db_session).run(action="create", title="Buy groceries")
    assert result.success
    assert "Buy groceries" in result.output

    from app.services.task_service import TaskService
    tasks = await TaskService(db_session).list()
    assert len(tasks) == 1
    assert tasks[0].title == "Buy groceries"


@pytest.mark.asyncio
async def test_task_skill_complete_by_title(db_session: AsyncSession):
    from app.services.task_service import TaskService
    from app.schemas.task import TaskCreate
    await TaskService(db_session).create(TaskCreate(title="Submit the quarterly report"))

    result = await TaskSkill(db=db_session).run(action="complete", title="quarterly report")
    assert result.success

    found = await TaskService(db_session).find_incomplete_by_title("quarterly report")
    assert found is None  # no longer incomplete


@pytest.mark.asyncio
async def test_task_skill_complete_unknown_title_fails_gracefully(db_session: AsyncSession):
    result = await TaskSkill(db=db_session).run(action="complete", title="something that does not exist")
    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_task_skill_list_when_empty(db_session: AsyncSession):
    result = await TaskSkill(db=db_session).run(action="list")
    assert result.success
    assert "no incomplete tasks" in result.output.lower()


@pytest.mark.asyncio
async def test_task_skill_without_db_fails_gracefully():
    result = await TaskSkill().run(action="list")
    assert result.success is False


# --- Phase 10: RoutineSkill ---------------------------------------------------
def test_routine_skill_matches_create_with_steps():
    match = RoutineSkill().match("create a routine called Morning Routine with steps: drink water, stretch")
    assert match is not None
    assert match.kwargs["action"] == "create"
    assert match.kwargs["name"] == "Morning Routine"
    assert match.kwargs["steps"] == ["drink water", "stretch"]


def test_routine_skill_matches_list_all():
    match = RoutineSkill().match("show me my routines")
    assert match is not None
    assert match.kwargs["action"] == "list"


def test_routine_skill_matches_show_one():
    match = RoutineSkill().match("what's my morning routine")
    assert match is not None
    assert match.kwargs["action"] == "show"
    assert match.kwargs["name"] == "morning"


def test_routine_skill_does_not_match_vague_habit_mention():
    """Must not infer a routine from a casual mention - see
    app/models/routine.py's 'explicit only, never inferred' docstring."""
    assert RoutineSkill().match("I usually stretch after waking up") is None


@pytest.mark.asyncio
async def test_routine_skill_create_persists_routine(db_session: AsyncSession):
    result = await RoutineSkill(db=db_session).run(
        action="create", name="Evening Routine", steps=["Read", "Sleep"]
    )
    assert result.success
    from app.services.routine_service import RoutineService
    routines = await RoutineService(db_session).list()
    assert len(routines) == 1
    assert routines[0].name == "Evening Routine"


@pytest.mark.asyncio
async def test_routine_skill_show_unknown_routine_fails_gracefully(db_session: AsyncSession):
    result = await RoutineSkill(db=db_session).run(action="show", name="nonexistent")
    assert result.success is False


# --- Phase 10: BriefingSkill ---------------------------------------------------
def test_briefing_skill_matches_explicit_phrasing():
    assert BriefingSkill().match("give me my daily briefing") is not None
    assert BriefingSkill().match("what's my day look like") is not None


def test_briefing_skill_does_not_match_casual_greeting():
    """Deliberately narrow trigger - see app/skills/briefing_skill.py's
    docstring for why bare greetings are excluded."""
    assert BriefingSkill().match("good morning") is None


@pytest.mark.asyncio
async def test_briefing_skill_run_returns_structured_output(db_session: AsyncSession):
    result = await BriefingSkill(db=db_session).run()
    assert result.success
    assert "narrative" in result.output
    assert "upcoming_reminders" in result.output


@pytest.mark.asyncio
async def test_briefing_skill_without_db_fails_gracefully():
    result = await BriefingSkill().run()
    assert result.success is False
