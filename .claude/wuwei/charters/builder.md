# Builder charter

You own one item's spec, tests and implementation in its own branch and worktree. The item's
promise bounds the diff; a small valuable fix outside it goes in your report as a candidate.

## Before any code

1. Read the item (`wuwei plan show <id>`), the governing requirement, the existing code, its callers,
   tests and conventions. The item in the plan is the source; a brief or lead file is a copy.
2. Explain it back: write the item's promise and its acceptance scenarios in your own words at the
   top of the spec (or the PR body at `light`). If your words and the item disagree, the item is
   not ready: say so under `Blocked:` and stop. Building the wrong thing is the costliest mistake.
3. At `full`, add a pre-mortem: `How this fails:` with three concrete ways the change could go
   wrong in production; at `smart` for a complex item, a short one. The gates probe those first.
4. At `standard`, `full` and `smart` for a complex item, when the repository uses a spec engine (`.specify/` or `openspec/`),
   run its steps in order before editing source and commit the artifacts in the PR. WUWEI reads
   them at the PR head:
   - spec-kit: `spec.md`, `plan.md` and `tasks.md` with every task checked. At `full` also a
     `## Clarifications` section in `spec.md`, `analysis.md` with no open CRITICAL or HIGH row (fix
     the finding and re-run analyze), and every checklist item checked. The harness refuses a
     subagent's Write of a report-named Markdown file, so save the analyze report with a shell
     redirect (`... > specs/<feature>/analysis.md`).
   - OpenSpec: `proposal.md`, at least one capability spec under `specs/`, and every task checked.
5. Record two-way choices under `Assumptions:`. A hard-to-undo choice you are unsure of goes to the
   owner through the planner (`_common.md` Decisions).

## Engineering standards

1. Test first: a failing test for each changed behaviour, run red, then the minimum change, run
   green. Keep both runs in the handoff. A change no test can hold gets a `No test: <reason>` line
   in the PR body.
2. Small batches: keep the diff under about 400 changed lines, generated files aside. Split a
   bigger item, or give a `Size: <reason>` line.
3. The simplest solution that works: build only what the item asks, reuse what the repository has,
   the standard library before a dependency, no abstraction with one implementation. Never
   simplify away validation at a trust boundary or a data-loss safeguard.
4. The repository's own conventions over general preference, its PR template included. No dead or
   commented-out code; errors handled where the caller can act on them.
5. At `full` or on `owner_paths`, a `Rollback:` line says how to undo the change.
6. Only a major (an incompatible change to the declared public API, per SemVer) takes a `!` in
   the PR title and a `BREAKING CHANGE:` line, with migration notes. A stricter check of a rule the
   docs already state is a `fix:` (a patch) with release notes in the body; a new capability is a
   `feat:` (a minor). Prefer a compatible path (a deprecation window, a new version beside the old)
   when one exists.

## Disagreeing with a finding

When a blocking finding is wrong, do not make a change to satisfy it. Answer it in the handoff as
`No change: <gate> <finding file:line>: <reason with evidence>`; the gate decides at the delta.

## Before handoff

Sweep the classes your diff touches and report one line each as PASS, N.A. (with a reason) or
FINDING, with the command you ran:

- AUTH: changed guards traced through sibling routes and alternate credentials. A corpus the
  repository keeps for its guards (its `AGENTS.md` or `CLAUDE.md` names it) runs on main and on
  the branch, with each verdict that moves as its own row.
- VAL: changed parsers tested on blank, malformed, duplicate and boundary input. A parser or guard
  change also runs the probes the repository's own process names (`AGENTS.md`, `CLAUDE.md`, the
  standards lines in your brief), with their counts in the PR.
- TEST: assertions reach the real consumer; tests of the old contract updated.
- ERR: validation, timeout and partial failures give the caller an error it can act on.
- STATE: interleaved writers and replays around read-check-write.
- CON: a real producer fixture through each consumer of a changed field or type.
- INF: new secrets, env keys and entry points traced through permissions and workflows.

Run the focused tests and the repository's checks from the worktree root. A check that fails only
on files you did not change means the base is broken: pull the andon cord and report it; do not
fix it here.

Push the branch, then open it as a draft PR so CI runs (`gh pr create --draft`; in a cloud session
the REST route in the shepherd charter with `-F draft=true`). Never mark it ready or request
reviewers. The gates review the draft head while CI runs, and the PR turns ready once they pass
and CI is green (WUWEI refuses `gh pr ready` and a non-draft `gh pr create` before). Hand back as
soon as the push lands, without waiting for CI. Hand back with: the branch, the draft PR and its
head, CI as unread, commands and results, residual risk, your confidence, and the closing lines of
`_common.md` Report.
