# ATLAS — PHASE 11 REPORT
## Android Verification, Proactive Scheduling & Hardening

## 1. Executive summary

The phase's own stated most-important goal — turn "we've never compiled
this" into a definitive, honest answer — is done: **Android build
verification was attempted for real and is not possible in this
environment**, with concrete evidence, not an assumption (section 9).
Everything else in this report follows that constraint: backend claims
are pytest-verified; every Android change is careful manual
cross-referencing against the actual current file contents, the same
standard (and the same limitation) as Phases 8, 9, 10, and the Phase 10
bug-fix pass.

Within that constraint, this phase:
- Added the shared API key auth (section 4) - backend fully verified,
  Android side implemented and hand-traced.
- Added the WorkManager-based proactive suggestions pipeline (section 2)
  - the single biggest "backend already supports this, Android just
  never called it" gap from Phase 10.
- Added voice-native yes/no confirmation (section 5), directly
  coordinated with the pending-confirmation-overwrite guard from the
  Phase 10 bug-fix pass rather than working around it.
- Cleaned up all 18 real `datetime.utcnow()` deprecation call sites
  (section 6) with a documented, deliberately narrower fix than "make
  everything timezone-aware" (see section 8 below for why).
- Explicitly deferred sections 3 and 7, and skipped section 9, all with
  written reasoning rather than silently dropping them.

## 2. Features implemented, against this document's numbered sections

- **Section 1 (Android build verification) - DONE.** See section 9
  below for the full evidence.
- **Section 2 (Proactive suggestions, Android-side scheduling) - DONE
  (not build-verified).** `ProactiveSuggestionsWorker` (Hilt
  `CoroutineWorker`, ~30 min period via `ProactiveSuggestionsScheduler`,
  `NetworkType.CONNECTED` constraint) calls the already-Phase-10
  `GET /briefing/suggestions` endpoint and posts at most one notification
  per run, only for suggestions not already surfaced
  (`ProactiveSuggestionTracker`, keyed on `suggestion_type:related_type:
  related_id` - a genuine state change, e.g. a reminder flipping from
  `due_soon_reminder` to `overdue_reminder`, is a different key on
  purpose, so it re-notifies; an unchanged set does not). Wired via
  `Configuration.Provider` + `HiltWorkerFactory` in `AtlasApplication`,
  with WorkManager's default auto-initializer disabled in the manifest
  (standard, documented pattern for combining Hilt with WorkManager).
  Permission Center's disclaimer text and permission list were updated
  to stay accurate - it previously said nothing runs in the background
  without an explicit instruction, which this feature makes untrue.
- **Section 3 (Routine creation UX) - DEFERRED, not started.** See
  section 10 (Phase 12 recommendations) for why and what's needed.
- **Section 4 (Basic backend authentication) - DONE, backend
  pytest-verified, Android hand-traced.** Single shared API key, exactly
  as scoped (not a multi-user system - `app/models/user.py` stays
  untouched, reserved for that future work). Backend:
  `Settings.API_KEY` (default unset = open, matching pre-Phase-11
  behavior), `app.core.deps.verify_api_key` (a FastAPI dependency
  reading the `X-API-Key` header via `APIKeyHeader`), applied to every
  router except `/health` (kept public so the Android app can
  distinguish "server unreachable" from "server reachable, key
  missing/wrong" at startup, before a key is necessarily configured).
  Android: `ApiKeyStore` (SharedPreferences-backed, no new persistence
  dependency), a narrower `ApiKeyProvider` interface for testability,
  `ApiKeyInterceptor` (OkHttp), a Settings screen field to enter/save it.
- **Section 5 (Voice-native confirmation) - DONE (not build-verified).**
  New `VoiceState.AWAITING_CONFIRMATION`, entered right after ATLAS
  finishes speaking a confirmation heads-up (now: "You can say yes or
  no, or check your screen"). The next final transcript in that state
  routes through `ConfirmationYesNoClassifier` (deterministic,
  start-anchored phrase matching - not an LLM call, matching this
  codebase's existing heuristic-over-model philosophy) instead of
  dispatching as an ordinary chat message. YES/NO resolve the pending
  action exactly like the existing on-screen tap path; UNCLEAR
  re-prompts and stays in the state rather than guessing. Falls back to
  the existing `ConfirmationDialog` automatically for push-to-talk users
  who don't tap (that dialog already renders regardless of voice state)
  or whenever the classifier is unsure. Explicitly coordinated with the
  Phase-10-bug-fix-pass guard in `handleEvent` (see that code's own
  comment) rather than replacing it - the guard is still what prevents a
  second command from slipping through; this state is what tells the
  UI/orb what's being asked and what makes `VoiceManager.startListening()`
  valid without passing back through IDLE.
- **Section 6 (`datetime.utcnow()` cleanup) - DONE, pytest-verified.**
  Added `app/utils/time.py::utc_now()` - takes the same non-deprecated
  code path as `datetime.now(timezone.utc)` but strips the tzinfo before
  returning, so it's bit-for-bit interchangeable with what
  `datetime.utcnow()` produced. Deliberately *not* a switch to genuine
  timezone-aware datetimes - see section 8 for the reasoning; that's a
  larger, separate, coordinated change this phase scoped out on purpose.
  Fixed all 18 real call sites (15 found by the first grep pass; 3 more
  - bare `datetime.utcnow` references with no parens, as
  `default`/`default_factory` callables - found by a second, broader
  sweep and fixed too). 944 -> 0 datetime deprecation warnings; full
  suite green throughout.
- **Section 7 (DeviceAction args type mismatch) - DEFERRED, not
  started.** The brief itself flags this as low priority, "only if
  spare room." Investigated the actual scope: widening Android's
  `DeviceAction.args` from `Map<String, String>` to `Map<String, Any>`
  would touch 14 read sites in `AutomationToolRouter.kt` (currently all
  `String?`-typed via `.orEmpty()`), none of which can be compiled here
  to verify. Given the risk (14 call sites, unverifiable) versus the
  reward (a latent, not-currently-live crash risk - no backend tool
  puts a non-string value in `args` today), this phase's "spare room"
  went to sections 2 and 5 instead. Still not live; still worth doing
  once a real build environment exists.
- **Section 8 (Text-mode confirmation reasoning) - RE-VERIFIED via
  static analysis, not a device.** Traced `sendMessage()`'s only call
  site in the entire app (`ChatScreen.kt`'s send button) and confirmed
  `ConfirmationDialog` is the stock Compose Material 3 `AlertDialog`,
  not a custom implementation - the reasoning holds, with more evidence
  behind it than the original claim, but "traced the call graph" is not
  the same confidence level as tapping through it on a real screen,
  which this environment still can't do.
- **Section 9 (Iterative agent loop) - correctly skipped, not started.**
  Per this document's own instruction ("do not attempt unless everything
  above is done with runway to spare") - sections 3 and 7 are deferred,
  so this condition isn't met. See Phase 12 recommendations.

## 3. Backend files changed

`app/core/config.py`, `app/core/deps.py`, `app/api/v1/router.py`,
`app/models/base.py`, `app/utils/time.py` (new),
`app/repositories/{document,memory,message}_repository.py`,
`app/schemas/{briefing,chat}.py`,
`app/services/{conversation_intelligence,daily_briefing_service,
memory_service,proactive_suggestion_service,reminder_service,
routine_service,task_service}.py`, `.env.example`.

## 4. Android files changed

New: `data/local/ApiKeyStore.kt` (+ `ApiKeyProvider` interface),
`data/local/ProactiveSuggestionTracker.kt`, `di/ApiKeyInterceptor.kt`,
`proactive/{ProactiveNotifications,ProactiveSuggestionsScheduler,
ProactiveSuggestionsWorker}.kt`, `voice/ConfirmationYesNoClassifier.kt`,
`ui/screens/settings/SettingsViewModel.kt`.

Modified: `AtlasApplication.kt`, `automation/PermissionStatusChecker.kt`,
`di/AppModule.kt`, `ui/components/VoiceOrb.kt`,
`ui/screens/permissions/PermissionCenterScreen.kt` (+ViewModel),
`ui/screens/settings/SettingsScreen.kt`,
`ui/screens/voice/VoiceScreen.kt`, `voice/ConversationAudioController.kt`,
`voice/VoiceManager.kt`, `voice/VoiceState.kt`,
`app/build.gradle.kts` (new deps: `androidx.work:work-runtime-ktx:2.9.0`,
`androidx.hilt:hilt-work:1.1.0` + its `hilt-compiler`),
`AndroidManifest.xml` (`POST_NOTIFICATIONS` permission, WorkManager
initializer override).

## 5. Database migrations

None. No model/schema changes with DB shape implications this phase.

## 6. New tests

Backend (all pytest-verified): `tests/test_api_key_auth.py` (6 tests -
open-by-default, missing/wrong key rejected, correct key accepted,
`/health` stays public, coverage across every Phase 10 resource group).

Android (hand-traced against fakes, not compiled):
`ApiKeyInterceptorTest.kt` (2), `ConfirmationYesNoClassifierTest.kt` (7),
5 new cases in `ConversationAudioControllerTest.kt` (voice-native
yes/no/unclear, push-to-talk doesn't auto-listen), 6 new cases in
`VoiceStateMachineTest.kt` (AWAITING_CONFIRMATION transitions), 3 new
cases in `PermissionCenterViewModelTest.kt` (notification permission
state).

## 7. Security changes

Single shared API key (section 4) - see that section and
`Settings.API_KEY`'s docstring for exactly what this protects (a
trusted-network deployment gains a real barrier against anything else on
that network) and doesn't (not per-user auth, not encryption in transit
beyond whatever TLS the deployment already has, not protection against
someone who obtains the key). Unset by default - existing/dev
deployments are unaffected until someone opts in.

## 8. Bugs discovered and fixed

Two real bugs surfaced during this phase's own work, both caught by
manual review before being called done rather than by a compiler (none
exists here):

- My first draft of `ApiKeyInterceptorTest.kt` referenced an undefined
  class and tried to subclass `ApiKeyStore` (a concrete, non-`open`
  class with a real `Context` constructor param) - would not have
  compiled. Fixed by extracting the `ApiKeyProvider` read-only interface
  `ApiKeyStore` implements, following the exact `@Provides fun provide
  X(impl): Interface = impl` pattern this codebase already uses for
  `SpeechToTextEngine`/`TextToSpeechEngine`, and rewrote the test against
  a proper fake implementing that interface.
- A first attempt at the Gmail-style fix for `PERSONAL_PACKAGE_KEYWORDS`
  in this same investigation window (see below) used a substring keyword
  that also matched an unrelated package - caught by re-simulating every
  existing test case in Python before editing the real file, not
  discovered by any compiler.

Also worth restating precisely, since a technical report should not
blur "found this phase" with "found last phase": the six bugs listed in
`docs/Phase10_BugFixes_Followup.md` were **not** rediscovered here - this
phase's step 9 (spot-check those diffs against actual file contents) 
confirmed they're still present and correctly applied, not that they
were newly found.

## 9. What was actually verified

**Backend: pytest, for real, repeatedly.** Final run this phase: **417
passed, 0 failed** (`cd backend && ./.venv/bin/python -m pytest -q`).
Every backend section (4, 6) was verified this way after every
meaningful change, not just once at the end.

**Android: build verification was genuinely attempted, and is not
possible in this sandboxed environment.** Concrete evidence, not an
assumption:
- No Android SDK installed (`which sdkmanager adb` -> nothing,
  `$ANDROID_HOME`/`$ANDROID_SDK_ROOT` unset).
- Network egress to every host an Android build needs -
  `dl.google.com`, `repo.maven.apache.org`, `services.gradle.org`,
  `maven.google.com` - returns `HTTP 403`, header `x-deny-reason:
  host_not_allowed`, confirming this is a deliberate allowlist
  restriction, not a transient failure.
- Actually ran `./gradlew clean assembleDebug` (not just inferred it
  would fail): it fails at the very first step, before Android SDK or
  any dependency resolution is even reached -
  `java.io.IOException: Server returned HTTP response code: 403 for URL:
  https://services.gradle.org/distributions/gradle-8.5-bin.zip` - the
  Gradle wrapper itself can't be downloaded.

Given that, every Android change in this phase was written with the
same discipline as Phase 10's bug-fix pass: read the actual current file
before editing it (not from memory - this caught real drift more than
once this session), hand-trace every existing test file's assertions
against the new logic before considering a change done, and where a
mistake was made (section 8 above), fix it via the same process, not by
assuming it was fine.

## 10. What could not be verified

Everything Android, beyond hand-tracing: no `./gradlew assembleDebug`,
no `./gradlew test`, no `connectedAndroidTest`, no install on a device
or emulator. Concretely, this means none of the following have been
seen to actually run: the Hilt dependency graph resolving (including
the new `ApiKeyProvider` binding and the `HiltWorker`/`AssistedInject`
wiring for `ProactiveSuggestionsWorker`), WorkManager's
`Configuration.Provider` override actually taking effect at runtime, the
`POST_NOTIFICATIONS` runtime permission flow on a real API 33+ device,
the notification channel/posting code, the voice state machine's new
transitions under real STT/TTS timing (as opposed to the deterministic
fake-driven unit tests), or Compose recomposition of any of the new/
changed screens.

## 11. Updated phone verification procedure

Unchanged from `docs/Phase10_Report.md` section 15 - this phase could
not attempt it (no device/emulator, no successful build to install).
Two additions for whoever runs it next, once a build succeeds:
1. After granting the Notification permission in Permission Center,
   wait up to ~30 minutes (or trigger the periodic work manually via
   `adb shell am broadcast` / WorkManager's own test utilities) and
   confirm a proactive-suggestion notification appears for a genuinely
   overdue reminder, and does *not* reappear on the next cycle if
   nothing changed.
2. In Voice mode, stage a confirmation-required action (e.g. "call
   [contact]"), wait for the heads-up, and say "yes" - confirm it
   executes without a screen tap. Repeat with "no", and with an
   unrelated phrase to confirm it re-prompts instead of guessing.

## 12. Updated roadmap

See `docs/Roadmap.md`, updated this phase.

## 13. Phase 12 recommendations

In priority order:
1. **Get a real Android build environment and actually run sections
   1's verification for real** - this is still the single highest-value
   thing any future phase can do; everything Android-shaped in Phases
   8-11 is still resting on manual review alone.
2. Section 3 (Routine creation UX form) - deferred this phase, not
   because it's unimportant, but because it's a substantial standalone
   Compose UI addition with no safety/correctness urgency, unlike
   sections 2/4/5/6. Scope: name, optional description, an editable
   ordered step list, optional time-of-day, optional days-of-week -
   explicit and user-authored, per `app/models/routine.py`'s
   "never inferred" principle, same as the existing chat-based creation
   path already respects.
3. Section 7 (DeviceAction args type widening) - still low priority,
   still not live, but now scoped precisely: 14 call sites in
   `AutomationToolRouter.kt`, all currently `String?`-typed via
   `.orEmpty()`.
4. Once section 1 is real: run `./gradlew test` and see what several
   phases of never-compiled Kotlin actually produces - expect real
   errors, per this document's own section 1 guidance to Phase 11.
5. Section 9 (iterative agent loop) only after 2 and 3 above, with
   runway to spare, exactly as this document instructed for Phase 11.
