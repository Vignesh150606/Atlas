# ATLAS Roadmap

## Phase 1: Foundation (Current)
- [x] Backend scaffolding (FastAPI, SQLALchemy)
- [x] Android scaffolding (Compose, MVVM, Hilt)
- [x] Provider abstraction layer
- [x] Basic health check and connectivity

## Phase 2: Core Interaction
- [x] LLM integration (Claude/OpenAI/Gemini/Ollama, config-driven via `DEFAULT_LLM_PROVIDER`)
- [ ] Basic chat interface on Android (works, but no markdown/timestamps/retry yet)
- [x] Persistent conversation history (context-window trimmed via `ConversationService`)
- [x] Basic structured logging (JSON request traces via `app/observability/trace.py`; `structlog` dep still unused - stdlib logging + manual JSON was simpler and sufficient)

## Phase 3: Voice & Speech
- [x] Speech-to-Text (STT) integration (Android `SpeechRecognizer`, Phase 7; runtime-verified Phase 8 - see `docs/Phase8_Report.md`)
- [x] Text-to-Speech (TTS) integration (Android `TextToSpeech`, Phase 7)
- [ ] Wake word detection
- [x] Voice-only interaction mode (push-to-talk and continuous mode, Phase 7)

## Phase 4: Memory System
- [ ] Vector database integration (ChromaDB/Qdrant) - deliberately deferred, not needed yet
- [x] Fact extraction from conversations (rule-based `MemoryExtractor`)
- [x] Structured memory retrieval, injected into every chat turn (`RetrievalService` - rule/keyword based, not vector/RAG; see note below)
- [ ] Personal profile management

> Note: "retrieval" above is deterministic (intent-pattern → memory type → keyword search), not embedding similarity. Vector-based RAG is still a real future phase, not something already done under a different name.

## Cognitive Pipeline (Cognitive Intelligence Engine)
- [x] Deterministic intent classification (`IntentService`) - no LLM call
- [x] Memory ranking (recency, importance, pinned, type match, keyword relevance, conversation context) - `app/retrieval/ranking.py`
- [x] Memory lifecycle fields (confidence, last_used, access_count, verification_state) - `access_count`/`last_used` updated automatically on retrieval since Phase 5; `confidence` sat unused as a field until Phase 9 actually started writing to it (see `docs/Phase9_Report.md`) - this line was accurate about the schema, not about runtime behavior, before Phase 9.
- [x] Tool Router with MemoryTool, CalculatorTool, TimetableTool - one-shot dispatch, not an agent loop
- [x] Deterministic Reasoning Planner - decides what's needed (retrieval? which tools?) before the provider is called, no chain-of-thought
- [x] Context Builder - system/developer prompt, date/time, active provider, planner focus, tool results, ranked memories, lightweight user-profile-from-pinned-memories, conversation history
- [x] Conversation intelligence - topic detection, deterministic summaries, session metadata, context rollover (older messages get summarized rather than silently dropped once history exceeds the window)
- [x] Structured observability traces (intent, planner notes, tools, retrieved memory ids, provider, latency, memory updates - no message/memory content logged)

> Not a multi-agent or iterative agent loop: the planner produces one plan, tools are dispatched once each, no re-planning based on tool output. That's deliberately out of scope per the roadmap below.

## Phase 5: Skill System
- [x] Calendar & Reminders integration - `app/skills/reminder_skill.py`, `calendar_skill.py` (Phase 9). Confirmation-only Skills backed by new `MemoryExtractor` rules 5/6 - see `docs/Phase9_Report.md`.
- [x] Web search capability - reinterpreted as local search over ATLAS's own memories+documents (`app/skills/search_skill.py`, Phase 9); there is no actual web-search API configured anywhere in this codebase, so a literal "web search" would have meant either fabricating results or a silent no-op, both rejected. See `docs/Phase9_KnownLimitations.md` #7.
- [x] Weather and Location awareness - `app/skills/weather_skill.py` + `app/providers/weather.py` (Phase 9). Interface and factory complete; no real weather API is wired in, so every response is an honest "not configured" rather than a real forecast. See `docs/Phase9_KnownLimitations.md` #5. "Location awareness" beyond an optional free-text location extracted from the message itself was not attempted (no device-location plumbing exists).
- [ ] Home automation (Home Assistant) - not attempted in Phase 9; no plausible non-fabricated implementation without a real smart-home integration to target. See `docs/Phase9_KnownLimitations.md`.

## Phase 6: Advanced Autonomy
- [~] Agentic planning (ReAct/Tool use) - deterministic single-shot planning + tool routing exists; iterative/ReAct-style multi-step agent loops are still future work (see Phase 10 section 9/Phase 11 section 9 - explicitly not attempted either phase, deferred to Phase 12 at the earliest)
- [x] Proactive notifications - Android-side scheduling done in Phase 11 (`ProactiveSuggestionsWorker`, ~30 min WorkManager period against the Phase 10 `GET /briefing/suggestions` endpoint); not build-verified, see Phase 11 below
- [ ] Offline model support
- [ ] Privacy-first local processing

## Phase 7: Voice Architecture
- [x] Full voice pipeline: VoiceScreen -> VoiceViewModel -> ConversationAudioController -> VoiceManager (state machine) -> STT/TTS engines -> ChatRepository -> backend -> TTS
- [x] Continuous mode and push-to-talk
- [x] Barge-in (interrupt TTS mid-speech)
- [x] Bluetooth/wired/speaker output-route detection
- [~] Build-verified only as of Phase 7 close - see Phase 8 for runtime stabilization

## Phase 8: Android Automation Foundation
- [x] Stabilized Phase 7 for actual runtime use - see `docs/Phase8_Report.md` for the specific bugs found and fixed (cleartext traffic blocking every network call; Voice screen's Retry button not resetting the state machine; output route tracked but never shown in the UI)
- [x] Accessibility Service module (read screen, click, long-click, scroll, type text, back/home/recents, open notifications)
- [x] Notification Listener module (list/summarize/group)
- [x] Media Session Controller module (play/pause/next/previous/volume/now-playing)
- [x] Application Manager module (launch/search installed apps, foreground-app detection)
- [x] Clipboard Tool module (read/write)
- [x] Intent Tool module (open URL, dial, contacts, share, maps, email)
- [x] Permission Center screen (live status for Accessibility, Notification Listener, Microphone; Overlay shown as not-yet-implemented)
- [x] Every automation action routed through the existing Planner -> ToolRouter architecture, not hardcoded - see `docs/Phase8_ArchitectureUpdate.md`
- [ ] Fine-grained on-screen targeting from freeform speech alone (e.g. "tap the blue Send button" with no prior screen-read context) - needs live screen content a deterministic keyword planner can't see; see `docs/Phase8_KnownLimitations.md`
- [ ] Overlay permission / on-screen highlighting

## Phase 9: Intelligence & Agent Skills
- [x] Pluggable Skill System - `app/skills/`, six skills (time, weather, search, notes, reminder, calendar), one generic Planner hook, zero Planner changes per additional skill. Completes most of Phase 5 above.
- [x] Multi-intent detection (`IntentService.classify_all`/`is_multi_intent`) and paraphrase coverage - additive, `classify()` unchanged.
- [x] Tool Router chaining (`dispatch_plan`, `depends_on` substitution), fallback routing, structured execution reports - see `docs/Phase9_KnownLimitations.md` #3 for the honest state of `depends_on` (mechanism proven, no current emitter).
- [x] Memory: shared semantic-like ranking, near-duplicate detection, confidence lifecycle + staleness maintenance script.
- [x] Knowledge: cross-document entity linking, unified timeline, multi-document summaries.
- [x] Conversation Intelligence: follow-up detection, ambiguity detection - wired into the real prompt, verified end-to-end.
- [x] Security: `requires_confirmation` signal on `dial`/`clipboard write` - backend-only, no Android consumer yet (see `docs/Phase9_KnownLimitations.md` #6).
- [ ] Voice Improvements (natural interruptions, continuity, response timing, state transitions) - Android-side, not attempted (no Android SDK in this environment). See `docs/Phase9_KnownLimitations.md` #1.
- [ ] Automation Improvements beyond the backend-side pieces above (device-side error recovery) - not attempted, same reason.
- [x] `CLAUDE.md` (persistent engineering memory, mandatory task) and root `.gitignore` (mandatory task) created.

## Phase 10: Personal Assistant & Proactive Intelligence
- [x] Personal Context Engine - no new generic storage; permanent facts/preferences and events stay on `Memory` (unchanged), temporary context gets a new `Memory.expires_at` TTL (`MemoryService.create_temporary_context`, excluded from retrieval once expired, hard-deleted by an extended `scripts/refresh_memory_lifecycle.py`), active/completed tasks and recurring routines get dedicated new models. See `docs/Phase10_ArchitectureUpdate.md`.
- [x] Reminder System - `app/nlp/datetime_parser.py` (deterministic: relative dates, weekdays incl. next/this, explicit times, recurrence incl. custom weekday sets), dedicated `Reminder` model + `ReminderService`, `ReminderSkill` now persists a real Reminder (Phase 9 confirmation-only behavior preserved when db is unavailable). Natural-language examples from the mission brief ("remind me to X tomorrow", "at 7pm", "every Monday", "in two hours") all verified via `tests/test_datetime_parser.py`/`tests/test_reminder_service.py`.
- [x] Task Management - dedicated `Task` model, `TaskService` (create/complete/cancel/list/update/prioritize), `TaskSkill` for chat, full REST CRUD. Deliberately flat, no subtasks/projects.
- [x] Daily Briefing - `DailyBriefingService` composes existing Reminder/Task/Routine/Memory services (no new orchestration), reachable via `BriefingSkill` (chat) and `GET /briefing/daily` (structured).
- [x] Routines - dedicated `Routine` model, `RoutineService` (explicit CRUD only, nothing auto-inferred), `RoutineSkill` for chat list/show/create.
- [x] Proactive Intelligence foundation - `ProactiveSuggestionService`, pure DB-query rules (overdue/due-soon reminders, routine time match, stale-memory backlog), zero LLM calls, `GET /briefing/suggestions` meant to be client-polled, not a backend background loop.
- [x] Android Integration - `requires_confirmation` (sent by the backend since Phase 9, never consumed) now fully wired: `ChatViewModel`/`ConversationAudioController` stage confirmation-required actions, shared `ConfirmationDialog` composable gates execution in both text and voice mode, cancellation reported back to the backend. New DTOs/API methods/repository for reminders/tasks/routines/briefing; new tabbed `PersonalAssistantScreen`.
- [x] Voice Experience - confirmation gating applied identically to the voice path ("never bypass confirmation for voice" - mission brief section 8/9); no unrelated rewrite of the voice state machine (per the mission brief's "fix actual problems found, don't rewrite unnecessarily" - none found beyond the confirmation gap itself).
- [x] Confirmation System - see Android Integration above; this is the mission-brief-mandated completion of Phase 9's backend-only `requires_confirmation` signal.
- [x] Notification Intelligence - new deterministic `NotificationCategorizer` (IMPORTANT/ROUTINE/PROMOTIONAL/SYSTEM/PERSONAL/UNKNOWN, package+keyword rules, no LLM), wired into `AtlasNotificationListenerService`/`NotificationBridge`/`AutomationToolRouter` for category filtering and promotional-noise suppression in summaries.
- [x] Memory + Proactivity - temporary-context TTL (above) is the concrete link; `ProactiveSuggestionService` also surfaces a stale-memory-backlog suggestion reusing the existing `MemoryLifecycleService` staleness flag, no second staleness system.
- [x] Security & Privacy review - see `docs/Phase10_KnownLimitations.md` (no auth/authorization exists anywhere in this backend, single-user assumption documented, not newly introduced by Phase 10).
- [x] 408 backend tests passing (up from 303), zero regressions. Migration `005_personal_assistant` verified upgrade+downgrade against a real SQLite file; maintenance script verified end-to-end against a real migrated DB.
- [ ] Android build verification (`./gradlew assembleDebug`/`test`) - not possible in this sandbox (no Android SDK / Google Maven access), same constraint as Phase 8 and 9. Kotlin changes manually cross-referenced against existing signatures only. See `docs/Phase10_KnownLimitations.md` and the phone verification procedure in `docs/Phase10_Report.md`.
- [x] Voice-native ("say yes") confirmation - done in Phase 11 (`ConfirmationYesNoClassifier` + `VoiceState.AWAITING_CONFIRMATION`), not build-verified.
- [ ] LLM-assisted date-parsing fallback - the seam exists in `ReminderService`, nothing calls it yet.

## Phase 10 bug-fix pass (between Phase 10 and Phase 11)
- [x] 6 real bugs found and fixed beyond what the Phase 10 test suite caught (3 backend, pytest-verified; 3 Android, hand-traced) - see `docs/Phase10_BugFixes_Followup.md`.

## Phase 11: Android Verification, Proactive Scheduling & Hardening
- [x] Section 1 (Android build verification, gating) - attempted for real, concretely confirmed not possible in this sandbox (no SDK; `dl.google.com`/`repo.maven.apache.org`/`services.gradle.org`/`maven.google.com` all `403 host_not_allowed`; `./gradlew clean assembleDebug` fails downloading the Gradle distribution itself). Every Android item below is manual cross-referencing only, same as every prior phase.
- [x] Section 2 (Proactive suggestions, Android-side scheduling) - `ProactiveSuggestionsWorker` (Hilt + WorkManager, ~30 min period, `GET /briefing/suggestions`), dedup via `ProactiveSuggestionTracker`, Permission Center extended for `POST_NOTIFICATIONS`.
- [ ] Section 3 (Routine creation UX form) - deferred, not started. Routines tab is still list/view/delete only; creation remains chat-only.
- [x] Section 4 (Basic backend authentication) - single shared API key (`Settings.API_KEY`, `verify_api_key` dependency, `/health` excluded), Android `ApiKeyStore`/`ApiKeyInterceptor`/Settings field. Backend pytest-verified (417 passing, up from 411); Android hand-traced.
- [x] Section 5 (Voice-native confirmation) - `VoiceState.AWAITING_CONFIRMATION` + `ConfirmationYesNoClassifier`, coordinated with (not replacing) the Phase-10-bug-fix-pass pending-confirmation guard.
- [x] Section 6 (`datetime.utcnow()` cleanup) - `app/utils/time.py::utc_now()`, all 18 real call sites fixed, 944 -> 0 datetime deprecation warnings, deliberately not a switch to genuine timezone-aware storage (documented as future, separate work).
- [ ] Section 7 (DeviceAction args type mismatch) - deferred, precisely scoped this phase (14 read sites in `AutomationToolRouter.kt`), still not live.
- [x] Section 8 (Text-mode confirmation reasoning) - re-verified via static call-graph analysis (single `sendMessage()` call site, gated by the stock Compose `AlertDialog`); still not device-verified.
- [ ] Section 9 (Iterative agent loop) - correctly not attempted, per this phase's own brief ("do not attempt unless sections 1-8 are genuinely complete with runway to spare" - sections 3 and 7 weren't).
- [x] 417 backend tests passing (up from 411), zero regressions.
