# Feature Specification: a fix to a broken base skips the soak, and merge check says either wait or who merges

**Feature Branch**: `668-soak-base-fix`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #668 (owner, 2026-10-10, items 29 and 30): a green, clean PR that
fixes the lint break on main was held by the soak window while every branch cut from main
failed on the same break. `merge check` said "soak window has not passed; the owner merges;
ask the owner", which reads as both wait and the owner must merge. Deliver: a PR that fixes a
broken base skips the soak (`merge.soak_skip = base_fix` by default) and the result says so;
`merge check` prints one sentence per state, `waits: soak ends at <time>` or
`owner merges: <rule>`, never both, and its `Next:` line matches it.

## Root cause

Reproduced in-process on `main` with the `tests/test_merge.py` `case` fixture: PR
`example/project#7`, head checks green, the `tests` check failing at the base commit
(`base_sha`), `soak_minutes = 180`, last update two hours ago.

| Step | Today |
|---|---|
| `merge.check(REF)` | exit 1, reason `merge policy: soak window has not passed; the owner merges; ask the owner` |
| Code host reads | `checks` once, at the head only; the base commit's checks are never read |

In the code:

- `cli/wuwei/merge.py:313`: the soak rule is a bare
  `require(granted or now - last >= timedelta(minutes=policy['soak_minutes']), 'soak window has not passed')`.
  It has no exception: nothing in `check` knows whether the base is broken or whether this PR
  repairs it. The PR's own checks are read (`checks_at`, line 287) but never compared with
  the checks at `pr['base_sha']`.
- `cli/wuwei/merge.py:326`: every `Refused` becomes
  `merge policy: <rule>; the owner merges; ask the owner`. The soak is the one rule that
  clears by itself with time, so for it the owner clause is wrong, and the end time, which
  the check could compute from `last`, is not printed.
- `cli/wuwei/commands/merge.py:24` prints only the reason; there is no `Next:` line.
- `main_broken` items (#648) are not on `main` (no reference in `cli/`), so the item kind
  cannot be the signal today.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: What makes a PR "a fix to a broken base"? A: Measured on the code host, not read from a
  record: at least one check that failed at the PR's base commit (`pr['base_sha']`,
  conclusion `failure` or `error`) succeeds at the PR head. A `main_broken` fix item (#648)
  meets this by construction, since its PR turns the failing check green, so no item field
  is read; a seat-writable item kind would be a forgeable trust (pre-flight checklist).
- Q: "Or whose diff only touches the failing path"? A: Check evidence carries no failing path,
  so the measured red-to-green rule above stands in for it. A diff that touches the failing
  path but does not turn the check green is not a fix and keeps the soak.
- Q: What does the skip lift? A: The soak only. Every other rule (auto, breaker, cap, quiet
  hours, plan and risk, size, never-auto paths, gates, green checks, approvals, threads,
  bot) still runs first and still refuses.
- Q: Config values? A: `repos.merge.soak_skip`, `"base_fix"` (default) or `"never"`.
  `never` keeps today's soak for every PR.
- Q: When are the base checks read? A: Only when the soak would hold (not granted, the window
  not over, `soak_skip = base_fix`). A PR past its soak, or under a grant, makes no extra
  code host read. An unreadable base check result is exit 2 (fail closed), like any other
  unreadable evidence.
- Q: What does a skip look like? A: Exit 0 as today, and the evidence JSON gains
  `"soak": "skipped: fixes the broken base: <names> fail at <base_sha> and pass at head"`.
  `soak` is `null` when the soak passed or a grant applied. The evidence is journaled with
  the merge, so the reason stays on record.
- Q: The two refusal sentences? A: Soak: reason `merge policy: waits: soak ends at <ISO
  time>`, `Next: run bin/wuwei merge <pr> after <ISO time>`. Every other policy rule: reason
  `merge policy: owner merges: <rule>`, `Next: run bin/wuwei merge <pr>: it merges under the
  owner's grant, or asks the owner on a card` (the #524 path, the same words the PR guard
  already uses). The `Next:` text travels as `Result.data['next']` on exit 1, and only
  `merge check` prints it, so the guard, the shepherd sweep and the event payloads keep a
  one-line reason.
- Q: Exit 2 and granted refusals? A: Unchanged.

## User Scenarios and Testing

### User Story 1 - A fix for a broken base merges now (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a PR inside its soak window whose `tests` check fails at the base commit and
   succeeds at head, with every other rule clear, **When** `merge check` runs, **Then** it
   exits 0 and the evidence carries `soak` naming `tests`, the base commit and `fixes the
   broken base`.
2. **Given** the same PR with `merge.soak_skip = "never"`, **Then** it waits (US2).
3. **Given** the same PR but the base commit's checks all green, **Then** it waits.
4. **Given** the base check fails and the head's same check also fails, **Then** the
   existing required-check refusal stands (the soak is never reached).

### User Story 2 - merge check says wait or who merges, never both (Priority: P1)

**Acceptance Scenarios**:

1. **Given** an ordinary PR inside its soak window, **When** `merge check` runs, **Then** it
   exits 1, prints `merge policy: waits: soak ends at <time>` with the end time (last
   update or approval plus `soak_minutes`), then `Next: run bin/wuwei merge <pr> after
   <time>`; neither line contains `owner merges` or `ask the owner`.
2. **Given** a PR refused by another rule (for example `merge.auto` off), **Then** it prints
   `merge policy: owner merges: merge.auto is off` and `Next: run bin/wuwei merge <pr>: it
   merges under the owner's grant, or asks the owner on a card`, and no `waits`.

### Edge Cases

- Base checks still running or none at the base commit: no failure, so no skip; the PR waits.
- A base check `cancelled`, `timed_out` or `skipped`: not a failure, no skip.
- A check failing at base and absent at head: no skip (the head never ran it).
- A grant: the soak is already lifted (#524); no base read and `soak` is `null`.
- An unreadable or malformed base check result while the soak would hold: exit 2 with the
  reason, never a skip.
- `wuwei merge <pr>` and `pr act` inside the soak: unchanged, the refusal still goes to the
  grant path (card or owner-only command).

## Requirements

- **FR-001**: `repos.merge.soak_skip` in `MERGE_SCHEMA`, string, default `"base_fix"`,
  choices `"base_fix"`, `"never"`.
- **FR-002**: One pure helper `merge.fixes_base(base, head)` returns the sorted check names
  whose conclusion at base is `failure` or `error` and at head is `success`.
- **FR-003**: `merge.check`, at the soak rule, when not granted and the window is not over:
  with `soak_skip = base_fix` it reads the base commit's checks through the existing
  `checks_at` and skips the soak when `fixes_base` names any check; otherwise it returns
  exit 1 with the soak reason and `next` of FR-005.
- **FR-004**: The exit 0 evidence gains `soak`: the skip reason, else `null`.
- **FR-005**: Refusal wording: soak reason `merge policy: waits: soak ends at <end ISO>`, data
  `{'next': 'run bin/wuwei merge <pr> after <end ISO>'}`; other `Refused` reason
  `merge policy: owner merges: <rule>`, data `{'next': "run bin/wuwei merge <pr>: it merges
  under the owner's grant, or asks the owner on a card"}`.
- **FR-006**: `wuwei merge check` prints `Next: <data['next']>` after the reason on exit 1
  when `next` is present.
- **FR-007**: Invariant I40 in design 9.2 and `tests/test_invariants.py`: the soak is skipped
  only for a head that turns a check failing at its base commit green.
- **FR-008**: Docs: `docs/site/configuration.md` row for `repos.merge.soak_skip`, the Soak
  entry in `docs/site/concepts.md`, and a dated amendment line under design 4.6.

## Success Criteria

- **SC-001**: The reproduction above exits 0 with `soak` naming `tests`, with no other rule
  changed.
- **SC-002**: No `merge check` refusal contains both `waits` and `owner merges`.
- **SC-003**: The full suite passes.

## Assumptions

- No orchestrator notes file exists for #668; the reproduction used the `tests/test_merge.py`
  fixture in a temporary workspace instead of a dry-run workspace.
- #648 (`main_broken` items) is not on `main`. The measured red-to-green rule covers its fix
  items without reading the item record, so this feature does not depend on #648.
- GitHub's `base_sha` is the base commit the PR was last compared with, not always the base
  branch tip. A PR whose base was red then but was fixed on the branch since could still
  skip the soak; strict branch protection (`merge_state` must be `clean`) refuses such a
  stale branch first. Accepted, as the skip lifts only the wait.
- A flaky base failure that passes on the PR also skips the soak. Accepted: every other
  rule, approvals at head included, still holds.
- The time is printed as ISO 8601 with offset, the form the rest of the merge evidence uses.
- The owner's "or get a shorter one" is covered by `soak_skip = never` plus the existing
  `soak_minutes`; no separate shorter-soak setting.
- Owner item 31 (launch registration with appended notes) is a separate issue, not this one.
- I40 is the next free invariant id on `main` today; if another branch lands I40 first, the
  builder takes the next free id.

## Deferred

- None.
