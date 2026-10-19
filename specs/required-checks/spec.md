# Feature Specification: a required status check that never ran on the head is a gap

**Feature branch**: `fix/required-checks`
**Item**: required-checks, tier full, goal G-1
**Input**: release PRs #1156 and #1157 merged with main's required checks (`test (3.11)`, `test
(3.12)`, `ziran-audit`) never run on their heads. release-please pushes with the workflow token,
which starts no workflow. `enforce_admins` is false, so an admin merge went through while GitHub
reported `mergeable_state` blocked. `wuwei evidence` said no gaps, because it reads only the checks
that reported.

## The promise in my words

`wuwei evidence` (and so the merge door and the board) learns which checks the PR's base branch
requires. It reads them from branch protection (the `protection.required_status_checks.contexts`
of `GET repos/{o}/{r}/branches/{b}`) and from the rulesets that apply to the branch (`GET
repos/{o}/{r}/rules/branches/{b}`, every page), both through REST. A required check with no
check run and no commit status of that name on the head is a safety gap that names the check. A PR
that GitHub reports as `mergeable_state` blocked, while WUWEI finds no safety gap that explains it,
gets a safety gap that says GitHub holds it for a reason WUWEI cannot name. When the protection or
rulesets read fails or is malformed, the evidence shows a waiting safety gap, so the merge door stays
shut. A branch with no protection, or protection without required checks, requires none and is not a
gap: the branch read answers it with `enabled: false` and no contexts, never a 404. The protection read is cached per repository and base branch for `PR_TTL` (15 minutes),
and a failed read is never cached. Files: `cli/wuwei/evidence.py`, `cli/wuwei/gh.py`, tests, the
vendored copy, docs. Runtime grows by at most 10 lines.

The acceptance scenarios, restated:

1. A PR whose head has CodeQL green and no run of the required check `test (3.11)`: `wuwei evidence`
   shows a safety gap naming `test (3.11)`, and the merge door refuses the merge.
2. A PR whose head has every required check green: the evidence is the same as on main.

## How this fails

1. A token that cannot read the branch or its rules (a revoked token, a repository renamed, a plan
   whose rules endpoint answers 403) gets an error on every read. Every PR in that repository then
   shows `required checks unreadable` and every merge is refused. This fails closed by design; the
   gap names the error so the owner can fix the token. The branch read needs only read access, so a
   token without Administration read still reads protection (checked live, unauthenticated, on
   `taoq-ai/wuwei` main).
2. A check is required by a name that the head reports under another name (a matrix job renamed, a
   status context with a prefix). The gap shows on every PR until protection or the workflow is
   fixed. GitHub blocks the same PRs, so WUWEI agrees with the host.
3. Right after a push, before GitHub creates the check runs, the head has no run of a required check.
   The gap shows for a few seconds beside `CI not started`, then clears on the next read once the
   runs exist. A cached PR entry is written only when its CI settled, so the gap is never held from a
   stale read of a running head.

## Clarifications

### Session 2026-10-19

- Q: Which read gives branch protection, and which 404 means "no protection"? A: The brief named
  `GET .../branches/{b}/protection/required_status_checks`. It needs Administration read and answers
  an unprotected branch with `gh: Branch not protected (HTTP 404)`, so WUWEI would have to tell that
  404 from a masked `Not Found` for a token without the right. `GET .../branches/{b}` carries the
  same `protection.required_status_checks` to anyone with read access (read live: main gives
  `test (3.11)`, `test (3.12)`, `ziran-audit` with `enforcement_level` `non_admins`; `wuwei/state`
  gives `enabled: false` and no contexts). WUWEI reads that, so no 404 means "no protection": every
  error, a 404 included, fails closed.
- Q: What counts as a run of a required check? A: A check run whose name, or a commit status whose
  context, equals the required context. A failing or running run is already `CI failing` or `CI
  running`; this item adds only the check with no run at all. The app id a protection rule names is
  not compared (assumption below).
- Q: What is a "reason WUWEI can name" for `mergeable_state` blocked? A: Any safety gap WUWEI already
  found at that read (a required check not run, CI failing or running, a gate, a thread, an owner
  review). Only a blocked PR with no safety gap gets the new gap. `unknown`, `clean`, `unstable`,
  `behind`, `dirty`, `draft` and a missing state add nothing.
- Q: How long is the protection read kept? A: `PR_TTL` (900 seconds), keyed by repository and the
  sha256 of the base branch name, so `a/b` and `a__b` never share an entry. A failed read is not
  kept. A board of many PRs on one base reads protection once per 15 minutes.
- Q: Does auto-merge pass with a required check not run? A: No. Only `CI running` is exempt for
  auto-merge; a required check that never ran waits forever, so arming auto-merge on it is refused.
- Q: Is the gap actionable or waiting? A: Actionable: nobody's run will start it, someone has to push
  or re-run. The unreadable gap is waiting, like `evidence unreadable`.

## User Scenarios & Testing

### US1: a required check with no run on the head holds the merge (P1)

Acceptance 1: protection requires `test (3.11)`, the head has CodeQL green. The gap names `test
(3.11)`, it is safety, and `guards.merge_door` refuses. A check required by a ruleset counts the same,
and a check required by both is named once.

### US2: every required check green reads as on main (P1)

Acceptance 2: protection and rulesets require checks that all ran green; the gaps equal those of the
same PR with no protection. A required check reported as a commit status counts as run.

### US3: no protection is not a gap, an unreadable read fails closed (P1)

An unprotected branch and a protected one with no required check read as none. A 403, a `Not Found`,
a `Branch not found`, a malformed answer and a failed or malformed rulesets read each give `required
checks unreadable on main: <error>`, and the merge door refuses.

### US4: GitHub's blocked state with no named reason is a gap (P1)

`mergeable_state` blocked with no other safety gap gives the blocked gap; blocked beside another
safety gap, and every other state, add nothing.

### US5: the protection read is cached per repository and branch (P2)

Two reads within `PR_TTL` call the host once; another base branch or repository reads its own; a
failed read is read again; a warm board makes no protection call.

## Requirements

- FR-001: `gh.required_checks(repo, branch)` returns the contexts required by protection (the
  branch read) and by the rulesets for the branch, once each, in their order; any error raises.
- FR-002: `gh.rules` reads every page of the branch's rules.
- FR-003: `gh.pr` carries `mergeableState` from the PR's `mergeable_state`.
- FR-004: `evidence.gaps` adds `required check[s] not run at <sha7>: <names>` (safety, actionable) for
  each required context with no check run or status of that name on the head.
- FR-005: a failed or malformed protection read adds `required checks unreadable on <base>: <error>`
  (safety, waiting) and is not cached.
- FR-006: `mergeable_state` blocked with no other safety gap adds `GitHub reports the merge blocked
  for a reason WUWEI cannot name: read the merge box on the PR` (safety, actionable).
- FR-007: the protection read is cached `PR_TTL` per repository and base branch.
- FR-008: runtime grows by at most 10 lines; `.claude/wuwei/` matches `cli/wuwei/`; the docs state
  the rule.

## Assumptions

- Matching is by context name only, not by the app id a protection check names. Overturned if a
  repository has two apps that report one check name and only one is trusted.
- The required read is kept 15 minutes. A rule the owner adds can take that long to hold. Overturned
  if the owner wants the merge door to read protection fresh.
- The recorded replay case gains answers for the two new reads (no protection, no rulesets), so it
  still gives its recorded gaps. Overturned if replay cases must never be edited.
- The branch read, not the `protection/required_status_checks` read the brief named, because it
  needs only read access and has no 404 for "no protection" to tell from a refusal. Overturned if a
  host answers the branch read without `protection` for some token; that reads as unreadable and
  fails closed, so the cost is a held merge, never a pass.

## Rollback

Revert the commit. No config key, ledger kind or file format changes; the `required-*` cache entries
expire in 15 minutes and nothing else reads them.
