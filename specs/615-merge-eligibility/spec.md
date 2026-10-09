# Feature Specification: merge eligibility after a real day (risk evidence for plan add, the deploys question, size_exclude)

**Feature Branch**: `615-merge-eligibility`
**Created**: 2026-10-09
**Status**: Draft
**Input**: GitHub issue #615 (owner report, 2026-10-09): wuwei v0.23.0 ran a full autonomous day
under Claude Code desktop and three merge eligibility rules kept every pull request with the
owner. (A) `wuwei merge check` exits 2 with "approved item risk evidence is missing; replan the
item; run bin/wuwei plan add <item> again so its risk is measured" for every item admitted with
`plan add` after the gate: `merge.item_evidence` reads flags only from `plan.approved` and
`state.import` events, `plan add` writes a `plan.added` event without flags, and `plan add`
refuses an item already in the plan, so the advice cannot work. (B) `repos.merge_deploys`
defaults to `true`, so every merge is a deploy (owner-only, one-way) and auto-merge is silently
off for repositories that never deploy; calibration measures deploy signals but never proposes
`merge_deploys = false`, and nothing asks the owner. (C) `repos.merge.max_changed_lines` counts
generated data files: a 39k-line results JSON blocked a 1.4k-line change.

## Clarifications

### Session 2026-10-09

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Which event carries the risk evidence of an item admitted after the gate? A: `plan.added`,
  with `flags: {item: flags}`, the shape `plan.approved` uses. A discovery candidate carries its
  measured flags; an owner-named item carries all-False flags, as today (the owner naming it is
  the decision).
- Q: What does `plan add <item>` do for an item already in the plan? A: When no day's events
  hold risk evidence for it (an item admitted before this fix), it records the evidence from the
  item's flags in the day state as a `plan.added` event with `source: "replan"` and returns
  `{"action": "risk recorded"}`. The item flags are producer-owned (only `plan approve` and
  `plan add` write them; `state set` refuses `items.<id>.flags`), so this is the value admission
  wrote. With evidence present it is refused as today. No new event kind: `plan.added` already
  has its writer, signal class and metrics readers, and every reader keeps the first start.
- Q: Where does the evidence lookup live? A: One function, `merge.risk_evidence(root, name)`,
  read by `item_evidence` and by `plan add`.
- Q: How is `merge_deploys` set when calibration never proposes `false`? A: The owner answers a
  per-repository interview question, `deploys` ("Does merging a pull request in {repo}
  deploy?"), asked before `merge`. `Merges deploy` sets `repos.merge_deploys = true`, `Merges do
  not deploy` sets `false`. The answer is the explicit declaration design 4.6 asks for; the
  calibration rule "never proposes `merge_deploys = false`" stays true for calibration itself.
- Q: Which choice is recommended? A: The one listed first (`decision.widget`: the recommended
  option first; the terminal lists it as 1). `Merges do not deploy` only when calibration
  measured no deploy workflow, deploy deny command or never-auto path for that repository;
  `Merges deploy` when it measured one, or when it is unmeasured (fail closed). Setup reads the
  survey it runs anyway (moved before the interview); the cards and `calibrate --interview`
  read the approved snapshot `.wuwei/calibration.json`, so the interview still profiles no
  checkout and calls no port.
- Q: How does an existing workspace see it? A: Through `interview.unanswered`: no recorded day
  answers `deploys`, so `init --upgrade` and doctor count it and the next plan asks it on a card
  (`wuwei calibrate --questions`), like every new question.
- Q: How does `size_exclude` treat a rename? A: A file counts toward `max_changed_lines` unless
  every path it names (`path`, and `previous_path` when set) matches a `size_exclude` glob, so a
  rename into or out of an excluded path still counts. Matching reuses `merge.matched` (any path
  suffix), the never-auto rule. The completeness checks compare the unfiltered sums with the PR
  totals, and never-auto paths still apply to excluded files.

## User Scenarios and Testing

### User Story 1 - An item admitted after the gate can auto-merge (Priority: P1)

**Acceptance Scenarios**:

1. **Given** an approved gate, **When** `plan add` admits a discovery candidate or an
   owner-named item, **Then** the `plan.added` payload carries `flags: {item: <its flags>}`.
2. **Given** an item admitted with `plan add` and a clean pull request, **When** `merge check`
   runs, **Then** the item's risk evidence is found (exit 0 on the clean fixture).
3. **Given** an item in the plan with no risk evidence on any day, **When** `plan add <item>`
   runs, **Then** it records a `plan.added` event with `source: "replan"` and the item's flags,
   returns `risk recorded`, and `merge check` then finds the evidence.
4. **Given** an item in the plan with evidence, **When** `plan add <item>` runs, **Then** it is
   refused with `already in the plan` and no event is written.
5. **Given** no evidence, **When** `merge check` runs, **Then** exit 2 names
   `bin/wuwei plan add <item>` with the item's id.

### User Story 2 - Setup asks whether merges deploy (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a repository whose calibration measured no deploy signal, **When** its `deploys`
   card or terminal question is shown, **Then** `Merges do not deploy` is listed first.
2. **Given** a repository with a deploy workflow, or no measurement, **Then** `Merges deploy`
   is listed first.
3. **Given** the answer `Merges do not deploy` for `repos.N`, **When** it is promoted, **Then**
   `repos.N.merge_deploys = false` (and `true` for `Merges deploy`).
4. **Given** an upgraded workspace without a `deploys` answer, **Then** `interview.unanswered`
   lists `(deploys, <repo>)` for each repository.

### User Story 3 - Generated files do not block the size rule (Priority: P2)

**Acceptance Scenarios**:

1. **Given** `size_exclude = ["results/*.json"]` and a pull request whose only large file is
   `results/run.json`, **When** `merge check` runs, **Then** the size rule passes.
2. **Given** the same pull request without the setting, **Then** it is refused with
   `diff exceeds max changed lines`.
3. **Given** an excluded file that also matches a never-auto path, **Then** it is refused with
   `never-auto path`.
4. **Given** a rename from an excluded path to a counted one, **Then** its lines count.

## Requirements

- **FR-001**: `plan add` writes `flags: {item: flags}` in every `plan.added` payload.
- **FR-002**: `merge.risk_evidence(root, name)` returns the flags recorded for an item by
  `plan.approved`, `state.import` and `plan.added` events across days; `item_evidence` uses it.
- **FR-003**: `plan add` for an item already in the plan records the evidence from the item's
  state flags when `risk_evidence` is empty, and is refused otherwise.
- **FR-004**: The missing-evidence reason names `bin/wuwei plan add <item>` for the actual item.
- **FR-005**: A per-repository `deploys` interview question, before `merge`, sets
  `repos.merge_deploys`; the choice listed first follows `calibrate.deploys(facts)` and fails
  closed to `Merges deploy`.
- **FR-006**: `calibrate.deploys(facts)` is the one measure of "merges deploy" (profile's
  `merge_deploys` fact and the interview's recommendation).
- **FR-007**: `repos.merge.size_exclude`, a glob list defaulting to `[]`; files whose every path
  matches it do not count toward `max_changed_lines`.
- **FR-008**: The template carries a commented `size_exclude` line; configuration.md documents
  `repos.merge.size_exclude`, the `deploys` question and that calibration still never proposes
  `false` while the interview asks.

## Success Criteria

- **SC-001**: The 2026-10-09 day's items admitted after the gate reach `merge check` with
  evidence, and a stuck item recovers with one `plan add`.
- **SC-002**: A repository without deploys auto-merges after one setup answer, with no hand
  edit of `config.toml`.
- **SC-003**: A change with a large generated file is sized by its source lines.

## Assumptions

- The issue is #615. The three bugs share one cause class (an eligibility rule that kept every
  merge with the owner) and one feature, as the issue asks.
- `.wuwei/calibration.json` holds the approved deploy facts per repository
  (`deploy_workflows`, `deploy_deny`, `never_auto`); a repository missing there is unmeasured.
- A deploy file that calibration flags (instruction-like or unsafe text) contributes no fact, as
  for calibration's own `merge_deploys` proposal; the owner still answers the question.
- The replan event reuses `plan.added`; `why` shows it as one more `queued` line for the item.

## Design spec conflict (raised, not resolved)

Design 4.6 says "The diff is at most `merge.max_changed_lines` (default 400)". This feature
lets the owner exclude generated files from that count. The design spec is amended only by its
owner, so the pull request asks for (proposed text): "The diff, without the files whose every
path matches `merge.size_exclude` (default none), is at most `merge.max_changed_lines`
(default 400); never-auto paths still apply to every file." Since this changes an eligibility
rule, the pull request also proposes a 9.2 row: "I25 | A file excluded from the size rule still
meets the never-auto paths, and the diff completeness checks read every file | `merge.check` on
an excluded large file, an excluded never-auto file and an incomplete file list | #615".
`tests/test_invariants.py` pins its table to the design (`test_table_matches_the_checks`), so
the check is carried by the regression tests in `tests/test_merge.py` until the owner adds the
row.

## Deferred

- None.
