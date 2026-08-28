# ATLAS — Daily Driver Requirements

Architecture session, 2026-08-28. This is the first document in this repo that
defines *done* in product terms rather than phase terms.

---

## 0. The question this document answers

> "What must ATLAS have before I can realistically use it every day as my
> primary personal AI assistant on my phone?"

Everything below is written as a **binary gate**. A capability is either
demonstrably true on a real phone with the development PC powered off, or it is
not done. "Implemented", "tested", and "documented" are not the standard. The
standard is: *the developer stopped reaching for a different app.*

---

## 1. The Daily Driver Standard (DDS)

ATLAS is a daily driver when **all 14 gates below pass on a physical phone, on
mobile data, with the development PC shut down, for 7 consecutive days without
the developer touching the backend.**

That last clause is the real test. Any gate that only passes while someone is
watching a terminal is not passing.

| # | Gate | Pass condition |
|---|---|---|
| **G1** | **Reachability** | The app talks to the backend over HTTPS from mobile data and from any Wi-Fi, with no PC running and no IP address edited into a build file. |
| **G2** | **Chat** | A text turn returns a useful answer in <= 3 s p50 / <= 8 s p95, or fails with a message that says *what* failed and what to do. |
| **G3** | **Voice in** | Tap (or headset button) then speak, producing a transcript, working with the phone in a pocket and audio over Bluetooth earbuds. |
| **G4** | **Voice out** | Reply is spoken through the same earbuds, starts within 2 s of the first token, and can be interrupted by speaking over it. |
| **G5** | **Time correctness** | "Tomorrow at 8" means 08:00 *in the user's local timezone*, in every surface: reminders, briefing, "what's today", prompt context. |
| **G6** | **Reminders actually fire** | A reminder set for 15:00 produces a phone notification at 15:00 +/- 60 s, with the screen off, the app killed, and the backend idle. |
| **G7** | **Memory** | "Remember X" is recallable in a *new* conversation days later; visible in a list; editable; deletable. |
| **G8** | **Knowledge** | A PDF or notes file uploaded from the phone is searchable by content and cited by name when used in an answer. |
| **G9** | **Schedule** | "What do I have today / tomorrow?" gives a correct, chronologically ordered answer from real structured data, not free-text guessing. |
| **G10** | **Phone automation** | The 6 lowest-risk actions (open app, media control, read notifications, read screen, clipboard read, open URL/maps) work reliably; every higher-risk action asks first, in both text and voice. |
| **G11** | **Offline degradation** | With no network: history, reminders, tasks, and today's briefing are readable from cache; new input is queued, not lost; the failure is stated once, not looped. |
| **G12** | **Security** | No cleartext HTTP; API key required and stored encrypted; no message content in device logs in release builds; destructive actions gated. |
| **G13** | **Durability** | Losing the phone or the server loses nothing. A restore path exists and has been executed at least once. |
| **G14** | **Cost predictability** | Monthly spend is known, capped, and observable; a runaway loop cannot silently generate a large bill. |

**Current status: 0 of 14 pass.** See §4 for why that is less bad than it sounds.

---

## 2. Per-domain minimum bar

### 2.1 Voice
- Push-to-talk from a **foreground service**, so a session survives the screen turning off.
- **Bluetooth SCO** (or `AudioManager.setCommunicationDevice` on API 31+) actually engaged, so the *earbud mic* is used, not the phone's.
- Headset media-button starts a session.
- **Response streaming**, so TTS begins on the first sentence rather than after the full generation.
- **Barge-in**: speaking during TTS stops playback.
- Offline fallback: on-device recognition preferred when the network is down; a spoken "I can't reach the server" rather than silence.
- **Not required for daily driver:** wake word, always-on listening, custom voices, speaker identification.

### 2.2 Chat
- Streaming text, retry on a failed turn, and the user's message never lost on failure (already true server-side).
- Conversation list and history readable offline.
- Markdown rendering and timestamps (currently missing — `docs/Roadmap.md` Phase 2 still has this unchecked and it is correct to be unchecked).

### 2.3 Memory
- Create / read / update / delete from the phone, plus source attribution on anything ATLAS asserts from memory ("you told me this on the 14th").
- Explicit forget: one tap, hard delete, confirmed.
- Contradiction handling: at minimum, a newer explicit statement outranks an older one, and the conflict is surfaced rather than silently averaged.

### 2.4 Knowledge
- Upload from the phone; the Android share sheet is the natural entry point.
- Search by content; answers cite the document title.
- Delete a document and everything derived from it.

### 2.5 Reminders and tasks
- **Exact-time local delivery** (`AlarmManager` with `SCHEDULE_EXACT_ALARM`), not periodic polling.
- Notification actions: Done / Snooze 10m / Open.
- Recurrence that survives completion (already implemented server-side and tested).
- Server remains the source of truth; the phone holds a scheduled mirror.

### 2.6 Phone automation
- The capability tiers in `ARCHITECTURE_TARGET.md` §5 enforced **on-device**, not merely signalled by the backend.
- Every confirmation works identically in text and voice.
- A visible, per-capability kill switch.

### 2.7 Notifications (reading other apps')
- Category filtering already exists. What is missing is user-visible control over *which* apps ATLAS may read, and a guarantee that notification text never leaves the phone unless the user asked a question that needs it.

### 2.8 Cloud access
- One always-on HTTPS endpoint, one stable hostname, automatic TLS, no PC in the path.

### 2.9 Security
- See `SECURITY_PLAN.md`. Minimum: TLS, non-optional API key in production, encrypted key storage on device, no BODY logging in release builds, confirmation boundaries enforced client-side.

### 2.10 Reliability
- Every one of the 11 failure modes in `ARCHITECTURE_TARGET.md` §8 has a defined and tested behavior.

### 2.11 Offline
- Read-only cache of conversations, reminders, tasks, and the last briefing.
- Outbound queue for messages and reminder completions, flushed on reconnect.

### 2.12 Error recovery
- No silent failures. Every swallowed exception in the current codebase is a defect (there are several — see `MASTER_PLAN.md` §2.4).
- One clear error surface per failure, with a retry affordance.

### 2.13 Backups
- Nightly automated database backup, stored off the primary host, restore-tested.
- User-triggered full export (memories + documents + reminders + conversations) as a single file.

### 2.14 Observability
- The existing `RequestTrace` shipped somewhere queryable, plus uptime alerting that reaches the phone.

### 2.15 Cost control
- Hard monthly token ceiling enforced **in the backend**, not just watched on a provider dashboard.
- Per-turn token budget; a cheap model for cheap turns.

---

## 3. The 22 scenarios that define "useful"

These are the acceptance scenarios. Each must work end-to-end, by voice, over
earbuds, with the PC off. `[N]` marks the phase from `FINAL_ROADMAP.md` that
delivers it.

**Capture and recall**
1. "Remember that my advisor's name is Dr. Rao and he prefers email." → stored, confirmed, recalled a week later in a new conversation. `[12]`
2. "What did I tell you about my advisor?" → answer with attribution to when it was said. `[15]`
3. "Forget what I said about the internship." → finds it, confirms, hard-deletes. `[15]`
4. Share a PDF to ATLAS from another app → imported and acknowledged. `[15]`

**Time and schedule**
5. "Remind me to submit my assignment tomorrow at 9." → fires at 09:00 local, next day, phone locked. `[14]`
6. "What classes do I have today?" → correct list, in order, for the correct local weekday. `[14]`
7. "What do I have tomorrow?" → merged reminders + calendar events + due tasks. `[14]`
8. "Move my 3pm to 5." → identifies the item, confirms the change, reschedules the alarm. `[14]`
9. "Every weekday at 7am remind me to take my medicine." → recurring, survives completion. `[14]` (parser already exists and is tested)
10. "What's due this week?" → deadline list drawn from documents + tasks + reminders. `[14]`

**Work review**
11. "What did I work on yesterday?" → from conversation history plus completed tasks. `[15]`
12. "Summarize my day." → deterministic briefing, then an LLM narrative over it. `[14]`
13. "Summarize my day" at 22:00 with no network → serves the cached briefing and says it is cached. `[12]`

**Documents**
14. "Search my documents for the placement eligibility criteria." → cited answer. `[15]`
15. "What's in the syllabus PDF I uploaded last week?" → summary with the document named. `[15]`

**Phone control**
16. "Open Spotify." → launches. `[12]` (already implemented; blocked today only by connectivity)
17. "Pause the music." / "What's playing?" → media session control. `[12]`
18. "Read my important notifications." → filtered, promotional noise suppressed, read aloud. `[13]`
19. "Call Mom." → resolves the contact, **asks for confirmation aloud**, then opens the dialer pre-filled. `[13]`
20. "Copy this to my clipboard." → asks first (already gated server-side), then writes. `[12]`
21. "What's on my screen?" → reads and summarizes the foreground content. `[13]`

**Conversation quality**
22. Full earbud session: press the headset button, speak, hear a reply within ~2 s, interrupt it mid-sentence with a follow-up, and have the follow-up understood in context — screen off the whole time. `[13]`

---

## 4. Honest position statement

The backend's *cognition* — intent, planning, tool routing, memory, knowledge,
reminders, briefing — is genuinely well built and genuinely tested (417 passing
tests, verified 2026-08-28 by running the suite). Call that roughly 70% of what a
daily driver needs from a backend.

The *product* — a thing that runs on a phone without a developer attached — is
closer to 15% complete. Not because the work is bad, but because every phase so
far optimized for architecture quality inside a sandbox, and the phone-first,
PC-off requirement was never a gate. Three specific defects (a hardcoded LAN IP
sitting behind a cleartext block, UTC-only time handling, and polling-based
reminder delivery) are each *individually* sufficient to make ATLAS unusable as a
daily assistant, and none of them are hard to fix.

The gap is **integration and deployment, not intelligence.** That is the good
kind of gap to have this late in a project.
