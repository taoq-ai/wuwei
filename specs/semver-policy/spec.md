# Feature Specification: a breaking change is an incompatible change to the declared public API, per SemVer

**Feature branch**: `docs/semver-policy`
**Item**: semver-policy, tier full, goal G-2
**Input**: the owner, 2026-10-19: "Yes, fix the concept of breaking change; use semver policy".
Arch rule 7 calls a change breaking when an existing client would behave differently, and says
yes when unsure. Fixes that closed guard bypasses or added gaps were released as majors: v2.0.0
to v4.0.0 in four days, and release PR #1147 proposes 5.0.0 from #1148 and #1150.

## The promise in my words

Breaking gets one definition, written once, and every other place points to it.

1. `docs/site/concepts/evidence.md`, section Breaking changes, declares WUWEI's public API: the
   CLI commands, flags, exit codes and the output documented for scripts; config keys and their
   defaults; the ledger, state and verdict file formats; the PR body lines and owner question
   shapes that seats and owners write; the hook input and output contract.
2. The same section classifies a change, citing SemVer 2.0.0. Major: a public API element is
   removed, renamed or changes meaning, an input becomes required, an exit code or a format
   changes. Minor: a new capability, or a fix that makes WUWEI refuse or report more (a bypass
   closed, a gap it missed), as ESLint treats a fix that reports more errors. Patch: a fix that
   refuses or reports less, docs, internals. Behaviour that contradicted the docs was a bug, so
   fixing it is not a major. One sentence says v2.0.0 to v4.0.0 were bumped under the earlier
   rule and the SemVer policy applies from 4.1.0; no tag moves.
3. `charters/sentinel-arch.md` rule 7 says the same in no more words than today (66), replaces
   "When unsure, say yes" with "When unsure, ESCALATE", and `Breaking: yes` means a major only.
4. `charters/builder.md` rule 6: `!` and `BREAKING CHANGE:` mark a major only; a stricter check
   is a `fix:` with release notes in the body.
5. `docs/design.md`, `docs/site/reference.md`, `docs/site/concepts/decisions.md` and
   `charters/_common.md` say a breaking change is a major and point to the section.
6. The `Announcement:` line and the owner's `breaking:` confirmation stay keyed to a breaking
   change, which now means a major only. No change under `cli/wuwei/`.
7. The squash commit carries `Release-As: 4.1.0`, so release-please cuts 4.1.0 for #1148 and
   #1150 instead of 5.0.0.

Outside: the runtime, the verdict parser, any tag or published release.

The acceptance scenarios, restated:

1. A gate brief for a fix that closes a guard bypass or adds a gap: the arch seat reads rule 7 and
   writes `Breaking: no` naming the bump as a minor.
2. A change that renames a CLI flag or changes an exit code: rule 7 makes it `Breaking: yes`.
3. After the merge, release-please reads `Release-As: 4.1.0` from the squash commit and its
   release PR proposes 4.1.0.
4. After `bin/wuwei agents build`, every `agents/*.md` is at or under AGENT_WORDS (2,250).

## How this fails

1. The arch seat reads "refuses or reports more" as covering a change that also renames a flag or
   a PR body line, and calls a real break a minor. Held: rule 7 lists the major cases first and
   the docs say a change with any major part is a major; when unsure the gate ESCALATEs, so the
   owner decides instead of the gate guessing either way.
2. Release-please ignores `Release-As:` because the lead squashes with a message that drops the
   footer, or puts it in the PR body only. Held: the PR body says the lead carries the line alone
   in the squash commit message; acceptance 3 is read on the release PR after the merge. Rollback:
   a later commit with `Release-As: 4.1.0` before the release PR merges.
3. The rule 7 rewrite or the `_common.md` edit pushes `agents/sentinel-arch.md` over 2,250 words
   and the ceiling test fails. Held: rule 7 is 65 words (66 before), `_common.md` loses one word,
   and the build is measured with `wc -w agents/*.md`.

## Clarifications

### Session 2026-10-19

- Q: The charters are generic, but the public API list names WUWEI's surfaces. Where does each
  live? A: The docs section declares WUWEI's own API. Rule 7 says "the declared or documented
  public API", so in another repository the arch seat reads that repository's declaration.
- Q: A stricter reading of a PR body line (#1148 counts an `Announcement:` line only as a bare
  URL) changes a format seats write. Is that a major? A: No when the docs already stated the
  stricter form: behaviour that contradicted the docs was a bug. The docs section says so.
- Q: How does the arch seat name the bump when the verdict has only a `Breaking:` field? A:
  `Breaking: no (minor)`; the parser already reads `no` followed by any text as no.
- Q: Which versions does the history sentence cover? A: v2.0.0 to v4.0.0, as the coordinator's
  brief asked. Published tags and releases stay as they are.

## User Scenarios & Testing

### US1: rule 7 classifies by SemVer (P1)

Acceptance 1 and 2. Red: `test_a_breaking_change_is_a_semver_major_of_the_declared_public_api`
fails on main. Green after the charter edits.

### US2: one definition, pointed to (P1)

The docs section declares the API and the classification; design.md, reference.md and
decisions.md link to it. Held by the same test.

### US3: release 4.1.0 (P1)

Acceptance 3, read on the release PR after the merge.

### US4: the agents fit (P1)

Acceptance 4, held by `test_a_generated_agent_stays_under_the_word_ceiling` and `wc -w`.

## Requirements

- FR-001: `evidence.md` Breaking changes declares the public API, the classification, the
  SemVer 2.0.0 and ESLint citations and the history sentence.
- FR-002: `sentinel-arch.md` rule 7, at most 66 words, names the public API, a major, and
  ESCALATE when unsure.
- FR-003: `builder.md` rule 6: `!` and `BREAKING CHANGE:` for a major only; a stricter check is a
  `fix:` with release notes.
- FR-004: `_common.md`, `design.md`, `reference.md`, `decisions.md` match and point to the section.
- FR-005: `agents/` rebuilt, `.claude/` re-vendored, every agent at or under 2,250 words.
- FR-006: the PR body holds `Release-As: 4.1.0` alone on a line for the squash commit.

## Assumptions

- `Release-As: 4.1.0` in the squash commit body overrides the 5.0.0 release-please would compute
  from the `!` commits of #1148 and #1150. Overturned if release-please still proposes 5.0.0; then
  a follow-up commit carries the footer.
- The arch seat names the bump in the `Breaking: no` field's free text; no verdict format change.
  Overturned if the owner wants a separate `Bump:` field, which would be a runtime item.
- The history sentence names v2.0.0 to v4.0.0, per the coordinator. v1.0.0 is left out of it.

## Rollback

Rollback: revert the squash commit, then run `bin/wuwei agents build` and `setup.vendor('.')`. If
release-please already cut 4.1.0, the tag stays; the next release follows whichever rule is then
in force.
