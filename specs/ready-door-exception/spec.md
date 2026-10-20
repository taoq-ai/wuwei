# Feature Specification: the ready and reviewer doors honour an owner exception the way wuwei evidence does

**Feature branch**: `fix/1168-ready-door-exception`
**Item**: 1168, tier full, goal G-2
**Input**: taoq-ai/wuwei#1168. The owner accepted `exception: owner/repo#n at <sha7>: gates missing at
head <sha7>: goal`, the hook recorded it, and `wuwei evidence` dropped the gap. `gh pr ready` was still
refused twice with the same gap: the ready door never reads the exception.

## The promise in my words

Every route that turns a draft ready or asks a reviewer on a draft (`gh pr ready`, `gh pr edit
--add-reviewer`, the REST `ccr/ready_for_review` and `requested_reviewers` POSTs, the MCP
`update_pull_request` and `request_copilot_review` tools) ends in `guards.ready_door`. That door
judges through `create_door` and `evidence.gate_gaps` and never calls `evidence.excepted`, so an owner
exception that `wuwei evidence` and the merge door honour does not open it.

After this item the ready door drops a gate gap that an approved `exception` ruling names for that PR
(`<repo>#<number>`, as the door reads it) at that head, by the same rule as `wuwei evidence`: the
printed gap text, or the exact gate list, with case, spacing, end marks and a printed `[waiting]` set
aside (design section 5). A head that moved, another PR's ruling, or a ruling that names only part of
the gate list leaves the door shut.

`gate_gaps` lists the `verdict ... not counted: <why>` lines under a gate gap, to explain why a gate is
missing. When the owner accepts that gate gap, those lines go with it, in the ready door and in
`evidence.gaps`; today both would still hold the lines, and the merge door would refuse on them.

Out of scope: the create door (a PR opened ready has no number an exception can name) and how verdicts
count (the ready door still reads verdicts with no PR, as section 6 says).

The acceptance scenarios, restated:

1. Draft `acme/app#7` at `abc1234`, goal gate missing, an approved exception for `acme/app#7` at
   `abc1234` on `gates missing at head abc1234: goal`: `gh pr ready 7 --repo acme/app` passes.
2. The same ruling: `gh pr edit 7 --add-reviewer x`, the REST POST on `pulls/7/ccr/ready_for_review`
   and MCP `update_pull_request` with draft false each pass.
3. Accepted at `abc1234`, the head moved to `def5678`: `gh pr ready 7` is refused with `gates missing
   at head def5678: goal`.
4. A ruling for `acme/app#8`, or one naming only `security` of `gates missing at head abc1234:
   security, goal`: `gh pr ready 7` is refused.
5. An accepted gate gap and an unattested verdict file for the item: neither the ready door nor `wuwei
   evidence acme/app#7` lists the not-counted line.
6. The route corpus read through the guards at main and at the head: the PR lists every route whose
   verdict moves, and only ready-door routes with an approved exception move.

## How this fails

1. The door reads the PR as `O/R#7` (a `-R O/R` flag) while the ruling was recorded as `o/r#7`. The
   ruling's `pr` is compared exactly, as in `wuwei evidence`, so the exception does not apply and the
   door stays shut. This fails closed; the agent names the repository as the question did.
2. The compare call's last commit is not the PR head (a base moved under the branch). The door names
   the compare head in its gap and checks the exception at that same head, so the gap the owner
   accepted and the gap the door waives are always the same text. A ruling at another sha waives
   nothing: fails closed.
3. A not-counted line explains a gate gap that is not the one accepted, for example a delta-review gap
   the ruling does not name. Only one gate gap is listed per read, and the lines are dropped only
   when a gate gap was dropped, so a standing gate gap keeps its explanation.

## Clarifications

### Session 2026-10-20

- Q: Which head does the ready door check the ruling against? A: The head its own gap names, the last
  commit of the compare between base and branch. It equals `headRefOid` on a current branch, and the
  owner accepts the gap text the door printed.
- Q: Which PR reference does the ruling need? A: `<repo>#<number>` exactly as the door reads them,
  the form `evidence.gaps` builds for the merge door.
- Q: Does the create door honour exceptions? A: No. It runs before a PR number exists, so it passes
  no reference and keeps its behaviour.
- Q: Which not-counted lines go with an accepted gate gap? A: Every `verdict <path> not counted:
  <why>` line in the same read. `gate_gaps` lists them only after a gate gap, and a read has at most
  one gate gap.
- Q: Does the probe of `excepted-exact` change? A: Its oracle learns the new rule: a not-counted line
  is named when the accepted gap names a gate gap in the same list. All other pairs keep their
  verdicts.

## User Scenarios & Testing

### US1: an accepted gate gap opens every ready and reviewer route (P1)

Acceptance 1 and 2 through the READY route list and the MCP tools.

### US2: a moved head, another PR or a partial gate list keeps the door shut (P1)

Acceptance 3 and 4.

### US3: the not-counted lines go with the accepted gate gap (P1)

Acceptance 5 in the ready door and in `evidence.gaps`.

### US4: only ready routes carrying an exception move in the route corpus (P1)

Acceptance 6, by `specs/ready-door-exception/route_probe.py` at main and at the head.

## Requirements

- FR-001: `guards.ready_door` applies `evidence.excepted` to its gate gaps with the PR's reference and
  the head its gaps name.
- FR-002: `guards.create_door` without a reference is unchanged.
- FR-003: `evidence.excepted` drops the `verdict ... not counted` lines when it drops a gate gap.
- FR-004: runtime grows by at most 5 lines; `.claude/wuwei/` matches `cli/wuwei/`.

## Assumptions

- The ruling's PR reference is matched exactly, as in `evidence.gaps`. Overturned if the owner wants a
  case-insensitive match in both readers.
- The excepted-exact probe's oracle is extended, not left as is, since the item asks the not-counted
  lines to go. Overturned if a gate reads that probe's oracle as frozen.

## Rollback

Revert the commit. No config key, ledger kind or file format changes; an exception recorded before
or after reads the same.
