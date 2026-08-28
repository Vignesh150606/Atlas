# Phase 8 — Report

## Summary

Phase 8 had two objectives: stabilize Phase 7's voice pipeline for actual
runtime use, and build the Android Automation Foundation. Both are
implemented. This report is a factual account of what was found, what was
built, and — importantly — what could and could not be verified given this
environment's constraints (see §4).

## 1. Phase 7 stabilization: three real bugs found and fixed

These were found by reading the actual code end-to-end, not assumed from
the mission brief's "build-verified, not runtime-verified" framing. Two of
the three would have made voice mode partially or entirely unusable on a
real device or emulator.

### 1a. Cleartext HTTP traffic blocked (critical)

`targetSdk = 34`, and Android has blocked cleartext (plain HTTP) traffic
by default since API 28 unless a network security config explicitly
allows it. The app's `BASE_URL` was `http://10.0.2.2:8000/api/v1/` — plain
HTTP — with no `networkSecurityConfig` declared anywhere. Every Retrofit
call, not just Phase 8's additions, would fail at runtime with a
`CLEARTEXT communication ... not permitted` exception, despite building
and installing without any error. This is almost certainly *the* reason
Phase 7 was build-verified but not runtime-verified — a plain "say hello"
text chat would have failed too.

**Fix:** `android/app/src/debug/res/xml/network_security_config.xml`
(permits cleartext to `10.0.2.2`/`localhost`/`127.0.0.1` only) +
`android/app/src/debug/AndroidManifest.xml` (references it). Scoped to the
`debug` build variant only via Android's standard source-set manifest
merging — release builds get no override and keep the platform default of
blocking cleartext entirely.

### 1b. Voice screen's "Retry" button did not actually recover from an error

`VoiceStateMachine.ALLOWED_TRANSITIONS` only allows leaving `ERROR` via a
`reset()` call. The Retry button called
`ConversationAudioController.clearError()`, which cleared the *displayed*
error text (`VoiceSessionState.error = null`) but never told
`VoiceManager`'s own state machine to leave `ERROR`. Cancel worked (it
calls `cancel()`, which does reset the machine); Retry silently did not —
the orb stayed on "Something went wrong" indefinitely after the first
error.

**Fix:** added `VoiceManager.clearError()` (resets the state machine only
if currently in `ERROR`, a no-op otherwise so it can't interrupt a live
session) and wired `ConversationAudioController.clearError()` to call it.
Regression-tested in `VoiceManagerTest.testClearErrorResetsErrorStateBackToIdle`
and two adjacent tests for the no-op and recovery cases.

### 1c. Output route was tracked but never shown anywhere

The mission brief explicitly asks to verify Bluetooth routing.
`VoiceSessionState.outputRoute` was already being computed correctly
(`AudioSessionManager.currentOutputRoute()`, refreshed on every
`startListening()` call) — but nothing in `VoiceScreen` ever rendered it,
so there was no way to visually confirm it was working.

**Fix:** small `Audio: Speaker / Wired headset / Bluetooth` label added
below the state label in `VoiceScreen`. Deliberately minimal — a
diagnostic signal, not a primary control.

### Also, as a byproduct of fixing 1b properly

`AudioSessionManager` was a concrete class requiring an Android `Context`,
so `VoiceManager`/`ConversationAudioController` had *no* unit test
coverage before Phase 8 (`VoiceStateMachineTest` tested the pure state
machine; `VoiceViewModelTest` tested against a hand-written fake
`VoiceRepository`, one layer above where the actual bug lived). It was
extracted into an interface (`AudioSessionManager`) + implementation
(`AndroidAudioSessionManager`), mirroring the pattern already used for
`SpeechToTextEngine`/`TextToSpeechEngine`. `FakeAudioSessionManager` now
exists, and `VoiceManagerTest.kt` / `ConversationAudioControllerTest.kt`
exist for the first time — 20+ new test cases between them.

## 2. Android Automation Foundation

All six mission-specified modules are implemented: Accessibility Service,
Notification Listener, Media Session Controller, Application Manager,
Clipboard Tool, Intent Tool — plus Permission Center. See
`Phase8_ArchitectureUpdate.md` for the structural detail and
`Phase8_ImplementationNotes.md` for module-by-module notes.

**One gap found and fixed during self-review, worth stating plainly:**
partway through, `AutomationToolRouter` was already injected into both
`ChatViewModel` and `ConversationAudioController` but neither one actually
called `.execute()` on it — a `device_action` from the backend was
silently dropped in both text and voice mode, and the two view-layer test
files (`ChatViewModelTest.kt`, `ConversationAudioControllerTest.kt`) still
called the pre-automation constructor signatures, which would not have
compiled. Both are now wired and fixed; see git-diff-equivalent notes in
`Phase8_ArchitectureUpdate.md` §5. This is exactly the kind of
integration gap the mission brief's "do NOT assume this works, verify
every connection" instruction was warning about, and it's called out here
rather than glossed over.

## 3. Testing

Backend: **201/201 pytest passing** (baseline was 141; 60 new tests added
for device tools, planner routing, and the device-action endpoints — see
`Phase8_TestingChecklist.md` for the exact command and current count).

Android: cannot be executed in this environment (see §4), but 6 new test
files were added covering every piece of *logic* that doesn't require the
Android framework itself: `AutomationToolRouterTest.kt` (dispatch table,
19 cases), `PermissionCenterViewModelTest.kt` (6 cases),
`VoiceManagerTest.kt` (new, 10 cases, including the 1b regression),
`ConversationAudioControllerTest.kt` (extended, +5 device-action cases),
`ChatViewModelTest.kt` (extended, +3 device-action cases), plus the
pre-existing `VoiceStateMachineTest.kt` (unaffected, still applicable).

## 4. What could not be verified, and why

This is a plain statement of environment constraints, not a hedge:

- **No Android SDK, no Gradle network access.** This sandbox's network
  egress allowlist does not include `dl.google.com` (Google's Maven repo,
  required for the Android Gradle Plugin and every AndroidX dependency),
  `repo.maven.apache.org` (Maven Central), or `services.gradle.org` (the
  Gradle wrapper's own distribution download). `./gradlew clean
  assembleDebug` and `./gradlew test` as requested in the mission brief
  **could not be run** — not "were run and passed," genuinely could not
  execute at all. Every Kotlin change was written with the same care as
  compiled code and cross-checked by hand against the existing codebase's
  actual imports/signatures (see `Phase8_VerificationGuide.md` for what
  manual checks *were* done and their results), but this is not a
  substitute for an actual compile.
- **Backend Python tests genuinely did run** — `pip install` from PyPI is
  allowed, `pytest` executed for real, 201/201 passing is an actual
  result, not a projection.

**Practical implication:** run `./gradlew clean assembleDebug &&
./gradlew test` locally before treating the Android side as done. See
`Phase8_VerificationGuide.md` for the full local verification procedure,
and `Phase8_KnownLimitations.md` for a consolidated list of every place
this report or the code comments flag something as unverified,
best-effort, or deliberately out of scope.
