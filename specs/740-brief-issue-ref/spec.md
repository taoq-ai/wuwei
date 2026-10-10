# Feature Specification: an owner/repo#N reference in a brief never fails registration with Not Found

**Feature Branch**: `740-brief-issue-ref`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #740 (owner, 2026-10-10, item 66): `wuwei brief` looks every
`owner/repo#N` reference up through the pull-request endpoint; a ticket that is an issue got
"Not Found" and the brief was refused (the error was hidden behind redaction, #738). The
owner worked around it by taking the ticket reference out of the brief. #606 already taught
the outward guard that a bare `owner/repo#N` the pulls endpoint 404s on is an issue; `brief`
does not use it.

## Root cause

Reproduced read-only with the recording code host fake (no network): a workspace with one
repository `acme/widget`, a builder brief whose body says `Ticket: acme/widget#24`, and the
fake's `pr` returning the exact result the GitHub adapter gives an issue number,
`Result(2, None, 'github.pr: could not run: gh exited 1 (acme/widget): gh: Not Found (HTTP 404)')`:

```text
exit 2
stderr: wuwei brief: github.pr: could not run: gh exited 1 (acme/widget): gh: Not Found (HTTP 404)
calls:  [('pr', ('acme/widget#24',), ...)]
no briefs/b1.md, no brief written event
```

- `cli/wuwei/brief.py:528` to `532`, in `write`: for every configured repository, every
  `<repo name>#N` in the body other than `--pr` is read with `read(host.pr, other, root=root)`
  to print a `Counterpart <ref> head (no-cache)` line.
- `adapters/code_host/github.py:197`, `pr`, reads `repos/<repo>/pulls/<N>`. GitHub answers
  404 for an issue number there.
- `cli/wuwei/brief.py:126` to `132`, `read`, raises `ValueError` on any non-zero exit, so the
  404 aborts `write` before the state write: exit 2, no brief, whatever the posture.

The counterpart lines exist so a seat sees the head of a related pull request (a paired PR in
another repository). A ticket reference was never meant to be a counterpart, but the regex
cannot tell one from the other, and a failed read of an optional evidence line refuses the
whole brief.

`cli/wuwei/outward.py:304` to `308` (#606) already holds the rule for the outward guard: a
`pr` lookup whose reason carries `(HTTP 404)` on a bare reference means "not a pull request,
no PR context". The rule lives inline there, so `brief` could not reuse it.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Does the code host port get a new `reference` operation that returns
  `{kind: issue|pr}` (the issue's Deliver)? A: No. See Assumptions A1. The fix reuses the
  #606 rule, moved into one shared helper that both `brief` and the outward guard call.
- Q: What does the brief say for a reference that is not a readable pull request? A: One
  header line, `Warning: <ref> is no pull request the host could read (<reason>); kept as a
  reference`. The body keeps the reference text unchanged.
- Q: Which failures become a warning? A: Below `strict` every failed counterpart read (the
  reference is optional evidence, and design 9.1 and invariant I1 say no wall below strict).
  Under `strict` a 404 is still a warning (an issue reference is legitimate and a 404 cannot
  tell it from a typo), and any other failure (auth, timeout, damaged data) still refuses
  with its reason, as today.
- Q: Does the `--pr` read change? A: No. `--pr` names the pull request the brief is for (a
  gate needs its head); a failure there keeps refusing.

## User Scenarios and Testing

### User Story 1 - a brief that names a ticket registers (Priority: P1)

The planner writes a builder brief whose body names the item's ticket, `acme/widget#24`, an
issue. The brief registers, the seat can launch, and `why` still shows the ticket.

**Why this priority**: it is the owner's reported defect; today the only workaround is to
take the ticket out of the brief.

**Independent Test**: `main(['brief', 'builder', 'X', ...])` against the recording fake code
host whose `pr` returns the GitHub 404 result for `acme/widget#24`.

**Acceptance Scenarios**:

1. **Given** a brief that names an issue reference (`acme/widget#24`, the pulls endpoint
   answers 404), **When** `wuwei brief` runs, **Then** it exits 0, `briefs/<name>.md` exists
   with a `Warning: acme/widget#24 ...` header line and the body text `acme/widget#24`
   unchanged, a `brief written` event is appended, and `why X --json` (the `live` reader)
   shows the item's ticket.
2. **Given** a brief that names a reference the host does not know at all (also a 404),
   **When** `wuwei brief` runs, **Then** the same: a warning line, exit 0, never a refusal.
3. **Given** a brief that names a real counterpart pull request, **When** `wuwei brief`
   runs, **Then** the `Counterpart <ref> head (no-cache): {...}` line is unchanged.

### User Story 2 - an unreadable counterpart follows the posture (Priority: P2)

A counterpart read fails for a reason other than 404 (bad credentials, timeout).

**Acceptance Scenarios**:

1. **Given** posture `guarded` (default) and a counterpart read that fails with
   `HTTP 401`, **When** `wuwei brief` runs, **Then** it exits 0 with the warning line
   naming the reason.
2. **Given** posture `strict` and the same failure, **When** `wuwei brief` runs, **Then**
   it exits 2 with the reason on stderr and no brief is written (today's behaviour).
3. **Given** posture `strict` and a 404, **When** `wuwei brief` runs, **Then** it exits 0
   with the warning line.

### User Story 3 - one rule for "not a pull request" (Priority: P3)

The outward guard (#606) and `brief` decide "this reference is not a pull request" with the
same helper, so the two cannot drift.

**Acceptance Scenarios**:

1. **Given** the existing #606 table (`tests/test_outbound.py`,
   `test_issue_reference_reads_without_pr_context`), **When** the outward guard calls the
   shared helper, **Then** every row keeps its current result.

### Edge Cases

- The same reference twice in the body: one line (the existing `sorted(set(...))`).
- The reference equals `--pr`: skipped, as today.
- `acme/widget#0` or another value the adapter's own parser refuses: the read fails with a
  non-404 reason; below strict a warning, under strict a refusal.
- A damaged adapter result (`read` raises the `ADAPTER_DATA` error): a failed read like any
  other; below strict a warning.
- The reason text is the adapter's already redacted reason (`github._run` redacts and caps
  the stderr line); `brief` adds nothing from the response body.

## Requirements

### Functional Requirements

- **FR-001**: `brief.write` MUST NOT refuse a brief because a counterpart reference in its
  body failed to read with a not-found (HTTP 404) reason, in any posture.
- **FR-002**: Below `strict`, `brief.write` MUST NOT refuse a brief because any counterpart
  read failed; under `strict` a non-404 failure MUST keep refusing with exit 2 and its
  reason.
- **FR-003**: A failed counterpart read MUST add exactly one header line
  `Warning: <ref> is no pull request the host could read (<reason>); kept as a reference`
  and MUST leave the body text unchanged.
- **FR-004**: A successful counterpart read MUST keep the existing
  `Counterpart <ref> head (no-cache): <json>` line byte for byte.
- **FR-005**: The not-found rule MUST live in one helper, `references.not_found(reason)`,
  called by both `brief.write` and `outward._pr_context`; the outward guard's results for
  the #606 table MUST NOT change.
- **FR-006**: The code host port, its adapters and fakes MUST NOT change.

### Key Entities

- Counterpart reference: a `<configured repo name>#N` token in a brief body, other than
  `--pr`.
- Brief header warning line: the new line for an unreadable counterpart.

## Success Criteria

- **SC-001**: The owner's brief with its ticket reference in the body registers without
  editing the body.
- **SC-002**: The full suite passes; the #606 outward table passes unchanged.

## Assumptions

- **A1 (deviation from the issue's Deliver, recorded for review)**: the issue asks for a new
  port operation `reference(repo, number)` that reads the issue endpoint first and the PR
  endpoint for PR-only fields, called by `brief`, the outward guard and `pr state`. This
  spec does not add it:
  - The owner's own report (2026-10-10) names the fix: wuwei already has a fix for this
    (#606) and `brief` does not use it. Reusing #606 is the requested fix.
  - #606's notes bind the outward guard to no second network call. Issue-first costs a
    second call for every pull request the guard and `brief` read; the common case is a
    pull request.
  - What a `kind` would add (issue versus unknown) has no reader: the seat reads the item's
    ticket from live state (#722), not from the brief header, and both cases get the same
    treatment (keep the text, never refuse).
  - A new operation touches the registry, two adapters, the fake and the adapter contract
    table, for a value nothing consumes (Constitution V).
  - The owner's acceptance (issue ref registers, unknown ref warns, never a refusal) is met
    by the warning line alone.
- **A2**: `pr state` is unchanged. `pr_actions.evaluate` refuses any ref that is not a PR
  raised or claimed today before any host call (`cli/wuwei/pr_actions.py:251`), so an issue
  reference never reaches the pulls endpoint there.
- **A3**: The issue's warning wording ("ticket <ref> not found on the host") is replaced by
  the FR-003 wording: a 404 does not prove absence (an issue, or a repository the token
  cannot see), and the same line also covers non-404 failures below strict. The reason in
  parentheses says which.
- **A4**: "below strict and never a refusal" is read with design 9.1 ("Under `strict`,
  refusals stay"): a 404 never refuses (FR-001); other failures refuse only under `strict`
  (FR-002). The posture is read with the shared `workspace.posture(config)[0]`.
- **A5**: `brief` is a command, not a guard or decision rule, so no design 9.2 row and no
  `tests/test_invariants.py` case is added; the change moves `brief` toward I1 (no wall below
  strict), it adds no new wall.
- **A6**: "why shows the ticket" is the existing `why <item> --json` reader (`live`) of the item's ticket
  (`cli/wuwei/commands/why.py:125`); the brief does not copy the ticket (#722). The test
  asserts it after the brief registers.
- **A7**: The orchestrator notes file for this issue does not exist; the root cause was
  reproduced with the recording fake instead of a dry-run workspace.
- **A8**: Item 67 of the same owner message (`plan add --ticket 24` stores a bare number) is
  a separate issue and out of scope.

## Deferred

- None.
