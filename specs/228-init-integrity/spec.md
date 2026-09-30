# Feature Specification: A workspace is usable right after init

**Feature Branch**: `228-init-integrity`
**Created**: 2026-09-30
**Status**: Ready for implementation
**Input**: Issue #228, fix(security). Design sections 7.1 and 9.1. Depends on #104 and
#165. Evidence: the v0.6.0 operator dry run of 2026-09-30, finding 4 and the ws2 probe.

## Root cause (reproduced read-only in the dry-run probe workspace)

`bin/wuwei init .` from the v0.6.0 signed install, then `bin/wuwei hook PreToolUse` with a
Bash `ls` payload in that workspace (the ws2 probe, re-run through this branch's
`bin/wuwei`):

```text
exit 2
plugin integrity unmeasured: [Errno 2] No such file or directory:
'<workspace>/.wuwei/integrity/verdict.json'; run wuwei integrity check on the host
```

`.wuwei/integrity/` holds only `pinned.pub`. In the main dry-run workspace the same refusal
hit the first tool call after init; `bin/wuwei integrity check` then printed
`plugin integrity: clean` and every later call passed.

- `cli/wuwei/commands/init.py:75-76`: `run` calls `integrity.initialize` (pins the key,
  starts workspace history) but never `integrity.check`, so no verdict is cached.
  `upgrade` (`cli/wuwei/commands/init.py:167-230`) never measures either.
- `cli/wuwei/guards/integrity.py:12`: PreToolUse reads only the cached verdict through
  `integrity.cached` (`cli/wuwei/integrity.py:176`). The missing file raises at
  `cli/wuwei/integrity.py:178` and becomes the errno message at
  `cli/wuwei/integrity.py:192`. Every tool is refused until something on the host runs
  `integrity.check` (SessionStart, a sweep, or `wuwei integrity check`).
- Development checkout (probed from this branch, a clean checkout, in a scratch
  workspace): after `init` and `integrity check`, PreToolUse is refused with
  `page: plugin integrity: development checkout requires host reconfirmation`
  (`cli/wuwei/integrity.py:81`). It names no command, so the owner is not told to run
  `wuwei integrity reconfirm`. The dirty-checkout reason (`cli/wuwei/integrity.py:160`)
  names none either.
- Cost found while reproducing: on a clean development checkout `integrity check` took
  9 s. `measure` lists the tracked tree through `vcs.read_tree`
  (`adapters/vcs/git.py:586-592`), which starts one `git show` per tracked file (771
  files, about 10 ms each). One `git cat-file --batch` reads the same blobs in about
  0.1 s. The suite runs `init` from the repository (a development checkout) about 45
  times, so once init measures, a clean checkout (CI, main) would add minutes to the
  171 s suite.

## User Scenarios & Testing

### User Story 1 - Signed install is clean right after init (Priority: P1)

The owner runs `wuwei init` from a signed release and starts Claude Code in the workspace.
The first tool call runs without any other command.

**Independent Test**: `init.run` into a temp directory with `integrity.PLUGIN` pointed at
a signed test plugin (manifest written, fake signature adapter returning 0), then the
PreToolUse hook on a Bash payload in that workspace.

**Acceptance Scenarios**:

1. Given `wuwei init` from a signed install, when the next PreToolUse in that workspace
   runs, then it exits 0 without any other command.
2. Given `wuwei init` from a signed install, then init prints `plugin integrity: clean`
   and `.wuwei/integrity/verdict.json` records exit 0 with a fingerprint.
3. Given an existing workspace, when the owner runs `wuwei init --upgrade`, then the
   verdict is measured and cached as the last step; `init --upgrade --dry-run` does not
   measure and writes nothing.

### User Story 2 - Development checkout says reconfirm, once and clearly (Priority: P1)

The developer runs `wuwei init` from a source checkout. Init tells them to reconfirm, and
the first tool call is refused with that same one-line instruction, not an errno.

**Independent Test**: `init.run` with `integrity.PLUGIN` pointed at a test plugin that has
a `.git` directory and a VCS fake (HEAD, clean status, tracked tree), then PreToolUse.

**Acceptance Scenarios**:

1. Given a development checkout, when init completes, then it prints one line naming
   `wuwei integrity reconfirm` on the host.
2. Given a development checkout, when the first PreToolUse after init runs, then it is
   refused (exit 2) with that one-line reconfirm instruction, and the reason contains no
   `Errno`.
3. Given a dirty development checkout, then the line says to restore a clean commit and
   run `wuwei integrity reconfirm` on the host.
4. Given the owner then reconfirms on the host, then PreToolUse passes (unchanged #165
   behaviour, covered by the existing checkout tests).

### User Story 3 - Measuring a development checkout stays fast (Priority: P2)

Init, SessionStart and `integrity check` on a clean development checkout read the tracked
tree with one git process for all blobs instead of one per file, so init stays quick and
the suite does not grow by minutes.

**Independent Test**: `read_tree` on a real temp git repository returns the same content
map as before (including a file name with a space) with two git processes.

**Acceptance Scenarios**:

1. Given a repository with N tracked files, when `read_tree(repo, ref, ['.'])` runs, then
   it starts two git processes (`ls-tree` and `cat-file --batch`) and returns
   `{path: content}` exactly as before.
2. Given a listed entry that `cat-file` reports missing or not a blob (for example a
   submodule entry), then `read_tree` returns exit 2, as a failing `git show` did.

### Edge Cases

- Integrity cannot be measured at init (no git, no ssh-keygen, unreadable plugin): init
  prints the `plugin integrity unmeasured: ...` reason and the cached verdict is exit 2,
  so PreToolUse stays refused with that reason. Init never prints clean when unmeasured.
- A workspace created before #165 has no `pinned.pub`: `init --upgrade` caches an
  unmeasured verdict naming the missing pin and does not create the pin (the owner copies
  it after review, as `docs/integrity.md` says).
- Init fails before the rename: no workspace exists and nothing is measured.
- Outside a workspace, PreToolUse still returns 0 (scope unchanged).
- The PreToolUse gate still never walks the plugin; SessionStart and sweeps still
  re-measure.

## Requirements

- **FR-001**: `wuwei init` (new workspace) runs `integrity.check(root)` on the created
  workspace as its last step and prints `result.reason or 'plugin integrity: clean'`.
- **FR-002**: `wuwei init --upgrade` without `--dry-run` does the same as its last step.
- **FR-003**: The development-checkout reason and the dirty-checkout reason each end with
  `run wuwei integrity reconfirm on the host`, on one line. The same string reaches init
  output, `wuwei integrity check`, SessionStart and the PreToolUse denial (through the
  cached verdict).
- **FR-004**: Init's exit code is unchanged by the integrity verdict: it still reports
  workspace creation and MCP registration. The verdict is enforced by the PreToolUse gate.
- **FR-005**: `read_tree` in the git adapter reads all listed blobs with one
  `git cat-file --batch` process; its return value and failure semantics are unchanged.
  The command allowlist admits exactly `cat-file --batch`.
- **FR-006**: No guard refuses less: a missing, invalid or failing verdict still denies;
  #165 pinning and confirmation rules are unchanged; upgrade never writes `pinned.pub` or
  `confirmation.json`.

### Key Entities

- Cached verdict: `.wuwei/integrity/verdict.json`, written only by `integrity.check`
  (producer unchanged), now also produced at init.

## Success Criteria

- SC-001: After init from a signed install, zero extra commands are needed before the
  first tool call succeeds.
- SC-002: After init from a development checkout, the first refusal names the reconfirm
  command and contains no errno.
- SC-003: `read_tree` of this repository's HEAD uses one `ls-tree` and one `cat-file`
  process (was one process per file, 9 s on the owner's host).
- SC-004: The full suite on a clean checkout takes at most about 10 percent longer than
  the 171 s baseline on the owner's host.

## Assumptions

- Init prints the verdict on stdout, the same line `wuwei integrity check` prints.
- Init's exit code does not include the verdict (FR-004). Returning 1 would make every
  development-checkout init fail and break the tests that init from the repository; the
  gate already fails closed on the cached verdict, so nothing is weakened.
- "Last step" means after MCP registration, just before returning, so the cached verdict
  is the newest measurement when init ends.
- `init --upgrade --dry-run` does not measure: `integrity.check` writes the verdict, and a
  dry run writes nothing.
- The reconfirm wording reuses the phrase `cached` already uses
  (`run wuwei integrity reconfirm on the host`).
- The `read_tree` speed-up is in scope because this issue makes every init from a
  development checkout measure the tree (US3). It changes no port signature, so
  `closing.py` and every fake are unaffected.
- Docs: `docs/integrity.md` says init and `init --upgrade` cache the verdict; the README
  and `docs/site/index.md` quick starts drop the separate `integrity check` line and say
  init prints the verdict. No new config key.

## Deferred

- Workspaces created before this change that never run `init --upgrade` still get the
  errno message until SessionStart or `integrity check` runs; that message already names
  the command.
- A development checkout still reads HEAD and status on every PreToolUse (cached
  checkout comparison), as noted in #211.
