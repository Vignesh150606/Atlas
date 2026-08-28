# ATLAS — Master Plan

Architecture session, 2026-08-28. Opus 5 acting as principal architect.
**No production code was written during this task.**

This document is the audit and the strategic conclusions. The companion
documents are `ARCHITECTURE_TARGET.md`, `DEPLOYMENT_PLAN.md`,
`DAILY_DRIVER_REQUIREMENTS.md`, `SECURITY_PLAN.md`, `TEST_STRATEGY.md`,
`FINAL_ROADMAP.md`, and `SONNET_IMPLEMENTATION_PLAN.md`.

---

## 1. What was actually verified in this session

Everything in §2 was checked against source, not against prior phase reports.
Two things were executed, not read:

| Check | Command | Real result |
|---|---|---|
| Backend suite | `venv/Scripts/python.exe -m pytest -q` | **417 passed**, ~40 s |
| Android unit tests | `.\gradlew.bat test` (PowerShell) | **BUILD SUCCESSFUL, 123 tests, 0 failures** across 12 classes |
| Android build | `.\gradlew.bat assembleDebug` | **BUILD SUCCESSFUL** |

The claim repeated throughout `CLAUDE.md` and every phase report that Android
cannot be compiled in this environment **is no longer true on this machine**
(JDK 21 + Android SDK + cached Gradle 8.5 are all present). That has been
corrected in `CLAUDE.md`. It was accurate history for the sandboxes phases 8–11
ran in; it is not a current constraint.

What is still unverified by anyone: **runtime behavior on a device.** No
`connectedAndroidTest` has ever run. A green `assembleDebug` proves compilation,
nothing more — and §2.1 below is the concrete proof that this distinction is not
academic.

---

## 2. Audit findings

### 2.1 BLOCKER — the app cannot reach the backend from a physical phone

`android/app/build.gradle.kts:34`:

```
buildConfigField("String", "API_BASE_URL", "\"http://10.141.145.170:8000/api/v1/\"")
```

`android/app/src/debug/res/xml/network_security_config.xml` permits cleartext to
exactly three hosts: `10.0.2.2`, `localhost`, `127.0.0.1`. `10.141.145.170` is
not among them, and `src/main/AndroidManifest.xml` declares no
`networkSecurityConfig` at all, so the platform default (cleartext blocked since
targetSdk 28) applies to that host.

**Every Retrofit call from the installed APK fails** with
`CLEARTEXT communication to 10.141.145.170 not permitted by network security policy`.

This is precisely the bug `docs/Phase8_Report.md` proudly documents fixing — it
regressed the moment the base URL was pointed at a LAN IP without the allowlist
being updated. The APK installing successfully on a phone is fully consistent
with it never having worked. Nothing in the 123 Kotlin unit tests could catch
this; it is a manifest-merge and runtime-policy interaction.

Also note the URL is a **DHCP-assigned laptop address**. Even with cleartext
allowed, it breaks when the router reassigns, when the phone is on mobile data,
and when the PC is off — i.e. it violates the phone-first requirement by
construction.

### 2.2 BLOCKER — the entire system is UTC-only

`app/utils/time.py::utc_now()` returns naive UTC. Every `DateTime` column is
timezone-naive. `PromptBuilder` (line 152) injects `datetime.now(timezone.utc)`
as "now" into the prompt. `ReminderService.create_from_text` defaults
`reference_time` to `utc_now()` and `timezone` to `"UTC"`. `Reminder.timezone`
exists as a column but is **stored verbatim and never used for conversion** —
grep confirms exactly one caller passes it (`app/api/v1/endpoints/reminders.py:29`),
and nothing reads it back for arithmetic.

For a user in IST (UTC+05:30) this means:
- "remind me at 8am" resolves to 08:00 UTC = **13:30 local**.
- "what do I have today" asks about the wrong day for 5.5 hours out of every 24.
- The daily briefing's "today" boundary is wrong by 5.5 hours, every day.

`app/utils/time.py`'s own docstring correctly identifies this as deferred work.
It can no longer be deferred; it is load-bearing for six of the 22 daily-driver
scenarios.

### 2.3 BLOCKER — reminders are polled, not scheduled

`ProactiveSuggestionsScheduler` enqueues a **30-minute periodic** WorkManager job.
`ProactiveSuggestionService` computes "due within 30 minutes" server-side. There
is no `AlarmManager` usage anywhere in the codebase (verified by grep).

Consequences: a 15:00 reminder surfaces somewhere in 15:00–15:29; WorkManager
periodic work is subject to Doze batching and can slip much further; and the
notification carries no `contentIntent` and no actions, so tapping it does
nothing and there is no way to complete or snooze from the shade.

A reminder system that is late by an unbounded amount is not a reminder system.

### 2.4 Silent-failure defects (real, currently masked)

| Location | Problem |
|---|---|
| `app/repositories/memory_repository.py:28-66` | `init_fts()` creates the `memories_fts` FTS5 table but is **called only from a test** (`tests/test_memory_repository.py:9`). In production the table never exists, so `sync_fts_entry` fails on every memory write and `search()` falls through to `LIKE` — all three paths wrapped in bare `except Exception: pass`. A documented feature that has never run in production and cannot report that it isn't running. |
| `app/repositories/memory_repository.py:141` | The FTS query is also SQLite-specific raw SQL. On Postgres it will fail permanently and silently. This must be resolved *before* any database migration, not after. |
| `app/services/chat_service.py` | Provider failure is caught and turned into a `[ATLAS could not reach the ...]` string in the assistant's own voice, persisted as a real assistant message. The failure becomes indistinguishable from content in later turns. |
| `android/.../di/AppModule.kt` | `HttpLoggingInterceptor.Level.BODY` is applied unconditionally, including release builds — full chat bodies and the `X-API-Key` header go to Logcat. |

### 2.5 Architectural gaps against the daily-driver bar

| Gap | Evidence | Impact |
|---|---|---|
| **No local persistence on Android** | Every repository in `data/repository/` is a pure Retrofit pass-through; `data/local/` holds only `ApiKeyStore` and `ProactiveSuggestionTracker`, both SharedPreferences | Offline = a blank app. No cached history, reminders, or briefing. |
| **No streaming anywhere** | `LLMProvider.generate_response` returns `str`; the chat endpoint is a plain `POST` returning JSON | Voice latency is full-generation latency. Nothing can start speaking early. |
| **No foreground service** | No `FOREGROUND_SERVICE` permission, no `Service` beyond the two system-bound ones | Voice dies when the screen turns off. Earbud-in-pocket use is impossible. |
| **Bluetooth mic never engaged** | `AndroidAudioSessionManager` only *reports* the output route; no `startBluetoothSco()` / `setCommunicationDevice()` | Earbud playback works; the earbud **microphone** does not get used. |
| **No barge-in in practice** | `interruptSpeaking()` exists but the mic is not listening during TTS | The documented "barge-in" is a manual button, not voice. |
| **Timetable is free text** | `TimetableTool`'s own docstring: schedule is stored as free text like "9am on Mondays"; no day/time structure | "What classes do I have today?" is an LLM guess over unstructured strings. Roadmap already admits `get_unified_timeline` only sorts document-sourced items correctly. |
| **No calendar integration** | Nothing reads `CalendarContract`; `Memory(EVENT)` holds unparsed strings | The single highest-value personal-data source on the phone is untouched. |
| **No version control** | `git status` → *not a git repository*. `.gitignore` exists but there is no `.git` | Zero history, zero rollback, zero off-machine copy of the source. This is the largest non-technical risk in the project. |
| **No CI** | No `.github/` | Nothing enforces the 417+123 tests before a change lands. |
| **No release signing** | `build.gradle.kts` release block has no `signingConfig`, `isMinifyEnabled = false` | No installable release build exists; only debug. |
| **CORS wide open** | `allow_origins=["*"]` with `allow_credentials=True` in `app/main.py` | Invalid combination per spec, and wrong for a deployed API. |
| **API key optional by default** | `verify_api_key` no-ops when `API_KEY` is unset | Correct as a migration default; unacceptable once public. Must become mandatory when `APP_ENV != development`. |
| **`create_all` at startup** | `app/main.py` lifespan calls `Base.metadata.create_all` alongside a real Alembic history | Two schema sources of truth. In cloud deployment this must be removed in favour of `alembic upgrade head`. |

### 2.6 What is genuinely good and must not be rewritten

Naming these explicitly so the implementation phase does not "improve" them:

- **The deterministic cognitive layer.** Intent → Planner → ToolRouter → PromptBuilder is readable, explainable, and heavily tested. Do not replace it with an LLM router.
- **The Skill system.** `Skill` extends `Tool`, `match()` lives on the skill, and the Planner has exactly one generic hook. Adding a skill costs zero planner edits. This design is correct.
- **`app/nlp/datetime_parser.py`.** 356 lines, 28 tests, handles relative dates, weekday names, "in N units", am/pm, and five recurrence types with span tracking. This is the hard part of reminders and it is already done well.
- **The provider abstraction.** ABC + factory + honest `UnconfiguredWeatherProvider`. Extending it with streaming is additive.
- **`RequestTrace` redaction.** Logs counts and ids, never content. Preserve this property.
- **Confirmation plumbing.** `requires_confirmation` flows backend → DTO → both text and voice UI with a shared dialog. The model is right; it just needs more actions classified and client-side enforcement.
- **The test discipline.** Real DB, real MockProvider, no internal mocking.

---

## 3. Product answer: what "daily driver" requires

Defined in full in `DAILY_DRIVER_REQUIREMENTS.md`. Summary: 14 binary gates, 22
acceptance scenarios, and one framing rule — *it only counts with the PC off.*

---

## 4. The twelve questions, answered

### 1. How far is ATLAS from the Daily Driver goal?

**0 of 14 gates pass today.** But the distance is smaller than that implies:
the backend cognition is ~70% of what is needed; the deployed phone product is
~15%. Realistically **4 phases / 6–9 focused working weeks** for one developer,
of which the first phase alone moves it from "cannot function" to "usable but
rough". The dominant costs are deployment, timezone correctness, on-device
scheduling, and offline caching — all well-understood engineering, none of it
research.

### 2. Top 10 missing pieces

1. **A reachable, always-on, HTTPS backend** — plus removal of the hardcoded LAN IP and the cleartext block. Nothing else matters until this is true.
2. **Timezone correctness end-to-end** — client sends its IANA zone and local time; server stores UTC and renders local.
3. **Exact-time reminder delivery on-device** (`AlarmManager` + notification actions), replacing 30-minute polling.
4. **Local persistence + offline cache on Android** (Room), plus an outbound queue.
5. **Response streaming** (SSE backend → incremental TTS), the single biggest voice-latency win.
6. **A voice foreground service + Bluetooth SCO**, so earbud sessions work with the screen off.
7. **Structured schedule data** — a real timetable/calendar source instead of free-text `Memory(CLASS)` rows; read the device calendar.
8. **Production security posture** — mandatory API key, TLS, encrypted key storage, no BODY logging in release, tightened CORS.
9. **Backups and export** — nightly off-host DB backup plus a user-triggered export.
10. **Version control and CI** — the project is not in git and has no CI. Everything above is riskier without it.

### 3. What should be built next?

Phase 12 (`FINAL_ROADMAP.md`): git + CI, cloud deployment, timezone, offline
cache, and the security baseline. It converts ATLAS from "an architecture" into
"a thing that runs". Every later phase depends on it.

### 4. What should NOT be built?

- **A vector database / embedding retrieval.** No evidence justifies it at single-user scale (low thousands of rows) when deterministic ranking already works. Trigger condition for revisiting is stated in `ARCHITECTURE_TARGET.md` §6.4 — build it only if that measurement fails.
- **An iterative agent loop.** Deferred since Phase 8 and still correct to defer. It multiplies latency, cost, and failure modes; the one-shot planner covers all 22 scenarios.
- **A wake word.** Battery, false-positive, and dependency cost far exceed the value of not pressing a button. The headset button plus a quick-settings tile solves the same problem for free.
- **Microservices, message queues, Kubernetes, a second datastore.** One container, one database, one user.
- **Gmail / Google Calendar OAuth integration.** The phone's own `CalendarContract` and `ContactsContract` give ~80% of the value for ~5% of the effort and none of the OAuth verification burden or cloud privacy exposure.
- **Home automation, multi-tenancy, a web UI, LLM-based intent classification, custom TTS voices.**
- **Porting the dead FTS5 code.** Delete it (§2.4); `semantic_match` + `LIKE` is sufficient and honest.

### 5. Local, cloud, or hybrid backend?

**Cloud**, with a small deliberate hybrid edge. The phone-first requirement is
explicit and non-negotiable, and a PC-hosted backend fails it outright. Full
reasoning and the rejected alternatives are in `DEPLOYMENT_PLAN.md` §2.

The hybrid part is narrow and intentional: **scheduling and speech stay on the
device** (alarms fire locally; STT/TTS are on-device Android engines), so the
two most latency- and availability-sensitive paths do not depend on the network.
Everything cognitive is cloud.

### 6. Is Render appropriate, and what alternatives?

Render is **appropriate but not optimal for this user**, and its free tier is
actively harmful here — free web services idle out and cold-start, which is
fatal for a voice assistant where the first request of the day would pay a
multi-tens-of-seconds penalty.

Recommended: **Fly.io, deployed to the Mumbai (`bom`) region**, because this
developer is in IST and region proximity is the single largest fixed latency
term in a voice turn. Render's nearest region is Singapore.

Ranked alternatives, with what must be checked before committing, are in
`DEPLOYMENT_PLAN.md` §3. **All pricing and free-tier claims in that document are
marked as requiring verification at deploy time** — provider pricing, regions,
and free-tier rules change frequently and none of it should be trusted from this
document alone.

### 7. How should the database be hosted?

**Managed PostgreSQL from the same provider and region as the app**, reached
over the internal network. Rationale, and the honest counter-argument for
SQLite-on-a-volume, are in `DEPLOYMENT_PLAN.md` §4. The decisive factor is
backups: a managed Postgres gives automated, restorable, off-instance backups
without the developer building that themselves, and G13 is a daily-driver gate.

Pre-migration blocker: the SQLite-only FTS5 raw SQL in `MemoryRepository` must be
deleted first (§2.4), and `create_all`-at-startup must be replaced by
`alembic upgrade head`.

### 8. How should memories/documents be backed up?

Three layers, described fully in `DEPLOYMENT_PLAN.md` §6:
1. **Provider-managed automated Postgres backups** (retention verified at setup).
2. **A nightly `pg_dump` to off-provider object storage**, encrypted, so a provider-account loss is survivable.
3. **A user-triggered export endpoint** producing one portable archive (memories, documents, reminders, tasks, routines, conversations) that the phone can save anywhere.

Uploaded document *files* need object storage or a volume; today they are parsed
into the DB, so confirm whether originals are retained before designing this.
**A backup that has never been restored is not a backup** — restoring into a
scratch database is an explicit acceptance criterion in Phase 15.

### 9. How should voice work when the internet is unavailable?

Three tiers, and the honest answer is that tier 3 is unreachable:
- **Tier 1 — capture always works.** STT and TTS are already on-device Android engines. Add `EXTRA_PREFER_OFFLINE` when the network is down, keep the foreground service running, and the microphone still works.
- **Tier 2 — offline answers from cache.** Reminders, tasks, today's briefing, conversation history, and memory list all served from the Room cache, spoken locally, clearly marked as cached. Utterances that need reasoning go into the outbound queue and are answered when connectivity returns.
- **Tier 3 — offline reasoning: not in scope.** A local LLM on the phone is not viable for this app's latency and battery budget. `OllamaProvider` already exists for a *self-hosted* fallback, which is a different thing and only helps when the phone can reach that host.

The rule: **ATLAS must always be able to hear you and always tell you the truth
about what it can do right now.** Silence is the failure mode to eliminate.

### 10. How many remaining phases are necessary?

**Four.** Phase 12 (Make It Real), Phase 13 (Voice You'd Actually Use), Phase 14
(Time, Schedule and Genuine Proactivity), Phase 15 (Trust, Durability and
Release). See `FINAL_ROADMAP.md`. Anything beyond these is post-daily-driver
backlog, not a phase.

### 11. Exact definition of "ATLAS is ready for daily use"

> All 14 gates in `DAILY_DRIVER_REQUIREMENTS.md` §1 pass, and all 22 scenarios in
> §3 have been executed successfully on a physical phone, over Bluetooth earbuds,
> on mobile data, with the development PC powered off — and the developer has
> then used ATLAS as their only assistant for **7 consecutive days without
> touching the backend or rebuilding the app.**

The 7-day clause is the whole definition. Everything else is a proxy for it.

### 12. Final Sonnet 5 implementation plan

`docs/SONNET_IMPLEMENTATION_PLAN.md`.

---

## 5. Standing instructions for the implementation sessions

1. **Get it into git before anything else.** One commit per phase step.
2. **Run both suites before reporting anything.** `pytest -q` (backend) and `.\gradlew.bat test` (PowerShell). Report real numbers. The Android toolchain works on this machine now — "cross-referenced only" is no longer acceptable for Kotlin.
3. **Do not redesign.** The architecture decisions are made in `ARCHITECTURE_TARGET.md`. If evidence contradicts one, stop and flag it with the evidence rather than quietly diverging — the same rule this project has followed since Phase 8, and it has caught real bugs.
4. **Prefer deleting to adding.** Two of the highest-value changes in this plan (dead FTS5, `create_all` at startup) are deletions.
5. **Nothing counts until it runs on the phone.** Every phase ends with a device check, not a green build.
