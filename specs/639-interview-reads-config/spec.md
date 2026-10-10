# Feature Specification: the interview reads the config before asking

**Feature Branch**: `639-interview-reads-config`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #639 (owner, 2026-10-10): `merge_deploys = false` was already set for
both repositories, and calibration asked the deploys question again on cards; the planner
recorded the existing answers instead of asking the owner. Deliver: `interview.unanswered`
treats a question as answered when every key it would write is set explicitly in the raw
TOML (not a default), for the repository in question when the scope is `repo`.
`calibrate --questions` prints no card for it, and `init --upgrade` and `doctor` do not count
it. The recorded value is the config's own, so no `interview.json` is needed for it;
`calibrate --interview merge` still re-asks on request.

## Root cause

Reproduced in-process on `main` (a temporary workspace whose only config is one `[[repos]]`
table `acme/widget` with `merge_deploys = false`, no `interview.json`):
`interview.unanswered(root, ['acme/widget'])` contains `('deploys', 'acme/widget')`, and
`interview.widgets(root, ['acme/widget'])` lists `autonomy, deploys, merge, ...`.

In the code:

- `cli/wuwei/interview.py:660-665` (`unanswered`) decides "answered" only from
  `_recorded(root)` (`interview.py:628-654`), which is membership in some day's or archived
  day's `interview.json`. It never reads `.wuwei/config.toml`, so a key the owner set by hand
  (or through `config set`, a profile, or an older interview whose day file is gone) does not
  count.
- `unanswered` is the one count (#530): `widgets` (`interview.py:668-677`, used by
  `calibrate --questions` in `cli/wuwei/commands/calibrate.py`), `init --upgrade`
  (`cli/wuwei/commands/init.py:443`) and `doctor` (`cli/wuwei/commands/doctor.py:427`) all
  route through it, so the fix belongs in `unanswered` and nowhere else.
- Presence alone is not enough: the shipped template (`templates/workspace/config.toml`)
  writes ten interview keys explicitly, each at its schema default (`cap = 0`,
  `host.seats = 0`, `control_plane.content`, `deploy.deny`, `owner.verbosity.default`,
  `spec.engine`, `adapters.tracker`, `adapters.chat`, `adapters.review_bot`,
  `shepherd.min_reviewers`). Counting presence would silence ten setup questions on every
  fresh workspace.

## User Scenarios and Testing

### User Story 1 - A question the config already answers is not asked (Priority: P1)

The owner set `merge_deploys = false` for a repository by hand. The morning cards, the
`doctor` row and the `init --upgrade` count no longer ask or count the deploys question for
that repository; other repositories without the key are still asked.

**Why this priority**: it is the reported defect; re-asking a settled question costs the
owner a card and invites the planner to answer for the owner.

**Independent Test**: write the key into a test workspace's config, no `interview.json`,
and read `unanswered` and `widgets`.

**Acceptance Scenarios**:

1. **Given** `repos.0.merge_deploys = false` in the raw config and no `interview.json`,
   **When** `unanswered` and `widgets` run, **Then** `unanswered` omits
   `('deploys', repo 0)` and `widgets` prints no card for it; repo 1 without the key is
   still asked.
2. **Given** `outbound.default_tier` and the other autonomy keys (`security.posture`,
   `merge.default_tier`, `outbound.learn`, `autonomy.mode`) all set explicitly, **When**
   `unanswered` runs, **Then** the autonomy question is not in it.

### User Story 2 - Defaults and template values still ask (Priority: P1)

A fresh workspace, or a key left at its default, gets every question as today.

**Why this priority**: the setup interview must not go silent on a new workspace.

**Independent Test**: the shipped template config plus one repository, no
`interview.json`: `unanswered` returns every (question, repository) pair in table order.

**Acceptance Scenarios**:

1. **Given** the key is absent (the default), **When** `unanswered` runs, **Then** the
   question is asked as today.
2. **Given** the shipped template config, **When** `unanswered` runs, **Then** every
   question is still asked.
3. **Given** only four of the five autonomy keys set, **When** `unanswered` runs, **Then**
   the autonomy question is asked.

### User Story 3 - Asking by name still asks (Priority: P2)

`calibrate --interview merge` and `calibrate --questions deploys` ask the named question
even when the config answers it.

**Independent Test**: with `merge_deploys = false` set, `widgets(root, repos, ['deploys'])`
still returns the card for that repository.

**Acceptance Scenarios**:

1. **Given** `merge_deploys = false` on repo 0, **When** the deploys question is requested
   by id, **Then** its card is printed for repo 0.

### Edge Cases

- A question that writes no config key (charter or voice rows such as `interrupt`,
  `hours`, `avoid`, and `allowlist`) is never answered by the config.
- A question whose choices write several keys (`merge`: `merge.auto` and
  `merge.soak_minutes`; `tickets`: `tracker.required` and `tracker.skip_tiers`) counts only
  when every one of those keys is set.
- A key set to its schema default counts as not answered, so `merge_deploys = true` written
  by hand or by calibration is still asked (the fail-closed default, as today).
- An unreadable or unparsable `config.toml` raises `OSError` or `ValueError`; every caller
  already reports that as unmeasured (`doctor`, `init --upgrade`) or exit 2 (`calibrate`).

## Requirements

### Functional Requirements

- **FR-001**: `interview.unanswered` MUST omit a (question, repository or None) pair when the
  raw `.wuwei/config.toml` sets every config key the question's choices write (in the
  `[[repos]]` table of that repository for a `repo` question) and at least one of those
  values differs from its schema default.
- **FR-002**: A question whose choices write no config key MUST stay governed by
  `interview.json` only.
- **FR-003**: `widgets` without ids, `init --upgrade` and `doctor` MUST reflect FR-001 through
  `unanswered` with no change of their own.
- **FR-004**: Asking by id (`widgets` with ids, `ask`, `calibrate --interview <id>`) MUST be
  unchanged.
- **FR-005**: Nothing is written: no `interview.json`, no config change.
- **FR-006**: An unreadable or unparsable config MUST raise, never count as answered.

### Key Entities

- **Question keys**: the union of the config keys (effects that `_setting` accepts) over a
  question's choices. Free-text answers are not part of it.

## Success Criteria

- **SC-001**: With `merge_deploys = false` set for a repository, `calibrate --questions` prints
  no deploys card for it.
- **SC-002**: On the shipped template plus one repository, the unanswered count is unchanged
  from `main`.
- **SC-003**: The full suite passes with the existing #530 one-count tests unchanged.

## Assumptions

- "Set explicitly (not a default)" means present in the raw TOML with at least one of the
  question's values differing from the schema default (the same default the #604 `kept`
  check reads through `configtext.declared` and `workspace._default`). Presence alone is
  ruled out because the template writes defaults explicitly. An owner who hand-writes only
  default values is asked, as today; answering records `interview.json` as before.
- "Every key it would write" is the union over the question's choices, not one choice's
  keys: for `merge`, `merge.auto = false` alone is still asked. This errs toward asking.
- A seat that can write `config.toml` can already change the behaviour those keys govern
  (spec 9.1); skipping the card grants nothing new, records nothing, and is not a guard or
  decision rule, so no 9.2 invariant row is added.
- `init --upgrade --dry-run` counts against the config on disk, not the migrated text; only
  a `guards.mode = "shadow"` workspace whose other autonomy keys are all defaults could
  differ, and the non-dry run writes the migrated file before it counts.
- The orchestrator notes file named in the task (`notes/639-full.md`) does not exist; the
  issue text is the only input. The failure was reproduced in a temporary workspace instead
  of a named dry-run workspace.
- The setup command (`bin/wuwei setup`) asks every question by id and is out of scope.
