# Feature Specification: one evidence read per PR action, a listing read per repository, briefs without a standing doctor run

**Feature Branch**: `907-github-reads`

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #907 (independent review, item 7): read PR evidence once per action and
stop sending every seat through doctor. Field evidence: the owner's core quota went from 5000
to 0 in about 40 minutes with 8 to 13 seats.

## Root causes (0.29.0)

1. `pr_actions.evaluate` reads `watch.evidence` (PR, reviews, discussion, checks) for each PR;
   `launch` and `act` then read the same bundle again (`cli/wuwei/pr_actions.py:251, 454, 638,
   644, 653`), and `_rebase` a third time (`:282`). One PR action collects two or three bundles.
2. `derive.refresh` (`cli/wuwei/derive.py:107`) returns on the first failed repository without
   writing `prs.json`: the repositories after it are never read, the ones before it are read
   and thrown away, and `derive.stale` stays true, so every next `wuwei next` repeats the batch.
3. `brief.DOCTOR` (`cli/wuwei/brief.py:32`) tells every seat to run doctor, which reads every
   adapter, at the start of every brief.
4. Each counterpart PR a brief body names is read from the code host (`brief.py:575`).
5. No charter forbids polling: a builder may loop `gh pr checks --watch`.

## User Scenarios & Testing

### User Story 1 - one PR action, one evidence bundle (P1)

1. **Given** a raised PR with red checks, **When** `wuwei pr act` or next's launch of it runs,
   **Then** the code host sees one `pr`, one `reviews` and one `threads` read.
2. **Given** an unanswered review thread asking a fix, **When** `wuwei pr act` runs, **Then**
   the same single bundle opens the fix round.

### User Story 2 - an unchanged next calls nothing (P1)

1. **Given** three repositories and thirteen PR lanes, one repository failing its listing,
   **When** `wuwei next` runs, **Then** it makes one listing call per repository; **When** it
   runs again inside `pr.poll_seconds`, **Then** it makes no remote call at all.
2. **Given** the poll interval has passed, **Then** each repository is read again, the failed one
   included.

### User Story 3 - briefs read nothing they do not need (P2)

1. Every brief keeps one Doctor line, conditional: only after a WUWEI command fails and its
   refusal names no fix.
2. A counterpart PR in the brief body is written from the day's PR listing with that listing's
   time; one the listing lacks (an issue, an unlisted PR, a failed repository) stays a reference.
   The brief makes no code-host call for it.

### User Story 4 - no seat polls the code host (P2)

1. The common charter (every agent) says: never loop `gh pr checks --watch` or `gh run watch`,
   never repeat `gh pr view`; read once, hand back, `wuwei next` reads again.

## Requirements

- **FR-001**: `evaluate` hands each PR's evidence to its caller; `launch`, `act` and `_rebase`
  act on it and never call `watch.evidence` again.
- **FR-002**: the listing records, per repository, the time of its last read and, when that read
  failed, the reason; `stale` returns the repositories due (never read, read `pr.poll_seconds`
  ago, or read before WUWEI's own last raise, claim, push or merge); `refresh` reads only those
  and keeps the others' rows.
- **FR-003**: `brief.DOCTOR` is conditional on a failure whose refusal names no fix.
- **FR-004**: counterpart lines come from `derive.listing`, never from `host.pr`.
- **FR-005**: `_common.md` carries the no-polling rule; `agents/` is regenerated.

## Success Criteria

- **SC-001**: red-CI `pr act`: 9 code-host calls before, 5 after (one bundle plus the base-check
  read); thread fix: 8 before, 4 after.
- **SC-002**: three repositories, one failing, an hour-old listing: every `wuwei next` made 2
  calls before (the third repository never read) and offered 13 fix launches from stale red
  checks; after, 3 calls on the first and 0 on each unchanged next, the two healthy repositories'
  PRs wait on their fresh state and the failed one's four PRs are unmeasured.

## Assumptions

- Fresh validation before merge or push is unchanged: `merge.execute` and `_gated_push` still read
  the PR themselves, and `_rebase` pushes with the read head as its lease. Reusing the evidence
  read in the same action a moment earlier is as fresh as the second read was.
- The no-polling rule lives in `_common.md`, not `builder.md`: sentinels (CI check-runs at step
  zero) and the shepherd poll too, and a sentence has one home. Overturn: a builder-only failure.
- A counterpart's current remote state is optional evidence; a seat that needs it reads it once
  itself. The item's own PR head line still reads the host.
- Residual, out of scope: a claimed PR with a worktree whose `pr act` launch resolves to a plain
  run (a review question) is read once per `wuwei next` until the planner acts on it.
- The rate-limit message logic (#899) is untouched.
