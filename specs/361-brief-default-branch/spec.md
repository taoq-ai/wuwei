# Feature Specification: item worktrees use their repository's default branch, and plan propose reads the scanner findings list

**Feature Branch**: `361-brief-default-branch`
**Created**: 2026-10-03
**Status**: Ready for implementation
**Input**: Issue #361, fix(brief). UX adoption sweep of 2026-10-03, findings F2 and F3 (no
dependencies). Owner's brief for the sweep: adoption should be as easy as possible, and the
workflow should coach people instead of simply blocking. Design 5.7 (every discovery source
reports "unmeasured" when it cannot be read; it never stops the plan) and the vcs port row of
the adapter table (`merge_base(repo, ref)`).

## Findings from the sweep (pasted from the review)

| ID | Where | What happens today | Coaching fix |
| --- | --- | --- | --- |
| F2 | first plan | Setup proposes `adapters.scanner = "ziran"` whenever `ziran` is on PATH. `plan propose` then exits 2 `wuwei plan: invalid scanner findings`: `discovery.py:202` expects a list, the adapter returns `{files_analyzed, findings}`. Every owner with ZIRAN installed cannot plan. | Read `result.data["findings"]`; a scanner failure marks the source unmeasured in the sweep and the plan continues. (Setup asking before turning a scanner on belongs to the setup issue.) |
| F3 | first builder brief | `brief.py:245` finds the repository by path equality, which never matches an item worktree, so it falls back to `origin/main`. Repositories on `master` or `develop` get `wuwei brief: git.merge_base: could not run: git exited 128`. | Resolve the repository through the worktree; on a missing remote ref say `origin/master not found in widget; run git -C widget fetch origin`. |

Catalogue rows (section d) for these two findings:

| Location | Reason today | Rewrite from the review |
| --- | --- | --- |
| `adapters/vcs/git.py` `merge_base`, surfaced by `brief.py` | `git.merge_base: could not run: git exited 128` | `origin/<branch> is not in this checkout; run git -C <repo> fetch origin, then retry.` |
| `cli/wuwei/discovery.py:203` (internal invariant) | `invalid scanner findings` | Not an owner message: the shape is the adapter's documented report, so read it; a real failure is an `unmeasured` sweep line, never an exception. |

## Root cause (read on main, ed28ab4)

### F3: the brief never finds the repository of an item worktree

`cli/wuwei/brief.py` `write()`:

- line 245: `repo = next((r for r in config['repos'] if (root / r['path']).resolve() == tree), {})`.
  Item worktrees live at `worktrees/<item>` under the workspace, so `tree` never equals a
  configured checkout path and `repo` is `{}`.
- line 246: `ref = config['brief']['remote'] + '/' + repo.get('default_branch', 'main')`
  becomes `origin/main` for every item worktree, whatever the repository's
  `default_branch` says.
- line 247: `read(vcs.merge_base, tree, ref, root=root)` runs `git merge-base HEAD
  origin/main` (`adapters/vcs/git.py:258-259`), which exits 128 when the repository has no
  `origin/main`. `read()` (brief.py:85-91) raises `ValueError('git.merge_base: could not
  run: git exited 128')` and `commands/brief.py:47-49` prints `wuwei brief: ...` and exits 2.

The worktree anchor (`wuwei-workspace` in the worktree's git directory, read by
`workspace.worktree_workspace`, workspace.py:234-251) names the workspace only, not the
repository. The repository of a worktree is the configured repository that shares its git
common directory. That lookup already exists once: `guards/commit_push.context(cwd, {}, {},
root, identity=False)` (commit_push.py:59-91) returns the configured repository whose common
directory matches, or raises `repository is not configured in this workspace`.
`commands/build.py:_repo` (lines 83-90) already does exactly "path equality, else
`commit_push.context`" for `build next`. `brief.py:245` is the only other path-equality
lookup of a repository from a worktree in `cli/`.

Reproduced read-only in a throwaway workspace (the notes name no dry-run workspace): a
repository `acme/widget` on `master` pushed to a bare `origin`, `default_branch = "master"`
in `[[repos]]`, `git worktree add worktrees/X`; `brief.write('builder', 'X', 'b1', 'body',
worktree='worktrees/X')` raises `ValueError: git.merge_base: could not run: git exited 128`.
In the same workspace `commit_push.context(<worktree>, {}, {}, root, identity=False)[0]`
returns the `acme/widget` entry.

### F2: discovery reads the audit report as if it were the findings list

`cli/wuwei/discovery.py` `discover()`, lines 192-206:

- line 198 calls `scanner.audit(<repo path>)`. The ZIRAN adapter returns
  `Result(code, report)` where `report` is the validated audit report
  `{"files_analyzed": <int>, "findings": [...]}` (`adapters/scanner/ziran.py:173-190` and
  `211-220`; recorded shape in `tests/fixtures/scanner/audit.json`).
- line 202 checks `isinstance(result.data, list)`, which a report dict never is, so line 203
  raises `ValueError('invalid scanner findings')`. `plan.propose` (plan.py:95) lets it
  through and `wuwei plan propose` exits 2. The watch sweep (`watch.py:226`) and `wuwei
  discover` fail the same way.
- Even with a list, line 204 `found.extend(result.data)` would hand ZIRAN finding rows
  (`rule`, `severity`, `file`, `line`, `message`) to `dedupe()`, which requires an `id` on
  every candidate (discovery.py:30-31) and would raise `scanner: candidate id required`.
- A result outside the port contract raises instead of marking the source unmeasured, unlike
  the tracker branch of the same function (lines 81-88).

Reproduced in-process: with `adapters.scanner = "ziran"` and one repository, `discover()`
with a scanner port returning `Result(1, <recorded report>)` raises `ValueError: invalid
scanner findings`. No test covers the scanner branch of `discover()` today.

## User Scenarios & Testing

### User Story 1 - A builder brief in an item worktree measures against the repository's default branch (Priority: P1)

The owner's repository uses `master` (or `develop`). After the morning gate a seat writes a
builder brief for an item whose worktree is `worktrees/<item>`. The brief header shows the
merge base against `origin/master`, and the build loop continues. When the remote branch is
not in the checkout, the refusal says which ref is missing, in which repository, and the one
command that fixes it.

**Why this priority**: today the first builder brief on any repository whose default branch
is not `main` exits 2, so the day cannot start building.

**Independent Test**: `python -m pytest -q tests/test_brief.py -k "default_branch or merge_base or not_configured"`.

**Acceptance Scenarios**:

1. **Given** a configured repository `acme/widget` at `widget` with `default_branch =
   "master"`, `origin/master` present, and an item worktree `worktrees/X` of that
   repository, **When** `bin/wuwei brief builder X <name> --worktree worktrees/X` runs,
   **Then** it exits 0 and the brief header has `Merge-base: <sha> (origin/master)`.
2. **Given** the worktree is the configured checkout itself, **When** the brief is written,
   **Then** the ref comes from that repository's `default_branch` as today (no extra git
   read).
3. **Given** no repository is configured, **When** a brief names a worktree, **Then** the ref
   stays `origin/main` as today.
4. **Given** the same setup as 1 but `origin/master` is not in the checkout, **When** the
   brief is written, **Then** it exits 2, writes no brief and no `brief written` event, and
   stderr reads `wuwei brief: no merge base with origin/master in acme/widget
   (git.merge_base: could not run: git exited 128); run git -C <worktree path> fetch origin,
   then write the brief again`.
5. **Given** repositories are configured and the worktree belongs to none of them, **When**
   the brief is written, **Then** it exits 2 with `repository is not configured in this
   workspace`, the same reason `build next` and the commit guard give, and writes no brief.

---

### User Story 2 - plan propose reads the ZIRAN findings and survives a scanner that cannot run (Priority: P1)

The owner has ZIRAN installed and `adapters.scanner = "ziran"`. The morning `plan propose`
lists the scanner's findings under Discovery intake and shows `discovery.scanner: measured:
<n>` in the sweep. When ZIRAN cannot run, the sweep says why and the plan is still proposed.

**Why this priority**: today every owner with ZIRAN configured cannot plan at all.

**Independent Test**: `python -m pytest -q tests/test_plan.py -k scanner`.

**Acceptance Scenarios**:

1. **Given** `adapters.scanner = "ziran"`, one repository `acme/widget` at `widget`, and a
   fake ZIRAN whose audit prints the recorded report (one high `SA003` finding in
   `vulnerable.py` line 5) and exits 1, **When** `bin/wuwei plan propose <input>` runs,
   **Then** it exits 0, the proposal sweep has `discovery.scanner: measured: 1`, and the
   Discovery intake lists `acme/widget:scanner:SA003:vulnerable.py:5: high SA003
   vulnerable.py:5: Untrusted input reaches eval`.
2. **Given** the audit report has no findings and exits 0, **Then** the sweep has
   `discovery.scanner: measured: 0` and the command exits 0.
3. **Given** ZIRAN cannot run (version below 0.39.0, the audit command exits 3, or prints
   malformed JSON), **When** `plan propose` runs, **Then** it exits 0 and the sweep has
   `discovery.scanner: unmeasured: acme/widget: ziran audit: unmeasured: <cause>`.
4. **Given** a scanner port answers outside the contract (a list instead of the report, a
   report without a `findings` list, an exit code outside 0 to 2, or not a `Result`),
   **When** discovery runs, **Then** the source reads `unmeasured: acme/widget: invalid
   scanner result` and nothing raises.
5. **Given** the scanner is unmeasured, **When** `bin/wuwei discover` runs, **Then** it still
   exits 2 (any unmeasured source is exit 2, unchanged), and exits 0 once the scanner
   measures.

### Edge Cases

- Several repositories: the first one whose audit is unmeasured makes the whole source
  unmeasured and names that repository; no partial count is reported (same rule as today).
- The same finding found again later in the day dedupes by its stable id.
- Scanner candidate ids contain `:` and `/`, so intraday intake never auto-admits them (it
  skips ids that are not plain item names, as it does for review-bot findings); they reach
  the owner through the proposal's Discovery intake.
- A gate brief on a dirty item worktree is still refused for the dirty tree, after the
  merge base is read, as today.

## Requirements

### Functional Requirements

- **FR-001**: When a brief names a worktree that is not a configured checkout path and
  repositories are configured, the brief MUST find the repository through the shared git
  common directory, with the same lookup `build next` uses, and take the ref from that
  repository's `default_branch`.
- **FR-002**: A worktree that is a configured checkout MUST keep today's path match; with no
  repository configured the ref MUST stay `<remote>/main`.
- **FR-003**: When the merge base cannot be read, the brief MUST exit 2 with a reason that
  names the ref, the repository and the fetch command with the real worktree path and remote,
  and MUST write no brief.
- **FR-004**: Discovery MUST read the findings from the scanner's audit report and turn each
  into a candidate with a stable id (`<repo name>:scanner:<rule>:<file>:<line>`) and one-line
  evidence (`<severity> <rule> <file>:<line>: <message>`).
- **FR-005**: A scanner audit that cannot run, or a result outside the port contract, MUST
  mark the scanner source `unmeasured: <repo name>: <reason>` and MUST NOT raise; `plan
  propose` MUST still exit 0.
- **FR-006**: Regression tests MUST cover both findings, the scanner one with a fake ZIRAN
  that returns the recorded report shape through the real adapter.

### Key Entities

- **Scanner candidate**: one ZIRAN finding as a discovery candidate: `id`, `evidence`,
  `source = "scanner"` (added by `dedupe`).

## Success Criteria

### Measurable Outcomes

- **SC-001**: On a repository whose default branch is `master` or `develop`, the first
  builder brief in an item worktree succeeds with 0 manual steps when the remote branch is
  fetched.
- **SC-002**: When the remote branch is missing, the refusal contains the one command that
  fixes it, with real values, and running it then rewriting the brief succeeds.
- **SC-003**: With ZIRAN configured, 100% of `plan propose` runs exit 0 whether the scanner
  measures or not, and the sweep line says which.

## Assumptions

- The issue's `sweep.scanner` is the proposal sweep key `discovery.scanner`
  (plan.py:108-109 prefixes every discovery source with `discovery.`).
- A worktree inside a workspace that belongs to no configured repository is refused with the
  existing `repository is not configured in this workspace` reason, as `build next` and the
  commit guard already do; before this fix it silently measured against `origin/main`.
  Rewording that reason belongs to the refusal-catalogue issue of the same sweep.
- `workspace.py` needs no change: its anchor names the workspace, not the repository, and the
  repository lookup by common directory already lives in `guards/commit_push.context`.
- The fetch hint uses the worktree path: fetching inside a worktree updates the shared
  repository's remote refs.
- The merge base failure is reported as a missing merge base, not as a missing ref, because
  `git merge-base` exits 128 for both and the fetch is the right first step for either.
- Finding rows are trusted as validated by the adapter (`ziran._report`); the core checks only
  the container shape, as the review-bot branch does.
- Evidence carries ZIRAN's rule message unredacted, like review-bot evidence; CLI output is
  already filtered for known credentials.
- Setup asking before it turns the scanner on (the rest of F2) is in the setup issue of the
  same sweep, not here.
- The notes name no dry-run workspace; both failures were reproduced in a throwaway workspace.
