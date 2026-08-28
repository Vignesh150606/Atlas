# Phase 9 — Architecture Update

This documents the *deltas* to the architecture, and the reasoning behind
each - `CLAUDE.md`'s Architecture section is the reference for the
resulting whole; this is the "what changed and why" companion, in the
same spirit as `Phase8_ArchitectureUpdate.md`.

## New layer: Skills (`app/skills/`)

Before Phase 9, adding a new capability meant either extending `Planner`
with new keyword-matching logic *and* registering a new `Tool` in
`ToolRouter` (two files, coupled), or - for anything resembling "does
this message apply to me, then do a small thing" - not being buildable
without that same two-file coupling.

**Decision:** introduce `Skill(Tool)` - IS-A `Tool` (same `ToolResult`
contract, same `run()` signature, zero new concepts for `ToolRouter` to
understand) that additionally owns its own trigger detection via
`match()`. Skills self-register into a module-level `SkillRegistry` via
a class decorator at import time. `Planner` gained exactly one new
method, `_build_skill_tool_calls()`, which asks the registry "what
matches this message" - it has no knowledge of how many skills exist or
what they do. `ToolRouter.__init__` gained one line,
`self._tools.update(SkillRegistry.instantiate_all(db))`.

**Why IS-A Tool rather than a parallel type:** a parallel `SkillRouter`
alongside `ToolRouter` would mean `ChatService` (and any future caller)
needing to know about *two* dispatch paths and merge their results -
strictly more coupling than folding Skills into the exact same
`ToolRouter._tools` dict and `dispatch_many`/`dispatch_plan` methods
that already existed and were already tested.

**Why match() lives on the Skill, not the Planner:** the alternative -
Planner holding a big dict of `{skill_name: trigger_regex}` - would mean
Planner growing by one entry per skill forever, which is exactly the
coupling the mission brief asked to eliminate ("the architecture should
allow new skills without modifying the planner"). Each skill's own
`match()` is a real behavioral unit test target too (see
`tests/test_skills.py`), whereas a shared dict of regexes tested via
Planner would conflate "does Planner call skills correctly" with "is
this specific skill's trigger phrase correct."

## Confirmation-only Skills as a deliberate sub-pattern

Three of the six skills (Notes, Reminder, Calendar) do not write to the
database in `run()` - they only produce a confirmation `ToolResult`. See
`app/skills/notes_skill.py`'s docstring for the full reasoning; the
short version is that `MemoryExtractor` already independently processes
every chat message for exactly this content (favorites, tasks, notes,
and - Phase 9 - reminders/events), and `ChatService` runs both the
Planner/ToolRouter path and the `MemoryExtractor` path on every turn
regardless of each other. A Skill that also wrote to the database here
would create two uncoordinated writers for the same data. The fix:
`MemoryExtractor.parse_reminder`/`parse_event` are extracted as
standalone, reusable static methods; the corresponding Skills call the
*same* functions to build their confirmation text, so extraction and
confirmation can never disagree, and there is exactly one writer.

## `ToolRouter`: `dispatch_many` untouched, `dispatch_plan` added alongside

Rather than modifying `dispatch_many`'s behavior (risking every existing
caller and the ~200 tests that exercise it), Phase 9 added a new method,
`dispatch_plan`, that accepts `PlannedToolCall` objects directly (not
plain dicts) so it can see the new `depends_on` field, and returns a
richer `ExecutionReport` alongside a `.results` list that's drop-in
identical in shape to what `dispatch_many` already returned. `ChatService`
was **not** switched over to `dispatch_plan` this phase - it still calls
`dispatch_many` - so this is currently additive, tested infrastructure
rather than a change to the live request path. See
`Phase9_KnownLimitations.md` #3 for the honest state of `depends_on`'s
actual usage.

## `app/retrieval/semantic_match.py`: a shared module, not a shared base class

Memory ranking (`app/retrieval/ranking.py`) and document ranking
(`app/knowledge/ranking.py`) had near-identical private
`_keyword_relevance_score` functions before Phase 9 - a real, pre-
existing DRY violation, not something Phase 9 introduced. Rather than
inventing a shared base class or ranking interface (more structural
change than the problem warranted), the fix was a shared *function*
module both call into. Each ranking module keeps its own
`_keyword_relevance_score` wrapper (same name, same call sites, same
tests) - only its body changed to delegate.

## Provider abstraction extended to weather

`app/providers/weather.py` mirrors `app/providers/base.py` +
`factory.py` exactly: an ABC, a settings-driven factory, one concrete
default implementation. The default (`UnconfiguredWeatherProvider`)
raises `NotImplementedError` with an explanatory message rather than
returning a `MockProvider`-style plausible-looking fake response - this
is a deliberate divergence from how `MockProvider` works for LLMs.
`MockProvider` is explicitly a *test* tool (only used when
`DEFAULT_LLM_PROVIDER=mock`, i.e. never in a real user-facing response);
weather has no equivalent "test-only" mode distinction; the default
*is* what a real, unconfigured deployment sees, so it has to be honest
by default, not just honest in tests.

## Cross-document entity linking: exact-match, not fuzzy

`EntityRepository.find_same_entity_elsewhere` links entities by exact
(case-insensitive) name + type match across documents, deliberately not
a fuzzy/similarity match. Considered a looser match (e.g. reusing the
new `semantic_match.relevance_score`) but rejected it: entity identity
("is this the same John Smith") is a much higher-stakes judgment than
memory-ranking relevance, and a wrong fuzzy link (conflating two
different people/projects with similar names) actively damages the
cross-document reasoning feature's trustworthiness in a way a merely
sub-optimal ranking score doesn't. Precision was chosen over recall
here specifically, unlike the deliberately-more-lenient near-duplicate
memory detection (which is default-permissive because a false-positive
duplicate merge is low-stakes and reversible, while a false cross-
document entity link would misinform the user about what a document
actually says).

## `get_unified_timeline` and `find_cross_document_connections`: additive, not modifications to `get_timeline`

Both are new methods on `KnowledgeRetrievalService`, not changes to
`get_timeline`'s existing return shape. `get_timeline` is a known,
external contract - consumed by `TimelineTool` and (per
`docs/FolderStructure.md`) the Android `TimelineScreen`/
`TimelineViewModel` - and changing its shape without being able to
verify the Android consumer still matches (see
`Phase9_KnownLimitations.md` #1) would be an unverifiable breaking
change. Additive methods sidestep that risk entirely.

## Conversation Intelligence hints: a new PromptBuilder section, not a new prompt-construction path

`detect_follow_up`/`detect_ambiguous_command` results are collected into
a plain `List[str]` and passed to the existing `PromptBuilder.build()`
as one new optional parameter, rendered as one new named section
("Conversation intelligence notes") using the exact same
section-assembly pattern every other context type (tool results,
memories, documents, user profile) already used. No new prompt-building
mechanism was introduced.
