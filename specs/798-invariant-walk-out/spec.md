# Feature Specification: delete the invariant walk and the prose-pinning tests

**Feature Branch**: `798-invariant-walk-out`
**Created**: 2026-10-11
**Status**: Draft
**Input**: GitHub issue #798, part 1 of the deletion pass #789 (supersedes #736). Delete the
invariant walk in `tests/test_invariants.py` and keep only the refusal-string lint
(`test_reason_corpus_has_no_wall` and its helpers). Move the three merge cases that guard real
process errors (merge only at the gated green head, `owner_merge` on every path, a
trust-surface item waits on its gate) next to the merge tests. Delete the prose-pinning tests
in `tests/test_docs.py` and `tests/test_charters.py`; keep the structural ones. Remove the
constitution rule that every guard change adds an invariant row, and replace the design spec
9.2 table with the edge table (host merge, approve, admin, force push, deploy, outward send,
and `gh pr create` routed to `pr raise --item`).

## Why (read on main at bfbf6a3)

- `tests/test_invariants.py` (1766 lines) walks 47 invariant rows over a 7-dimension product
  (posture x audience x topic x kind x grant x umbrella x connector mode, at least 18000
  cases), with a per-invariant CPU budget (`INVARIANT_BUDGET = 0.4`), a timing group in CI and
  an 18-entry table of broken rules. Most rows check autonomy machinery the pass deletes
  (grants, cruise, pace, budget classes, calibration, shadow, undo, novelty, graph, drafts,
  setup cards). The walk makes every guard change a process task: the constitution's Workflow
  rule says a guard change "adds its invariant to the design spec 9.2 table and to
  `tests/test_invariants.py`, or the review refuses it".
- `tests/test_docs.py` (90 tests) and `tests/test_charters.py` (25 tests) mostly assert that
  given phrases appear in README, site pages, skills and charters. They pin prose, so every
  later deletion PR would have to edit text only to satisfy them.

## User Scenarios and Testing

### User Story 1 - A guard change is a code change, not a table entry (Priority: P1)

A builder who changes a guard writes the guard's own test. No walk, budget or design table row
is required, and no review refuses the change for a missing invariant row.

**Independent Test**: `tests/test_invariants.py` holds one test,
`test_reason_corpus_has_no_wall`, and it passes; the constitution has no invariant-row rule.

**Acceptance Scenarios**:

1. **Given** the suite, **When** `tests/test_invariants.py` runs, **Then** only the
   refusal-string lint runs and passes.
2. **Given** `tests/test_dev_cycle.py`, **When** it lists the clock tests in the timing group,
   **Then** the walk is not among them and the list still matches the marked tests.
3. **Given** the constitution, **When** a reader looks for the invariant-row rule, **Then** it
   is gone, the version is bumped and the amendment is dated.

### User Story 2 - The process errors the walk caught are still caught (Priority: P1)

The three merge cases that stop a real process error keep a test in the merge test module.

**Independent Test**: run `tests/test_merge.py`; the moved cases pass, and each fails when the
rule it guards is broken (checked once by hand with a temporary mutation, not committed).

**Acceptance Scenarios**:

1. **Given** the gate verdicts name an older head than the PR head, **When** `merge.execute`
   runs under the auto policy, **Then** nothing is merged and the reason names the gates at
   the current head.
2. **Given** an item with `owner_merge` set, **When** each of `merge check`, `wuwei merge`,
   `pr act`, the PR guard on `gh pr merge` and the overnight shepherd runs, **Then** each
   refuses naming the hold and nothing is merged.
3. **Given** a `trust_surface` item whose security gate is FIX, **When** `merge.execute` runs
   under any grant, **Then** it waits on the gate, never routes to the owner and merges
   nothing (the existing test in `tests/test_merge.py` is the home).

### User Story 3 - Docs and charter tests check structure only (Priority: P2)

Docs and charter tests check that pages link, the nav is complete, config keys and commands
are documented, the release ships every linked doc, generated files match their generator,
charters have frontmatter, ordered lists, no banned content, no blocking instruction, the
plain-tone rule, no verdict format of their own, and sentinels carry the clean-probe rule.

**Independent Test**: `tests/test_docs.py` and `tests/test_charters.py` pass with only the
kept tests; no kept test asserts a sentence of prose except where it guards a process error
(the skills' executable rule, the clean-probe rule) or a kept lint (plain tone).

### Edge Cases

- A kept test still needs a helper or import that a deleted test also used: deleting it breaks
  the module. The plan lists what each kept test uses; the touched files are run.
- `tests/test_dev_cycle.py::test_exactly_the_clock_tests_share_the_timing_group` compares the
  marked tests with `TIMING`; the walk's entry must leave `TIMING` in the same change.
- The docs tone budget (`tests/test_tone.py`, class `docs`) reads README: the edited sentences
  must not add a sentence over 35 words or raise nominalisations.
- `tests/test_calibrate.py::test_instruction_like_passes_this_repository` reads README and the
  constitution: the edits must not read as an instruction to a model.

## Requirements

### Functional Requirements

- **FR-001**: `tests/test_invariants.py` MUST contain only `test_reason_corpus_has_no_wall`
  and the names it uses (`WALL`, `CARD`, `wall`, `CALLED`, `LATER`, `OWNED`, `MERGES`,
  `EXEMPT`, `_functions`, `corpus`, `listed`) with only the imports they need.
- **FR-002**: No test module MUST import from `tests/test_invariants.py` (none does today; the
  check is that none is added).
- **FR-003**: `tests/test_merge.py` MUST hold a case that `merge.execute` merges nothing when
  the gate verdicts name an older head (auto policy, no grant), and a path table that
  `owner_merge` set refuses on `merge check`, `wuwei merge`, `pr act`, the PR guard and the
  overnight shepherd with no merge call.
- **FR-004**: The trust-surface case MUST keep a passing home: the existing
  `tests/test_merge.py::test_an_open_security_gate_waits_whatever_the_grant` (open gate waits,
  no owner route, no merge, no grant used) and
  `test_an_owner_path_is_merged_by_the_owner_whatever_the_grant`; no duplicate is added.
- **FR-005**: `tests/test_docs.py` MUST keep only the structural tests listed in plan.md and
  delete the rest with the helpers and imports only they used.
- **FR-006**: `tests/test_charters.py` MUST keep only the structural tests listed in plan.md
  and delete the rest with the constants only they used.
- **FR-007**: `tests/test_dev_cycle.py` `TIMING` MUST drop the walk's entry.
- **FR-008**: No CI workflow, script or config MUST refer to the walk or its budget.
- **FR-009**: The constitution MUST drop the Workflow bullet requiring an invariant row, bump
  its version to 2.0.0 (a governance removal is MAJOR under the speckit-constitution rule) and
  set Last Amended to 2026-10-11.
- **FR-010**: Design spec 9.2 MUST be replaced by the edge table: host merge, approve, admin,
  force push, deploy, outward send, and `gh pr create` for a recorded item routed to
  `wuwei pr raise --item`; each row names the guard and the test file that checks it.
- **FR-011**: README and NOTICE MUST stop saying that a test walks every case of the 9.2
  table.

### Key Entities

- **Refusal-string lint**: `test_reason_corpus_has_no_wall`, which reads every guard reason
  and fails when one is a wall under observe or guarded.
- **Edge table**: design spec 9.2 after this change; one row per irreversible edge.

## Success Criteria

- **SC-001**: `tests/test_invariants.py` is under 125 lines and runs one test.
- **SC-002**: `python -m pytest -q tests/test_invariants.py tests/test_merge.py
  tests/test_docs.py tests/test_charters.py tests/test_dev_cycle.py tests/test_tone.py
  tests/test_calibrate.py` passes.
- **SC-003**: `git grep -n "test_invariants_hold\|INVARIANT_BUDGET"` finds nothing outside
  `specs/` and `CHANGELOG.md`.
- **SC-004**: The constitution reads version 2.0.0, Last Amended 2026-10-11, and has no
  invariant-row bullet.

## Clarifications

### Session 2026-10-11

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Where do the three moved cases go, given the issue names `tests/test_merge.py` and
  `tests/test_dispatch.py`? A: All three exercise `merge.execute`, `merge.check` and the merge
  paths, and need the `case` fixture of `tests/test_merge.py`. `cli/wuwei/dispatch.py` has no
  merge step and never reads `owner_merge` (checked with grep), so no case belongs in
  `tests/test_dispatch.py`; its trust-surface gate selection is already covered by
  `test_code_or_trust_surface_keeps_three_gates`. `tests/test_dispatch.py` is not edited.
- Q: What is "one case each"? A: One test per moved invariant, keeping only the axis that is
  the process error and dropping the posture and grant axes (posture and grants are deleted
  later in the pass). Merge head: one case, the moved head, because the gated head and the red
  head under execute are already covered (`test_merge_pins_head_and_writes_evidence_and_undo`,
  `test_refused_merge_never_calls_mutation`) and the moved head is covered only under a grant
  (`test_moved_head_merges_under_no_grant`). `owner_merge`: the five-path table with the flag
  set; the cleared half is the normal policy every other merge test runs. Trust surface:
  already covered by two tests; no copy.
- Q: Which docs tests are structural? A: The eight the pass plan lists plus
  `test_hero_files_match_their_generator` (a generated file matches its generator; it pins no
  prose). The hero animation tests pin what the picture shows and go.
- Q: Which charter tests are structural? A: The pass plan's list plus
  `test_charter_sentences_have_one_home` (no sentence in two charters; it pins no prose) and
  the self-tests of two kept lints
  (`test_generic_patterns_cover_case_without_english_false_positives`,
  `test_blocking_pattern_samples`).
- Q: Edit README and NOTICE although the README is rewritten later in the pass? A: Yes, one
  sentence in each place: they say a test walks every case of 9.2, which is false after this
  change. `docs/site/*` is not edited (no kept test forces it and no page names the walk).
- Q: Code comments that cite a 9.2 id (`cli/wuwei/pace.py` I15, `cli/wuwei/commands/init.py`
  I18, `cli/wuwei/guards/__init__.py` I1, the design spec pace line on I15 to I17, test
  comments in `tests/test_graph.py`, `tests/test_vcs.py`, `tests/test_verdict.py`,
  `tests/test_undo.py`, `tests/test_novelty.py`)? A: Left as they are. Each names a unit a
  later PR of the pass deletes (pace, grants and setup, posture, graph, undo, novelty) or is a
  historical "proposed" note; editing them now is churn the later PR repeats.
- Q: Constitution version? A: 2.0.0: removing a governance rule is MAJOR under
  `.agents/skills/speckit-constitution`. The dated line also goes in the commit message
  (Governance section).

## Assumptions

- The design spec is amended only by its owner; the owner ordered this 9.2 replacement in the
  pass plan (#789), so this change carries it out.
- No local full suite: only the touched test files run; CI is the gate.
- `CHANGELOG.md` entries that mention the walk are history and stay.
- The edge table describes main as it stands: `gh pr create` for a recorded item warns naming
  `pr raise --item` below strict and is refused under strict. A later PR of the pass narrows
  the edges to exact argv and edits the rows then.

## Deferred

- None filed. Dangling 9.2 ids in comments go with the PRs that delete their units (see
  Clarifications).
