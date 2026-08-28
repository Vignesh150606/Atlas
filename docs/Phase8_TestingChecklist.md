# Phase 8 — Testing Checklist

Checked items were actually run and passed in this environment. Unchecked
items require the local Android toolchain (see `Phase8_VerificationGuide.md`)
and could not be executed here — see `Phase8_KnownLimitations.md` for why.

## Backend (executed in this environment)

- [x] `python -m pytest -q` — 201/201 passing (baseline 141, +60 new)
- [x] `test_device_tools.py` — all 7 device tools: valid actions produce
      correct directives, invalid/missing args are rejected cleanly (20 tests)
- [x] `test_planner_device_routing.py` — keyword routing, including the
      "open X" ambiguity cases (maps/contacts/notification-shade/URL vs.
      generic app launch) and confirming ordinary questions/greetings do
      *not* spuriously trigger a device action (23 tests)
- [x] `test_device_action_endpoint.py` — end-to-end via the real FastAPI
      app: `/chat` returns `device_action` for automation phrases and
      `null` otherwise; `/chat/device-result` persists both success and
      failure outcomes and they're visible in later conversation turns (7 tests)
- [x] `test_tools.py` — updated `available_tools()` assertion for the 7
      new tool names; full backend suite re-run clean after every change,
      not just once at the end
- [x] Existing 141 tests — confirmed unaffected (identical pass count
      before touching device tools, before touching the Planner
      command-intent regex, and after all changes)

## Android (requires local toolchain — not run here)

- [ ] `./gradlew clean assembleDebug` — compiles cleanly
- [ ] `./gradlew test` — all suites pass, including:
  - [ ] `AutomationToolRouterTest` (19 cases — every module/action pair,
        plus unknown-module and unknown-action failure paths)
  - [ ] `PermissionCenterViewModelTest` (6 cases)
  - [ ] `VoiceManagerTest` (10 cases, including the Retry-fix regression:
        `testClearErrorResetsErrorStateBackToIdle`,
        `testClearErrorIsANoOpOutsideErrorState`,
        `testAfterClearErrorTheUserCanStartListeningAgain`)
  - [ ] `ConversationAudioControllerTest` (extended +5: device-action
        execution, speaking the verified result vs. raw LLM text,
        reporting back to the backend, and the ordinary-response case
        being unaffected)
  - [ ] `ChatViewModelTest` (extended +3: same device-action coverage
        for text-chat mode)
  - [ ] `VoiceStateMachineTest`, `ChatRepositoryTest`,
        `MemoryViewModelTest`, `VoiceViewModelTest` — pre-existing, confirm
        still green (nothing in Phase 8 should have touched their
        behavior, but constructor-signature changes elsewhere make this
        worth re-confirming explicitly rather than assuming)

## Runtime (requires a device/emulator — not run here)

- [ ] Cleartext-traffic fix: a plain chat message succeeds on a
      targetSdk 28+ emulator/device (see `Phase8_VerificationGuide.md` §3)
- [ ] Retry button recovers the Voice screen from an error state
- [ ] Output-route label reflects Speaker/Bluetooth/Wired headset correctly
- [ ] Permission Center: all three implemented rows (Accessibility,
      Notification Listener, Microphone) show correct live status and the
      Enable button reaches the right destination; status updates
      immediately on return from system Settings without needing to leave
      and reopen the screen
- [ ] One phrase per automation module produces both the on-device action
      and a spoken/shown result (table in `Phase8_VerificationGuide.md` §4)
- [ ] Accessibility actions attempted while the permission is disabled
      fail with a clear message instead of crashing
- [ ] `<queries>` package-visibility check: app search/launch finds
      multiple installed apps by name on an Android 11+ device/emulator,
      not just the ones that happen to be exempt

## Not yet covered by any test, by design (see `Phase8_KnownLimitations.md`)

- Real on-device `AccessibilityNodeInfo` tree walking, real
  `NotificationListenerService` callbacks, real `PackageManager` queries,
  real `ClipboardManager` behavior — these require either Robolectric
  (unavailable in this environment) or an instrumented test on a real
  device/emulator, and were not written as instrumented tests in this
  phase. Everything upstream of the Android-framework boundary
  (`AutomationToolRouter`'s dispatch logic, the ViewModels, the backend's
  entire device-tool contract) is unit-tested; the framework calls
  themselves are only verified by manual testing per
  `Phase8_VerificationGuide.md` §4.
