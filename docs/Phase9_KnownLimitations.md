# Phase 9 — Known Limitations

Same format as `Phase8_KnownLimitations.md`: each item says what the
limitation is, why it exists, and what it would take to remove.

## 1. Android was not touched, built, or run this phase

This is an environment constraint, not a design decision - identical in
kind to `Phase8_KnownLimitations.md` #7, and it persisted unchanged into
this phase:

- No Android SDK installed in this sandbox.
- The network egress allowlist available here does not include
  `dl.google.com`, `repo.maven.apache.org`, or `services.gradle.org`.
- Because of this, none of Phase 9's Android-facing asks from the
  mission brief were attempted: **Voice Improvements** (natural
  interruptions, better continuity, response timing, cleaner state
  transitions) and **Automation Improvements** (better command
  interpretation, device-action reporting, error recovery) beyond what
  could be done purely on the backend side (see item 2 below) are all
  entirely unstarted.
- `requires_confirmation` (§ below, and see `CLAUDE.md`) is produced by
  the backend but has no Android consumer yet - the confirmation dialog
  itself doesn't exist.

**To remove:** run this phase's remaining Android-facing work in an
environment with a real Android SDK and Gradle/Google Maven network
access (or continue in a tool with that access already configured, e.g.
Claude Code on a real machine) rather than this sandboxed chat
environment.

## 2. "Automation Improvements" were only partially addressed, and only backend-side

The mission brief's Automation Improvements bullet (better command
interpretation, better device-action reporting, better error recovery)
is genuinely only achievable in full on the Android side (the code that
actually executes device actions and can observe real failures lives
there). What Phase 9 delivered on the backend side:
- `requires_confirmation` (see item 6 below) - a real, if partial, piece
  of "don't execute destructive actions silently."
- `ToolRouter.dispatch_plan`'s `ExecutionReport` - richer structure
  around tool execution than the plain `List[ToolResult]` `dispatch_many`
  returns, available for a future observability/debug view.
- The dial/reminder disambiguation bug fix (see `CLAUDE.md` Lessons
  Learned) is arguably "better command interpretation."

What's still missing: any actual improvement to *device-side* error
recovery (e.g. retrying a failed accessibility action, better messaging
when a target app isn't installed) - none of that code was touched.

**To remove:** scope a dedicated Android-side pass once Android tooling
is available.

## 3. `PlannedToolCall.depends_on` has no current Planner emitter

The dependency-chaining mechanism in `ToolRouter.dispatch_plan`
(`{{depends_on.output}}` placeholder substitution) is real,
implemented, and directly tested (`tests/test_tool_router_chaining.py`,
6 tests exercising it end-to-end through `ToolRouter`). What's missing:
no rule in `Planner.build_plan` currently sets `depends_on` on a
`PlannedToolCall` it produces - every existing tool call in this
codebase is independent of every other, so there was no honest,
non-contrived case to wire it into this phase without inventing a
combination that doesn't reflect real usage.

**Why this is being stated explicitly rather than silently left:** it
would have been easy to force some skill combination to use this field
just to claim "fully wired end-to-end," but that would be exactly the
kind of fabricated completeness this project's own coding standards
prohibit. The mechanism is genuinely ready; nothing currently needs it.

**To remove:** the next skill or tool that legitimately needs a prior
call's output (e.g. a future "summarize the document I just found"
two-step skill) should set `depends_on` - no ToolRouter changes needed.

## 4. Chat-extracted reminder/event dates are free text, not parsed dates

`MemoryExtractor.parse_reminder`/`parse_event` (Phase 9) capture
"Friday", "next Monday", "6pm" etc. verbatim into `structured_data`
rather than resolving them to an actual date. This is consistent with
how the pre-existing `MemoryExtractor` rule 3 (task deadlines) already
worked before this phase - not a new gap, but its effect is now more
visible because `get_unified_timeline()` (Phase 9) merges these
memory-sourced items with document-sourced items that *do* have
extractor-parsed ISO dates. The merged timeline's chronological sort is
therefore only fully reliable for document-sourced items; memory-sourced
items sort alphabetically by their raw text among themselves. Documented
directly in `get_unified_timeline`'s own docstring, not just here.

**To remove:** add a small deterministic relative-date resolver (e.g.
"Friday" → next occurring Friday from a reference date) shared by
`MemoryExtractor` and consumed by `get_unified_timeline`'s sort key.
Deliberately not attempted this phase - a naive implementation would
need real care around timezones and "does 'Friday' mean this week or
next," and doing it hastily would risk shipping confidently-wrong dates,
which is worse than honestly-unparsed text.

## 5. Weather has no real provider

`WeatherSkill`/`WeatherProviderFactory` (Phase 9) are real, tested
infrastructure, but `WEATHER_PROVIDER` defaults to `"unconfigured"` and
no real implementation (e.g. OpenWeatherMap) exists in this codebase.
Every weather question currently gets an honest "not configured"
response, never a fabricated forecast. This is the same "interface
ready, real integration deliberately deferred" pattern already
established in this codebase for `LLMProvider.get_embedding`.

**To remove:** implement a `WeatherProvider` subclass against a real
API and register it in `WeatherProviderFactory.create()`; set
`WEATHER_PROVIDER`/`WEATHER_API_KEY`. No other code needs to change.

## 6. `requires_confirmation` is a signal, not an enforcement mechanism

The backend cannot itself pause and wait for user confirmation before a
device action fires - it can only attach `requires_confirmation: true`
to the directive it sends. Currently set for `dial` and
`clipboard write` only (see `app/tools/device_tools.py` for the
reasoning per action - notably, other intent_action verbs like
`open_url`/`contacts`/`maps`/`share`/`email` are judged non-destructive
and don't set it). Since Android doesn't yet read this field (item 1),
it currently has no observable effect on the actual user experience -
it's real, tested, wire-format-complete groundwork, not yet a delivered
feature end-to-end.

**To remove:** Android's `AutomationToolRouter` needs to check the flag
before dispatch and show a confirmation UI when true.

## 7. Search skill is local-only, not web search

`app/skills/search_skill.py` searches ATLAS's own memories and
documents. There is no web-search capability anywhere in this codebase
- no search API key, no configured provider, and this environment's own
network egress allowlist does not include a general search API either.
Building a "search" skill that silently returned nothing or fabricated
results for a web query would violate this project's own "never
fabricate" standard, so this was scoped narrowly and honestly rather
than attempted incompletely.

**To remove:** would need a real, licensed search API and a
provider-abstraction wrapper following the same pattern as
`WeatherProvider` - not attempted, no existing precedent to build from
in this codebase, unlike weather.

## 8. Phase 1-4 and Phase 6/7 summaries in CLAUDE.md were not independently re-verified line-by-line this session

`CLAUDE.md`'s "Completed Phases" section for Phases 1-4, 6, and 7 was
compiled from `docs/Roadmap.md` and cross-checked against the current
file structure (module names, class names) actually present in the
repository - but the deep implementation history of those phases (exact
commit-by-commit decisions, exact original test counts at the time) was
not re-derived from scratch this session the way Phase 8 and 9's own
history was. Phase 8's own documentation (`Phase8_Report.md` and
friends) was read and is accurately reflected; earlier phases rely on
`Roadmap.md`'s own checklist being accurate, which was not independently
audited against, e.g., git history (there is no `.git` in this
checkout).
