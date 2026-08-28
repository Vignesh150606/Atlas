# Phase 8 — Verification Guide

This environment could not run Android builds at all (see
`Phase8_Report.md` §4 and `Phase8_KnownLimitations.md` for exactly why).
Everything in this guide needs to be run locally before treating the
Android side as verified. Backend steps genuinely were run here and are
included so you can reproduce the same result.

## Backend (can be verified right now, either here or locally)

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # if not already present
python -m pytest -q
```

**Actual result in this environment:** `201 passed, 0 failed` (baseline
before Phase 8 was 141; 60 tests added). If your result differs, something
about your environment (Python version, a stale `.env`) differs from
what was used here — the code itself was not changed after this run.

Spot-check the new endpoint directly:

```bash
uvicorn app.main:app --reload
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Open WhatsApp"}' | python -m json.tool
# Expect a "device_action" object: {"tool": "launch_app", "module": "app_manager", "action": "launch_app", "args": {"query": "WhatsApp"}}
```

## Android (must be run locally — this environment cannot)

### 1. Build

```bash
cd android
./gradlew clean assembleDebug
```

If this fails, it is the single most important signal in this whole
phase — every Kotlin file added or changed in Phase 8 was checked by hand
against the existing codebase's actual class names, constructor
signatures, and import paths, but hand-checking is not a compiler. Read
the error; if it's in a Phase 8 file, it's a real gap this report didn't
catch. Start with the automation package and the four files touched for
the retry/cleartext fixes (`VoiceManager.kt`, `ConversationAudioController.kt`,
`AudioSessionManager.kt`, `AppModule.kt`).

### 2. Unit tests

```bash
./gradlew test
```

New test files to look for in the output:
`AutomationToolRouterTest`, `PermissionCenterViewModelTest`,
`VoiceManagerTest`, plus extended `ConversationAudioControllerTest` and
`ChatViewModelTest`. If `ChatViewModelTest` or
`ConversationAudioControllerTest` fail to *compile* (not just fail an
assertion), check that no other code path still calls the old
constructor signatures — `ChatViewModel(repository)` (now 2-arg) or
`ConversationAudioController(voiceManager, chatRepository)` (now 3-arg).

### 3. Runtime — Phase 7 stabilization fixes

Point the backend at the emulator (`adb reverse` not needed —
`10.0.2.2` is already the emulator's host-loopback alias) and run the app
on an emulator or device, backend running locally per the backend section
above.

- **Cleartext fix:** open the Chat or Voice screen and send any message.
  Before this fix, this would fail with a network error on any targetSdk
  28+ device/emulator. If it now returns a response, the fix is working.
- **Retry fix:** trigger a voice error (e.g. deny the microphone
  permission, or stop the backend mid-request and start a voice turn),
  wait for the orb to show "Something went wrong," tap Retry. The orb
  should return to "Tap to talk" and accept a new tap. Before the fix, it
  would stay on the error state indefinitely (Cancel still worked as a
  workaround).
- **Output route indicator:** open Voice screen with and without a
  Bluetooth audio device connected; confirm the small "Audio: ..." label
  under the state text changes between Speaker/Bluetooth/Wired headset.

### 4. Runtime — Android Automation Foundation

Enable permissions first: Settings → Automation → Permission Center →
grant Accessibility, Notification Listener, and Microphone (each opens
the relevant system screen; return to the app afterward and confirm the
row now shows "Enabled" without needing to reopen the screen).

Then, by voice or text, try one phrase per module and confirm both the
action happens on-device and a result message appears:

| Say | Module | Expect |
|---|---|---|
| "Open WhatsApp" (or any installed app) | Application Manager | App launches; "✅ Opened WhatsApp." (or the actual app name) |
| "Check my notifications" | Notification Listener | Spoken/shown summary of current notifications |
| "Pause" / "Play" / "Volume up" | Media Session Controller | Active media session responds (requires something already playing and Notification Listener enabled — see `Phase8_ImplementationNotes.md`) |
| "Copy hello world to clipboard" | Clipboard | Clipboard now contains "hello world" (paste anywhere to confirm) |
| "Call 555-1234" | Intent Tool | Dialer opens pre-filled (does not place the call automatically — see `Phase8_ImplementationNotes.md` for why) |
| "Go back" / "Go home" | Accessibility | Standard back/home navigation fires |

If Accessibility is disabled, on-screen actions should return a clear
"Accessibility service is not connected" result rather than crashing —
worth confirming explicitly, since it's the failure path most likely to
be reached by a real user who hasn't granted the permission yet.

### 5. Package-visibility sanity check specifically

Android 11+ device/emulator: say "open" followed by several different
installed app names. If most or all fail to find the app despite it being
installed, the `<queries>` block in `AndroidManifest.xml` did not merge
correctly — this is the one manifest change in this phase with no
graceful fallback if it's missing or malformed.
