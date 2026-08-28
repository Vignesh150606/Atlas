# ATLAS — Deployment Plan

Architecture session, 2026-08-28.

> **Pricing warning, stated once and applying to this entire document.**
> Every cost figure below is an order-of-magnitude planning estimate, not a
> quote. Provider pricing, free-tier rules, regions, idle/spin-down policies,
> and backup retention all change frequently. **§8 lists exactly what must be
> checked on the provider's own pricing page before committing.** Do not treat
> any number here as current fact.

---

## 1. Requirements the deployment must satisfy

Derived from `DAILY_DRIVER_REQUIREMENTS.md`:

1. Reachable from mobile data and any Wi-Fi, with the development PC off. *(hard requirement, stated by the user)*
2. HTTPS with a valid certificate — the app must not ship with cleartext exceptions.
3. **No cold starts.** A voice assistant that pauses 30–60 s on the first request of the day is not usable. This single constraint eliminates most free tiers.
4. Durable database with automated, restorable backups.
5. Low round-trip latency from India (the developer is in IST).
6. Deployable and maintainable by one person, part-time.
7. Predictable monthly cost, low enough for a student.
8. Secrets held outside the repository.

---

## 2. Architecture options compared

### A. Backend on the development PC (+ tunnel)
| | |
|---|---|
| Cost | ~zero |
| Latency | Excellent on LAN; poor or broken elsewhere |
| Reliability | **Fails the primary requirement.** PC must be on, awake, and online |
| Notes | A tunnel (Cloudflare/ngrok) fixes reachability but not availability, and adds a rotating hostname unless paid |

**Rejected.** The user's requirement — "must not depend on my PC" — is explicit.
Useful for development only.

### B. Cloud-hosted FastAPI container + managed Postgres — **RECOMMENDED**
| | |
|---|---|
| Cost | One small always-on instance + managed DB. Order of magnitude USD 10–25/mo combined |
| Latency | Good if the region is chosen correctly (§3) |
| Reliability | Provider-managed restarts, health checks, TLS |
| Ops | Lowest. `Dockerfile` already exists in `docker/backend.Dockerfile` |

**Recommended.** Matches the current architecture almost exactly — a stateless
FastAPI app plus a database. No redesign required.

### C. Hybrid local + cloud
Two deployment targets, two configs, and a data-sync problem for a
single-user system. **Rejected as a *backend* topology.**

However, ATLAS is deliberately hybrid in a *narrow* sense already, and this is
correct: **alarms fire on the phone and speech is processed on the phone.** The
two most latency- and availability-critical paths never touch the network. That
is the right hybrid boundary — device/cloud, not local-server/cloud-server.

### D. Something more advanced (serverless, k8s, multi-region, queues)
Serverless is the interesting one and it still loses: cold starts violate
requirement 3, and long-lived SSE streams fit awkwardly into
request-response function runtimes. Kubernetes, multi-region, and message
brokers are unjustifiable for one user and one container.

**Rejected.** No evidence supports the complexity.

---

## 3. Provider evaluation

Region is the decisive factor. The developer is in India; a round trip to a US
region adds roughly 250–350 ms to *every* turn, which is a large fraction of the
2.3 s voice budget in `ARCHITECTURE_TARGET.md` §4.3. This alone reorders the
list.

| Provider | Nearest region to India | Always-on small tier | Managed Postgres | Verdict |
|---|---|---|---|---|
| **Fly.io** | **Mumbai (`bom`)** | Yes | Yes (Managed Postgres / Fly Postgres) | **Recommended.** Best latency; Docker-native; volumes available; scale-to-zero is opt-in so it can be left off |
| **Render** | Singapore | Yes (paid Starter; **free tier spins down**) | Yes | Strong second. Simplest UX, managed TLS, good docs. Loses on region and on a free tier that is unusable here |
| **Railway** | Southeast Asia | Yes (usage-based) | Yes | Viable. Usage-based billing is harder to cap predictably |
| **VPS (Hetzner / DigitalOcean / Oracle)** | Varies; some have Indian regions | Yes | Self-managed (or add managed DB) | Cheapest and zero cold starts, but you own OS patching, TLS renewal, backups, and monitoring. Good if the developer *wants* that; it is real ongoing work |
| **Google Cloud Run / AWS App Runner** | Mumbai available | Scale-to-zero by default | Cloud SQL / RDS (relatively expensive) | Cold starts unless min-instances is set, at which point the cost advantage disappears |

### Is Render appropriate?

**Yes, appropriate — but not the best fit here, and its free tier is a trap for
this use case.** Render is a perfectly reasonable choice: excellent developer
experience, native Docker deploys, automatic TLS, managed Postgres with backups.
Two reasons it is not the recommendation:

1. **Region.** Nearest is Singapore, versus Mumbai on Fly.io. For a voice-first product this is a real, felt difference.
2. **The free tier spins down when idle.** ATLAS is used in short bursts throughout the day — exactly the pattern that maximizes cold starts. The free tier must not be used, which erases the main reason people choose Render.

If the developer prefers Render's simplicity over ~100 ms of latency, that is a
defensible trade. **Use the paid tier either way.**

### Recommendation

> **Fly.io, Mumbai (`bom`) region, one always-on machine running the existing
> Docker image, plus managed Postgres in the same region.**
> Fall back to **Render (paid, Singapore)** if Fly's CLI-driven workflow proves
> frustrating. Consider a **VPS** only if cost becomes the binding constraint
> and the developer accepts the ops burden.

---

## 4. Database hosting

**Recommendation: managed PostgreSQL, same provider and region, private
networking.**

The honest counter-argument: SQLite on a mounted volume would work fine at this
scale, keeps the current stack, and makes backup a single file copy. It is not
wrong. It loses on one decisive point — **G13 (durability) is a daily-driver
gate**, and managed Postgres provides automated, off-instance, restorable
backups without the developer building and monitoring that themselves. A
single-file backup you wrote yourself and never restored is exactly the kind of
thing that fails when it matters.

### Migration prerequisites (must happen before the switch)

1. **Delete the SQLite-only FTS5 code** in `MemoryRepository` (`init_fts`, `sync_fts_entry`, and the FTS branch of `search()`). It is already dead in production — `init_fts` is called only from a test — and on Postgres it would fail permanently and silently inside its bare `except`. Keep the `LIKE` path plus the existing ranking layer.
2. **Remove `Base.metadata.create_all`** from the `app.main` lifespan. Deployment runs `alembic upgrade head`. Tests keep their own `create_all` in `conftest.py`.
3. **Verify the five existing migrations apply cleanly on Postgres.** They were authored against SQLite. Watch for: `JSON` column behavior, `String` without length, boolean defaults, and any implicit type coercion.
4. Add `asyncpg` to `requirements.txt`; `DATABASE_URL` becomes `postgresql+asyncpg://...`.
5. Keep SQLite as the test database — `conftest.py` should not change. This does mean the suite does not exercise Postgres; a single migration-smoke job against a real Postgres in CI closes that gap (see `TEST_STRATEGY.md`).

---

## 5. Secrets and configuration

| Secret | Where it lives |
|---|---|
| `CLAUDE_API_KEY` / other provider keys | Provider secret store (Fly secrets / Render env). Never in the image, never in git |
| `API_KEY` (shared client key) | Provider secret store; entered once on the phone into `EncryptedSharedPreferences` |
| `DATABASE_URL` | Injected by the provider |
| `SECRET_KEY` | Generated per environment; the current `"secret-key-for-development-only"` default must fail startup outside development |
| Backup encryption key | Off-provider secret manager or a password manager |

`API_BASE_URL` stops being a compile-time constant. It becomes a **user-editable
setting in the app**, defaulting to the production hostname — which removes the
class of bug found in the audit and lets the developer point at localhost for
testing without a rebuild.

---

## 6. Backups

Three layers. Layer 1 alone is not sufficient, because it fails to survive
provider-account loss.

1. **Provider-managed automated backups.** Enable at DB creation; verify retention period on the provider's page.
2. **Nightly `pg_dump`, encrypted, pushed off-provider** (e.g. Cloudflare R2 / Backblaze B2 / a private GitHub release asset). A ~30-line script on a scheduled job. 30-day rolling retention.
3. **User-triggered export** — `GET /api/v1/export` returns one JSON archive of memories, documents, reminders, tasks, routines, and conversations, savable from the phone. This is the layer that survives *everything*, including the developer abandoning the hosting provider.

**Restore drill is an explicit acceptance criterion**, not a nice-to-have: restore
last night's dump into a scratch database, run `alembic current`, boot the app
against it, and confirm the phone shows the same data. A backup that has never
been restored is not a backup.

Document originals: confirm during Phase 15 whether uploaded files are retained
at all today (the importer parses to text; originals may not be kept). If they
are retained, they need volume or object storage and their own backup line.

---

## 7. Monitoring and operations

Deliberately minimal — one user, one service:

- **Uptime:** an external HTTP monitor hitting `/api/v1/health` every 5 minutes, alerting to the phone. `/health` is already keyless and already reports DB status, so no new endpoint is needed.
- **Logs:** the provider's log stream. `RequestTrace` already emits one structured JSON line per chat turn with content redacted — that is genuinely good observability already and just needs to be somewhere queryable.
- **Errors:** a free-tier error tracker (e.g. Sentry) is optional and justified only if debugging proves painful without it.
- **Cost:** provider billing alert **plus** the server-side monthly token ceiling from `ARCHITECTURE_TARGET.md` §3.4. Do not rely on the dashboard alone.

No APM, no metrics stack, no dashboards. Adding them for one user is
over-engineering.

---

## 8. Verify before committing to a provider

Check each of these on the provider's own current documentation:

1. **Is there a region in or near India?** (largest single latency factor)
2. **Does the chosen instance tier idle down or cold start?** If yes, it is disqualified.
3. **Current price** of the smallest always-on instance that fits FastAPI + Python 3.12.
4. **Current price** of the smallest managed Postgres, and whether it also idles.
5. **Backup retention and restore procedure** for that Postgres tier — including whether point-in-time restore is included.
6. **Egress/bandwidth limits and overage pricing.**
7. **Free-tier expiry.** Several providers offer databases free for a fixed initial period and then delete or bill them. Know which.
8. **TLS/custom-domain support** on the chosen tier.
9. **Whether long-lived SSE connections are supported** without an aggressive proxy timeout — this matters for streaming voice responses.
10. **Deploy mechanism** (Docker image vs buildpack) and whether the existing `docker/backend.Dockerfile` works as-is.

---

## 9. Rollout sequence

1. Put the repository in **git** (it is not currently under version control) and push to a private remote.
2. Provision the app instance and the database in the chosen region.
3. Set secrets, including a real `API_KEY`.
4. Run `alembic upgrade head` against the new database.
5. Deploy; confirm `/api/v1/health` over HTTPS from a browser.
6. Confirm a keyless request returns **401** and a keyed request returns **200**.
7. Point the Android app at the hostname via the new in-app setting; remove the cleartext exception from the debug network-security config, keeping only `10.0.2.2` for emulator work.
8. Run the device smoke test from `TEST_STRATEGY.md` §6 **with the PC powered off.**
9. Enable the uptime monitor and the nightly backup job.
10. Perform the restore drill.

Step 8 is the one that actually proves the deployment. Steps 1–7 are setup.
