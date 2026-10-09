# Feature Specification: guard false refusals on a published merge and on read-only gate reads

**Feature Branch**: `616-guard-false-refusals`
**Created**: 2026-10-09
**Status**: Draft
**Input**: GitHub issue #616: WUWEI v0.23.0 ran a full autonomous day under Claude Code
desktop and two guards refused work that broke no rule. (A) Merging `main` into a feature
branch and pushing it was refused by the push identity check, because `main` carries GitHub's
merge commit (committer `GitHub <noreply@github.com>`) and that commit is in
`origin/<branch>..HEAD`. (B) The verdict lint ran on read-only Bash calls (`cat`, `grep`,
`shasum` of a gate file) and linted every gate file of the day with the caller's role (the
planner's or a builder's), so the planner's reads were refused, each refusal was recorded as
a `verdict.rejected` event, and the day's `verdict_lint_rejections` metric was inflated.

## Root cause

- A: `adapters/vcs/git.py` `push_commits` reads `git log -z <format> <base>..<local> --`,
  where `<base>` is the remote SHA, the destination's tracking ref, or the default branch's
  tracking ref for a new branch. After `git merge origin/main` every commit `main` gained since
  the branch last reached the remote is in that range, including commits already published by
  someone else. `cli/wuwei/guards/commit_push.py` `push_check` identity-checks each of them, so
  the GitHub-committed merge fails `committer differs`. The native pre-push hook
  (`cli/wuwei/commands/git_hook.py`) and `pr_actions` call the same `push_check`.
- B: `cli/wuwei/guards/verdict.py` `check_write` treats any Bash command whose text contains
  `gate-` as a possible gate write: it globs every `gate-*.md` in today's `decisions/` and
  calls `lint_file(path, role=<caller's agent_type>)`. Nothing asks whether the call can write
  at all, and the caller's role is applied to gate files other seats wrote (a
  `sentinel-quality` caller applies the quality rules to a security gate).

## Clarifications

### Session 2026-10-09

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Which commits does the push identity check skip? A: Every commit reachable from any
  remote-tracking ref (`git log <base>..<local> --not --remotes --`). Those are already
  published, so their author and committer are not this push's. Every other outgoing commit
  is still checked, including one by another identity that no remote has.
- Q: Only the push's own remote (`--remotes=<remote>`) or any remote? A: Any remote. A commit
  on any remote is already published by someone; an upstream and a fork remote is a normal
  layout, and the narrower form would keep the false refusal there.
- Q: A remote-tracking ref can be written locally (`git update-ref refs/remotes/...`). Does
  that open a bypass? A: Not a new one. The range base already comes from the same refs (the
  destination's tracking ref, or the default branch's for a new branch), so a forged tracking
  ref already shortens the checked range today; design 9.1 states no local file is a
  boundary. The identity check is attribution, not a trust boundary; protected refs and the
  owner's credentials anchor publishing (4.5).
- Q: Which Bash calls are read-only for the verdict lint? A: The ones the shared classifier
  (`shell.classify(command, cwd=...)`, the walk every Bash guard and I10 use) marks
  `readonly`. A redirect, an interpreter snippet, a write program or an unparsed publisher
  is not read-only and is still linted.
- Q: Are checksum tools read-only? A: Yes. `shasum`, `sha1sum`, `sha256sum`, `sha512sum`,
  `md5sum` and `cksum` only read their operands (or stdin) and print digests; none has an
  output-file option or runs a program. They join `shell.READ_ONLY`, which also makes them
  readers for `protect_state` (no write target) and keeps them out of the `unread` refusals,
  both correct for a command that writes nothing.
- Q: With which role does a Bash write lint a gate file? A: The one its file name implies
  (`role=''`; `lint_file` derives the quality and class-sweep rules from the name, as the
  `verdict lint FILE` CLI does without `--role`). A Bash call cannot say which gate file it
  wrote, so the caller's role is not evidence for any one of them. The Write/Edit path keeps
  the caller's role (its target is exact), and SubagentStop keeps the stopping seat's role on
  the seat's own gate file, so a quality seat that writes a generically named gate through
  Bash is still held to the quality rules when it stops.
- Q: Does a Bash write still lint every gate of the day? A: Yes; the scan is unchanged (the
  written target cannot always be read from shell text). Only reads stop reaching it.

## User Scenarios and Testing

### User Story 1 - Merging main into a feature branch pushes (Priority: P1)

A builder merges `origin/main` into its branch after `main` gained GitHub's merge commit, and
pushes. The push identity check sees only the branch's own new commits.

**Acceptance Scenarios**:

1. **Given** a bare remote whose `main` holds a commit committed by `GitHub
   <noreply@github.com>`, and a feature branch with owner-identity commits that merges
   `origin/main` (the merge commit by the owner), **When** `push_commits` reads the range for
   the branch (pushed before, or new), **Then** it returns only the feature's own commits and
   `push_check` passes.
2. **Given** the same branch plus a commit by another identity that is on no remote, **When**
   the range is read, **Then** that commit is returned and `push_check` refuses it with
   `pushed commit identity`.
3. The native pre-push hook and `pr` actions read the same range (one function).

### User Story 2 - Reading a gate file is not a gate write (Priority: P1)

**Acceptance Scenarios**:

1. **Given** today's `gate-a-quality.md` would fail the lint, **When** a Bash call runs `cat`,
   `grep` or `shasum` on it, **Then** `check_write` returns clean and no `verdict.rejected`
   event is recorded.
2. **Given** the same file, **When** a Bash call writes to a gate path (`cp x
   .../decisions/gate-a-quality.md`, or a redirect into it), **Then** the lint runs and the
   finding is returned and recorded.
3. **Given** a caller whose role is `sentinel-quality` and a security gate file that passes
   its own rules, **When** a Bash write runs, **Then** the security file is not held to the
   quality rules.
4. An interpreter snippet naming a gate file is still refused as an opaque gate write.

## Requirements

- **FR-001**: `push_commits` reads `git log -z <format> <base>..<local> --not --remotes --`
  for every base it uses (remote SHA, destination tracking ref, default-branch tracking ref);
  the `_run` allowlist admits exactly that form.
- **FR-002**: `push_check` is unchanged: it identity-checks every commit `push_commits`
  returns.
- **FR-003**: `verdict.check_write` returns clean for a Bash call that
  `shell.classify(command, cwd=cwd).readonly` marks read-only, before the interpreter check
  and the scan, and records nothing.
- **FR-004**: A Bash call that can write lints each of today's gate files with `role=''`.
  The interpreter-snippet refusal, the Write/Edit path and the SubagentStop path are
  unchanged.
- **FR-005**: `shell.READ_ONLY` gains `shasum`, `sha1sum`, `sha256sum`, `sha512sum`,
  `md5sum` and `cksum`.
- **FR-006**: Each changed rule has its invariant test, and its design 9.2 row is raised
  for the owner (below).

## Success Criteria

- **SC-001**: A branch that merged `main` after a GitHub merge pushes with no refusal.
- **SC-002**: A day's `verdict_lint_rejections` counts only gate files a call could have
  written, never the planner's reads.

## Assumptions

- GitHub's merge commit reaches the workspace through `git fetch`, so it is on
  `refs/remotes/origin/main` before the feature branch merges it; a merge from a ref with no
  remote-tracking copy is checked as before.
- The lint's role inference from the file name (`quality`, `arch`, `security` tokens) is the
  existing rule of `verdict lint FILE`; gate files follow `gate-<item>-<role>.md`.
- The issue is #616.

## Design spec conflict (raised, not resolved)

The constitution asks every changed guard rule for a design 9.2 row and a check in
`tests/test_invariants.py`. The design spec is amended only by its owner, and
`test_table_matches_the_checks` requires the table rows and `INVARIANTS` to match, so the
checks are pinned as `test_invariant_*` tests in `tests/test_vcs.py` and
`tests/test_verdict.py` (as #556 and #557 did) and the pull request asks the owner to add:

| Id | Invariant | Checked by | Notes |
| --- | --- | --- | --- |
| I25 | The push identity check reads every outgoing commit no remote-tracking ref reaches, and only those | `push_commits` on a real repository whose `main` holds a GitHub-committed commit merged into a feature branch, with and without a foreign-identity commit on no remote | #616; the pinned case stays in `tests/test_vcs.py` |
| I26 | The verdict lint runs only on a call that can write, with the role the gate file names; a read-only Bash call records no rejection | `check_write` on `cat`, `grep` and `shasum` of a failing gate file, a `cp` and a redirect into it, and a `sentinel-quality` caller writing beside a security gate | #616; the pinned cases stay in `tests/test_verdict.py` |

Design 4.1's `git commit`, `git push` row would read "author or committer of a commit the
push publishes first (one no remote-tracking ref reaches) differs from repository config".
Its `decisions/gate-*.md` row already says "write to", which this feature now honours.

## Deferred

- A fast-forward merge of `origin/main` into a branch with no commits of its own leaves HEAD
  on GitHub's commit, and `push_check`'s HEAD identity row (the `head` argument of
  `identity_check`) still refuses that push. The reported day merged with a merge commit, so
  this is a follow-up issue to file, linked to #616, not silent scope.
- Moving the two pinned invariant tests into `tests/test_invariants.py` `INVARIANTS` once the
  owner adds rows I25 and I26 to design 9.2.
