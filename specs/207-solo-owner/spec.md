# Feature Specification: Solo owner without reviewers or chat

**Feature Branch**: `207-solo-owner`
**Created**: 2026-09-30
**Status**: Ready
**Input**: GitHub issue #207, "fix(team): a solo owner can raise, push and close without reviewers or chat". Depends on #163 (solo PR raise). Design spec sections 4.1, 4.2, 5.2.

## Root cause (reproduced from the v0.5.0 operator dry run, rows 28, 29 and 39)

The dry run used a one-person workspace: `adapters.chat = "none"`, `shepherd.lead_login = ""`, one owner handle, no second author. Reproduced in-process on a scratch copy of its config against `main`:

1. `cli/wuwei/shepherd.py:45-46` (`_rank`): an authorship email missing from `shepherd.authors` raises `shepherd.authors has no mapping for owner@example.test` before the code host is asked. The owner's own commits hit this, so `wuwei pr raise` exits 2 even though the owner is later excluded as the PR author.
2. `cli/wuwei/workspace.py:78`: the schema entry `"min_reviewers": (int, 1, 1)` rejects `0`, so `wuwei config check` exits 1 and `wuwei pr raise` exits 2 with `shepherd.min_reviewers: expected integer >= 1`. With the minimum at 1 and no other author or lead, `_rank` refuses at `cli/wuwei/shepherd.py:61-62` (`fewer eligible reviewers than shepherd.min_reviewers`, exit 1). There is no valid setting for "the owner merges".
3. `cli/wuwei/shepherd.py:285-287` (`raise_pr`): the reviewer request runs unconditionally after the PR is created. The GitHub adapter refuses an empty login list (`adapters/code_host/github.py:390-392`, `expected reviewer logins`), so a raise that selected no reviewer would create the PR and then exit 2.
4. `cli/wuwei/guards/pr.py:203-206` (`create_check`): `gh pr create` without `--reviewer` is refused (`PR create requires a named --reviewer in the same command`) whatever the configured minimum.
5. `cli/wuwei/obligations.py:143-145` and `:158-159` (`_visibility`): with no requested reviewer the sweep owes `reviewer`, and with no producer-written channel post it owes `channel-post`. With `adapters.chat = "none"` no channel post can ever be produced (`shepherd.post_review_request` posts only through the chat port), so after `pr claim` the dry run's `sweep obligations` exited 1 with `OWED reviewer` and `OWED channel-post`. The same `_visibility` feeds the merge policy (`cli/wuwei/merge.py:273`) and the day close (`cli/wuwei/closing.py:233` through `obligations.evaluate`), so an open owned PR in such a workspace can never clear either.

## User Scenarios and Testing

### User Story 1 - Solo owner raises a PR (Priority: P1)

A solo owner sets `shepherd.min_reviewers = 0`, leaves `shepherd.lead_login` empty and `adapters.chat = "none"`, and does not map their own email in `shepherd.authors`. `wuwei pr raise` passes the existing gates and creates the PR without requesting reviewers.

**Independent test**: raise against fake VCS and code-host ports where the only authorship row is the owner's unmapped email.

**Acceptance scenarios**:

1. **Given** a solo owner config, **when** `wuwei pr raise` runs, **then** it exits 0, creates the PR, records it with an empty reviewer list and makes no reviewer request.
2. **Given** `shepherd.min_reviewers = 1` and no eligible reviewer, **when** `wuwei pr raise` runs, **then** it still refuses with exit 1 naming `shepherd.min_reviewers`.
3. **Given** an authorship email missing from `shepherd.authors`, **when** the code host resolves it to a login, **then** that login is used (excluded when it is the PR author, eligible otherwise).
4. **Given** an authorship email missing from `shepherd.authors`, **when** the code host cannot resolve it, **then** the raise exits 2 with the existing message naming `shepherd.authors` and the email.

### User Story 2 - Solo owner pushes the PR through the create guard (Priority: P1)

**Acceptance scenarios**:

1. **Given** `shepherd.min_reviewers = 0` and passed pre-PR gates at HEAD, **when** the planner runs `gh pr create` without `--reviewer`, **then** the PR guard allows it.
2. **Given** `shepherd.min_reviewers = 0`, **when** `gh pr create` names an empty or malformed `--reviewer`, **then** the guard still refuses (exit 1).
3. **Given** `shepherd.min_reviewers = 0` and pre-PR gates not passed at HEAD, **when** `gh pr create` runs, **then** the guard still refuses on the gates.
4. **Given** the default `shepherd.min_reviewers = 1`, **when** `gh pr create` has no `--reviewer`, **then** the refusal is unchanged.

### User Story 3 - Solo owner's sweep and close owe nothing for reviewers or chat (Priority: P1)

**Acceptance scenarios**:

1. **Given** a solo owner config and an open owned PR with no requested reviewer, no channel post and a recorded PASS gate verdict at its head, **when** `wuwei sweep obligations` runs, **then** it exits 0, the `watch: sweep` event has `visibility_owed` 0, and it prints one `NOT APPLICABLE` line each for `reviewer` and `channel-post` naming the reason.
2. **Given** `shepherd.min_reviewers = 1`, `adapters.chat = "none"` and no requested reviewer, **when** the sweep runs, **then** `reviewer` is still owed and `channel-post` is reported not applicable.
3. **Given** `shepherd.min_reviewers >= 1` and a configured chat adapter, **when** the sweep runs, **then** reviewer and channel-post obligations are unchanged.
4. **Given** a solo owner config, **when** the verdict for the PR head is missing, **then** `verdict` is still owed.

### Edge Cases

- `shepherd.min_reviewers = -1` is still a config finding (`expected integer >= 0`).
- The code host lookup for an unmapped email fails, returns an error body or returns a non-login value: exit 2, never a silently empty reviewer set.
- A login resolved by fallback and selected as a reviewer is still verified by the existing reviewer verification loop.
- Merge policy uses the same `_visibility`, so its visibility precondition follows the same not-applicable rule; every other merge precondition is unchanged.

## Requirements

- **FR-001**: `shepherd.min_reviewers` accepts integers `>= 0`; the default stays `1`.
- **FR-002**: With no eligible reviewer and `shepherd.min_reviewers = 0`, reviewer selection returns an empty list and `wuwei pr raise` creates the PR, records it, and skips the reviewer request. With a non-empty selection the request and its verification are unchanged.
- **FR-003**: Reviewer selection resolves an authorship email missing from `shepherd.authors` through `code_host.author_login(repo, email)` before refusing; failure keeps the exit 2 message naming `shepherd.authors` and the email.
- **FR-004**: The PR create guard requires a named `--reviewer` only when `shepherd.min_reviewers > 0`. A `--reviewer` that is present must still be well formed. All other create checks, including the pre-PR gate check, are unchanged.
- **FR-005**: The visibility obligation `reviewer` is not applicable when `shepherd.min_reviewers = 0`. The visibility obligation `channel-post` is not applicable when `shepherd.min_reviewers = 0` or `adapters.chat = "none"`. One helper in `cli/wuwei/obligations.py` defines this rule; the sweep, the day close and the merge policy all read it through `_visibility`.
- **FR-006**: `sweep obligations` prints `<ref> NOT APPLICABLE <finding>: <reason>` for each not-applicable finding of an open owned PR and does not count it as owed.
- **FR-007**: The workspace template and `docs/site/configuration.md` describe `shepherd.min_reviewers = 0`, the author fallback and the chat-none channel-post rule. No new config key is added.

## Success Criteria

- Every acceptance scenario above passes with in-process fakes; no network, real `gh` or real chat.
- Existing tests for the default configuration keep passing; fixtures that exercise the channel-post rule configure a chat adapter.
- The full suite passes.

## Assumptions

- "The code host's authenticated login" in the issue is read as the orchestrator notes state it: the existing `code_host.author_login(repo, email)` port, which resolves a commit author email to its code-host login. `auth_status` returns no login, and no new port is added.
- The issue's "no second reviewer and chat = none" and the notes' "min_reviewers = 0 or chat is none" are reconciled per finding: `reviewer` depends only on the reviewer minimum (a missing chat adapter says nothing about review), while `channel-post` is not applicable when the minimum is 0 (nothing to announce) or chat is `none` (no port can produce the record, so it could never be satisfied). Under `min_reviewers >= 1` with chat `none`, `reviewer` stays owed, so the merge policy and close still block a PR with no reviewer.
- `shepherd.min_reviewers = 0` is an owner-only decision: `config.toml` is refused to agent tools by `cli/wuwei/guards/protect_state.py`, so a seat cannot lower it.
- The design spec 4.1 row "no reviewer named in the same action" is narrowed by this owner issue for `min_reviewers = 0`. The design spec is amended only by its owner, so it is not edited here; the conflict is raised in the plan.
- Not-applicable findings are printed only; the `watch: sweep` event keeps its existing keys.
- "Push" in the title needs no change: the dry run's push succeeded; the blocker on that path was the `gh pr create` reviewer rule.

## Deferred

- A solo PR with no requested reviewer still becomes `review_stale` after `pr.review_window`, and `pr act` then calls `shepherd.post_review_request`, which cannot request an empty reviewer set. The owner merges, parks or carries it. Handling `review_stale` for `min_reviewers = 0` is outside this issue's scope.
