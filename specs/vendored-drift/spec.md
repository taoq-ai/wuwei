# Feature Specification: the vendored plugin in .claude/ matches the tree it was copied from

**Feature branch**: `claude/vendored-drift`
**Item**: vendored-drift, tier full, goal G-1
**Input**: the plugin copy in `.claude/wuwei/` that runs this repository's cloud sessions said 1.1.0
while main said 1.2.1, and `evidence.py`, `gh.py` and `setup.py` differed. Merged fixes did not
reach the doors in this repository.

## The promise in my words

A test in `tests/test_setup.py` runs `setup.vendor()` into a scratch directory and compares the
result with the committed `.claude/`. It fails, naming each path, when any file vendor writes is
missing or different, or when `.claude/wuwei/` or one of WUWEI's skill folders holds a file vendor
would not write. `__pycache__` and `.pyc` files are ignored. release-please bumps
`.claude/wuwei/.claude-plugin/plugin.json` along with the root `plugin.json`, so a release PR stays
green. This PR re-vendors the copy at its head. After it, any PR that changes `cli/`, `charters/`,
`agents/` or `skills/` must carry the re-vendored copy, or the suite fails. No runtime lines are
added. `vendor()` itself, symlinks and doctor checks are out of scope.

The acceptance scenarios, restated:

1. A file under `.claude/wuwei/cli/wuwei/` differs from `cli/wuwei/`: the drift test fails and
   names that file.
2. `.claude/` freshly written by `setup.vendor()`: the drift test passes.
3. A release PR bumps the root `plugin.json`: release-please bumps the copy's too, so both carry
   the same version and the drift test passes.
4. At the PR head the copy's `plugin.json` says the main version. The item says 1.2.0; main moved
   to 1.2.1 with release #1072, so the copy says 1.2.1.
5. The runtime size test still passes at 3,000 lines or fewer.

## Clarifications

### Session 2026-10-16

- Q: Which version must the copy carry? A: Whatever the root `.claude-plugin/plugin.json` says at
  the head, now 1.2.1. The "1.2.0 today" in the item predates release #1072.
- Q: Does a project's own agent or skill in `.claude/` count as drift? A: No. Extra files count
  only under `.claude/wuwei/` and WUWEI's own skill folders, which vendor owns. In
  `.claude/agents/` only the files vendor writes are compared, because a project may keep its own
  agents there and vendor does not remove them.
- Q: How does the test get "what vendor writes"? A: It calls `setup.vendor()` into a temporary
  directory and compares bytes, so the test follows vendor's own file list and never restates it.
- Q: Where does the release-please test look? A: It checks that `extra-files` has a `json` entry
  with `jsonpath` `$.version` for both plugin.json paths, and that both files carry the same
  version at the head.

## User scenarios

### US1: the copy cannot silently lag the tree (P1)

Acceptance 1, 2 and 4. Test: `test_the_vendored_plugin_matches_the_tree_it_was_copied_from` and
`test_the_drift_check_names_a_changed_vendored_file`.

### US2: a release keeps the copy in step (P1)

Acceptance 3. Test: `test_release_please_bumps_the_vendored_plugin_version_with_the_root`.

## Requirements

- FR-001: A test fails, naming each path, when the committed `.claude/` differs from a fresh
  `setup.vendor()` run, ignoring `__pycache__` and `.pyc`.
- FR-002: Extra files under `.claude/wuwei/` and WUWEI's skill folders count as drift; a project's
  own agents and skills do not.
- FR-003: `release-please-config.json` bumps `.claude/wuwei/.claude-plugin/plugin.json` `$.version`.
- FR-004: The PR re-vendors `.claude/` at its head.
- FR-005: No line is added under `cli/wuwei/`.

## How this fails

1. A release PR bumps the root version but release-please does not touch the copy (wrong path or
   jsonpath), so the first release after merge goes red on main. Guarded by the config test, which
   checks the exact path and jsonpath release-please reads.
2. A local `__pycache__` or an editor file inside `.claude/wuwei/` makes the test fail on a
   developer machine while CI stays green. `__pycache__` and `.pyc` are ignored; other stray files
   are real drift and the message says how to fix it.
3. A contributor changes `cli/` and forgets to re-vendor, and the failure reads as unrelated. The
   assertion message names the paths and the fix (`wuwei init --cloud` or `setup.vendor()`).

## Assumptions

- A project's own agents in `.claude/agents/` are not drift (see Clarifications). Overturned if
  the owner wants vendor to own that folder outright.
- The ADR for the 1.2.1 release goes in `docs/adr/`, the folder `docs/site/concepts/decisions.md`
  and `hook.py` name, created here because none existed.

## Success criteria

- SC-001: The suite passes at the head with the re-vendored copy and fails with the old one.
- SC-002: `cli/wuwei/` stays at 3,000 lines.
