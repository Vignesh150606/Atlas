# Phase 10 — Known Limitations

Same format as `Phase8_KnownLimitations.md`/`Phase9_KnownLimitations.md`:
each item says what the limitation is, why it exists, and what it would
take to remove.

## 1. Android changes were written but not build-verified

Same environment constraint as Phase 8 and Phase 9, unchanged, and it
persisted into this phase too:

- No Android SDK installed in this sandbox.
- The network egress allowlist available here does not include
  `dl.google.com`, `repo.maven.apache.org`, `maven.google.com`, or
  `services.gradle.org` - so even a bare `./gradlew` invocation cannot
  resolve the Android Gradle Plugin or any AndroidX/Compose/Hilt
  dependency, let alone assemble or test the app.
- Every Kotlin file touched this phase (see `docs/Phase10_Report.md`'s
  file list) was written by manually cross-referencing existing
  signatures, DI bindings, and Compose patterns already in the codebase -
  the same practice Phase 8 established and Phase 9 documented
  continuing. This is a real, careful process, but it is **not the same
  as compiling**. A typo, an import cycle, a signature mismatch against
  an androidx/Hilt API this session doesn't have visibility into, or a
  Compose recomposition bug would all currently go undetected.
- Three phases of Kotlin changes (8, 9, 10) have now accumulated without
  a single `./gradlew assembleDebug` run against any of them. This is
  flagged in `CLAUDE.md`'s Future Vision as the top Phase 11 priority for
  a reason: the trust gap compounds with each additional phase built on
  top of unverified code.

**To remove:** run `./gradlew clean assembleDebug && ./gradlew test` in
an environment with a real Android SDK and Google Maven/Gradle-
distribution network access (a real machine, or a sandboxed tool
explicitly configured with that access) before trusting any of Phase 8,
9, or 10's Kotlin changes. See the phone verification procedure in
`docs/Phase10_Report.md` for the full manual-testing checklist to run
once it compiles.

## 2. The Reminder text parser is deliberately deterministic-only, with real, documented gaps

`app/nlp/datetime_parser.py` handles a specific, enumerated set of
patterns (see its module docstring) - not general English date/time
understanding. Concretely unhandled:

- Relative phrases beyond the enumerated set: "the day after tomorrow",
  "next week" (as a date rather than a recurrence), "end of the month",
  "in a couple of days" is handled (`_NUMBER_WORDS["couple"] = 2`) but
  "a few days" only resolves to 3 by the same mechanism, not a range.
- Ambiguous bare weekday mentions are resolved by one documented rule
  ("today counts if it matches and the day hasn't been established as
  already passed") - there is no attempt to reason about whether saying
  "Friday" at 11pm on a Thursday most likely means "in 13 hours" or "in
  8 days"; it always means the nearest upcoming Friday, today included
  if today were Friday.
- No timezone-aware arithmetic - `reference` is a naive datetime the
  caller has already localized; DST transitions, cross-timezone phrasing
  ("7pm Pacific"), and timezone-name parsing are all out of scope. The
  `timezone` field on `Reminder` is stored as a plain string and never
  used in arithmetic anywhere in this phase.
- `ReminderService` has a documented seam for an optional LLM-assist
  fallback on phrases this parser fails to recognize (see that module's
  docstring), but nothing calls it - every unresolved phrase currently
  just saves `due_at=None` with the raw text preserved, which is honest
  but not maximally useful.

**To remove:** either extend the deterministic pattern set (safe,
incremental, testable - the existing `tests/test_datetime_parser.py`
structure makes new cases cheap to add) or actually wire the LLM-assist
fallback behind an explicit settings flag, following the same
"provider-abstraction, honest not-configured default" pattern Phase 9
used for weather.

## 3. `Memory(TASK)`/`Memory(EVENT)` free-text dates are unchanged

The new deterministic parser was deliberately *not* retrofitted onto
`MemoryExtractor` rules 5/6 (the passive "remind me to X" / "meeting on
Y" chat-capture that predates Phase 10's real Reminder system - see
`app/models/reminder.py`'s docstring for why these are two different,
complementary things now). Those rows still store the due-date phrase as
raw text exactly as before. This means:

- `get_unified_timeline`'s chronological sort (Phase 9) remains fully
  reliable only for document-sourced items, unchanged from the Phase 9
  known-limitations note this carries forward.
- A reminder mentioned in passing conversation ("I should really call
  the dentist sometime this week") still only produces a `Memory(TASK)`
  row with unparsed text, unless it's phrased as an actual "remind me to
  ..." request that `ReminderSkill` matches.

This was a deliberate scope decision, not an oversight: the mission
brief's numbered feature list named Reminder/Task/Routine specifically,
not a rework of the general memory-extraction rules, and retrofitting
those rules would have meant re-touching Phase 9 code with real
regression risk (all 6 `MemoryExtractor` rules and their tests) for a
capability (parsed dates on passively-captured, non-reminder memories)
the mission brief didn't ask for.

**To remove:** decide explicitly (product decision, not just an
engineering one) whether `Memory(TASK)`/`Memory(EVENT)` rows should also
get resolved dates, and if so, run `parse_datetime_expression` over their
`structured_data.due_date`/`date` fields at write time in
`MemoryExtractor`, with new tests covering the existing 6-rule test
suite plus the new date-resolution behavior.

## 4. No authentication or authorization exists anywhere in this backend

Not a Phase 10 regression - this has been true since Phase 1 and Phase 10
did not change it, but Phase 10 adds four new resource types (reminders,
tasks, routines, plus the temporary-context slice of memory) with zero
new access control, worth stating plainly rather than leaving implicit:

- Every `/api/v1/*` endpoint, old and new, is unauthenticated. Anyone who
  can reach the backend's port can read and write every reminder, task,
  routine, and memory.
- `python-jose`/`passlib` are in `requirements.txt` but genuinely unused
  anywhere in the codebase (verified by grep, same as the pre-existing
  `structlog` situation noted in earlier phases) - they are leftover
  scaffolding from an earlier phase's intent, not a partially-built auth
  system.
- This is a defensible posture *only* under the explicit single-user,
  localhost-or-trusted-network assumption documented in
  `docs/Architecture.md` and the phone verification procedure below
  (backend runs on a PC on the same trusted network as the phone). It is
  not defensible if this backend is ever exposed to an untrusted network
  or the public internet.

**To remove:** add real authentication (even a single shared API key
checked via a FastAPI dependency would be a meaningful improvement over
nothing) before any deployment scenario broader than "my own phone
talking to my own PC on my own network."

## 5. Proactive suggestions require the client to poll; there is no push

`GET /briefing/suggestions` is a stateless, on-request query - by design
(mission brief section 17: no constant backend polling/battery drain).
This means:

- If nothing ever calls this endpoint, the user never sees a proactive
  suggestion, no matter how overdue a reminder gets. There is no backend
  timer, no push notification, no OS alarm scheduling.
- A real "notify me when a reminder fires" experience needs Android-side
  scheduling (e.g. `AlarmManager`/`WorkManager` periodic work calling
  this endpoint and posting a local notification) - none of that Android
  scheduling code was written this phase. `PersonalAssistantScreen`
  fetches the daily briefing when opened; nothing calls the suggestions
  endpoint from Android at all yet, though the DTO/repository/API method
  exist and are ready to be called.

**To remove:** add a Android `WorkManager` periodic job (e.g. every
15-30 minutes, per the mission brief's own suggested cadence) that calls
`getProactiveSuggestions()` and posts a local notification for anything
new - this is genuinely Android-side work requiring the build environment
from item 1 to develop and verify against.

## 6. Voice confirmation requires a screen tap, not a spoken "yes"

Mission brief section 9 says "never bypass confirmation merely because
the user is using voice" - Phase 10 satisfies this literally (voice mode
gates on confirmation exactly like text mode, and speaks a heads-up
rather than silently waiting) but the actual confirmation input mechanism
in voice mode is still a tap on `ConfirmationDialog`, not an interpreted
spoken "yes"/"confirm". A fully voice-native flow would need
`ConversationAudioController`'s state machine to enter a distinct
"awaiting confirmation" state that listens for and classifies the next
utterance, which is meaningfully more voice-state-machine work than this
phase's brief allowed room for alongside everything else, and the brief
explicitly said not to rewrite the voice subsystem unnecessarily.

**To remove:** add an `AWAITING_CONFIRMATION` `VoiceState`, route STT
results through a small yes/no classifier when in that state, and only
fall back to the on-screen dialog if the classifier is unsure or the
mic isn't active.

## 7. Notification categorization is heuristic and will misclassify some real notifications

`NotificationCategorizer` (mission brief section 10) is deliberately
simple package-name/keyword matching - no ML, no LLM call, fully
on-device and instant, but therefore also fully capable of getting a
specific notification wrong (e.g. a food-delivery app's genuinely
important "your order has arrived" notification isn't in any of the
IMPORTANT/PERSONAL keyword lists and would fall to UNKNOWN; a personal
message that happens to contain "% off" from a friend forwarding a deal
is correctly kept PERSONAL only because package-identity is checked
first - text-only categorization without that priority order would have
gotten it wrong). This is the same tradeoff Phase 9 made for
`MemoryLifecycleService`'s staleness thresholds: explainable and
instantly fixable with a one-line rule change, not a black box, but not
maximally accurate either.

**To remove:** expand the keyword/package lists based on real usage data
(which requires the Android build/runtime this phase doesn't have), or
replace with a small on-device classifier if false categorizations prove
common enough to matter in practice.

## 8. Security review was a documentation exercise, not a penetration test

"Review the entire new proactive architecture" (mission brief section
12) was done as a careful reading of every new code path for the
specific items the brief named (authentication, authorization,
confirmation boundaries, notification privacy, stored personal
information, logs, secrets, local database exposure, API exposure,
background execution) - see items 4 and 5 above for the two substantive
findings. This was not an automated security scan, a dependency
vulnerability check, or an adversarial test of any endpoint. No new
attack surface was identified beyond "there is no auth, at all, same as
every prior phase" - which is itself the main finding, not a caveat on
a clean bill of health.

**To remove:** run an actual dependency vulnerability scanner (e.g.
`pip-audit`) and consider a real security review once authentication
(item 4) exists, since reviewing authorization boundaries is not
meaningful before there's any authentication for them to be boundaries
of.
