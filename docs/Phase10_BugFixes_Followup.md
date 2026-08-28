# Phase 10 Follow-up — Bugs Found and Fixed

A post-Phase-10 pass specifically hunting for real bugs beyond what the
existing test suite catches (408 passing tests is not the same claim as
"no bugs" - it means the tests that exist pass). Same standard as the
rest of this project: every backend claim below was actually run, not
reasoned about; Android claims are explicitly marked as manually traced,
not compiled, for the same environment reasons as Phases 8-10 (see
`docs/Phase10_KnownLimitations.md` #1).

## Backend (verified: `python -m pytest -q` → 411 passed, 0 failed)

1. **Reminder recurrence anchored to the wrong day for multi-day CUSTOM
   schedules.** `app/nlp/datetime_parser.py`'s `parse_datetime_expression`
   picked `recurrence_days[0]` (the numerically-lowest weekday) as the
   first occurrence, instead of the *nearest* upcoming day. "Every Tuesday
   and Thursday" created on a Wednesday resolved to the following Tuesday
   (6 days away) and skipped Thursday (1 day away) entirely. Confirmed by
   direct reproduction; fixed to take `min()` across all candidate days,
   matching the logic `ReminderService._advance_recurrence` already used
   correctly for the same problem. The existing test for this case
   asserted the buggy value - corrected it and added a second independent
   case (`tests/test_datetime_parser.py`).

2. **Daily briefing narrative double-counted overdue reminders.**
   `DailyBriefingService._build_narrative` folded overdue reminders into
   both "N overdue" and "N reminders in the next 24 hours" (the second
   figure used the merged overdue+upcoming list without subtracting the
   overdue ones). 1 overdue + 1 genuinely-upcoming read as "1 overdue
   reminder; 2 reminders in the next 24 hours". Fixed to subtract
   `overdue_count`; added `test_briefing_narrative_does_not_double_count_
   overdue_as_upcoming`.

3. **Routine time-of-day matching broke across midnight.**
   `RoutineService.get_active_around` compared times with a plain `abs()`
   difference in minutes-since-midnight, so a routine at 23:50 checked 15
   minutes later at 00:05 measured as ~1430 minutes apart instead of 15,
   and never matched any reasonable window. Fixed to use circular
   (wraparound-aware) distance. This also corrected `routines_today`'s
   12-hour window (exactly half a day - with the fix, circular distance
   from any reference point never exceeds it, so it now correctly
   includes every active routine matching today's weekday regardless of
   clock time, instead of arbitrarily excluding ones on the opposite side
   of the clock). Added `test_get_active_around_matches_across_midnight`;
   updated `test_briefing_includes_routines_around_now`'s assertion with
   an explanation of why the old expectation was itself a symptom of the
   bug, not intentional.

## Android (traced by hand against the actual logic; NOT compiled - no
Android SDK/Google Maven access in this sandbox, same constraint as
Phases 8-10)

4-5. **`NotificationCategorizer` had two real misclassifications, both
   already contradicted by its own (never-compiled) test file.**
   - `com.android.dialer` (the stock Android phone app) was swallowed by
     the broad `"com.android."` SYSTEM prefix before the IMPORTANT check
     ever ran, returning SYSTEM instead of IMPORTANT for a missed-call
     notification - directly contradicting the class's own docstring
     ("SMS/calls" named as an unambiguous IMPORTANT case) and its test's
     assertion.
   - `com.google.android.gm` (Gmail's real, Google-truncated package id)
     matched neither `"gmail"` nor `"mail"` as a substring, so it fell
     through to UNKNOWN instead of PERSONAL, also contradicting its test.

   Fixed by reordering IMPORTANT/PERSONAL checks ahead of the SYSTEM
   prefix check, and adding a precise `endsWith(".gm")` check for Gmail
   (a plain substring keyword like `"android.gm"` was tried first and
   rejected - it also matches `com.google.android.gms`, i.e. Play
   Services, as a false positive). All 16 assertions across every
   existing test in `NotificationCategorizerTest.kt` were hand-traced
   against the fixed logic and confirmed to pass (see this session's
   transcript for the full trace); this has not been machine-verified by
   an actual Kotlin compiler/JUnit run.

6. **Voice mode could bypass its own confirmation gate.** In
   `ConversationAudioController`, `VoiceManager` forwards a final
   transcript to `handleEvent` unconditionally, regardless of the current
   `VoiceState` (confirmed by reading `VoiceManager.handleSttEvent`) - so
   in continuous mode, a second utterance arriving while a device-action
   confirmation was already pending would dispatch as an ordinary new
   chat message. If that second message also produced a
   confirmation-required action, it would silently overwrite
   `pendingConfirmation`, orphaning the first (still on-screen)
   confirmation with no way back to it - a real gap in "never bypass
   confirmation merely because the user is using voice" (mission brief
   section 9), distinct from the already-documented "voice can't
   interpret a spoken yes/no" limitation. Fixed by guarding
   `TranscriptUpdated(isFinal=true)` handling: if a confirmation is
   already pending, remind the user to resolve it instead of dispatching
   the new utterance. Added
   `testSecondUtteranceWhilePendingConfirmationDoesNotOverwriteIt` to
   `ConversationAudioControllerTest.kt`, hand-traced against the fake
   STT/chat infrastructure but not compiled.

## Not changed

- Text-mode chat (`ChatViewModel`) has the same theoretical
  pendingConfirmation-overwrite shape, but its confirmation dialog is a
  standard Compose `AlertDialog`, which blocks further input by
  construction - unlike voice mode's microphone, which isn't mediated by
  any UI element. Left as-is; flagging here in case that assumption is
  ever revisited.
- `datetime.utcnow()` is used ~30 times across the backend and is
  deprecated (visible as 944 pytest warnings). Not fixed here - it's a
  larger, mechanical, cross-cutting change (naive vs. timezone-aware
  datetimes have real comparison-semantics implications if done
  inconsistently) that deserves its own dedicated pass rather than being
  folded into a bug-hunt session, and every current use is internally
  consistent (all naive, all UTC) so it isn't causing incorrect behavior
  today.
- `DeviceActionSchema.args` is typed `Dict[str, Any]` on the backend but
  `Map<String, String>` on Android. Every current call site in
  `device_tools.py` only ever puts strings in `args`, so this isn't live
  today, but it's a latent crash risk (a Gson deserialization failure) if
  a future tool ever puts a non-string value there. Worth a type
  broadening on the Android side if that happens.
