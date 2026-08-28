# ATLAS — Implementation Plan for Sonnet 5

Written by the Opus 5 architecture session, 2026-08-28, for the Sonnet 5
implementation sessions.

**Read this before writing code. Do not redesign the architecture.** Decisions
are made in `ARCHITECTURE_TARGET.md`, `DEPLOYMENT_PLAN.md`, and
`SECURITY_PLAN.md`. If evidence contradicts a decision, **stop and flag it with
the evidence** rather than diverging quietly — that rule has caught real bugs in
this project repeatedly.

---

## 0. Ground rules for every session

1. **Get the repo into git first.** `git status` currently reports *not a git repository*. Nothing else in this plan is safe until that is fixed. One commit per numbered step below.
2. **Verify, never assume.** Run `venv/Scripts/python.exe -m pytest -q` from `backend/` and `.\gradlew.bat test` from `android/` **in PowerShell** (`java` is absent from the Git Bash PATH). Report real counts. Baselines to beat: **417 backend, 123 Android.**
3. **The Android toolchain works on this machine** (JDK 21 + SDK + cached Gradle 8.5, verified 2026-08-28). "Cross-referenced but not compiled" is no longer an acceptable status for Kotlin work.
4. **Smallest change that solves the problem.** Two of the highest-value items here are deletions.
5. **Never weaken a test to make it pass.** Grow an assertion consciously and say so.
6. **After adding trigger-phrase routing, hand-run realistic messages through the planner.** Green tests have missed this class of bug twice before.
7. **A phase is not done until the device check passes with the development PC powered off.**

---

# PHASE 12 — Make It Real

**Objective:** cloud-deployed, timezone-correct, offline-tolerant, secured.
**Gates:** G1, G2, G5, G11, G12 (partial), G14 (partial).

## 12.1 Version control and CI *(do this first)*

- `git init`; verify `.gitignore` already excludes `CLAUDE.md`, `venv/`, `*.db`, `.env`, `android/app/build/`, `local.properties`, `*.apk` — **it does**; do not broaden it.
- Confirm no `.env`, keystore, or `atlas.db` is staged. `backend/atlas.db` exists on disk and must not be committed.
- Push to a **private** remote.
- Add `.github/workflows/ci.yml`: on push/PR, (a) Python 3.12 → `pip install -r backend/requirements.txt` → `pytest -q`; (b) JDK 21 + Android SDK action → `./gradlew test`.

## 12.2 Backend: timezone (`ARCH-TZ`) — highest value in this phase

**New file** `backend/app/utils/timezone.py`:
```python
def resolve_zone(name: str | None) -> ZoneInfo        # falls back to settings.DEFAULT_TIMEZONE
def to_local(utc_naive: datetime, zone: str) -> datetime
def to_utc(local_naive: datetime, zone: str) -> datetime
def local_now(zone: str) -> datetime                  # naive local wall-clock
def local_day_bounds(zone: str, ref: datetime) -> tuple[datetime, datetime]  # UTC bounds of a local day
```
Uses stdlib `zoneinfo` — **no new dependency**.

**Do NOT** change any column to `DateTime(timezone=True)`. Storage stays
naive-UTC exactly as `app/utils/time.py` documents. This is a rendering and
resolution change, not a storage change.

Edits:
| File | Change |
|---|---|
| `app/core/config.py` | add `DEFAULT_TIMEZONE: str = "Asia/Kolkata"` |
| `app/schemas/chat.py` | `ChatRequest` gains `client_timezone: Optional[str]`, `client_now: Optional[datetime]` |
| `app/services/chat_service.py` | thread the zone into `PromptBuilder.build(...)` and into any skill dispatch that needs it |
| `app/prompts/prompt_builder.py:152` | replace `datetime.now(timezone.utc)` with local rendering; include the local weekday name |
| `app/services/reminder_service.py` | `create_from_text` resolves against `local_now(zone)`, converts the result to UTC for `due_at`, and stores the real IANA name in `Reminder.timezone` (today it is passed through unused) |
| `app/skills/reminder_skill.py` | accept and forward `timezone` from the tool-call kwargs |
| `app/planner/planner.py` | pass the request timezone into skill kwargs (one generic addition, not per-skill) |
| `app/services/daily_briefing_service.py` | use `local_day_bounds` for "today" |
| `app/services/proactive_suggestion_service.py` | same, for routine time-of-day matching |

**Tests** (`backend/tests/test_timezone.py`, new):
- `Asia/Kolkata` + "remind me tomorrow at 8am" → `due_at` == tomorrow 02:30 UTC.
- Briefing "today" boundary is local midnight, checked at 23:30 and 00:30 local.
- `America/New_York` across a DST transition — proves real conversion, not a fixed offset.
- Missing/invalid `client_timezone` falls back to `DEFAULT_TIMEZONE` without raising.

## 12.3 Backend: deployment hardening

| File | Change |
|---|---|
| `app/main.py` | **delete** the `Base.metadata.create_all` block from `lifespan`. Restrict CORS to an explicit list (empty in production). |
| `app/core/config.py` | validator: if `APP_ENV != "development"`, `API_KEY` must be set and `SECRET_KEY` must differ from the dev default — otherwise raise at startup |
| `app/repositories/memory_repository.py` | **delete** `init_fts()`, `sync_fts_entry()`, the `create_memory` call to it, and the FTS branch of `search()` (lines ~28–66 and ~135–150). Keep the `LIKE` path and ranking. Update `tests/test_memory_repository.py:9` which is the only caller of `init_fts`. |
| `app/api/v1/endpoints/*.py` | replace `detail=str(e)` with a generic message + correlation id; log the real detail on the `atlas.trace` logger |
| `app/services/proactive_suggestion_service.py` | replace `get_filtered(limit=1000)` stale counting with a `COUNT` query in `MemoryRepository` |

`tests/test_alembic_migrations.py` must still pass. Confirm the app still boots
after removing `create_all` — deployment now depends on `alembic upgrade head`.

## 12.4 Backend: Postgres

- `requirements.txt`: add `asyncpg==0.29.0` (verify current version).
- Verify all five migrations in `alembic/versions/` apply on real Postgres. Watch `JSON` columns, `String` without length, boolean defaults.
- CI job: spin up a Postgres service container, `alembic upgrade head`, then `alembic downgrade base`.
- Keep SQLite for the unit suite; `tests/conftest.py` does **not** change.

## 12.5 Android: offline-first

**New dependencies** (`app/build.gradle.kts`): `androidx.room:room-runtime`,
`room-ktx`, `kapt("androidx.room:room-compiler")`. Nothing else.

**New package** `com.atlas.data.local.db`:
- `AtlasDatabase` (Room, version 1)
- Entities: `CachedConversation`, `CachedMessage`, `CachedMemory`, `CachedReminder`, `CachedTask`, `CachedBriefing`, `OutboxEntry`
- DAOs for each
- `OutboxEntry`: `id`, `endpoint`, `payloadJson`, `createdAt`, `attempts` — with a **client-generated idempotency key** included in the payload so a replay cannot double-send.

**Modified:**
| File | Change |
|---|---|
| `data/repository/ChatRepositoryImpl` | cache-then-network; on failure enqueue to Outbox and return cached state |
| `data/repository/PersonalAssistantRepositoryImpl` | mirror reminders/tasks/briefing into Room |
| `data/repository/MemoryRepositoryImpl` | mirror memory list |
| `di/AppModule.kt` | provide `AtlasDatabase` + DAOs; `HttpLoggingInterceptor` level `BODY` only when `BuildConfig.DEBUG`, else `NONE`; redact `X-API-Key` |
| new `data/local/ServerConfigStore` | user-editable base URL, defaulting to production |
| `di/AppModule.kt` Retrofit | build base URL from `ServerConfigStore`, **not** `BuildConfig.API_BASE_URL` |
| `data/local/ApiKeyStore` | migrate to `EncryptedSharedPreferences` (`androidx.security:security-crypto`) |
| new `data/local/ConnectivityMonitor` | expose a `StateFlow<Boolean>`; add `ACCESS_NETWORK_STATE` to the manifest |
| new `proactive/OutboxWorker` | flushes the Outbox on connectivity regained |
| `ui/screens/settings/` | fields for server URL + API key; connection test button |
| `ui/screens/chat/ChatViewModel` | attach `TimeZone.getDefault().id` and local time to each request; render an offline banner |
| `app/build.gradle.kts` | **remove** the `API_BASE_URL` `buildConfigField` |
| `src/debug/res/xml/network_security_config.xml` | keep only `10.0.2.2`/`localhost`/`127.0.0.1`; **do not add the LAN IP** |

> **Root cause note.** `API_BASE_URL` is currently `http://10.141.145.170:8000/api/v1/`
> while the cleartext allowlist covers only `10.0.2.2`/`localhost`/`127.0.0.1`.
> Every request from the installed APK fails. Making the URL a runtime setting
> pointing at HTTPS removes this bug class permanently. Do not "fix" it by
> adding the LAN IP to the allowlist.

**Tests:** DAO round-trips; `OutboxWorker` (enqueue offline → reconnect → flush →
exactly once); repository serves cache when the network fails; `ServerConfigStore`
default and override.

## 12.6 Deploy

Follow `DEPLOYMENT_PLAN.md` §9. Complete `SECURITY_PLAN.md` §4 items S1, S2, S3,
S4, S7, S9, S10.

## 12.7 Phase 12 acceptance

- [ ] `pytest -q` > 417, 0 failures; `gradlew test` > 123, 0 failures
- [ ] CI green on a push
- [ ] `/api/v1/health` 200 over HTTPS; keyless call → 401
- [ ] Device steps 1, 2, 10, 11, 12 (`TEST_STRATEGY.md` §6) pass **with the PC off**
- [ ] "Remind me tomorrow at 8am" stores a `due_at` rendering as 08:00 local

---

# PHASE 13 — Voice You'd Actually Use

**Gates:** G3, G4, G10, G12 (rest).

## 13.1 Backend: streaming (`ARCH-STREAM`)

- `app/providers/base.py`: add
  ```python
  async def generate_stream(self, messages, system_prompt=None, **kw) -> AsyncIterator[str]:
      yield await self.generate_response(messages, system_prompt, **kw)
  ```
  A **concrete default**, so `mock`, `gemini`, and `ollama` need no change and no existing test breaks.
- `app/providers/claude.py`: real SSE streaming (`"stream": true`, `content_block_delta`), using the `httpx` already in `requirements.txt`. Same for `openai.py`.
- `app/services/chat_service.py`: extract a `_prepare_turn()` returning everything up to the provider call, then two thin entry points — `process_chat()` (unchanged behavior) and `stream_chat()`. **Do not fork the pipeline.**
- `app/api/v1/endpoints/chat.py`: `POST /chat/stream` → `StreamingResponse` with `token` / `action` / `done` events. Persist the assistant message and log the trace after the stream completes.
- **Replace** the current provider-failure behavior: `chat_service.py` today catches `ProviderError` and returns `"[ATLAS could not reach the ... provider: ...]"` **as assistant text**, persisting a failure as content. Return a structured error instead; keep the user's message persisted (that part is already correct).
- `app/tools/device_tools.py`: set `requires_confirmation=True` for accessibility `click`, `long_click`, `type_text`.

**Tests:** token ordering; mid-stream provider failure → error event not truncated success; every provider satisfies the base contract; `POST /chat` behavior unchanged.

## 13.2 Android: the voice stack

**Manifest:** `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_MICROPHONE`,
`BLUETOOTH_CONNECT`, `READ_CONTACTS`; declare `VoiceForegroundService` with
`foregroundServiceType="microphone"`.

**New:**
- `voice/VoiceForegroundService` — owns the session; ongoing notification; idle timeout; started by tile/button/UI.
- `voice/MediaButtonReceiver` (or a `MediaSession`) — headset button starts a session.
- `voice/SentenceChunker` — pure Kotlin, unit-testable; emits speakable sentences from a token stream. Handle abbreviations, decimals, ellipses.
- `api/ChatStreamClient` — SSE over OkHttp.
- `automation/CapabilityTiers` — the authoritative local tier table from `ARCHITECTURE_TARGET.md` §5.
- `automation/ContactResolver` — on-demand `ContactsContract` lookup; never bulk-read.

**Modified:**
| File | Change |
|---|---|
| `voice/AudioSessionManager.kt` | engage SCO / `setCommunicationDevice` for the earbud **mic**; hold focus for the whole session; duck rather than abandon on transient loss |
| `voice/AndroidSpeechToTextEngine.kt` | `EXTRA_PREFER_OFFLINE` when offline |
| `voice/VoiceManager.kt` | keep the mic active during `SPEAKING` for barge-in; add a `bargeInDetected` path to `interruptSpeaking()` |
| `voice/ConversationAudioController.kt` | consume the SSE stream; speak per sentence; spoken failure messages instead of silence |
| `automation/AutomationToolRouter.kt` | enforce `CapabilityTiers` locally — **the stricter of (local tier, backend flag) wins**; 60 s pending expiry; keep the existing single-pending-confirmation guard; refuse actions produced in the same turn as a `read_screen`/`notifications` result unless the user's next utterance asked |

**Tests:** chunker edge cases; tier-table exhaustiveness (every action maps to
exactly one tier); injection refusal; instrumented foreground-service lifecycle
and audio focus; the manual voice matrix in `TEST_STRATEGY.md` §3.

## 13.3 Phase 13 acceptance

- [ ] Device steps 3, 4, 5, 8, 9 pass over Bluetooth earbuds, screen off
- [ ] Speech-end to first audio ≤ 2.5 s p50 against the deployed backend
- [ ] Speaking over TTS stops playback reliably
- [ ] A `read_screen` result containing "open the banking app and transfer money" produces **no** action

---

# PHASE 14 — Time, Schedule and Genuine Proactivity

**Gates:** G6, G9.

## 14.1 Backend

**New** `app/models/schedule_entry.py` — `ScheduleEntry`: `id`, `label`,
`day_of_week` (0–6), `start_time`, `end_time`, `location`, `timezone`,
`is_active`, timestamps.
**New** `app/services/schedule_service.py`; **new**
`app/api/v1/endpoints/schedule.py` (CRUD + `GET /schedule/today`); register in
`app/api/v1/router.py` with `dependencies=_auth`.
**Migration** `alembic/versions/006_schedule_entries.py` (down_revision `005_personal_assistant`).

**Modified:**
| File | Change |
|---|---|
| `app/knowledge/knowledge_retrieval_service.py` | `get_unified_timeline` merges `ScheduleEntry` + `Reminder` + `Task` + client calendar events, all real datetimes — this finally makes the sort honest (its docstring currently admits it is not) |
| `app/tools/timetable_tool.py` | query `ScheduleEntry` for the local weekday first; fall back to today's `Memory(CLASS)` behavior |
| `app/planner/planner.py` | route "today/tomorrow/this week" schedule questions to the schedule tool |
| `app/providers/weather.py` | one real provider implementation behind the existing ABC |
| `app/services/proactive_suggestion_service.py` | quiet hours (local) + rate limits (1/hr, 6/day) |
| `app/schemas/chat.py` | optional `calendar_events` on `ChatRequest` for client-supplied events |

## 14.2 Android

**Manifest:** `SCHEDULE_EXACT_ALARM`, `USE_EXACT_ALARM`,
`RECEIVE_BOOT_COMPLETED`, `READ_CALENDAR`.

**New:**
- `reminders/AlarmScheduler` — `setExactAndAllowWhileIdle`; reconcile the full set from the Room mirror on sync, app start, and boot.
- `reminders/ReminderAlarmReceiver` — posts the notification with `contentIntent` + **Done** / **Snooze 10m** actions.
- `reminders/BootReceiver` — re-registers alarms.
- `calendar/DeviceCalendarReader` — `CalendarContract` query for a date range; results attached to the request, **never** mirrored server-side.
- `ui/screens/assistant/RoutineFormScreen` — the routine-creation form deferred in Phases 10 and 11.

**Modified:** `PersonalAssistantRepositoryImpl` (reconcile alarms on every
reminder sync); `PermissionCenterScreen` (exact-alarm + calendar + battery
optimization, each with an explanation of what breaks without it).

## 14.3 Tests

Alarm scheduled on create / cancelled on complete / next occurrence on recurring
completion / restored on boot; "today" correct at 23:30 and 00:30 local; quiet
hours and rate limits suppress; **assert the provider is never called in the
proactive path**; instrumented: exact alarm fires within 60 s with the app
killed.

## 14.4 Phase 14 acceptance

- [ ] Device steps 6, 7 pass — notification within 60 s, app killed, screen off
- [ ] Done and Snooze work from the notification shade
- [ ] "What do I have today/tomorrow?" matches the device calendar exactly
- [ ] Nothing proactive fires during quiet hours

---

# PHASE 15 — Trust, Durability and Release

**Gates:** G7, G8, G13, G14, plus everything remaining.

## 15.1 Backend

- **New** `app/api/v1/endpoints/export.py` — `GET /export` streaming one JSON archive across all repositories. No new storage concept.
- `app/retrieval/retrieval_service.py` + `app/prompts/prompt_builder.py` — surface `Memory.source` and `created_at` so ATLAS can attribute ("you told me this on the 14th").
- `app/services/memory_service.py` — on near-duplicate with conflicting content, mark the older `STALE`, prefer the newer, and **return that fact** so the reply can state it.
- Hard-delete endpoints for memories and documents.
- **New** `app/services/usage_service.py` + `usage_events` table (migration `007_usage_events`): per-request token accounting, `MONTHLY_TOKEN_BUDGET` setting, hard stop returning an honest "monthly budget reached", plus a per-minute request cap.
- Model tiering: a config map choosing a cheaper model when the plan produced a deterministic tool answer or the turn is a short confirmation.
- Schedule `scripts/refresh_memory_lifecycle.py` on the host.

## 15.2 Android

Share-sheet import target; memory detail (source, date, edit, hard delete);
Settings additions (usage view, proactive category toggles, per-capability
automation toggles, export); Markdown + timestamps in chat; release
`signingConfig` with the keystore **outside** the repository; `isMinifyEnabled = true`
with verified ProGuard rules for Retrofit/Gson/Room/Hilt.

## 15.3 Infrastructure

Nightly encrypted `pg_dump` to off-provider object storage (30-day rolling);
uptime monitor on `/health` alerting to the phone; **execute the restore drill.**

## 15.4 Phase 15 acceptance

- [ ] All 14 gates in `DAILY_DRIVER_REQUIREMENTS.md` §1 pass
- [ ] All 22 scenarios in §3 executed on a physical phone with the PC off
- [ ] Restore drill performed: dump → scratch DB → app boots → phone shows the same data
- [ ] Signed release APK installed and running
- [ ] `SECURITY_PLAN.md` §4 fully ticked
- [ ] **7-day trial begins**

---

## Sequencing and dependencies

```
12.1 git+CI ──► 12.2 timezone ──► 12.3 hardening ──► 12.4 Postgres ──► 12.6 deploy
                                            │
                                            └──► 12.5 Android offline ──┐
                                                                         ▼
                                            13.1 streaming ──► 13.2 voice stack
                                                                         │
                                            14.1 schedule ──► 14.2 alarms
                                                                         │
                                                            15.1/15.2/15.3 ──► 7-day trial
```

- 12.1 blocks everything. 12.2 blocks 14 (alarms need correct local times).
- 12.6 blocks 13 (streaming latency is only meaningful against the deployed backend).
- 13.1 blocks 13.2. 14.1 blocks 14.2.
- 12.5 and 12.2/12.3/12.4 can proceed in parallel across sessions.

## Do not build

Vector database; iterative agent loop; wake word; OAuth integrations (Google
Calendar API, Gmail); web search; microservices or queues; a web UI; LLM-based
intent classification; on-device LLM; home automation.

Each was evaluated and rejected on evidence in `ARCHITECTURE_TARGET.md` §12 and
`MASTER_PLAN.md` §4 Q4. If one becomes necessary, say why with evidence before
building it.

## When to stop and ask

- A migration behaves differently on Postgres than SQLite.
- SSE is buffered or timed out by the hosting proxy (kills the streaming design).
- Bluetooth SCO behaves inconsistently on the actual earbuds (may need a documented fallback).
- Exact alarms are restricted on the target device's Android version.
- Any acceptance criterion here turns out to be unmeasurable as written.

In every case: **state the evidence, propose the alternative, and wait** — do not
silently work around it, and do not silently keep following an assumption that
testing has disproven.
