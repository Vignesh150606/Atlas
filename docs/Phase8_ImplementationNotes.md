# Phase 8 — Implementation Notes

Module-by-module notes on non-obvious decisions. For the request/response
contract and wiring, see `Phase8_ArchitectureUpdate.md`.

## Accessibility Service

`accessibility_service_config.xml` declares only what the seven documented
capabilities need: `flagReportViewIds | flagRetrieveInteractiveWindows`,
`canRetrieveWindowContent="true"`, `canPerformGestures="false"`. No touch
exploration, no fingerprint gestures — those would require justifying a
much more sensitive Play Store accessibility-service declaration for
capabilities this app doesn't use.

`click`/`long_click`/`type_text` locate a control by matching visible text
or content-description against the `target` argument (case-insensitive
substring match, walking the node tree from the active window's root).
This is inherently best-effort — the same weakness every
accessibility-based automation tool has, not specific to this
implementation. `read_screen` walks the same tree and returns a flattened
text summary rather than the raw node dump, since the raw dump is not
useful to an LLM or to speak aloud.

Foreground-app detection is implemented via
`TYPE_WINDOW_STATE_CHANGED` accessibility events rather than
`UsageStatsManager`, deliberately — `PACKAGE_USAGE_STATS` is a special
permission granted only through a separate system settings screen with its
own consent flow, and the accessibility service already receives the
signal it needs as a side effect of being enabled at all. One fewer
permission to explain to the user.

## Notification Listener

Read-only. `AtlasNotificationListenerService` never calls
`cancelNotification()` or constructs a reply/action `PendingIntent` — the
mission brief lists "observe / summarize / group," not "act on." Grouping
uses `StatusBarNotification.groupKey` (platform-provided) rather than
inferring groups heuristically.

## Media Session Controller

**Real platform constraint, not a bug:** `MediaSessionManager.getActiveSessions()`
requires the calling app to itself hold *notification listener* access —
there is no separate, lesser permission for "just media session control."
This means the Media module's actual runtime dependency is the
Notification Listener permission, not a permission of its own — reflected
in Permission Center (media control is not listed as a fourth row; it
piggybacks on the Notification Listener row's description) and called out
in `AndroidMediaSessionController`'s doc comment so a future reader
doesn't mistake it for an oversight.

## Application Manager

`queryIntentActivities(ACTION_MAIN, CATEGORY_LAUNCHER)` requires the
`<queries>` declaration added to `AndroidManifest.xml` in Phase 8 — on
Android 11+, without it, this call returns almost nothing due to package
visibility filtering. This is the one `<queries>` entry that automation
functionally cannot work without; see `AndroidManifest.xml`'s inline
comment and `Phase8_VerificationGuide.md` for how to confirm it's working.

App matching is fuzzy (case-insensitive substring against the launcher
label), consistent with how a person would actually say an app's name by
voice ("open whatsapp" should match "WhatsApp" without exact-case typing).

## Clipboard Tool

**Read is intentionally best-effort and may return nothing on Android
10+.** Since API 29, an app can only read the clipboard if it is the
default input method, or currently has input focus in the foreground —
this is a platform privacy restriction with no permission that unlocks
it, not a limitation of this implementation. `AndroidClipboardTool.read()`
returns a clear "clipboard access restricted" result rather than silently
returning empty, so the failure is legible instead of looking like a bug.
Write is unrestricted and works from the background as normal.

## Intent Tool

`ACTION_DIAL` (opens the dialer pre-filled, requires a user tap to
actually call) is used, not `ACTION_CALL` (calls immediately) —
deliberately: `ACTION_CALL` requires the dangerous `CALL_PHONE` runtime
permission and removes the user's final confirmation before a call is
placed. Voice-triggered automation placing a real phone call with no
human-in-the-loop step is a foreseeable way to place unwanted calls (e.g.
misheard transcription), so this trades a small amount of convenience for
a meaningful safety margin. Every other Intent Tool action
(`open_url`/`contacts`/`share`/`maps`/`email`) already requires the user
to act on the resulting Activity (tap send, tap send-email, etc.) as a
natural consequence of using standard `Intent`s rather than lower-level
APIs — dial is the one action type where Android offers both an
"immediate" and a "staged" variant, so it's the one place this needed an
explicit choice.

## Permission Center

Status for Accessibility and Notification Listener is read directly from
`Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES` and
`NotificationManagerCompat.getEnabledListenerPackages()` — not from
`AccessibilityBridge.isConnected` / `NotificationBridge.isConnected`.
Those bridge flags only reflect "has our Service been bound at least once
this process lifetime," which lags behind the user flipping the system
toggle (no guaranteed instant rebind, and never un-sets if the process
hasn't revisited the code path). Reading the platform's own settings APIs
gives an immediate, accurate answer the instant the user returns from
Settings — the actual point of this screen.

## Naming conventions followed

New Android files followed the codebase's existing conventions rather
than introducing new ones: `Interface` + `AndroidInterface` (matching
`SpeechToTextEngine`/`AndroidSpeechToTextEngine` from Phase 7), one
concept per file, KDoc explaining *why* on every non-obvious decision
(matching the density of comments already present in `VoiceManager.kt`/
`VoiceStateMachine.kt`), `@Singleton` + `@Inject constructor` + a thin
Hilt `@Provides` binding method per interface (matching `AppModule.kt`'s
existing pattern exactly).
