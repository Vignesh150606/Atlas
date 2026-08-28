# Phase 10 — Architecture Update

Same spirit as `Phase8_ArchitectureUpdate.md`/`Phase9_ArchitectureUpdate.md`:
the *deltas* and the reasoning behind each, not a restatement of
`CLAUDE.md`'s Architecture section.

## New models instead of a bigger `Memory` table

The mission brief was explicit (section 1): "Do not put everything into
the generic memory table... The architecture must prevent temporary
information from becoming permanent memory accidentally." Three genuinely
new SQLAlchemy models were added - `Reminder`, `Task`, `Routine` - rather
than extending `Memory` with more `memory_type` values or more JSON in
`structured_data`.

**Why separate tables, not more memory_type variants:** a `Reminder`
needs `due_at`/`recurrence`/`recurrence_days`/`status`/`completed_at` -
fields with real, indexed, queryable semantics (`ReminderRepository.
get_due_within`/`get_overdue` are plain `WHERE` clauses, not JSON
extraction). Cramming that into `Memory.structured_data` (an untyped
JSON blob) would mean every query needing to know Memory's internal JSON
shape for one specific memory_type, and would reintroduce exactly the
"generic bucket" problem the brief warned against. A dedicated table
with dedicated, typed, indexed columns is the more honest model of what
these things actually are: schedulable, completable, first-class
resources, not memories-of-things-said.

**Why `Memory.expires_at` instead of a fourth new table for "temporary
context":** unlike Reminder/Task/Routine, temporary context genuinely
*is* the same shape as an ordinary memory (title, content, category,
tags) - it only differs in lifecycle (it should stop being retrievable
after a TTL). Adding one nullable, indexed column plus filtering it out
in `MemoryRepository.get_filtered`/`search` is a strictly smaller change
than a fourth model, and keeps "is this fact still relevant" as one
concept (expiry) rather than splitting facts across two tables based on
how long they're expected to matter. `MemoryService.
create_temporary_context()` is the one write path (see its docstring)
so this isn't a flag anyone can silently set - it's a deliberate,
separate method call.

## Reminder persistence: two write paths for two different resources, not a duplicate

Phase 9 established a pattern: skills that might otherwise duplicate
`MemoryExtractor`'s writes (Notes, Reminder, Calendar) stay
confirmation-only, deferring persistence entirely to `MemoryExtractor`.
Phase 10 partially breaks this pattern for `ReminderSkill` specifically -
see that file's docstring for the full reasoning, summarized here:

`MemoryExtractor` rule 5 and the new `Reminder` model are not the same
resource. Rule 5 produces a `Memory(TASK)` row - a passive record that
the user said something reminder-shaped, useful for general recall
("did I ever mention needing to call the dentist?"). The new `Reminder`
row is an active, schedulable object - it has a real `due_at`, a
`status` that transitions, and is what `DailyBriefingService`/
`ProactiveSuggestionService`/the Android Reminders tab actually query.
Writing both from the same "remind me to X" message is not the
"duplicate write to the same table" problem Phase 9's confirmation-only
pattern existed to prevent (see `app/skills/notes_skill.py`) - it's two
different tables, each the single source of truth for a different
question. `CalendarSkill` and `NotesSkill` were deliberately left
untouched (still confirmation-only) - see `docs/Phase10_KnownLimitations.md`
#3 for why calendar events didn't get the same dedicated-model treatment.

Backward compatibility for `ReminderSkill` specifically was achieved
without any special-casing: `run()` already had to tolerate `self.db`
being `None` (unit tests construct skills bare and call `run()` directly -
see `app/skills/base.py`), so the new persistence logic is simply
`if self.db is not None: ...` - every Phase 9 test for this skill passes
completely unchanged; new tests cover the db-bound path directly.

## `ReminderService.create_from_text`: recombine, don't parse twice

`MemoryExtractor.parse_reminder` only ever splits a message into
`task` + trailing `at/by/on <when>` clause (unchanged this phase - see
`app/nlp/datetime_parser.py`'s docstring for why touching it was out of
scope). This means a recurrence word appearing *before* that trailing
clause - "take my medicine **every day** at 8am" - would be silently
lost if only the split-off `due_date` fragment ("8am") were handed to
the new date parser.

**Decision:** `ReminderService.create_from_text` recombines
`task + " " + due_date` into one string and re-parses *that* with
`parse_datetime_expression`, which searches for recurrence/date/time
patterns independently across the whole string rather than requiring
them in a fixed left-to-right order. `ParsedSchedule.remaining_text`
(the input with every recognized phrase's character span removed) then
becomes the clean title, and `ParsedSchedule.matched_text` becomes the
`raw_when_text` shown back to the user - both derived from the same
parse, so they can never disagree with each other. This was a real bug
found during testing, not a hypothetical - see
`tests/test_reminder_service.py::test_create_from_text_with_time_and_recurrence`
and the fix's reasoning in `ReminderService`'s own docstring.

## Daily Briefing and Proactive Suggestions: composition, not new orchestration

Mission brief section 4: "The architecture must use existing skills/
tools rather than creating another parallel orchestration system."
`DailyBriefingService` and `ProactiveSuggestionService` are both thin -
neither owns any state or does anything `ReminderService`/`TaskService`/
`RoutineService`/`MemoryRepository`/`MemoryLifecycleService` don't
already do. "What's due soon" is defined exactly once
(`ReminderRepository.get_due_within`) and used by both services -
avoiding the specific "second implementation" anti-pattern the mission
brief's architectural rule (section 16) named directly.

**Why two services instead of one "assistant orchestrator":** briefing
and suggestions have different callers and different shapes (briefing is
pulled once, deliberately, e.g. on screen open; suggestions are meant to
be polled periodically) and different output shapes (a rich structured
briefing vs. a flat list of atomic suggestions). Merging them into one
service would mean every caller of one paying the query cost of the
other. Both are still callable from a single narrow surface each
(`BriefingSkill` for chat, two GET endpoints for direct API/Android use) -
the "one capability, reused from multiple front doors" pattern already
established by e.g. `KnowledgeRetrievalService`.

## No scheduler, no background loop - proactivity is stateless and pull-based

Mission brief section 6 and 17 were both explicit: no uncontrolled
background agent, no constant polling/battery drain. This backend has no
Celery, no APScheduler, no cron-like infrastructure at all, and Phase 10
deliberately did not add one. `ProactiveSuggestionService.get_suggestions()`
is a pure function of "what's in the database right now" - calling it
twice with no writes in between returns the same result; there is no
hidden state it accumulates or forgets. The client (Android, in the
intended design - see `docs/Phase10_KnownLimitations.md` #5 for what's
NOT yet built on that side) is responsible for deciding when to ask.

## Android: closing a gap that already existed, not opening a new one

`DeviceActionSchema.requires_confirmation` has existed on the backend
since Phase 9 (`app/schemas/chat.py`) and has always been sent over the
wire in every `ChatResponse.device_action`. Android's `DeviceAction`
data class simply never declared the field, so Gson silently dropped it
on every deserialization - `requires_confirmation` has been true in the
JSON and `false` (the Kotlin default) in memory for an entire phase.
This was found by reading the exact field-by-field diff between the
backend schema and the Android DTO, not by guessing.

**Fix shape:** add the field to the DTO (one line), then gate on it at
the two call sites that turn a `DeviceAction` into an executed
`AutomationResult` - `ChatViewModel.dispatchMessage`'s success handler
and `ConversationAudioController`'s equivalent. Both now branch: confirm
required -> stage in UI state, show `ConfirmationDialog`, wait for a tap;
confirm not required -> execute exactly as before (zero behavior change
for the common case). `AutomationToolRouter` itself was not touched -
"should this run" is a UI-layer decision, "how does this run" stays the
router's job, keeping the same separation of concerns Phase 8 already
established.

## Notification categorization: a pure function, not a new pipeline

`NotificationCategorizer.categorize(packageName, title, text) ->
NotificationCategory` has zero dependencies - no Context, no database, no
network. It's called once, at read time, inside
`AtlasNotificationListenerService.toNotificationInfo()` (the same place
that already builds a `NotificationInfo` from a `StatusBarNotification`)
and the result is stored on the DTO rather than recomputed at every
filter check. This keeps the "no background polling or logging"
guarantee `Phase8_KnownLimitations.md` already established completely
intact - categorization only ever happens as a side effect of an
already-on-request read, never on its own schedule.

## One Android repository for four resources, not four

`PersonalAssistantRepository` covers reminders, tasks, routines, and
briefing/suggestions in a single file, unlike the one-repository-per-
resource pattern `MemoryRepository`/`KnowledgeRepository` established.
**Why the deviation:** those four resources are small (a handful of
methods each), share identical `safeCall` plumbing, and - unlike Memory
vs. Knowledge, which are genuinely different domains with different
screens - are consumed together by the same single screen
(`PersonalAssistantScreen`'s four tabs). Four near-empty repository
files each wrapping 3-6 endpoints would have been more indirection for
no real separation-of-concerns benefit. If any one of these resources
grows enough to need its own screen and independent lifecycle, splitting
it out is a mechanical refactor, not a design change.
