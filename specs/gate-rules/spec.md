# Feature Specification: gates stay out of the main worktree, write verdicts with Write, re-run surviving mutants and show shell findings by stub execution; approval checks the line budget

**Feature branch**: `claude/gate-rules`
**Item**: gate-rules, tier full, goal G-1
**Input**: findings from the seats on 2026-10-16: two gates checked out commits in the main
worktree, heredoc verdicts naming door programs were refused, a wrong env-wrapper claim became an
acceptance line without a real run, draft-raise was approved at +25 lines and landed at +37, and
two wording sites lag #1102 (PRs open as drafts first) and the cloud check-in.

## The promise in my words

Charter rules, built into `agents/`, plus four wording fixes. The runtime does not grow.

1. `_common.md` Evidence 4 and `_gate.md` rule 3: never check out, reset or build in the main
   worktree; copy the tree with `git archive` or `git worktree add` into the scratch folder.
2. `_gate.md`, The verdict: write the verdict file with the Write tool, never a shell heredoc,
   because the Bash door refuses a heredoc that names a door program.
3. `_gate.md` rule 3: re-run every mutant listed as surviving, in a fresh copy, before listing it.
4. `_gate.md` rule 4: a finding about how a shell, wrapper or gh parses a command names a run with
   a stub program on PATH (or gh with `http_unix_socket` pointed at a logging server); without
   that run it is a note.
5. `sentinel-security.md`: a normalisation round probes one input per path class (`//`, `%xx`,
   `/./`, `/../`) and per working-directory wrapper (`cd`, `env -C`, `sudo -D`).
6. `builder.md` AUTH sweep: for a guard change, run the route corpus on main and on the branch,
   record the sha256 of `tests/fixtures/routes.json`, and list a refusal naming a different PR or
   repository as its own row.
7. `planner.md` approval and `lead.md` Scope: an item adding runtime lines states an estimate and
   a budget about 1.5 times it; the planner checks the budget against the headroom (3,000 minus
   the measured lines) before asking for approval and orders a free-lines item first when it does
   not fit.

Wording: the verdict template PR line (`_gate.md:46`, `verdict.py:12`, `verdict.py:49`,
`docs/site/reference.md:79`, all checked at e34586d) says `<owner/repo>` alone before its draft PR
exists. The Stop hook line (`hook.py:90-91`) says nothing will wake the session unless a check-in
or PR subscription is armed, which WUWEI cannot see.

Outside: any guard or evidence rule in code; #1078's attestation path.

The acceptance scenarios, restated:

1. `bin/wuwei agents build` leaves `agents/` matching the charters, the drift test passes, and each
   `agents/sentinel-*.md` holds the main-worktree, Write-tool, mutant re-run and stub rules.
2. `verdict.parse` still accepts `PR: taoq-ai/wuwei` alone; a malformed PR line gets an error that
   names `<owner/repo> before its draft PR exists`.
3. With only waiting work and no watch pass in the last hour, the Stop line says nothing will wake
   the session unless a check-in or PR subscription is armed.
4. The runtime line count after the change is at most the count before (3,000).
5. `charters/planner.md` approval step names the budget check against headroom and the
   free-lines-first order.

## How this fails

1. The new Stop line grows past its two source lines and pushes the runtime over 3,000, failing
   `test_the_runtime_holds_its_size_budget`. Held: the edit replaces two lines with two lines; the
   count stays 3,000.
2. A gate copies the tree with `git worktree add` but then runs a checkout from the main worktree's
   cwd and still moves the main HEAD. The rule names the forbidden actions (check out, reset,
   build) on the main worktree, not only the copy method, so the gate can check itself against it.
3. The stub rule turns every real shell-parsing defect into a note when a gate cannot set up a
   stub, so a true bypass ships. The rule binds only parsing claims; a guard mutant with a concrete
   bad input still blocks under rule 3, and a trust-boundary security finding always blocks.

## Clarifications

### Session 2026-10-16

- Q: Where does the stub rule go, a new numbered rule or rule 4? A: Rule 4, which classifies what
  blocks; no renumbering, so no citation by number moves.
- Q: `builder.md` serves every repository, yet the rule names `tests/fixtures/routes.json`. A: The
  promise names it, and the file exists on main. A repository without it writes N.A. for that part
  of the sweep, as the sweep already allows.
- Q: `planner.md` is not built into `agents/` (the planner is the owner's session). A: It is still
  vendored into `.claude/wuwei/charters/`; acceptance 5 reads the charter.
- Q: Which tests change? A: `test_verdict.py` gains a wording test (acceptance 2), `test_hook.py`
  asserts the new Stop wording (acceptance 3), and `test_setup.py` asserts the four gate rules and
  the new PR wording in every built sentinel (acceptance 1).

## User Scenarios & Testing

### US1: built sentinels carry the four gate rules (P1)

Acceptance 1. Red: `test_every_gate_carries_the_worktree_write_mutant_and_stub_rules` fails for
all four sentinels before the charter edits. Green after the build.

### US2: the PR line says draft PR (P1)

Acceptance 2. Red: `test_the_pr_line_wording_says_gates_run_before_the_draft_pr_exists` fails on
the old error. Green after the verdict.py edit; the bare-repository test still passes.

### US3: the Stop line names the armed check-in (P1)

Acceptance 3. Red: `test_waiting_work_with_no_watch_armed_asks_once_to_arm_it` fails on the old
line. Green after the hook.py edit.

### US4: the runtime does not grow (P1)

Acceptance 4, held by `test_the_runtime_holds_its_size_budget` and `wc -l cli/wuwei/*.py`.

### US5: approval checks the budget (P2)

Acceptance 5, read in `charters/planner.md` The day 3.

## Requirements

- FR-001: `_common.md` Evidence 4 and `_gate.md` rule 3 forbid check out, reset and build in the
  main worktree and name `git archive` and `git worktree add`.
- FR-002: `_gate.md` The verdict says Write tool, never a heredoc, with the reason.
- FR-003: `_gate.md` rule 3 says re-run each surviving mutant in a fresh copy before listing it.
- FR-004: `_gate.md` rule 4 holds the stub-execution rule.
- FR-005: `sentinel-security.md` rule 6 holds the normalisation round.
- FR-006: `builder.md` AUTH line holds the route corpus differential.
- FR-007: `lead.md` Scope 3 and `planner.md` The day 3 hold the budget rule.
- FR-008: the PR line wording in `_gate.md`, `verdict.py` (both sites) and `reference.md`; the
  Stop line in `hook.py`. Runtime line count unchanged.
- FR-009: `agents/` rebuilt, `.claude/` re-vendored.

## Assumptions

- The Stop line keeps the `/loop 20m /wuwei-watch` advice and says "in the cloud both" for the PR
  subscription and check-in; the promise only asks for the "unless armed" clause. Overturned if
  the owner wants the advice dropped.
- free-lines-3 (draft PR #1104) also edits `hook.py` and `verdict.py`; a merge of origin/main
  resolves any overlap. Overturned if #1104 rewrites the same two lines differently.

## Rollback

Rollback: revert the commit, then run `bin/wuwei agents build` and `setup.vendor('.')`. No config,
ledger or file format change; the parser accepts the same inputs.
