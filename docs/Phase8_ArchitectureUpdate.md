# Phase 8 — Architecture Update

This document describes what changed structurally in Phase 8, and why each
decision was made. For narrative results (what was found, what was fixed)
see `Phase8_Report.md`. For the reasoning behind things Phase 8
deliberately did *not* build, see `Phase8_KnownLimitations.md`.

## 1. The device-tool contract (backend ↔ Android)

The backend's Planner/ToolRouter was already a deterministic, one-shot
dispatcher — tools run once, before the LLM call, and their output is
folded into the prompt (see `app/tools/router.py` and the "Cognitive
Pipeline" section of `docs/Roadmap.md`). This was a deliberate project
principle already in place before Phase 8, not something Phase 8
introduced.

The problem: a device tool *can't* actually execute on the backend. There
is no code path from a FastAPI process to a specific user's phone. So
Phase 8 tools don't execute anything — they validate the request and
produce a **directive**:

```python
ToolResult(
    tool_name="launch_app",
    success=True,
    output="Preparing to launch 'WhatsApp' on the user's device.",
    device_action={"module": "app_manager", "action": "launch_app", "args": {"query": "WhatsApp"}},
)
```

`ToolResult` gained one new optional field, `device_action`
(`app/tools/base.py`) — additive, every pre-existing tool is unaffected.
`ChatService._extract_device_action` lifts the first successful one onto
`ChatResponse.device_action` (`app/schemas/chat.py`), which the Android
client reads and executes locally via `AutomationToolRouter`.

The outcome is reported back via `POST /api/v1/chat/device-result`
(`app/api/v1/endpoints/chat.py`), which appends an assistant message to
the conversation and writes an `automation`-category Memory entry. This is
the "Result → Memory" leg of the mission's tool-architecture diagram, and
it's the only leg that *has* to be a round trip: the backend has no other
way to learn what happened on the device.

**Why one directive per turn, not a queue or a plan of several actions:**
see `Phase8_KnownLimitations.md` §1. Short version: the planner is
deterministic keyword matching, not a live agent loop, so there's nothing
on the backend that could sensibly react to a device action's result
mid-turn anyway.

## 2. Seven backend tools, six Android modules

The mission specifies six Android modules. The backend exposes seven tool
names because Application Manager's two capabilities (launch, search) are
different enough in shape (`launch_app` takes a name and launches
immediately; `search_app` takes a name and returns matches without
launching) that collapsing them into one tool with an `action` parameter
would have made the Planner's keyword-routing rules import edge cases
from every other module for two capabilities. Every other module (5 of 6)
*does* use a single tool with an `action` argument
(`app/tools/device_tools.py` — `AccessibilityActionTool`, `NotificationTool`,
`MediaControlTool`, `ClipboardTool`, `IntentActionTool`).

```
launch_app, search_app   -> app_manager module
accessibility            -> accessibility module   (click/long_click/scroll/type_text/back/home/recents/open_notifications/read_screen)
notifications             -> notifications module   (list/summarize/group)
media                      -> media_session module   (play/pause/next/previous/volume_up/volume_down/now_playing)
clipboard                  -> clipboard module        (read/write)
intent_action               -> intent module            (open_url/dial/contacts/share/maps/email)
```

`app/tools/device_tools.py::DEVICE_TOOL_NAMES` is the single source of
truth for "which tool names are device tools" — tests reference it rather
than re-deriving the list, so it can't silently drift.

## 3. Planner routing

`app/planner/planner.py::Planner._build_device_tool_call` adds
deterministic regex routing ahead of the existing keyword rules (memory,
timetable, documents, etc.) A device action is a standalone command, so
matching one short-circuits the rest of `build_plan` (memory/knowledge
retrieval are explicitly skipped — there's no reason to search prior
conversation context before, say, pausing music).

Ordering matters and is documented inline: several patterns share the
word "open" (`open WhatsApp` vs `open my contacts` vs `open the
notification shade` vs `open example.com`), so the more specific
intent/accessibility/URL patterns are tried before the generic
app-launch fallback. Getting this order wrong would silently launch an
app literally named "contacts" or "maps" instead of firing the intended
system intent.

## 4. Android: the automation package

New package `android/app/src/main/java/com/atlas/automation/`:

- `AutomationModels.kt` — `DeviceAction` (mirrors `DeviceActionSchema`
  exactly: `tool`, `module`, `action`, `args: Map<String, String>`) and
  `AutomationResult` (`success`, `summary`, `details`).
- `AtlasAccessibilityService.kt` + `AccessibilityBridge.kt`
- `AtlasNotificationListenerService.kt` + `NotificationBridge.kt`
- `MediaSessionController.kt`, `AppManager.kt`, `ClipboardTool.kt`,
  `IntentTool.kt` — one interface + one `Android*`-prefixed implementation
  each, matching the existing `SpeechToTextEngine`/`AndroidSpeechToTextEngine`
  naming convention from Phase 7's voice pipeline.
- `AutomationToolRouter.kt` — the Android-side counterpart to the
  backend's `ToolRouter`: maps `DeviceAction(module, action, args)` to the
  matching interface call. Pure dispatch logic with no Android-framework
  dependency of its own, which is what makes it unit-testable
  (`AutomationToolRouterTest.kt`) without Robolectric.
- `PermissionStatusChecker.kt` — reads live permission status from
  `Settings.Secure` / `NotificationManagerCompat` for Permission Center.

### The bridge pattern

`AtlasAccessibilityService` and `AtlasNotificationListenerService` are
instantiated by the OS, not by Hilt, when the user enables them in system
Settings — Android controls their lifecycle entirely. But the rest of the
app (specifically `AutomationToolRouter`) needs to call into whichever
instance is currently alive, and needs to do it through an interface it
can fake in tests.

The resolution is a `@Singleton` "bridge" class the Hilt graph actually
depends on (`AccessibilityBridgeImpl`, `NotificationBridgeImpl`). The
`@AndroidEntryPoint`-annotated Service injects the *concrete* bridge
singleton and calls internal `attach(self)`/`detach()` hooks on
`onServiceConnected()`/`onDestroy()`; everything else in the app depends
only on the public interface (`AccessibilityBridge`, `NotificationBridge`),
which exposes an `isConnected: StateFlow<Boolean>` and returns a clear
"service not connected" `AutomationResult` if the user hasn't enabled the
permission yet, rather than crashing.

## 5. Wiring into the existing chat/voice pipeline

Both `ChatViewModel` (text mode) and `ConversationAudioController` (voice
mode, via `VoiceManager`) now check `ChatResponse.device_action` after a
successful send, execute it through `AutomationToolRouter`, and report the
result back. This was the one piece of "no shortcuts" that Phase 8's own
self-review caught as incomplete mid-way through — both classes already
had `AutomationToolRouter` injected, but neither one called `.execute()`
on it, so a `device_action` was silently dropped in both modes. See
`Phase8_Report.md` §2 for details; this is now fixed and covered by
`ChatViewModelTest`/`ConversationAudioControllerTest`.

**Voice mode speaks the verified result, not the LLM's pre-action text.**
`response.response` is written by the LLM *before* the device action
executes (e.g. "Sure, opening WhatsApp now") — it can't know whether the
action actually succeeded. `ConversationAudioController.handleDeviceAction`
speaks `AutomationResult.summary` instead (e.g. "Opened WhatsApp." or "No
app matching 'Nonexistent' was found."), which is both more honest and
sidesteps having to sequence two separate TTS utterances around
`VoiceManager`'s auto-resume-listening transition in continuous mode.

**Text mode shows both**, as two separate chat bubbles — the LLM's
immediate reply, then a follow-up "✅ …" / "⚠️ …" message once the action
completes — since a scrollable chat transcript doesn't have voice mode's
double-utterance sequencing problem, and showing the LLM's conversational
reply has more value in a visual chat surface than it does spoken aloud
back-to-back with the result.

## 6. Permission Center

New screen (`ui/screens/permissions/PermissionCenterScreen.kt` +
`PermissionCenterViewModel.kt`), reachable from Settings → Automation →
Permission Center (`Routes.PERMISSIONS` in `AtlasNavGraph.kt`). Shows
Accessibility, Notification Listener, and Microphone with live
enabled/disabled status and a button to the relevant system settings
screen (or the in-app runtime-permission dialog, for microphone); Overlay
is shown as "Coming soon" per the mission brief's "(future)" note — there
is no overlay module to enable yet.

Status is re-read on every `ON_RESUME`, not just on first composition,
since two of the three permissions require leaving the app to grant and
there's no callback for "the user came back from Settings."
