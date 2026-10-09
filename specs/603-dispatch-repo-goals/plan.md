# Implementation Plan: next passes --repo to worktree add on a multi-repository workspace, and approves the day's proposed goals

**Branch**: `603-dispatch-repo-goals` | **Date**: 2026-10-09 | **Spec**: `spec.md`

## Summary

Two small fixes at the shared spots. Defect 1: the lead's candidate carries `repo`;
`plan.propose` keeps a configured name, derives a missing one from `paths`, writes it into
`proposal.json` and lints an unresolved one on the plan; `dispatch._start` passes `--repo`
when more than one repository is configured (an unresolved item with no worktree is parked
with its reason); `worktree add` without `--repo` falls back to the same proposal row, so
every remediation line that names `bin/wuwei worktree add <item>` works too. Defect 2:
`plan.approve` validates against the day's `goals.md` while memory has no goals. Root causes
with file and line: `spec.md`.

## Technical Context

Stdlib-only Python 3.11+ runtime; pytest dev-only. Run only the touched test files, never
the full suite: `python -m pytest -q tests/test_dispatch.py tests/test_worktree_command.py
tests/test_plan.py tests/test_path_day.py tests/test_invariants.py tests/test_charters.py
tests/test_docs.py tests/test_next.py tests/test_owner_edits.py`.

## Constitution Check

- Test first per behaviour (IV): every change below has its failing test first (tasks.md).
- Stdlib only (I); exits unchanged (II): `worktree add` still exits 2 when no repository is
  known; nothing new exits 1 or 2.
- No new refusal under observe or guarded (#530, VII): the repository lint is a plan line,
  not a refusal; approve refuses less, never more; strict keeps `goals edit` the owner's.
- #551: every action stays a command `next` returns; no `then` text changes.
- One behaviour, one function (III): the proposal row reader is one function shared by
  `_start` and `worktree add`; derivation lives once, in `plan.propose`.
- 9.2: two rows and their checks (I26, I27). Pass.

## Changes

### 1. The proposal row reader, shared (FR-001, FR-007)

- `cli/wuwei/dispatch.py`: lift the three lines at the top of `_start` (lines 402-404: read
  `proposal.json`, pick the row whose `id` is the item) into `candidate(root, name)`
  returning the row or `None`. `_start` calls it. No other change to its body text.

### 2. `_start` passes `--repo` (FR-001, FR-002, FR-006)

- `cli/wuwei/dispatch.py` `_start(root, name, repos)`: `launch_set` passes `config['repos']`
  (already loaded at line 329; the only caller is line 393).
- When the worktree is missing and `len(repos) > 1`:
  - the row's `repo` is a configured name: `wuwei worktree add {name} --repo
    {shlex.quote(repo)}`, then the brief command unchanged;
  - otherwise return only `wuwei plan park {name} --reason ` + `shlex.quote(...)` with a one
    line reason naming the missing field and the configured names, for example
    `names no configured repository (acme/code, acme/paper); the lead names repo for it when
    it is proposed again`.
- One repository, or the worktree present: unchanged output.
- Keep the edit local to `_start`: #600 edits `dispatch.py` (fast-check refusal) in
  parallel.

### 3. `worktree add` falls back to the proposal (FR-007)

- `cli/wuwei/commands/worktree.py` `add`, the `elif len(repos) > 1:` branch (line 44):
  `name = (dispatch.candidate(root, item) or {}).get('repo')` (local import), filter `repos`
  to that name; when none match, raise the existing `ValueError` with the configured names
  appended: `several repositories configured (a, b); pass --repo <name>`. Exit 2 stays.
- Why here: the remediation lines at `dispatch.py:119`, `:543`, `docs.py:51`,
  `workspace.py:845`, `commands/build.py:132`, `brief.py:350`, `pr_actions.py:268` and
  `fast_checks.py:66` name `bin/wuwei worktree add <item>`; one fallback in `add` fixes all
  of them, no text edits.

### 4. `plan.propose` keeps, derives and lints `repo` (FR-003, FR-004, FR-005)

- `cli/wuwei/plan.py` `propose`, after `data['candidates'] = rank.rank(...)` (line 204) and
  before the plan lines (line 218): when `len(config['repos']) > 1`, for each candidate whose
  `repo` is not a configured name, drop it and set `repo` to the one configured repository
  whose checkout (`root / Path(repo['path']).expanduser()`, as `worktree add` resolves it)
  contains at least one of its `paths` (`.exists()` only). Several or none: no `repo`.
- In the per-candidate plan lines (lines 231-236), when more than one repository is
  configured, add `Repository: <name>` or the lint line `Repository: not named; the lead
  adds "repo": one of <names> (the paths match none or several), then the planner runs wuwei
  plan propose again`.
- `proposal.json` (line 248) is written after this, so `_start` and `worktree add` read the
  derived name.
- `_proposal` is not changed: no new validation, no new refusal (a non-string `repo` is
  simply not a configured name).

### 5. The lead is asked (FR-008)

- `cli/wuwei/commands/next.py` `LEAD_BODY` (lines 70-76): one sentence, no single quote
  (line 77 rule): `With more than one configured repository each candidate also has repo,
  the configured repository name it changes.`
- `charters/lead.md` step 4: one sentence after the `paths` sentence: `With more than one
  configured repository, name each candidate's repository as repo (its configured name);
  the CLI derives it from paths only when they exist in exactly one repository.` Leave the
  frontmatter version as is (#579 added `paths` the same way).

### 6. `plan.approve` reads the day's proposed goals (FR-009, FR-010)

- `cli/wuwei/plan.py` `approve`, lines 307-309: read `memory/goals.md`; when
  `not goals.defined(text)` and `directory / 'goals.md'` is a file, use that file's text;
  pass the result to `_proposal`. Comment `# #603: the provisional goals the gate card showed`.
- Nothing else in `approve`; `next.py` row order is not touched.

### 7. Invariants (FR-011)

- `docs/specs/2026-09-24-wuwei-design.md` 9.2, after I24:
  - `| I26 | Every command next returns to start a planned item exits 0 in a multi-repository
    workspace: worktree add names the candidate's --repo, and an item with no repository is
    parked with its reason | dispatch.launch_set on a two-repository fixture with one
    candidate carrying repo and one with none; each start command run through main with the
    VCS port faked | #603; one repository keeps worktree add <item> |` (with backticks as the
    table uses them).
  - `| I27 | A fresh day's gate-confirmed proposed goals approve the plan, and approve never
    writes owner memory | plan.approve over the empty goals template with the day's goals.md;
    memory/goals.md unchanged after | #603; goals edit records them after the gate, and stays
    the owner's under strict |`.
- `tests/test_invariants.py`: `i26` and `i27`, each `rules.memo((...,), compute)` once, READS
  `()`, added to `INVARIANTS` and `READS`. Keep them in process and cheap (the walk's CPU
  budget is 1.0 s): a small workspace under `rules.root` with its own `.wuwei`, the VCS port
  faked as `tests/test_worktree_command.py` `fake` does, `WUWEI_WORKSPACE` pointed at it for
  the call and restored after. `test_table_matches_the_checks` then passes. If #599, #600 or
  #601 add rows first, take the next free ids on rebase.

## Shared helpers reused, not copied

- `goals.defined` (goals.py:63) for "memory has no goals".
- The proposal row read from `_start`, lifted once as `dispatch.candidate`.
- `plan.dispose` through the existing `wuwei plan park` command for the unresolved start.
- The repository path rule `root / Path(repo['path']).expanduser()` from `worktree.add`.

## What must not change

- One-repository `_start` output, byte for byte (`test_launch_set_orders_gates_builds_then_planned_within_cap`,
  `test_start_names_the_worktree_and_the_builder_brief`).
- `worktree add` exit codes and `test_repo_selection` rows (the multi-repository case
  without a proposal still exits 2 and names `--repo`).
- `next.step` row order and every `THEN` text; the `goals` row; `gate_widget`.
- `plan.propose` exits and refusals; `_proposal` validation; the draft write and unlink at
  `plan.py:249-252`.
- `memory/goals.md` is written only by `goals edit`; `protect_state` untouched.
- `pr_actions.py` adopt command (already passes `--repo`).

## Tests (each fails before its change)

- `tests/test_dispatch.py`: two-repository `day_set` variant: start commands carry `--repo`
  for a candidate with `repo`; an unresolved item is the park command; an existing worktree
  gives the brief only; the one-repository tests unchanged.
- `tests/test_worktree_command.py` `test_repo_selection`: a row with two repositories, no
  `--repo` and a proposal naming `web` exits 0 on `web`; the error names both repositories.
- `tests/test_plan.py`: propose keeps a configured `repo`, derives one from `paths` (a file
  in exactly one fake checkout), lints when none or both match, writes `Repository:` lines,
  and exits 0; one repository writes no `Repository:` line. Replace
  `test_approve_needs_recorded_goals` with `test_approve_reads_the_proposed_goals` (approve
  passes, `memory/goals.md` unchanged, state goals are the ids) and keep a case with no
  draft still failing `no goals`.
- `tests/test_path_day.py`: a walk with the empty goals template and goal blocks in the
  lead's proposal reaches `gate_approved` and then the goals row records memory; a walk with
  a second configured repository and `repo` on the candidate runs `worktree add A --repo
  acme/widget` to exit 0.
- `tests/test_charters.py` and `tests/test_docs.py` (line 1418 checks `LEAD_BODY`): assert the
  `repo` sentence in both.
- `tests/test_invariants.py`: I26, I27 and the table match.
