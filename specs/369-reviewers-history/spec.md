# Feature Specification: reviewers come from who touched the changed code with no configuration, the owner can override them, and a solo owner raises PRs with none

**Feature Branch**: `369-reviewers-history`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #369. Owner, 2026-10-03: "reviewers should be selected based on who
touched the code, unless instructed otherwise by the owner." UX sweep finding F5. Builds on
#177 (shepherd actions), #207 (solo owner, `shepherd.min_reviewers = 0`), #356 (bot authors
in `shepherd.authors`) and #360 (the interview question "Who reviews your pull requests?"),
all on `main`.

## Root cause (read and reproduced on main, b2a4557)

The ranking the owner asked for already exists in `cli/wuwei/shepherd.py::_rank`
(authorship of the changed source paths per window, PR author and `[bot]` logins excluded,
top two, three on a tie, plus `shepherd.lead_login`). What stops it on a fresh workspace:

- **Unresolved email refuses.** `cli/wuwei/shepherd.py:47-57`: an email not in
  `shepherd.authors` goes to `code_host.author_login`; any failure or an empty login raises
  `ValueError('shepherd.authors has no mapping for <email>')`, so `pr raise` exits 2
  (`:307-309`) and `pr ping` exits 2. Reproduced by the passing tests
  `test_unmapped_author_names_email_and_key` and
  `test_empty_code_host_login_names_email_and_key` in `tests/test_shepherd.py`.
- **Solo repository refuses.** `cli/wuwei/shepherd.py:72-73` raises
  `Refused('fewer eligible reviewers than shepherd.min_reviewers')` whenever fewer than
  `shepherd.min_reviewers` (default 1, `cli/wuwei/workspace.py:112`) logins remain. In a
  repository whose only author is the owner, the ranking is empty, and `setup` sets
  `shepherd.lead_login` to the owner's own login (`cli/wuwei/commands/setup.py:209-210`),
  which `:70` drops as the PR author. `pr raise` exits 1. Reproduced by the passing tests
  `test_zero_reviewers_names_minimum` and `test_owner_handle_case_differs_from_code_host_login`.
- **Owner-named logins need an email.** `cli/wuwei/shepherd.py:76-83` re-verifies every
  selected login through an email; a `lead_login` (or any owner-named login) with no email in
  `shepherd.authors` raises `reviewer needs a configured email`.
- **No override.** There is no setting that names reviewers directly; the only knobs are
  `lead_login` and `min_reviewers`.
- **Misleading refusal.** `cli/wuwei/guards/pr.py:207-210` refuses `gh pr create` without
  `--reviewer` when `min_reviewers > 0`, and the hook appends
  `posture: publish = block (owner-only action; no setting lowers it)`
  (`cli/wuwei/guards/__init__.py:55-56`) although `shepherd.min_reviewers = 0` lowers it.
- **Empty selection downstream.** `post_review_request` rejects a selection shorter than
  `min_reviewers` (`cli/wuwei/shepherd.py:188`) and would call `request_reviewers` with an
  empty list, which the GitHub adapter refuses (`adapters/code_host/github.py:498`).
  `obligations._visibility` (`cli/wuwei/obligations.py:152-178`) owes `reviewer` and
  `channel-post` for any PR with no reviewer unless `min_reviewers = 0`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reviewers from history with no configuration (Priority: P1)

An owner on a fresh workspace raises a PR in a team repository. The reviewers are the people
who committed most to the changed paths, resolved to code-host logins through the code host,
with nothing in `shepherd.authors`. An author the code host cannot resolve is skipped and
noted, never a refusal.

**Why this priority**: it is the owner's stated rule and the most common path.

**Independent Test**: `select_reviewers` against fake ports with an empty `shepherd.authors`.

**Acceptance Scenarios**:

1. **Given** a repository with three authors on the changed paths and no `shepherd.authors`,
   **When** `select_reviewers` runs, **Then** it returns the top two by commits (three when
   third place is within `shepherd.tie_commits` of second), each resolved through
   `code_host.author_login`, plus the lead when set and not the author.
2. **Given** an author email the code host cannot resolve (adapter reason
   `author login unavailable`, an invalid email, or an empty login), **When** the ranking
   runs, **Then** that email is skipped, one `reviewer.unresolved` event names the email's
   local part, and the PR still raises with the other reviewers.
3. **Given** the same email seen again the same day, **When** the ranking runs again,
   **Then** the code host is not asked again and no second event is written (the day
   state caches the result).
4. **Given** the code host cannot be reached (any other adapter failure), **When** the
   ranking runs, **Then** selection fails closed with exit 2 and the reason, as today.

### User Story 2 - Solo owner raises with no reviewer (Priority: P1)

An owner alone in a repository raises a PR on defaults (`min_reviewers = 1`). The ranking
finds nobody but the author, so the PR is raised with no reviewer and the record says so.

**Why this priority**: a solo owner cannot raise any PR today without editing config.

**Independent Test**: `raise_pr` with a single-author history and `lead_login` equal to the
owner.

**Acceptance Scenarios**:

1. **Given** a single-author repository, **When** `pr raise` runs, **Then** it exits 0,
   requests no reviewer, records `pr_reviewers[ref] = []` and prints
   `reviewers: none (solo)`.
2. **Given** a PR recorded with no reviewer, **When** `status --line` runs, **Then** the line
   contains `reviewers: none (solo)`.
3. **Given** a PR recorded with no reviewer, **When** `pr ping` runs and the gate clears,
   **Then** it requests nobody, posts nothing, prints `reviewers: none (solo)` and exits 0.
4. **Given** a PR recorded with no reviewer, **When** obligations are computed, **Then**
   `reviewer` and `channel-post` are not owed for that PR.
5. **Given** other eligible authors exist but fewer than `shepherd.min_reviewers`,
   **When** the ranking runs, **Then** it still refuses, and the refusal names the two ways
   out.

### User Story 3 - Owner override (Priority: P2)

The owner names reviewers directly, for the workspace or one repository, or removes logins
from the history ranking.

**Independent Test**: `select_reviewers` with `shepherd.reviewers` set.

**Acceptance Scenarios**:

1. **Given** `shepherd.reviewers = ["pat-dev"]`, **When** selection runs, **Then** the
   history ranking is not read, the lead is not added, and the PR requests exactly
   `pat-dev`.
2. **Given** `[repos.shepherd] reviewers = ["sam-dev"]` on the PR's repository and a
   different workspace `shepherd.reviewers`, **When** selection runs, **Then** the
   repository's list wins.
3. **Given** `shepherd.reviewers_exclude = ["alice"]` and history where `alice` ranks first,
   **When** selection runs, **Then** `alice` is not selected and the next author moves up.

### User Story 4 - The refusal names the ways out (Priority: P2)

**Acceptance Scenarios**:

1. **Given** `min_reviewers = 1`, **When** `gh pr create` runs without `--reviewer`,
   **Then** the refusal names `bin/wuwei config set shepherd.min_reviewers 0` and
   `bin/wuwei config set shepherd.reviewers '["login"]'`, and the hook adds no
   `no setting lowers it` line to it.

### User Story 5 - Explain the selection (Priority: P3)

**Acceptance Scenarios**:

1. **Given** an owned PR, **When** `bin/wuwei pr reviewers <ref> --explain` runs, **Then** it
   prints the deciding window, each ranked login with its total commits and commit counts
   per changed path, marks the selected logins, names the lead, lists unresolved local
   parts, and ends with the same selection `pr ping` would use. Without `--explain` it
   prints only the selection line. Exit 0 selected, 1 refused, 2 could not measure.

### Edge Cases

- The PR author appears in `shepherd.reviewers`: dropped (a code host refuses to request the
  author). An override left empty after that is the solo case.
- `reviewers_exclude` removes the lead too; it never edits an override.
- Every other author is unresolved or excluded: the ranking is empty, so the PR is solo,
  with one event per unresolved email.
- Logins are compared case-insensitively, as the author exclusion already is.
- A PR whose changed paths are all excluded by `shepherd.source_exclude` still refuses with
  `no changed source paths for reviewer selection`, unless an override is set.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: An author email not in `shepherd.authors` MUST be resolved through
  `code_host.author_login`, and the result (login, or unresolved) cached for the day in
  state key `author_logins`, written only by the shepherd.
- **FR-002**: An email the code host cannot resolve MUST be skipped with exactly one
  `reviewer.unresolved` event per email per day, payload `{repo, author}` where `author` is
  the local part only. Other adapter failures MUST still fail closed (exit 2).
- **FR-003**: `shepherd.authors` MUST keep precedence over the code host and keep its
  host verification of mapped logins.
- **FR-004**: When the ranking plus the lead yields nobody, selection MUST return an empty
  list (solo) instead of refusing; `min_reviewers` MUST still refuse when at least one but
  fewer than `min_reviewers` logins remain.
- **FR-005**: `shepherd.reviewers` (workspace) and `repos.shepherd.reviewers` (per
  repository, wins when non-empty) MUST replace the ranking, the lead and the
  `min_reviewers` check; `shepherd.reviewers_exclude` MUST remove logins from the ranking
  and the lead.
- **FR-006**: `pr raise`, `pr ping` and `pr reviewers` MUST use the one selection function.
- **FR-007**: A solo PR MUST print and record `reviewers: none (solo)`, request nobody, post
  nothing, owe no `reviewer` or `channel-post` obligation, and show on the status line.
- **FR-008**: The missing-reviewer refusals (the `gh pr create` guard and the ranking's
  `min_reviewers` refusal) MUST name both ways out and MUST NOT say no setting lowers them.
- **FR-009**: `pr reviewers <ref> [--explain]` MUST print the selection, and with
  `--explain` the ranking with commit counts per path.
- **FR-010**: The new keys MUST be documented next to `shepherd.lead_login` in the template
  and `docs/site/configuration.md`, and kept out of exported profiles.

### Key Entities

- **`author_logins`** (day state): `{email: login or null}`; null means unresolved today.
- **`reviewer.unresolved`** (event): `{repo, author}`; silent tier.
- **`shepherd.reviewers`, `shepherd.reviewers_exclude`, `repos.shepherd.reviewers`**
  (config): lists of code-host logins, default `[]`.

## Success Criteria *(mandatory)*

- **SC-001**: The four acceptance cases of the issue pass as tests in `tests/test_shepherd.py`.
- **SC-002**: A fresh single-author workspace raises a PR on defaults with exit 0.
- **SC-003**: The full suite passes.

## Assumptions

- #360 is on `main` (interview question `reviewers` present); nothing here changes it.
- "Cannot resolve" means the adapter reported `author login unavailable` or
  `invalid author email`, or returned an empty login. Any other failure (network, auth,
  error body) is unmeasured evidence and stays exit 2, per the constitution.
- The event is silent: it is a record, not something the owner must act on today. It is
  visible in `pr reviewers --explain`.
- Owner-named logins (`lead_login`, the override) are not re-verified through an email; the
  existing check that the code host's `requested` set equals the selection verifies them.
  Logins resolved through the code host are not looked up a second time.
- Logins from the override or the code host still need a chat mention in
  `shepherd.authors` for the review channel post, as today. The channel post is unchanged.
- The status line shows `reviewers: none (solo)` once when any owned PR today is solo,
  including PRs raised under `min_reviewers = 0`.
- `reviewers_exclude` applies to the workspace only; only `reviewers` has a per-repository
  form, which is what the issue names.
- The `review_stale` action for a PR with no reviewer is unchanged (it already applies to
  `min_reviewers = 0`); `pr ping` returning 0 for a solo PR is enough here.
