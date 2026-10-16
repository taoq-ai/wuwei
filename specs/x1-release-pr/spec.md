# Spec: a release-please PR is read as generated (X-1, X-2)

## In my words

The 1.2.1 release PR (taoq-ai/wuwei#1072 at 2fbffd8) bumped a version in three files and held two
gaps: "no test in the diff" and "gates missing: quality". You accepted both as exceptions, and every
release PR would need the same two. After this change evidence reads such a PR the way it reads a
docs PR: no test gap and no gate gap. CI, review threads, owner review and the other safety gaps
still apply.

A PR is a release PR only when all three hold:

1. Its author is `github-actions[bot]` or `release-please[bot]`.
2. Its head branch starts with `release-please--`.
3. Every changed file is `.release-please-manifest.json`, `CHANGELOG.md`, or an `extra-files` path
   that `release-please-config.json` names, read from the base branch.

Anything else keeps every gap. When the config cannot be read or parsed, only the manifest and
CHANGELOG.md count, so `plugin.json` keeps the gaps.

## Acceptance scenarios

1. The 1.2.1 shape (bot author, `release-please--` branch, plugin.json, manifest, CHANGELOG): neither
   "no test in the diff" nor a gates gap is listed.
2. The same files from a person, or on a branch not starting with `release-please--`: both gaps, as today.
3. A bot `release-please--` PR that also changes `cli/wuwei/guards.py`: both gaps.
4. `release-please-config.json` unreadable on the base branch: only the manifest and CHANGELOG count;
   plugin.json keeps both gaps.
5. The runtime size test still passes at 3,000 lines or fewer.

## Requirements

- FR-1: `evidence.release(repo, pr)` is true only when the author, branch and file conditions all hold.
- FR-2: the config is read with `gh.file` at the PR's base branch, never at its head, so a PR cannot
  widen its own allow list.
- FR-3: an `extra-files` path resolves under its package path; a leading `/` means the repository root.
- FR-4: a missing file, invalid JSON or an unexpected shape adds no paths (fails closed).
- FR-5: for a release PR, `gaps` passes no files to `gates_for` and lists no test gap; every other check is unchanged.
- FR-6: evidence.py frees the lines it adds; the runtime stays at 3,000 lines or fewer.

## Assumptions

- `release-please[bot]` is the login the Release Please GitHub App posts as; the action with the default
  token posts as `github-actions[bot]`. Overturned if the owner's release workflow uses another app token.
- A release PR follows the docs rule exactly: when the change failure budget is overrun, every gate is
  required again, as for docs. Overturned if the owner wants release PRs exempt even then.
- Only the root `CHANGELOG.md` counts, as the item says; a monorepo package's own changelog keeps the gaps.
  Top-level `extra-files` defaults in the config are not read. Both fail closed.
- The file condition checks paths, not the patch: a bot PR that edits more than the version inside
  plugin.json passes this check. Only workflows with write access can push a `release-please--` branch.
