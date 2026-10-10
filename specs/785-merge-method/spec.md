# Feature Specification: the merge method follows the repository

**Feature Branch**: `785-merge-method`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #785 (owner, 2026-10-10, item 75): WUWEI merges only with squash; a
repository whose base branch forbids squash merges sends every green PR to the owner.
Deliver `repos.<n>.merge_method = squash|merge|rebase|auto` (default `auto`); under `auto` the
code host port reads the repository's allowed merge methods and WUWEI picks squash, then
rebase, then merge; `merge check` names the method; the squash subject and body rules apply
to squash only, a merge commit keeps the PR title.

## Root cause (read on main at cb33150, reproduced read-only)

Reproduction: `tests/test_merge.py::test_squash_must_be_allowed` and
`tests/test_code_host.py::test_protection_measures_squash` run green on main in this
worktree: a repository that reports `allow_squash_merge: false` (or a ruleset whose
`allowed_merge_methods` lacks `squash`) yields `squash: False`, and `merge.check` refuses with
`<repo> does not allow squash merges into <base>; WUWEI merges only with --squash: ask the
owner to merge it in a host terminal`, whatever the repository does allow. The squash-only
assumption sits in five places:

1. `adapters/code_host/github.py:443` and `:471-474`: `protection` measures one boolean,
   `squash`, from `allow_squash_merge` and a ruleset's `allowed_merge_methods`; it never
   reads `allow_merge_commit` or `allow_rebase_merge`.
2. `cli/wuwei/merge.py:317-321`: `check` requires `protection['squash']`, so a merge-only
   repository is a policy refusal (exit 1) before any other rule.
3. `adapters/code_host/github.py:65`: the `_run` allowlist admits only
   `pr merge <url> --squash --match-head-commit <sha>`; `merge` (`:615-619`) always passes
   `--squash`.
4. `cli/wuwei/merge.py:453-455`: `owner_command`, the host-terminal command the owner is
   asked to run, always says `--squash`.
5. `cli/wuwei/workspace.py:69-80`: the `repos` schema has no method setting.

Two post-merge reads also assume a squash commit, and would break once WUWEI merges with a
merge commit:

- `adapters/code_host/github.py:524`: `history(..., patches=True)` (the 14-day outcome read,
  `cli/wuwei/merge.py:694-695`) refuses a base commit with more than one parent
  (`nonlinear base history`). After a merge commit that is exit 2, written as
  `monitor_error`, and `merge.check:297` then holds every later merge in that repository
  (`post-merge observations are unmeasured`) for days 14 to 28 of each merged PR.
- `cli/wuwei/merge.py:697`: the breaker's revert test matches
  `This reverts commit <sha>.`; the revert of a merge commit (`git revert -m 1`, and GitHub's
  revert of a merge-commit PR) reads `This reverts commit <sha>, reversing changes made to
  <parent>.`, so a reverted merge-commit PR would never trip the breaker.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Where does the setting live? A: `repos.<n>.merge_method`, next to `merge_deploys` in the
  repository table, as the issue names it: `auto` (default), `squash`, `rebase` or `merge`.
- Q: Who decides the method? A: The adapter reports the allowed methods (mechanics:
  `protection(repo, branch)['methods']`, the repository's `allow_*` flags narrowed by every
  ruleset's `allowed_merge_methods`). The choice is policy, one pure function in
  `cli/wuwei/merge.py`: an explicit setting is used only when allowed; `auto` takes the first
  allowed of squash, rebase, merge; nothing allowed is `None`.
- Q: An explicit setting the repository does not allow? A: A policy refusal (exit 1) naming
  the method, the base and `repos.merge_method`, routed as today's squash refusal (the
  owner's grant path, `no grant lifts this` under a grant). WUWEI never falls back to another
  method behind an explicit setting.
- Q: A repository that reports none of the three fields, or a non-boolean? A: Exit 2 as today
  for `allow_squash_merge` (fail closed): all three are read from the same repository
  response.
- Q: How does `merge check` name the method? A: Its exit 0 evidence carries `method`
  (printed in the JSON), the refusal names the method, and the owner's host-terminal command
  (`owner_only` tier, `merge.owner_paths`) carries `--<method>`.
- Q: Subject and body? A: WUWEI passes no `--subject` or `--body` to `gh pr merge` today, so
  the repository's own commit message settings already apply per method; a merge commit keeps
  what the repository writes (the PR title when the repository says so). Nothing changes.
- Q: The 14-day outcome measure for a non-squash merge? A: Measured for squash only. A merge
  commit or rebase merge is still followed for red base checks and reverts (the breaker), and
  is left out of the escaped-defect cohort instead of failing the watch. Line tracking through
  a nonlinear or multi-commit history is a follow-up (Deferred).
- Q: Is this a decision rule? A: Yes (the 4.6 merge precondition changes), so it gets a 9.2
  invariant row and a check in `tests/test_invariants.py`, and a 4.6 amendment line, as #668
  did.

## User Scenarios and Testing

### User Story 1 - A merge-only repository is merged by WUWEI (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a repository that allows only merge commits and the default
   `merge_method = auto`, **When** `wuwei merge check <pr>` runs on an otherwise clear PR,
   **Then** it exits 0 and its JSON carries `"method": "merge"`; **When** `wuwei merge <pr>`
   runs, **Then** the code host merge is called with method `merge` (argv
   `pr merge <url> --merge --match-head-commit <sha>`) and the journal evidence records
   `method: merge`.
2. **Given** a repository that allows squash (alone or with others), **When** the same
   commands run, **Then** today's behaviour: method `squash`, argv `--squash`.
3. **Given** squash forbidden and rebase and merge allowed, **Then** method `rebase`.

### User Story 2 - The owner pins the method (Priority: P2)

**Acceptance Scenarios**:

1. **Given** `merge_method = "merge"` and a repository that allows squash and merge,
   **Then** method `merge`.
2. **Given** `merge_method = "merge"` and a repository that allows only squash, **Then**
   `merge check` exits 1 naming `does not allow the merge method into main` and
   `repos.merge_method`, and no merge is called.
3. **Given** `merge_method = "fast"`, **Then** config load refuses it.

### User Story 3 - The owner's command and the watch follow the method (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a merge-only repository and `merge.default_tier = owner_only` (or a
   `merge.owner_paths` match), **Then** the printed host-terminal command is
   `gh pr merge <url> --merge --match-head-commit <sha>`.
2. **Given** a journaled merge with method `merge` aged 14 days, **When** the watch polls,
   **Then** history is read without patches, no outcome is recorded and the poll is not
   unmeasured.
3. **Given** a journaled merge whose merge commit is reverted with
   `This reverts commit <sha>, reversing changes made to <parent>.`, **Then** the breaker
   trips as it does for a squash revert.

### Edge Cases

- A repository that allows no method WUWEI uses (all three false, or a ruleset that narrows
  to nothing): exit 1, `allows no merge method into <base>`, the owner merges.
- A ruleset listing `squash` while `allow_squash_merge` is false: squash is not allowed (the
  intersection).
- Protection evidence whose `methods` is not a list of known method names: exit 2.
- A journal entry written before this feature (no `method` in its evidence) is a squash merge
  for the watch.
- A merge queue repository keeps today's path (`merge_queue` true): the chosen method flag is
  passed as `--squash` is today; the queue applies its own configured method.

## Requirements

- **FR-001**: `workspace.SCHEMA` `repos` entries gain `merge_method` (`auto`, `squash`,
  `rebase`, `merge`; default `auto`).
- **FR-002**: `code_host.protection(repo, branch)` returns `methods`, the allowed subset of
  `squash`, `rebase`, `merge` (in that order), replacing `squash`; a missing or non-boolean
  `allow_squash_merge`, `allow_rebase_merge` or `allow_merge_commit` is exit 2.
- **FR-003**: `merge.method_for(setting, allowed)` returns the method or `None`; `merge.check`
  refuses (exit 1) when it is `None`, naming the method or `no merge method`, and carries
  `method` in its exit 0 evidence.
- **FR-004**: `code_host.merge(ref, sha, method)` merges with `--<method>`; the GitHub `_run`
  allowlist admits exactly `--squash`, `--rebase` and `--merge` in that position; any other
  method is exit 2 before a subprocess. `merge.execute` passes the evidence method.
- **FR-005**: `merge.owner_command(ref, head, method)` names the method; `by_grant` and the
  `owner_paths` route pass it.
- **FR-006**: `merge.monitor` measures the 14-day outcome only for squash merges (evidence
  without `method` counts as squash), and its revert test also matches the merge-commit
  revert message.
- **FR-007**: Design spec 4.6 amendment line, adapter table `merge(ref, sha, method)`, 9.2 row
  and its check in `tests/test_invariants.py`; `docs/site/configuration.md` row
  `repos.merge_method` and the `merge.default_tier` row's command; `docs/site/concepts.md`
  merge paragraph.

## Success Criteria

- **SC-001**: On a merge-only repository, `wuwei merge` merges with a merge commit and
  `merge check` names `merge`; on a squash-allowing repository the argv and evidence are
  main's plus the `method` key.
- **SC-002**: No method the repository does not allow is ever passed to `gh pr merge`.
- **SC-003**: The full suite passes.

## Assumptions

- No `_pipeline/notes/785-full.md` exists; the issue, the code on main and the read-only
  reproduction above are the inputs.
- "The squash subject and body rules" are the repository's own commit message settings:
  WUWEI writes no subject or body, so they already apply per method and nothing is built.
- GitHub returns `allow_merge_commit` and `allow_rebase_merge` wherever it returns
  `allow_squash_merge` (same response, same permission), so requiring all three adds no new
  exit 2 for a token that reads the repository today. Test fixtures that replay the
  repository read gain the two fields.
- GitHub's revert of a merge-commit PR writes git's `-m 1` message (`This reverts commit
  <sha>, reversing changes made to <parent>.`); the breaker matches `<sha>.` or `<sha>,`.
- A rebase merge's `merge_commit` (GitHub's `merge_commit_sha`) is the rebased tip on the
  base branch; red base checks and a revert of that tip are followed as for squash.
- `merge.check`'s refusal stays a `Refused` (the owner's grant path), as the squash refusal
  is today: no grant lifts it.
- `guards/pr.py` and `guards/deploy.py` already accept every method flag on a session
  `gh pr merge` and refuse it naming `bin/wuwei merge`; unchanged.
- The invariant id is I72, or the next free id if another item in the wave takes it first.

## Deferred

- Line-level outcome tracking (5.6 escaped-defect cohort) for merge-commit and rebase merges:
  follow the first-parent history and the PR's whole commit range. Until then those merges are
  followed for red checks and reverts only. To be filed as its own issue.
