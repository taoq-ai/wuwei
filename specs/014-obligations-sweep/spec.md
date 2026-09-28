# Feature Specification: PR obligations sweep

**Feature Branch**: `014-obligations-sweep`
**Created**: 2026-09-28
**Status**: Ready
**Input**: Issue #14, reply and visibility obligations over open PRs.

## User Scenarios & Testing

### User Story 1 - Know which replies are owed (Priority: P1)

The shepherd checks every PR raised or claimed today against its absolute current
state, so missed polling intervals cannot hide unanswered reviews.

**Independent Test**: Supply recorded review surfaces and check each owed identifier.

**Acceptance Scenarios**:

1. Given a human review summary newer than our last reply, when swept, it is owed
   until that specific summary is acknowledged after a successful reply.
2. Given several unthreaded comments, replying to one does not clear the others,
   even when our reply is newer than all of them.
3. Given an inline thread, a last human word other than ours is owed; our reply or
   resolution clears it. An unanswered bot P1 on the current diff is owed.
4. Given an acknowledgement, an edited body becomes owed again. Generic state
   writes cannot forge acknowledgements.

### User Story 2 - Prove visibility (Priority: P1)

The shepherd checks that someone has been asked to review, a channel post naming
reviewers is logged, and a verdict is recorded against each open PR.

**Independent Test**: Remove each piece of evidence and observe a visibility finding.

**Acceptance Scenarios**:

1. Given no requested reviewer and no submitted human review, the PR owes a reviewer.
2. Given only a HELD note, a prose mention, or a posted link without reviewer
   mentions, the PR owes a channel post.
3. Given no linted gate verdict matching the current PR head, the PR owes a recorded verdict.

### User Story 3 - Fail closed and report (Priority: P1)

Unreadable evidence is reported distinctly and cannot make the day clean.

**Independent Test**: Replay read failures and verify exit 2 and one sweep event.

**Acceptance Scenarios**:

1. Given an API error body on stdout, the PR is reported unreadable with exit 2.
2. Given a failed or malformed read, other PRs are still checked and the sweep
   records owed counts, including unreadable PRs, in one `watch: sweep` event.
3. Given a closed PR, it has no obligations; duplicate raised/claimed references
   are checked once. An empty day set is clean only when its event history proves
   it was never nonempty today; raised and claimed lists refuse removal.

### Edge Cases

Missing day state, corrupt acknowledgement data, deleted authors, incomplete pages,
invalid timestamps, malformed PR references, errors after posting, and edits during
reply recording fail closed. Approval bodies are closeout information, not replies.

## Requirements

### Functional Requirements

- **FR-001**: Sweep the union of today's raised and claimed PRs using fresh reads.
- **FR-002**: Evaluate inline threads, PR comments, and review summaries separately.
- **FR-003**: Clear unthreaded human obligations only through a specific acknowledgement.
- **FR-004**: Require reviewer, posted channel evidence with mentions, and a verdict.
- **FR-005**: Return 0 clean, 1 owed, 2 unreadable; unreadable evidence counts as owed.
- **FR-006**: Record one sweep event with reply, visibility, and unreadable counts,
  without storing message bodies.

### Key Entities

- PR reference: repository owner/name and positive PR number.
- Acknowledgement: PR, surface, comment identity and revision, successful reply evidence.
- Visibility evidence: posted channel permalink and reviewer identities, PR verdict.

## Success Criteria

- Every acceptance fixture yields its expected three-state result.
- Every open PR in the day's union is read on each sweep, independent of prior sweeps.
- No failed read, held post, or unrelated acknowledgement produces a clean result.

## Assumptions

- Dependencies #5 and #87 are present; existing ports and state writer are reused.
- Identity comes from the single code-host login in workspace `owner.handles`.
  Bare Slack IDs matching `[UW][A-Z0-9]+` are excluded. Missing or ambiguous
  identity fails closed. There is no `--me` override or inference from PR authors.
- Raised and claimed lists contain canonical `owner/repo#number` strings. Malformed
  entries fail closed. An absent state file is unreadable, not an empty day.
- Unthreaded comments of any age remain owed without their own acknowledgement,
  matching the source harness. Nonempty approval bodies are deferred to merge closeout.
- Resolved inline threads clear; outdated human threads still need a reply. Bot P1
  threads require a human answer only while unresolved on the current diff.
- Requested reviewers and teams determine required channel mentions. Submitted
  human review authors are the fallback only when nobody is requested.
- Channel logs are structured day state, independent of any chat vendor, with explicit
  posted status, HTTPS permalink and reviewer mentions. `channel_posts` is reserved;
  without a dedicated posting producer it stays owed. Tests seed producer evidence
  through the internal writer only.
- Verdicts come only from linted `decisions/gate-*.md` files in today's directory,
  using `Verdict:` and `Head:` rows. A lint-valid 7 to 40 hex head must match the
  current PR head prefix. PASS, FIX, PARK and ESCALATE prove a recorded verdict,
  not merge permission. Editable state verdicts are ignored.
- State writes record `prs_seen` in events. Empty sets require recorded state
  history and reject prior PRs, prior sweeps with PRs, and unreadable history.
  `watch: sweep` and `reply: acknowledged` are reserved for dedicated writers.
- This explicit workspace command adds no hook guard. Existing scope, relevance
  before parsing, and WUWEI role-seat guard conventions remain applicable.
- Bot-specific rescore and summary-link parsing belongs to the review_bot adapter,
  not the generic obligations sweep.

## Deferred

Watch scheduling (#15), merge-closeout approval-body checks, bot-specific rescore
policy, full shepherd orchestration, and chat posting producers remain separate work.
