# Feature Specification: Claude Code in-use process markers are not a tamper finding

**Feature Branch**: `324-in-use-markers`
**Created**: 2026-10-03
**Status**: Ready for implementation
**Input**: Issue #324, fix(integrity). Design section 7.1 (and 9.1). Builds on #104, #165 and
#228. Evidence: the owner's first-run trial of v0.11.0 on Claude Code (2026-10-03),
blocker B1.

## Root cause (reproduced read-only)

Claude Code writes `<plugin install dir>/.in_use/<pid>` for every process that has the
plugin loaded, so its plugin cache cleanup skips versions in use. The installed v0.11.0
cache on the owner's host holds `.in_use/15760`, one 52-byte regular file. WUWEI treats
that file as installed content.

Reproduced in a scratch directory outside the repository against this branch's
`cli/wuwei/integrity.py`, with a small signed test plugin (manifest written, signature
adapter faked to 0) and a workspace with the key pinned:

```text
check:                    exit 0
fresh after marker:       exit 1  page: plugin integrity: .in_use/15760 changed after
                                  the cached verdict; run wuwei integrity check on the host
measure after marker:     exit 1  page: plugin integrity: .in_use/15760
reconfirm:                exit 0  plugin integrity: owner-confirmed content (local evidence)
check after 2nd marker:   exit 1  page: plugin integrity: .in_use/15760; .in_use/21591
```

- `cli/wuwei/integrity.py:39`, `inventory`: the walk prunes only `.git` and `__pycache__`,
  so `.in_use/<pid>` is hashed into `actual`.
- `cli/wuwei/integrity.py:99-100`, `measure`: every name in `expected | actual` whose
  digest differs is a reason, so the marker is an extra-file finding. `check` caches it
  (`integrity.py:171`), and the PreToolUse gate (`cli/wuwei/guards/integrity.py:12`,
  `integrity.cached`) refuses every tool with that reason until the next measurement.
- `cli/wuwei/integrity.py:213`, `fresh` (the cached-verdict mtime walk the heartbeat
  uses): the same prune list, so any marker newer than `verdict.json` is reported as a
  changed file.
- `cli/wuwei/integrity.py:101-102`: the fingerprint hashes `actual`, so `reconfirm` pins
  the current marker set. The next Claude process start or exit changes the set and
  voids the confirmation.

Shadow mode does not help: the integrity gate enforces regardless. Every signed-release
user on Claude Code hits this on the first day.

## User Scenarios & Testing

### User Story 1 - A signed install stays clean while Claude processes come and go (Priority: P1)

The owner installs the signed release, runs `wuwei init`, and works with several Claude
sessions. Each session's marker never pages integrity, never blocks a tool, and never
voids an earlier host confirmation.

**Independent Test**: the `plugin` and `workspace_root` helpers in
`tests/test_integrity.py` with a faked signature adapter; add and remove
`.in_use/<pid>` files and call `measure`, `check`, `cached`, `fresh` and `reconfirm`.

**Acceptance Scenarios**:

1. Given a signed install with `.in_use/12345` created after signing, when `measure()`
   and `integrity check` run, then both exit 0 and the fingerprint equals the one
   measured without the marker.
2. Given a clean cached verdict, when another marker `.in_use/23456` appears with an
   mtime newer than `verdict.json`, then `fresh` still returns exit 0 and `cached` stays 0.
3. Given an install whose content the owner confirmed on the host with `.in_use/12345`
   present, when that marker goes away and `.in_use/23456` appears, then `check` still
   returns the owner-confirmed exit 0 (the fingerprint did not change).

### User Story 2 - The excluded directory is not a hiding place (Priority: P1)

Only what Claude Code writes is skipped: regular files named by a process id, directly
under `.in_use/` at the install root. Anything else there, or an `.in_use` anywhere else,
is still a finding that names the path.

**Independent Test**: the same helpers, one case per shape, asserting exit 1 and the
specific reason from `measure`, and a non-zero `fresh` that names the entry.

**Acceptance Scenarios**:

1. Given `.in_use/evil.py`, when `measure()` runs, then it exits 1 with
   `page: plugin integrity: not a Claude Code process marker: .in_use/evil.py`.
2. Given a directory `.in_use/sub/` or a symlink `.in_use/12345`, then each is the same
   finding naming that entry.
3. Given `charters/.in_use/12345` (an `.in_use` below the root), then it is measured as
   an ordinary extra file: exit 1 naming `charters/.in_use/12345`.
4. Given `.in_use` itself is a symlink to a directory, then the existing refusal fires:
   exit 1 with `symlink in installed plugin: .in_use`.
5. Given `.in_use/evil.py` written after the cached verdict, then `fresh` is non-zero and
   its reason names `.in_use/evil.py`.
6. None of these can be blessed by `reconfirm`: a refusal carries no fingerprint, as for
   symlinks today.

### User Story 3 - The release asset works through the real launcher (Priority: P1)

**Independent Test**: one real smoke in `tests/test_integrity.py`, skipped when
`ssh-keygen` is absent: a release stage built by `scripts/build-release.py`, re-keyed and
signed with a throwaway key, a marker added, then `bin/wuwei` of that stage driven as a
subprocess.

**Acceptance Scenarios**:

1. Given the signed release stage with `.in_use/12345` present, when
   `<stage>/bin/wuwei init <ws>` runs, then it prints `plugin integrity: clean`.
2. Given that workspace, when a Bash `ls` PreToolUse payload is piped to
   `<stage>/bin/wuwei hook PreToolUse`, then it exits 0.
3. Given a second marker `.in_use/23456` then appears, when
   `<stage>/bin/wuwei integrity check` and the same hook run, then both exit 0.

### Edge Cases

- `.in_use` empty: pruned, nothing measured.
- `.in_use` is a regular file at the root (not a directory): it is not pruned and stays
  an ordinary extra-file finding.
- A marker name with leading zeros (`0123`) is all digits and accepted; a name with a
  sign, a space, a dot or non-ASCII digits is not.
- Development checkouts are unchanged: `measure` with a checkout reads the tracked tree
  through the VCS port, so untracked markers never enter it. Claude Code writes markers in
  its plugin cache, which holds release copies, not checkouts.
- Release builds are unchanged: `write_manifest` uses `inventory`, and a CI stage has no
  `.in_use`.
- The PreToolUse gate still reads only the cached verdict and never walks the plugin;
  hook latency is unchanged.

## Requirements

- **FR-001**: Both plugin walks (`inventory` and `fresh`) prune through one shared helper
  in `cli/wuwei/integrity.py`. It drops `.git` and `__pycache__` as today and drops
  `.in_use` only when the walk is at the install root and `.in_use` is a real directory
  (not a symlink).
- **FR-002**: Before pruning `.in_use`, the helper checks every direct entry. Each must be
  a regular file (not following symlinks) whose name is one or more ASCII digits.
  Otherwise it raises `ValueError('not a Claude Code process marker: .in_use/<name>')`,
  which `measure` reports as exit 1 `page: plugin integrity: ...` and `fresh` reports as
  a non-zero result with the same text.
- **FR-003**: A symlinked `.in_use` is never pruned, so the existing
  `symlink in installed plugin: .in_use` refusal fires. An `.in_use` below the root is
  never pruned and is measured like any other directory.
- **FR-004**: The fingerprint `measure` returns, which `check` caches and `reconfirm`
  confirms, excludes the pruned markers. No separate exclusion is added to `reconfirm`,
  `check` or `cached`: all of them go through `measure` and `inventory`.
- **FR-005**: `docs/integrity.md` names the exclusion and why: Claude Code writes one
  marker per running process, so they change whenever a process starts or exits, and
  anything else under `.in_use/` is still a finding.
- **FR-006**: No guard refuses less outside this exclusion. Exit semantics, the verdict
  producer, pinning, confirmation and scope (#165, #228) are unchanged.

### Key Entities

- In-use marker: `<install root>/.in_use/<pid>`, a regular file written and removed by
  Claude Code, never imported or executed by WUWEI.

## Success Criteria

- SC-001: With any number of markers present, a signed install measures clean and the
  first and every later tool call passes, with no owner action.
- SC-002: A process start or exit never changes the integrity fingerprint.
- SC-003: Every non-marker entry under the root `.in_use/` is a finding that names it.

## Assumptions

- Claude Code writes only regular files named by a decimal process id directly under
  `.in_use/` (the owner's host shows exactly that). A temporary or differently named file
  there would page; if one is ever observed, the name rule widens then.
- Marker content is not checked: it is Claude Code's, changes per process and is never
  read by WUWEI. Only the name and file type are checked.
- `fresh` keeps its current error mapping: a `ValueError` becomes exit 2 with the reason
  text. The heartbeat treats any non-zero `fresh` as failed and shows the reason, so the
  entry is named either way. `measure` (SessionStart, sweeps, `integrity check`) is where
  the exit 1 finding is cached.
- Listing `.in_use` fails closed: if it cannot be read (it vanished between the walk's
  listing and the check, or permission is denied), the walk raises `OSError` and the
  result is unmeasured, as for any unreadable path today. The next measurement retries.
- "Release-asset smoke" means an in-repo test that builds the stage with
  `scripts/build-release.py` and drives its real `bin/wuwei`; `scripts/headless_e2e.py`
  is not changed.
- The design spec 7.1 wording ("every shipped file") still holds: markers are not shipped.
  No design amendment is needed.

## Deferred

- None.
