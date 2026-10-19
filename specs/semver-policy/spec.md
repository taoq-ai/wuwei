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
   shapes that seats and owners write; the hook input and output contract; the skill names
   (with a renamed skill's alias while it ships), the plugin and marketplace names; the agent role
   names the config's `models` rows use; the owner-written files (`.wuwei/goals.md`,
   `.wuwei/standards.md`, the plan file format). The gate reads the list at the base commit.
2. The same section classifies a change by SemVer 2.0.0, strictly (fix round 1, the lead's
   decision, replacing the ESLint reading). Major: a documented element removed, renamed or given
   a different meaning or shape; an input every client must now give; a documented exit code's
   meaning changed (its meaning, not which inputs reach it). Minor: a new capability existing
   clients need not use; a new check that is off by default or only adds information. Patch: a
   fix of behaviour that contradicted the documented public API at the base, including a closed
   guard bypass and a gap the docs already promised; docs; internals. Refusing or reporting more
   is a patch only under that condition. When unsure, the gate ESCALATEs with `Breaking: yes`. One sentence says v2.0.0 to v4.0.0 were bumped under the earlier
   rule and the SemVer policy applies from 4.1.0; no tag moves.
3. `charters/sentinel-arch.md` rule 7 says the same (79 words; the arch agent stays at 2,248 by
   trimming its preamble and last paragraph), replaces "When unsure, say yes" with "When unsure,
   ESCALATE with Breaking: yes", reads the API at the base, and `Breaking: yes` means a major.
4. `charters/builder.md` rule 6: `!` and `BREAKING CHANGE:` mark a major only; a stricter check
   of a rule the docs already state is a `fix:` (a patch), a new capability a `feat:` (a minor),
   so release-please bumps what the policy says.
5. `docs/design.md`, `docs/site/reference.md`, `docs/site/concepts/decisions.md` and
   `charters/_common.md` say a breaking change is a major and point to the section.
6. The `Announcement:` line and the owner's `breaking:` confirmation stay keyed to a breaking
   change, which now means a major only. No change under `cli/wuwei/`.
7. The squash commit carries `Release-As: 4.1.0`, so release-please cuts 4.1.0 for #1148 and
   #1150 instead of 5.0.0.

Outside: the runtime, the verdict parser, any tag or published release.

The acceptance scenarios, restated:

1. A gate brief for a fix that closes a guard bypass or adds a gap: the arch seat reads rule 7 and
   writes `Breaking: no`. Under the lead's round-1 decision the bump is a patch when the docs
   already promised the behaviour, and a minor for a new check that is off by default or only
   adds information (the item's text says minor; see Assumptions).
2. A change that renames a CLI flag or changes an exit code: rule 7 makes it `Breaking: yes`.
3. After the merge, release-please reads `Release-As: 4.1.0` from the squash commit and its
   release PR proposes 4.1.0.
4. After `bin/wuwei agents build`, every `agents/*.md` is at or under AGENT_WORDS (2,250).

## How this fails

1. The arch seat reads "refuses or reports more" as a patch in a downstream repository where the
   old behaviour matched its documented API (stricter validation of a request its API accepted),
   and calls a real break a patch. Held: rule 7 makes refusing more a patch only when the old
   behaviour contradicted the documented API, and an ESCALATE carries `Breaking: yes`, so the
   unsure case still reaches the owner.
2. Release-please ignores `Release-As:` because the lead squashes with a message that drops the
   footer, or puts it in the PR body only. Held: the PR body says the lead carries the line alone
   in the squash commit message; acceptance 3 is read on the release PR after the merge. Rollback:
   a later commit with `Release-As: 4.1.0` before the release PR merges.
3. The rule 7 rewrite or the `_common.md` edit pushes `agents/sentinel-arch.md` over 2,250 words
   and the ceiling test fails. Held: rule 7 is 79 words (65 at the base, both counted with
   `str.split` after the `7.` marker), the preamble and last paragraph lose 15 words, and the
   build is measured with `wc -w agents/*.md`.

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
- Q (fix round 1): Is a stricter check a minor, as ESLint reads it, or a patch? A: The lead
  decided SemVer strictly: a fix of behaviour that contradicted the documented API is a patch,
  so `fix:` matches release-please's patch bump. A new check that is off by default or only adds
  information is a minor. ESLint's reading is dropped.
- Q (fix round 1): `wuwei evidence` exits 1 on one more PR after a stricter check. Is that a
  changed exit code? A: No. An exit code is classified by its meaning, not by which inputs reach
  it; 1 still means gaps.
- Q (fix round 1): What does an unsure arch seat write in `Breaking:`? A: ESCALATE with
  `Breaking: yes`, so the owner's `breaking:` question holds the merge even when arch is not a
  required gate.
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

- FR-001: `evidence.md` Breaking changes declares the public API (read at the base commit), the
  classification, the SemVer 2.0.0 citation and the history sentence.
- FR-002: `sentinel-arch.md` rule 7, at most 79 words, names the public API at the base, a major,
  the documented-API condition for a patch, and ESCALATE with Breaking: yes when unsure.
- FR-003: `builder.md` rule 6: `!` and `BREAKING CHANGE:` for a major only; a stricter check of a
  documented rule is a `fix:` with release notes, a new capability a `feat:`.
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
- Fix round 1 follows the lead's classification, which differs from the item text ("a stricter
  check is a minor"). Overturned if the owner keeps the ESLint reading; then the table rows and
  builder rule 6 move back and `feat:` marks a stricter check.
- This PR is breaking under the rule in force at its head (arch finding 5), so it carries an
  `Announcement:` line and waits for the owner's `breaking:` answer, which also settles 4.1.0
  against 5.0.0.

## Rollback

Rollback: revert the squash commit, then run `bin/wuwei agents build` and `setup.vendor('.')`. If
release-please already cut 4.1.0, the tag stays; the next release follows whichever rule is then
in force.
