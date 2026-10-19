# Implementation Plan: agent files carry the table's model and effort, the hook advises on a departure and records what ran, and the report shows outcomes by model and effort

**Branch**: `feat/models-record` | **Spec**: `specs/models-record/spec.md`

## Summary

`agents.TABLE` holds the planner table; `render` writes each role's default as frontmatter.
`hook.advise` reads an Agent launch against the table at the item's tier and returns a note, never
a decision. `post_tool`, `subagent_stop` and `_verdict_problem` add the model and effort fields.
`ws` gains the `models` key, `setup.doctor` two rows, `report.learning` one line per seat x model
x effort.

## Technical Context

Python 3.11 stdlib. Tests in `tests/test_models.py`, plus the payload corpus in
`tests/test_hook.py`. Runtime budget 3,400 lines; main is at 3,026 (`wc -l cli/wuwei/*.py` at
c7e0cd1, the merged main).

## Constitution Check

- I. Stdlib only: yes.
- III. An auditor: no new door and no refusal. The note is `additionalContext`; the route corpus
  shows no Bash verdict moves and no Agent launch gets a permission decision.
- V. Test first: 24 of the new tests ran red on main's code before the change.
- VI. Budgets: the sixth key is the one constitution VI names; runtime at 3,086.

## Design

- `TABLE[role]` maps `''` (the default), a tier, `PATHS` or `CONFLICT` to a setting string
  (`'Opus 5.5 high'`). `PATHS` and `CONFLICT` are the charter's own words, so the advice can name
  them and the parity test can compare them. The builder's default is its standard setting.
- `render` writes `model: claude-<family>-<version>` (the charter's full IDs) and `effort:`.
- `asked(data)` reads the item (`Item:` or `WUWEI-Item:`), the effort (the call's, else the
  brief's `Model:` line) and the `Model reason:` line from the brief. `post_tool` and `advise`
  share it.
- `advise` returns nothing for a role outside the table or a call with no brief (a Codex
  `spawn_agent`, which `hook.codex` maps without one). The tier comes from the plan item, else
  standard; the raise reads `evidence.budget` only when its cache file is fresh, so the hook never
  calls the code host. The owner's row for the role and tier, else for the role, replaces the
  table's settings. Otherwise the allowed settings are the tier's own plus the paths and conflict
  settings, since the hook cannot see either at launch. A launch with no `model` or `effort` is
  compared on the agent file's default, which is what Claude Code runs then. Models compare by
  family (`opus` in `claude-opus-5-5`), efforts exactly. Either environment variable turns its
  half off. A reason line or a fit ends the note unless the launch or the owner's row puts Haiku
  on a gate.
- `seat.started` adds `model` (`resolvedModel`, else `unmeasured`), `asked`, `effort`
  (`unrecorded` when absent), `reason` and `item`. `attest` adds `model` and `effort` from the last `seat.started` row with its
  agent id, and `blocking`, the verdict's blocking findings.
- `ws.config` keeps `models` entries whose value has two or more words; `_toml` writes a dict as
  a TOML inline table; `set_config` parses `role[ tier]=model effort` pairs split on commas;
  `retired` stops calling a `models` table a 0.34 shape.
- `report.learning` groups `seat.started` rows by role, model and effort. Fix rounds per item are
  the launches on an item past the first, over the items. Blocking findings sum the attests of
  the group's agents (`blocking`, else 1 for a non-PASS row written before this item). Escapes
  count the group's agents among the gates that passed a reverted PR. Tokens join `seat.stopped`
  by agent id.

## Lines

`git diff --numstat c7e0cd1 -- cli/wuwei/` at the merge: agents.py +9 -3, hook.py +40 -4,
report.py +14 -3, ws.py +9 -4, setup.py +2 -0, __main__.py +1 -1, upgrade.py +1 -1. Runtime 3,026
to 3,086 (+60) by `wc -l cli/wuwei/*.py`. Fix round 1 dropped the unread `effort` on
`seat.stopped` (1 line); the `set_config` parse of `models` stays, since reference.md and the
posted announcement name `wuwei config models`.
The item's budget was 40 (estimate 27). The overrun is the advice: `asked` and `advise` take 30
lines with their blank lines (`awk` from `def asked` to `def closed` in hook.py), where the
estimate put 6. The tier lookup, the cached raise, the owner rows, the allowed settings, the two
variables, the floor and the note each take a line or two. Headroom after this item: 314 lines.

## Guard testing (AGENTS.md)

- `specs/models-record/route_diff.py` runs every route in `tests/fixtures/routes.json` through
  `hook.handle` as a PreToolUse Bash call, every fixture payload under its own event, and 486
  Agent launches (3 tiers x 9 roles x 6 models x 3 efforts), at main and at the head, with the
  same corpus. It compares outputs and the ledger rows each case writes.
- Guard parsing is unchanged (`guards.py` and `hook.door` untouched), so the combinatorial parser
  probe and the normalisation probes do not apply.
- `specs/models-record/mutants.py` runs 40 mutants of the new conditions, each in a fresh copy
  with `.claude/` re-vendored so both copies of `cli/` carry it, and names the test that kills it.
