# Phase 8 — Known Limitations

Consolidated, honest list. Each item says what the limitation is, why it
exists, and what it would take to remove.

## 1. One device action per conversational turn

`Planner._build_device_tool_call` returns at most one tool call, and
`ChatService._extract_device_action` lifts at most one `device_action`
onto the response. "Open WhatsApp, then tap Search, then type Alice" is
three separate conversational turns, not one message that triggers three
chained actions.

**Why:** the existing Planner/ToolRouter is a deterministic, one-shot
dispatcher — tools run once, before the LLM call (this was a project
principle already in place before Phase 8; see the "Cognitive Pipeline"
section of `docs/Roadmap.md`). There is no mechanism for the backend to
see a device action's result and decide what to do next within the same
turn — that would require an iterative agent loop, which is explicitly
listed as future work in `docs/Roadmap.md`'s Phase 6. Bolting a fake
version of that onto Phase 8 specifically for device actions would create
two different automation mechanisms with different capabilities and no
shared testing story, which is a worse outcome than one consistent
mechanism with a clear boundary.

**To remove:** implement the (already-planned) agent loop generally, not
as a device-action special case.

## 2. Fine-grained on-screen targeting needs a screen-read first

The Planner can route "click the Send button" only if `target` is
supplied structurally — it cannot route "tap the blue button in the
corner" from freeform speech alone, because a deterministic keyword
planner has no access to what's actually on screen.

**Why:** this genuinely needs live screen content (from a prior
`read_screen` accessibility call) fed back to whatever is choosing the
target — either the LLM or a follow-up matching pass — which the current
single-shot, pre-LLM tool dispatch doesn't support. Same root cause as
Limitation 1.

**Current behavior:** `accessibility` with `action=click`/`long_click`/
`type_text` and an explicit `target` string works and is tested
(`test_accessibility_click_requires_target`,
`AutomationToolRouterTest.testAccessibilityClickRoutesWithTarget`); there
is just no deterministic keyword phrase that reliably extracts a `target`
from open-ended speech the way "open WhatsApp" reliably extracts an app
name.

## 3. Clipboard read is platform-restricted, not implementation-restricted

Since Android 10 (API 29), only the default input method or the
foreground-focused app can read the clipboard. `AndroidClipboardTool.read()`
will often correctly report "clipboard access restricted" outside those
conditions. There is no permission that removes this restriction — it's a
deliberate platform privacy control. See `Phase8_ImplementationNotes.md`.

## 4. Media control depends on Notification Listener, not a permission of its own

`MediaSessionManager.getActiveSessions()` requires the app to already hold
notification listener access. Permission Center reflects this by not
listing a separate "Media" row — see `Phase8_ImplementationNotes.md`.

## 5. Dialing stops short of placing the call

`intent_action` with `action=dial` opens the dialer pre-filled and
requires a user tap to actually place the call — it deliberately does not
use `ACTION_CALL`, which would call immediately and requires the
`CALL_PHONE` dangerous permission. This is a considered safety choice, not
an oversight: voice-triggered automation is subject to misheard
transcriptions, and placing a real phone call with zero human confirmation
step is a foreseeable way to create an unwanted call. See
`Phase8_ImplementationNotes.md` for the full reasoning.

## 6. Accessibility settingsActivity is the whole app, not Permission Center specifically

`accessibility_service_config.xml`'s `settingsActivity` points at
`MainActivity` (the app's only Activity — Permission Center is a Compose
destination inside it, not a separate Activity). Tapping the gear icon
next to "ATLAS" in system Accessibility settings opens the app at its
normal start destination, not directly at Permission Center.

**To remove:** either give Permission Center its own Activity (more
manifest surface for one navigation shortcut) or handle a launch-time deep
link into `AtlasNavGraph`'s `PERMISSIONS` route from `MainActivity`. Judged
not worth the complexity for Phase 8.

## 7. Android could not be built, run, or tested in this environment

This is an environment constraint, not a design decision, but it's the
single most important limitation in this phase and is repeated here for
completeness (full detail in `Phase8_Report.md` §4):

- No Android SDK installed.
- The network egress allowlist available to this environment does not
  include `dl.google.com`, `repo.maven.apache.org`, or
  `services.gradle.org` — meaning even a plain `./gradlew tasks` cannot
  resolve the Gradle wrapper distribution itself, let alone AGP or any
  AndroidX/Compose/Hilt dependency.
- Every Kotlin file in this phase was therefore verified by careful manual
  cross-referencing against the existing codebase's real class names,
  constructor signatures, and import paths (and several real mismatches
  *were* caught this way — see `Phase8_Report.md` §1b and §2) — but manual
  review is not a substitute for `./gradlew clean assembleDebug`, which
  has not been run since before this repository was uploaded.

**What this means practically:** treat the Android portion of this phase
as "implementation complete, compilation and runtime behavior not yet
confirmed" until `Phase8_VerificationGuide.md` has actually been run
locally. The backend portion does not carry this caveat — `pytest` ran
for real, repeatedly, in this environment.

## 8. Overlay module is not implemented

Listed in the mission brief as "(future)" and treated accordingly:
Permission Center shows an Overlay row marked "Coming soon," and no
`SYSTEM_ALERT_WINDOW` permission or overlay code exists yet. Not a gap
relative to Phase 8's actual scope — it's explicitly out of scope per the
brief's own parenthetical.
