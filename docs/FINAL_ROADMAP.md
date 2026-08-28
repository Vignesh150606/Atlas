# ATLAS — Final Roadmap

Architecture session, 2026-08-28. **This replaces the remaining unchecked items
in `docs/Roadmap.md` as the forward plan.** `Roadmap.md` stays as the historical
record of phases 1–11; it should not be used to decide what to build next.

Four phases. Each ends with a **device check with the development PC powered
off** — that is what makes a phase complete, not a green build.

---

## Phase 12 — Make It Real

> *Objective: ATLAS runs in the cloud, tells the correct time, and does not
> become useless when the network drops.*

**User-visible outcome:** The developer installs the app, enters a server URL and
key once, and it works — from anywhere, on mobile data, with the PC off. Times
and dates are correct. With no signal, yesterday's conversation and today's
reminders are still readable.

**Backend**
- `ARCH-TZ`: `client_timezone` / `client_now` on `ChatRequest`; `app/utils/timezone.py`; `PromptBuilder` renders local time and weekday; `ReminderService` resolves against local reference time and stores UTC + IANA zone; `DEFAULT_TIMEZONE` setting.
- Remove `Base.metadata.create_all` from the lifespan.
- Delete the dead FTS5 code in `MemoryRepository`.
- `API_KEY` and `SECRET_KEY` mandatory when `APP_ENV != development`.
- CORS restricted; generic error responses with a correlation id.
- Replace `ProactiveSuggestionService`'s `get_filtered(limit=1000)` stale count with a `COUNT` query.

**Android**
- Room database: cached conversations/messages, memories, reminders, tasks, last briefing.
- `Outbox` table + worker for queued writes; exactly-once flush on reconnect.
- Repositories become offline-first (cache-then-network).
- Server URL becomes a runtime **Setting**, not `buildConfigField`. Default: the production hostname.
- `EncryptedSharedPreferences` for the API key; `Level.NONE` HTTP logging in release.
- Connectivity awareness (`ACCESS_NETWORK_STATE`) and an honest offline banner.
- Send the device's IANA timezone with every chat request.

**Infrastructure**
- **Put the repo in git** and push to a private remote. *(It is currently not a git repository at all.)*
- GitHub Actions: `pytest -q` + `gradlew test` on push.
- Provision app + managed Postgres in the chosen region (`DEPLOYMENT_PLAN.md`).
- Deploy via `docker/backend.Dockerfile`; `alembic upgrade head` on release.

**Database:** SQLite → Postgres; verify all five migrations on Postgres; add `asyncpg`.

**Security:** `SECURITY_PLAN.md` items S1, S2, S3, S4, S7, S9, S10.

**Tests:** timezone suite (incl. a DST-crossing zone); Postgres migration test in CI; Room DAO + Outbox tests; offline-serves-cache test; deployed smoke script.

**Acceptance**
1. Device end-to-end steps 1, 2, 10, 11, 12 pass with the PC off.
2. `/health` responds over HTTPS; keyless request returns 401.
3. "Remind me tomorrow at 8am" stores a `due_at` that renders as 08:00 local.
4. Airplane mode: history and reminders still readable; a sent message queues and later delivers exactly once.
5. `pytest -q` count increased; `gradlew test` green.

**Dependencies:** none. **This phase gates every other phase.**

**Risks:** Postgres migration surprises (mitigate with the CI migration test *first*); Room introduces real complexity to the Android app (mitigate by caching read models only — no local write authority except the Outbox).

---

## Phase 13 — Voice You'd Actually Use

> *Objective: a real earbud conversation — screen off, low latency,
> interruptible, and safe.*

**User-visible outcome:** Press the headset button, ask something, hear the
answer start within about two seconds, interrupt it by talking, and never take
the phone out of a pocket.

**Backend**
- `ARCH-STREAM`: `LLMProvider.generate_stream()` with a non-breaking default; real streaming for Claude and OpenAI; `POST /chat/stream` (SSE) emitting `token` / `action` / `done`. `POST /chat` unchanged.
- Stop returning provider failures as assistant text; return a structured `provider_unavailable` error.
- Widen `requires_confirmation` to accessibility click / long-click / type-text.

**Android**
- `VoiceForegroundService` (`FOREGROUND_SERVICE_MICROPHONE`), ongoing notification, idle timeout.
- Bluetooth SCO / `setCommunicationDevice` so the **earbud microphone** is used.
- Media-button (`MediaSession`) start.
- SSE client; `SentenceChunker`; incremental TTS playback.
- Barge-in: mic active during SPEAKING; speech stops playback.
- Audio focus held for the session; duck rather than abandon on transient loss.
- `EXTRA_PREFER_OFFLINE` when the network is down; spoken failure messages, never silence.
- Capability tier table enforced in `AutomationToolRouter`; 60 s confirmation expiry.
- Prompt-injection boundary (refuse actions derived from read content).
- Contacts read-on-demand for "call Mom" → resolve, confirm aloud, then dial intent.

**Database:** none.

**Security:** S5, S6.

**Tests:** SSE ordering and mid-stream failure; chunker edge cases; tier table exhaustiveness; injection test; instrumented foreground-service and audio-focus tests; the manual voice matrix.

**Acceptance**
1. Device steps 3, 4, 5, 8, 9 pass over Bluetooth earbuds with the screen off.
2. Speech-end to first audio ≤ 2.5 s p50 on the deployed backend.
3. Speaking over TTS reliably stops playback.
4. Every USER-CONFIRMED action asks first, in both text and voice; a `read_screen` result containing an instruction produces no action.

**Dependencies:** Phase 12 (needs a deployed HTTPS backend for realistic latency).

**Risks:** SCO behavior varies significantly across earbuds and OEMs — test on the actual hardware early, and keep a "use phone mic" fallback. Some hosting proxies buffer or time out SSE — verify (`DEPLOYMENT_PLAN.md` §8 item 9) before building on it.

---

## Phase 14 — Time, Schedule and Genuine Proactivity

> *Objective: reminders that fire on time and a schedule ATLAS actually knows.*

**User-visible outcome:** "Remind me at 3" produces a notification at 3:00 with
Done and Snooze buttons. "What do I have today?" is correct, ordered, and drawn
from the real calendar.

**Backend**
- `ScheduleEntry` model + service (day-of-week, start, end, location, label), reusing `datetime_parser`.
- `get_unified_timeline` merges `ScheduleEntry` + `Reminder` + `Task` + client-supplied calendar events, all with real datetimes — making the chronological sort honest for the first time.
- Briefing composed against **local** day boundaries.
- A real `WeatherProvider` implementation behind the existing ABC.
- Quiet hours + rate limits in `ProactiveSuggestionService`.

**Android**
- `AlarmScheduler` using `AlarmManager` exact alarms; reconcile on sync, on app start, and on `BOOT_COMPLETED`.
- Reminder notifications with `contentIntent` + Done / Snooze 10m actions.
- `SCHEDULE_EXACT_ALARM` / `USE_EXACT_ALARM` permission flow in the Permission Center, with an explanation.
- Device calendar read (`READ_CALENDAR`), surfaced to the backend per request — never mirrored.
- Routine-creation form (deferred twice already, in Phases 10 and 11).

**Database:** migration `006_schedule_entries`.

**Security:** calendar read permission explained and revocable; quiet hours honoured.

**Tests:** alarm scheduling/cancel/recurrence/boot-restore; local-weekday correctness at 23:30 and 00:30 local; quiet-hours and rate-limit suppression; **assert no LLM call occurs in the proactive path**; instrumented exact-alarm-fires test.

**Acceptance**
1. Device steps 6 and 7 pass: notification within 60 s of target, app killed, screen off.
2. Notification actions work from the shade.
3. Recurring reminder survives completion and reschedules.
4. "What do I have today/tomorrow?" matches the device calendar exactly.
5. Nothing proactive fires during quiet hours.

**Dependencies:** Phases 12 (timezone) and 13 (voice confirmation paths).

**Risks:** exact-alarm policy is increasingly restricted on newer Android versions — verify against the target device's OS version early; have the inexact fallback path defined, and tell the user when it is in effect rather than silently degrading.

---

## Phase 15 — Trust, Durability and Release

> *Objective: ATLAS is safe to depend on, and losing any single thing loses
> nothing.*

**User-visible outcome:** A signed release build. Data is backed up and
exportable. ATLAS can say *why* it believes something. Costs are bounded.

**Backend**
- `GET /export`: one portable JSON archive of everything.
- Memory attribution (`source` + `created_at`) surfaced in retrieval and prompt.
- Contradiction handling: newer explicit statement wins, older flagged `STALE`, and the conflict is **stated** rather than silently resolved.
- Hard-delete endpoint for memories and documents.
- `usage_events` + monthly token ceiling + per-minute rate limit.
- Model tiering (cheap model for deterministic/short turns).
- Scheduled `MemoryLifecycleService` run.

**Android**
- Share-sheet target for document import.
- Memory detail: source, date, edit, hard delete.
- Settings: cost/usage view, proactive category toggles, per-capability automation toggles, export.
- Markdown rendering + timestamps in chat (the last unchecked Phase 2 item).
- Release signing config; `isMinifyEnabled = true` with verified ProGuard rules.

**Database:** migration `007_usage_events`.

**Infrastructure:** nightly encrypted `pg_dump` off-provider; uptime monitor to the phone; **restore drill executed**.

**Security:** S8 (documented key rotation), S14 (signing); full `SECURITY_PLAN.md` §4 checklist.

**Tests:** export round-trip; restore drill; production config refuses to start without `API_KEY`; error responses carry no exception text; `RequestTrace` redaction extended; **the full 22-scenario device run**.

**Acceptance**
1. All 14 gates in `DAILY_DRIVER_REQUIREMENTS.md` §1 pass.
2. All 22 scenarios executed successfully on a physical phone with the PC off.
3. Restore drill performed: dump → scratch DB → app boots → phone shows the same data.
4. A signed release APK is installed and running on the phone.
5. **Then the 7-day trial begins.**

**Dependencies:** Phases 12–14.

**Risks:** the 7-day trial will surface things no test found. Reserve time after Phase 15 for fixes rather than declaring completion at the trial's start.

---

## After the daily driver (backlog, not phases)

Ordered by expected value, to be reconsidered only once the 7-day trial passes:

1. **Iterative agent loop** — the long-standing known gap. Genuinely valuable for chained device actions and on-screen target resolution. Correctly deferred since Phase 8 and still correctly deferred.
2. **Embedding retrieval via `pgvector`** — only if the recall@5 measurement in `ARCHITECTURE_TARGET.md` §6.4 fails.
3. Calendar **write**; calendar events as a dedicated model.
4. LLM-assisted date-parsing fallback (the seam already exists in `ReminderService`).
5. Wake word.
6. Web search.
7. Home automation.

---

## Why four phases and not fifteen

Each phase here is a coherent, shippable change in what the user can do, and each
ends in a state where ATLAS is strictly more useful than before. Splitting them
further would produce phases that complete without changing anything the
developer can actually do with their phone — which is precisely the failure mode
of the previous eleven: eleven phases of real, well-tested engineering that
produced an app which, on the day of this audit, could not send a single request
from the phone it was installed on.
