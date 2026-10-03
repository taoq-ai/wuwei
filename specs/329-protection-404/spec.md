# Feature Specification: branch protection read falls back to rulesets on a classic 404 and reports each source

**Feature Branch**: `329-protection-404`
**Created**: 2026-10-03
**Status**: Ready for implementation
**Input**: Issue #329, fix(code_host). Owner trial of v0.11.0 (item B8, minor). Builds on
#243 (host protections in `config check`). Design 4.5, 4.6 and 9.1: the code host's
server-side rules are the publishing guarantee, so `config check` must measure them.

## Root cause (read on main, 69453ed)

`adapters/code_host/github.py` `protection()` reads the classic branch-protection endpoint
first (line 311) and only then the rulesets endpoint (line 339). A failed classic read
raises before the rulesets loop runs:

- `_run()` (lines 99-104) turns any nonzero `gh` exit into `ValueError('gh exited 1')`,
  except a 404 whose stderr says `Branch not protected (HTTP 404)`, which becomes
  `ValueError('branch protection absent')` (lines 100-103).
- GitHub answers the classic endpoint with a 404 both when the branch is unprotected and
  when the caller has no admin rights on the repository. The no-admin answer is a plain
  `Not Found (HTTP 404)`, so it becomes `gh exited 1`, `protection()` returns exit 2, and
  `wuwei config check` prints `protection: unmeasured` and exits 2
  (`cli/wuwei/commands/config.py:176-198`), although `rules/branches/<branch>` is readable.
- The `Branch not protected` form fares no better: `config check` prints
  `protected ref: missing` (`config.py:172-175`) and never looks at rulesets, which is
  why `docs/site/configuration.md` says "A branch protected only by rulesets currently
  reads as missing."

Reproduced read-only and offline: replaying `gh` with a classic 404 (either stderr form)
followed by a rulesets `[[]]` page through `fakes.replay`, `protection('acme/widget',
'main')` returns exit 2 after one `gh` call; the rulesets step is never consumed.

The trial also showed a second gap: on a repository whose reviews are enforced by a
required "Review Gate" check rather than by GitHub review rules, `required reviews: missing`
is accurate but gives no hint that the configured `shepherd.review_gate_check` may be
covering it, and `required checks` never lists which checks the host requires.

## User Scenarios & Testing

### User Story 1 - A classic 404 still measures the rulesets (Priority: P1)

The owner runs `bin/wuwei config check` on a repository whose classic branch-protection
endpoint answers 404 (unprotected, or the owner's login is not an admin). The check reads
the rulesets for the branch anyway, prints one line saying classic protection is not
visible and why that can happen, and prints the required checks, required reviews, force
pushes and deletions lines measured from the rulesets.

**Why this priority**: today the check exits 2 on such repositories, so the owner cannot
tell whether the publishing guarantee holds, and a ruleset-only branch can never read as
protected.

**Independent Test**: `python -m pytest -q tests/test_code_host.py tests/test_env_credentials.py -k "protection or classic"`.

**Acceptance Scenarios**:

1. Given a fake host that answers 404 on the classic endpoint and `[]` on the rulesets
   endpoint, when the owner runs `config check`, then the output has
   `acme/widget main: classic protection: none visible (404: unprotected or no admin)`,
   then `required checks`, `required reviews`, `force pushes` and `deletions` each as
   `missing` with the setting to change, no `unmeasured` line, and the command exits 1.
2. Given the same 404 with either stderr form (`Not Found (HTTP 404)` or
   `Branch not protected (HTTP 404)`), then the result is the same.
3. Given a classic 404 and rulesets that block force pushes and deletions, require a
   pull request with 1 approval and require the CI checks, then every line is `ok` and
   the command exits 0: a ruleset-only branch reads as protected.
4. Given a classic 404 and a rulesets endpoint that also fails (the repository is not
   visible to the caller, or the host is unreachable), then the check prints
   `protection: unmeasured` and exits 2, as before.
5. Given a readable classic protection, then the output keeps `protected ref: ok` and is
   unchanged except for the check names listed on the `required checks` line.

### User Story 2 - Required checks are listed and compared with the CI checks (Priority: P2)

The owner sees which checks the host requires and which of the repository's CI checks
(`repos.review_required_checks`) are not among them.

**Why this priority**: the owner cannot fix a required-checks gap without knowing what is
required now.

**Acceptance Scenarios**:

1. Given a rules response requiring `Security` and `unit` and
   `review_required_checks = ["unit"]`, then the line is
   `required checks: ok (Security, unit)`.
2. Given a rules response requiring `Security` and `review_required_checks = ["unit"]`,
   then the line is
   `required checks: missing (require status checks on main: unit; required now: Security)`
   and the command exits 1.
3. Given no required checks at all, then the line stays
   `required checks: missing (require status checks on main)`.

### User Story 3 - The review gate check is named when reviews are missing (Priority: P3)

When GitHub requires no approving review but a required check carries the name configured
in `shepherd.review_gate_check`, the `required reviews: missing` line says that check may be
satisfying the review requirement. The line stays a finding: WUWEI cannot see what the check
enforces.

**Acceptance Scenarios**:

1. Given 0 required approvals, `shepherd.min_reviewers` not 0, and a required check named
   `Review Gate` (the default `shepherd.review_gate_check`), then the line is
   `required reviews: missing (require at least 1 approving review on main, or set
   shepherd.min_reviewers = 0 for a solo owner; the required check Review Gate
   (shepherd.review_gate_check) may be satisfying it)` and the command exits 1.
2. Given the same without a `Review Gate` required check, then the line is unchanged
   from today.

### Edge Cases

- A typo in `default_branch`: the classic endpoint answers 404 and the rulesets endpoint
  answers `[]` for a branch name that does not exist, so the check reports the classic
  line and `missing` findings (exit 1), never clean.
- A 404 on the rulesets endpoint is never treated as "no rules": it stays exit 2.
- Any other classic failure (403, 5xx, timeout, error body, malformed body) stays exit 2
  without reading rulesets.
- A rulesets page with an error body or a malformed rule stays exit 2 (unchanged).
- A protection result without the new source flag (a malformed adapter result) is
  `unmeasured`, never clean.

## Requirements

### Functional Requirements

- **FR-001**: The GitHub protection read MUST treat any 404 from the classic
  branch-protection endpoint as "classic protection not visible" and continue to the
  rulesets endpoint.
- **FR-002**: With classic protection not visible, the classic-derived settings MUST take
  the values of an unprotected branch (no required checks, 0 approvals, force pushes and
  deletions allowed, no review options, admins not enforced, conversation resolution off),
  and the rulesets MUST then tighten them exactly as they do today.
- **FR-003**: The protection result MUST say which source was read: classic protection
  visible or not.
- **FR-004**: A failure of the rulesets read MUST still be exit 2 with its reason, so a
  repository the caller cannot see is unmeasured, never clean or merely missing.
- **FR-005**: `config check` MUST print `classic protection: none visible (404:
  unprotected or no admin)` in place of `protected ref: ok` when classic protection was
  not visible. That line is information, not a finding; findings come only from the
  measured lines.
- **FR-006**: `config check` MUST list the host's required check names on the
  `required checks` line (`ok (<names>)`, or `; required now: <names>` after the absent CI
  checks when it is missing), sorted by name.
- **FR-007**: When `required reviews` is missing and a required check is named exactly as
  `shepherd.review_gate_check`, the line MUST add that this check may be satisfying it.
- **FR-008**: Exit codes stay 0 when every line is ok, 1 on any missing line, 2 on any
  unmeasured repository; a classic 404 alone never causes exit 2.
- **FR-009**: The configuration page MUST document the classic line, the listed check
  names and the review gate note, and drop the sentence saying ruleset-only branches read
  as missing.

### Key Entities

- **Protection result**: the dict `protection()` returns today plus one boolean, `classic`:
  true when the classic endpoint answered 200, false when it answered 404.

## Success Criteria

- **SC-001**: On a repository whose classic endpoint answers 404 and whose rulesets are
  readable, `config check` reports every host-protection line as measured (ok or missing)
  in one run, with no `unmeasured` line for that repository.
- **SC-002**: A branch protected only by rulesets reads as fully `ok` when the rulesets
  cover checks, reviews, force pushes and deletions.
- **SC-003**: The full test suite passes; no test or fixture needs network or the real
  `gh`.

## Assumptions

- Both 404 forms are treated the same. GitHub gives no reliable way to tell "unprotected"
  from "no admin" on this endpoint, and the issue asks for one line that names both causes.
  The old split (only `Branch not protected` meant absent) existed to keep an invisible
  repository from reading as unprotected; the rulesets read now carries that job, because
  it also 404s for a repository the caller cannot see (FR-004).
- The "CI check names" the issue mentions are `repos.review_required_checks`, which
  calibration fills from the repository's workflows; the comparison is the existing one.
- The `required reviews` line stays `missing` when the review gate check is present. The
  issue says "keep that line"; the added text is a hint, not an exemption.
- Merge and shepherd read the same adapter, so after this change they receive rules-derived
  evidence on a classic 404 instead of exit 2. This is accepted: a caller without admin
  cannot bypass classic protection, and the merge policy still requires GitHub's own
  `mergeable_state` to be `clean`, which GitHub computes with the classic rules the caller
  cannot read. Shepherd's existing fallback to `review_required_checks` already triggers on
  an empty required-checks list.
- No new config key, event kind, state key, port operation or allowlisted `gh` command.
- No dry-run workspace was named for this issue; the failure was reproduced offline with
  the replay fake, which is the same boundary the tests use.
