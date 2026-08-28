# ATLAS Architecture

## System Overview

ATLAS follows a client-server architecture where the Android application serves as the primary interface, and a Python-based backend handles the intelligence, memory, and integrations.

## Backend Design

The backend is built with a layered architecture:

1.  **API Layer (FastAPI)**: Handles HTTP requests, versioning, and validation.
2.  **Service Layer**: Contains business logic and orchestrates between repositories and providers.
3.  **Repository Layer**: Manages data persistence using SQLAlchemy.
4.  **Provider Layer**: Abstraction for external AI services (OpenAI, Claude, Gemini, Ollama).
5.  **Skill System**: A plugin-based architecture for extending capabilities (Calendar, Weather, etc.).
6.  **Memory System**: A multi-tiered storage for facts, events, and long-term context.

## Frontend Design (Android)

The Android app follows modern development practices:

- **MVVM (Model-View-ViewModel)**: Separation of UI and business logic.
- **Jetpack Compose**: Declarative UI framework.
- **Repository Pattern**: Centralized data access.
- **Hilt**: Dependency injection.
- **Retrofit**: Type-safe networking.

## Data Flow

1.  User interacts via Voice/Text on Android.
2.  Android app sends request to FastAPI backend.
3.  Backend identifies intent and retrieves relevant context from the Memory System.
4.  Backend selects the configured LLM Provider.
5.  LLM generates a response, potentially triggering a Skill.
6.  Response is stored in Memory and sent back to Android.
7.  Android app renders response and plays voice output.

## Voice Pipeline (Phase 7, stabilized Phase 8)

Voice Screen (Compose) → VoiceViewModel → ConversationAudioController
(conversation policy: continuous vs push-to-talk, when to auto-resume
listening) → VoiceManager (owns VoiceStateMachine: IDLE / LISTENING /
PROCESSING / SPEAKING / ERROR) → SpeechToTextEngine / TextToSpeechEngine /
AudioSessionManager (all interfaces, Android framework implementations
injected via Hilt) → ChatRepository → backend `/api/v1/chat` → response
text is spoken via TextToSpeechEngine, and a `device_action` (if present)
is executed via AutomationToolRouter before the *result* is spoken (see
below) → back to IDLE (push-to-talk) or auto-resumes LISTENING (continuous
mode).

The Voice screen's text-input mode (ChatViewModel) follows the identical
`device_action` handling, so voice and text share one behavioral contract
with the backend rather than duplicating it.

## Android Automation Foundation (Phase 8)

Built entirely on official Android APIs (AccessibilityService,
NotificationListenerService, MediaSessionManager, PackageManager,
ClipboardManager, standard Intents) - no reverse engineering, no private
APIs.

**Tool architecture** (mirrors the mission brief's diagram exactly):

```
Voice or Text input
    -> ChatRepository.sendMessage()
    -> backend: IntentService -> Planner -> ToolRouter -> device tool
       (app/tools/device_tools.py - produces a directive, not an
       execution, since the backend has no access to the phone)
    -> ChatResponse.device_action (see app/schemas/chat.py)
    -> Android: AutomationToolRouter.execute() dispatches to the matching
       module (AccessibilityBridge / NotificationBridge /
       MediaSessionController / AppManager / ClipboardTool / IntentTool)
    -> AutomationResult (success/failure + human-readable summary)
    -> spoken/shown to the user, AND reported back via
       POST /api/v1/chat/device-result
    -> persisted as an assistant message + an "automation"-category Memory
       entry, closing the "Result -> Memory" loop
```

Six modules, one Kotlin file each under `android/app/src/main/java/com/atlas/automation/`:

| Module | File | Backed by |
|---|---|---|
| Accessibility Service | `AtlasAccessibilityService.kt` / `AccessibilityBridge.kt` | `AccessibilityService`, `AccessibilityNodeInfo` |
| Notification Listener | `AtlasNotificationListenerService.kt` / `NotificationBridge.kt` | `NotificationListenerService` |
| Media Session Controller | `MediaSessionController.kt` | `MediaSessionManager` (requires notification-listener access - a real platform constraint, not a bug) |
| Application Manager | `AppManager.kt` | `PackageManager` |
| Clipboard Tool | `ClipboardTool.kt` | `ClipboardManager` |
| Intent Tool | `IntentTool.kt` | Standard implicit `Intent`s |

`AtlasAccessibilityService` and `AtlasNotificationListenerService` are
system-instantiated (the OS creates them, not Hilt), so each publishes
itself through a small `@Singleton` "bridge" (`AccessibilityBridgeImpl`,
`NotificationBridgeImpl`) that the rest of the Hilt graph depends on
instead of the Service directly - this is the standard, documented pattern
for giving a system Service access to a Hilt-managed dependency graph.

**Deliberately one directive per conversational turn.** The existing
Planner/ToolRouter is a one-shot dispatcher (see `docs/Roadmap.md`'s
Cognitive Pipeline section - this was already a deliberate project
principle before Phase 8, not something introduced by it), not an
iterative agent loop. A device action needs the same treatment: "open
WhatsApp, tap Search, type Alice" is three conversational turns, not three
actions planned from one message and blindly executed. See
`docs/Phase8_KnownLimitations.md` for the reasoning and what this rules
out.
