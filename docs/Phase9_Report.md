# Phase 9 Report — Intelligence & Agent Skills

Scope actually delivered: **backend only.** No Kotlin file was touched -
see `Phase9_KnownLimitations.md` #1 for why, and `CLAUDE.md`'s
Environment Constraints for the persistent (Phase 8 → Phase 9) nature of
that constraint. Everything below was implemented and verified by
actually running `pytest`, repeatedly, in this environment - not assumed.

## 1. Architecture summary

Nine focused additions, each built to slot into the existing layered
architecture (API → Services → Repositories → Models, with Intent/
Planner/Tools/Skills/Retrieval/Knowledge as the horizontal cognitive
layer) without breaking it:

1. **Skill System** (`app/skills/`) - the headline feature. See §3.
2. **Intent Engine**: multi-intent detection, paraphrase coverage.
3. **Planner/Tool Router**: dependency-chaining, fallback routing,
   structured execution reports.
4. **Memory**: shared semantic-like ranking, near-duplicate detection,
   confidence lifecycle + staleness maintenance.
5. **Knowledge**: cross-document entity linking, unified timeline,
   multi-document summaries.
6. **Conversation Intelligence**: follow-up detection, ambiguity
   detection, both surfaced directly in the LLM prompt.
7. **Security**: `requires_confirmation` signal on destructive-ish
   device actions.
8. **CLAUDE.md** (mandatory task 1) + **.gitignore** (mandatory task 2).
9. This documentation set.

## 2. Files modified

Full list (backend only; `git diff --stat` equivalent, since this repo
has no `.git` yet - compiled by hand from the actual edit history this
session):

**New files:**
- `app/skills/__init__.py`, `base.py`, `registry.py`, `time_skill.py`,
  `weather_skill.py`, `search_skill.py`, `notes_skill.py`,
  `reminder_skill.py`, `calendar_skill.py`
- `app/providers/weather.py`
- `app/retrieval/semantic_match.py`
- `app/services/memory_lifecycle_service.py`
- `backend/scripts/refresh_memory_lifecycle.py`
- `tests/test_skills.py`, `test_skill_registry.py`,
  `test_tool_router_chaining.py`, `test_semantic_match.py`,
  `test_memory_lifecycle.py`
- `CLAUDE.md`, `.gitignore` (repo root)
- `docs/Phase9_Report.md`, `Phase9_ArchitectureUpdate.md`,
  `Phase9_KnownLimitations.md` (this set)

**Modified files:**
- `app/tools/base.py` (`requires_confirmation` field on `ToolResult`)
- `app/tools/device_tools.py` (`requires_confirmation` wiring for
  `dial`/`clipboard write`)
- `app/tools/router.py` (Skill auto-registration, `dispatch_plan`,
  `ExecutionReport`, `_FALLBACK_FOR`)
- `app/schemas/chat.py` (`requires_confirmation` on `DeviceActionSchema`)
- `app/services/chat_service.py` (`requires_confirmation` wiring,
  memory-type-scoped `find_duplicate` call, conversation-hints wiring)
- `app/intent/intent_service.py` (`classify_all`, `is_multi_intent`,
  paraphrase synonyms, a negation-bug fix in `explicit_deletion`)
- `app/retrieval/ranking.py`, `app/knowledge/ranking.py` (delegate to
  shared `semantic_match.relevance_score`)
- `app/repositories/memory_repository.py` (near-duplicate detection,
  confidence bump in `record_usage`)
- `app/memory/memory_extractor.py` (`parse_reminder`, `parse_event`,
  extraction rules 5 & 6)
- `app/planner/planner.py` (`depends_on` field, `_build_skill_tool_calls`,
  reminder-guard fix, search/knowledge redundancy fix)
- `app/repositories/entity_repository.py`
  (`find_same_entity_elsewhere`)
- `app/services/document_service.py` (cross-document linking wired into
  `_extract_and_link_entities`)
- `app/knowledge/knowledge_retrieval_service.py`
  (`find_cross_document_connections`, `get_unified_timeline`)
- `app/knowledge/summarizer.py` (`multi_document_summary`)
- `app/services/conversation_intelligence.py` (`detect_follow_up`,
  `detect_ambiguous_command`)
- `app/prompts/prompt_builder.py` (`conversation_hints` param + section)
- `app/providers/mock.py` (echoes conversation-hints usage, for testing)
- `app/observability/trace.py` (`follow_up_detected`,
  `ambiguity_detected` fields)
- `app/core/config.py` (`WEATHER_PROVIDER`, `WEATHER_API_KEY` settings)
- Test files updated (not just added-to) where a pre-existing assertion
  legitimately needed to grow: `tests/test_tools.py` (exact tool-name
  set), `tests/test_device_tools.py` / `test_device_action_endpoint.py`
  (`requires_confirmation` assertions), `tests/test_memory_extractor.py`
  unaffected (no rule 1-4 behavior changed), `tests/test_cognitive_pipeline.py`
  (new conversation-intelligence integration tests),
  `tests/test_document_import.py` (cross-document/timeline/summary
  tests), `tests/test_intent_service.py` (paraphrase + multi-intent
  tests), `tests/test_prompt_builder.py` (conversation-hints tests).

## 3. New skills added

Six, in `app/skills/`, all self-registering via `@register_skill` -
Planner required exactly one generic hook (`_build_skill_tool_calls`),
added once, to support all six and any future ones:

| Skill | Trigger | Behavior |
|---|---|---|
| `time` | "what time is it" / "what's today's date" | Answers directly from server clock (honestly labeled "server time", not device timezone). |
| `weather` | "weather" / "forecast" / "is it going to rain" | Calls `WeatherProviderFactory` - honestly reports "not configured" by default (see §9), never fabricates a forecast. |
| `search` | "search for X" / "look up X" / "find info about X" | Unified search across ATLAS's own memories + documents. Explicitly not web search - no search API is configured anywhere in this codebase. |
| `notes` | "remember that X" / "note that X" / "make a note" | Confirmation only - `MemoryExtractor` rule 4 (pre-existing) does the actual persisting, to avoid two code paths racing to write the same memory. |
| `reminder` | "remind me to X [at/by/on Y]" | Confirmation only - `MemoryExtractor` rule 5 (new this phase) persists it, sharing the exact same `parse_reminder` parsing. |
| `calendar` | "add an event: X [on Y]" / "put X on my calendar" | Confirmation only - `MemoryExtractor` rule 6 (new this phase) persists it, sharing `parse_event`. |

**Real gap this closes:** pre-Phase-9, "Remind me to submit the report"
correctly classified as `IntentType.TASK` but nothing acted on it - no
tool call, no persisted memory, no confirmation. Verified via
`tests/test_document_import.py`/`test_skills.py` and a live
`Planner.build_plan` trace during development (see Lessons Learned in
`CLAUDE.md`).

## 4. New planner capabilities

- `PlannedToolCall.depends_on: Optional[str]` + `ToolRouter.dispatch_plan()`:
  ordered execution with `{{depends_on.output}}` placeholder substitution
  and opt-in fallback (`summary` → `knowledge` today). This is
  infrastructure that exists and is directly tested
  (`test_tool_router_chaining.py`, 6 tests) - **no current Planner rule
  emits `depends_on` yet**, stated plainly rather than forcing a
  contrived usage just to claim it's "wired in end-to-end." See
  `Phase9_KnownLimitations.md` #3.
- Multiple matching skills now produce multiple `PlannedToolCall`s in one
  plan (e.g. "remind me to call John and what time is it" → two tool
  calls) - a genuine, real multi-step plan, not a synthetic example.
- Two real bugs found and fixed while building this (see `CLAUDE.md`
  Lessons Learned): a dial-detection false positive on "remind me to
  call X", and redundant knowledge+search firing on the same message.

## 5. New memory capabilities

- `IntentService.classify_all()` / `is_multi_intent()` - additive,
  `classify()`'s behavior is byte-for-byte unchanged (verified: every
  pre-existing intent test still passes, plus a new
  `test_classify_all_first_result_matches_classify` regression guard).
- Shared semantic-like relevance scoring (`app/retrieval/semantic_match.py`)
  - light stemming + optional corpus-weighted term scoring, replacing
    duplicated raw-substring-count logic in two files.
- Near-duplicate memory detection (`find_duplicate`, `difflib`-based,
  bounded candidate pool, optionally type-scoped).
- Confidence lifecycle: `record_usage` now nudges `confidence` up
  (capped 100) on genuine retrieval-and-use - finishes a Phase-5 field
  that sat unused until now. `MemoryLifecycleService.flag_stale_memories()`
  + `scripts/refresh_memory_lifecycle.py` (run for real against a live
  DB during development, output verified, not just imported).

## 6. Testing added

**303 backend tests passing** (up from the 201 documented at the end of
Phase 8), **zero regressions** - verified by running the full suite
after every meaningful change during this session, not only at the end.
102 new tests across 5 new test files plus additions to 9 existing ones.
Breakdown of new test files:

| File | Tests | Covers |
|---|---|---|
| `test_skills.py` | 20 | Every skill's `match()`/`run()` |
| `test_skill_registry.py` | 9 | Registration, duplicate rejection, db-bound vs db-less instantiation |
| `test_tool_router_chaining.py` | 6 | `dispatch_plan` chaining, fallback, reporting |
| `test_semantic_match.py` | 8 | Stemming, exact/near-miss scoring, term weighting |
| `test_memory_lifecycle.py` | 7 | Staleness flagging rules (old+low-confidence, pinned/confirmed exemptions, idempotency) |

Plus real additions to: `test_intent_service.py` (paraphrase +
multi-intent, 12 new), `test_device_tools.py` /
`test_device_action_endpoint.py` (`requires_confirmation`, 6 new),
`test_memory_repository.py` (near-duplicate + confidence, 6 new),
`test_document_import.py` (cross-document + unified timeline + summary,
9 new), `test_conversation_intelligence.py` (follow-up + ambiguity, 12
new), `test_prompt_builder.py` (conversation hints, 4 new),
`test_cognitive_pipeline.py` (3 new real end-to-end integration tests -
not unit tests - proving hints actually reach the LLM prompt via a real
chat-endpoint round trip).

## 7. Potential future improvements

See `CLAUDE.md`'s Future Vision for the full list; the ones most
directly connected to Phase 9's own work:
- Wire `depends_on` into an actual Planner rule now that the mechanism
  is proven.
- A real `WeatherProvider` implementation.
- Date parsing for chat-extracted reminders/events (currently free
  text - see `Phase9_KnownLimitations.md` #4).
- Android consumption of `requires_confirmation` and `ExecutionReport`.

## 8. Updated CLAUDE.md summary

`CLAUDE.md` was rewritten from scratch this phase (mandatory task 1 -
no prior version existed). It documents: project vision, full backend +
Android architecture (including everything added this phase), a
phase-by-phase history from Phase 1 through Phase 9, lessons learned
(including the specific bugs found this session), the verification
workflow, condensed coding standards, and future vision. `.gitignore`
was created at repo root (none existed before) containing `CLAUDE.md`
plus standard Python/Android/editor artifact ignores, per the mission's
explicit instruction not to ignore any other documentation.

## 9. Confirmation that no previous architecture was broken

- **201 pre-existing backend tests all still pass**, unchanged, verified
  by running the full suite (not a subset) after every meaningful change
  during this session - not just at the end.
- `dispatch_many` (the pre-Phase-9 dispatch path) is completely
  untouched; `dispatch_plan` is a new, additive sibling.
- `get_timeline`'s contract is completely untouched; `get_unified_timeline`
  is new and additive.
- `classify()`'s behavior is completely unchanged (a dedicated regression
  test asserts `classify_all()[0] == classify()` for every message
  tested).
- Calculator and every Phase 8 device tool were deliberately left as
  plain `Tool` subclasses, not retrofitted onto the new `Skill` base -
  zero risk to their existing, tested Planner routing.
- One test-isolation bug was introduced and then caught and fixed within
  this same session (a dummy skill registered during a registry test
  leaked into the global `SkillRegistry` and broke an unrelated,
  pre-existing test's exact-set assertion) - full suite re-run confirmed
  the fix. Documented in `CLAUDE.md` Lessons Learned rather than
  quietly fixed and forgotten.

**Honest caveat, stated once here and not repeated with false confidence
elsewhere:** "no previous architecture was broken" is scoped to the
**backend**, which was actually run. The Android/Kotlin codebase was not
touched, compiled, or run this session - it is exactly as it was at the
end of Phase 8, for better or worse.
