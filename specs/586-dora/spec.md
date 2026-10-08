# Feature Specification: The DORA four keys read from what WUWEI already records

**Feature Branch**: `586-dora`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #586: the DORA four keys read from what WUWEI already records.

The owner asked whether DORA metrics belong in the plugin. The issue's answer: two keys
come from records WUWEI already writes, one comes from the code host where it reports
deployments or releases, and one needs a signal WUWEI does not have yet. Each key is a
reading of existing evidence with its source named, and a key without evidence is marked
unmeasured with the reason. No new config key, no new event kind.

Builds on #567 (`metrics.cycles`, `cycle_minutes`, `metrics.cycle_by_tier`, the report's
`## Cycle time`), #579 (`metrics.by_pace`, `report.pace_lines`, the retro's `## Pace`),
design 5.6 (`metrics._escaped`, escaped defects per merged item), 5.13 (the weekly
telemetry aggregate and its share setting), 6.6 (the weekly digest written at close and by
consolidation) and #415 (the on-call seat, not on main: time to restore waits for it).
Design references: 5.6, 5.13, 6.6.

## Root cause

Line numbers are on the worktree base, `main` at 7370a2f.

WUWEI records every input of two DORA keys and can read a third from the code host, but no
function combines them and no output shows them:

- `cli/wuwei/metrics.py:406-438` (`cycles`) already yields, per merged item, `merged_at` and
  `cycle_minutes` (plan approval or add to merge). Nothing reads it as lead time for
  changes over a window.
- `cli/wuwei/metrics.py:381-400` (`_escaped`) already yields the merged items and those a
  later builder brief names (5.6). `by_pace` (`metrics.py:451-467`) counts them per pace,
  but nothing reads them as a change failure rate over a window.
- `cli/wuwei/registry.py:34-40` (`PARAMETERS['code_host']`) has no operation that reads
  deployments or releases, so `adapters/code_host/github.py` cannot report a deploy, and
  deployment frequency and lead time to deploy have no source.
- `cli/wuwei/report.py:150-151` (`build`: `## Cycle time`, `## Pace`),
  `cli/wuwei/retro.py:100-104` (`compile`: the cycle line and `## Pace`),
  `cli/wuwei/digest.py:100-110` (`write` and `build`), `cli/wuwei/telemetry.py:22-27`
  (`METRICS`) and `telemetry.py:99-213` (`aggregate`) show cycle time and pace but no DORA
  table and no DORA keys.
- There is no `wuwei dora` command in `cli/wuwei/commands/` or the help groups of
  `cli/wuwei/__main__.py:28-36`.

## User Scenarios and Testing

### User Story 1: The owner reads the four keys from local records (Priority: P1)

The owner runs `wuwei dora` in a workspace whose code host is `none`. It prints one table:
lead time to merge and change failure rate measured from the day records, with each source
named; deployment frequency, lead time to deploy and time to restore marked unmeasured with
the reason.

**Why this priority**: it is the issue's first acceptance line and needs no network.

**Independent Test**: a fixture workspace with day records (plan approvals, merged phase
changes, a later builder brief naming one merged item), `code_host = "none"`, `WUWEI_NOW`
set; run the `dora` command function in-process and assert on stdout and the exit code.

**Acceptance Scenarios**:

1. **Given** a workspace with merged items and escaped-defect records and `code_host =
   "none"`, **When** the owner runs `wuwei dora`, **Then** it prints a heading naming the
   28-day window and a table with rows `Lead time to merge` (the median `cycle_minutes` in
   hours, source `cycle_minutes of <n> merged items (#567)`), `Change failure rate` (escaped
   over merged, source `<k> of <n> merged items named by a later fix brief (5.6)`),
   `Deployment frequency` and `Lead time to deploy` (`unmeasured`, reason `code host
   adapter is none`) and `Time to restore` (`unmeasured`, reason `no on-call incident
   signal yet (#415)`), and exits 0.
2. **Given** no item merged in the window, **When** `wuwei dora` runs, **Then** lead time to
   merge and change failure rate are `unmeasured` with the reason `no item merged in the
   window`, never zero, and it exits 0.
3. **Given** `wuwei dora --window 7`, **Then** only items merged in the last 7 days count
   and the heading names 7 days. **Given** `--window 0`, **Then** it exits 2 with the reason
   `--window must be a positive number of days`.
4. **Given** no workspace or a damaged day record, **When** `wuwei dora` runs, **Then** it
   exits 2 with the reason on stderr and prints no table.

### User Story 2: Deployments measured from the code host (Priority: P1)

**Independent Test**: the GitHub adapter's `deployments` against replayed `gh api` output
(`fakes.replay.install_replay`), and `metrics.dora` with a fake code host module.

**Acceptance Scenarios**:

1. **Given** a GitHub repository with deployments in the window, **When** `wuwei dora`
   runs, **Then** `Deployment frequency` is measured (deploys in the window per week,
   source `<n> deployments in <d> days`) and `Lead time to deploy` is measured (median
   hours from each merged item's cycle start to the first deploy of its repository at or
   after its merge, source `<n> merged items reached a deploy`).
2. **Given** a repository with no deployments ever but published releases, **Then** the
   adapter reports releases (drafts and unpublished releases skipped) and the sources say
   `releases`.
3. **Given** a repository with neither, **Then** both deploy keys are `unmeasured` with the
   reason `the code host reports no deployments or releases`.
4. **Given** the adapter cannot run (`gh` exit, error body, timeout), **Then** the deploy
   keys are `unmeasured` with the reason `code host could not run: <reason>`, and `wuwei
   dora` still prints the table and exits 2 (fail closed: never clean when unmeasured by
   error).
5. **Given** `code_host = "none"`, **Then** `adapters/code_host/none.py` has `deployments`
   returning the shared unmeasured result, and `metrics.dora` never calls it (no `adapter:
   none` event for a read the config already rules out).

### User Story 3: The retro, the report and the weekly digest carry the same table (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the retro, **When** the steward compiles it, **Then** a `## DORA (last 28
   days)` section with the same table as `wuwei dora` follows `## Pace`, beside cycle time
   per tier (the cycle line) and per pace.
2. **Given** the day report, **When** it is built, **Then** a `## DORA (last 28 days)`
   section follows `## Pace`, at every verbosity.
3. **Given** a week digest (close or `wuwei consolidate`), **When** it is written, **Then**
   its `## Metrics` section ends with the same table computed over the digest's ISO week.
   A month digest is unchanged.

### User Story 4: The keys join the weekly telemetry signals (Priority: P2)

**Acceptance Scenarios**:

1. **Given** the weekly aggregate (5.13), **When** a week is computed, **Then** its
   `metrics` carry `lead_time_merge_hours`, `lead_time_deploy_hours`, `deploys_per_week`,
   `change_failure_rate` and `time_to_restore_hours`, each a non-negative number rounded to
   two decimals or `"unmeasured"`, over that ISO week, and `telemetry.validate` accepts the
   payload. The code host is read only when the week is final; the current week's deploy
   keys are `"unmeasured"`.
2. **Given** any `share` value, **Then** no new setting, prompt or interview question
   exists; what leaves the machine is still decided by `share` alone.
3. **Given** the code host fails during aggregation, **Then** the deploy keys are
   `"unmeasured"` and the aggregation and the sweep exit are unchanged.

### Edge Cases

- An item with no recorded pull request, or a pull request in a repository the config does
  not list, counts for lead time to merge and change failure rate but not for lead time to
  deploy.
- A merged item whose repository has no deploy after its merge yet is left out of lead time
  to deploy; if none reached one, the reason is `no merged item reached a deploy yet`.
- A code host timestamp without a timezone fails closed in the adapter (exit 2).
- Deployments count in every environment (see Assumptions).

## Requirements

### Functional Requirements

- **FR-001**: `metrics.dora(root, config, since, until, host=True)` returns the five rows in a fixed
  order (lead time to merge, lead time to deploy, deployment frequency, change failure
  rate, time to restore), each `{'value': number or 'unmeasured', 'source' or 'reason':
  text}`, plus `failed: True` on a row the code host could not measure. It reuses `cycles`
  and `_escaped`; it computes no second cycle time and no second escaped-defect measure.
- **FR-002**: Lead time to merge is the median `cycle_minutes / 60` of items whose
  `merged_at` falls in `[since, until)`. Change failure rate is escaped over merged for the
  same items, escaped meaning named by a later builder brief (`_escaped`).
- **FR-003**: The code host port gains `deployments(repo, since)` in
  `registry.PARAMETERS`, `adapters/code_host/github.py`, `adapters/code_host/none.py` and
  `tests/fakes/code_host.py`. GitHub returns `{'source': 'deployments', 'at': [...]}` from
  the deployments API when the repository has any deployment, else `{'source': 'releases',
  'at': [...]}` from published, non-draft releases, else `{'source': None, 'at': []}`;
  `at` holds the ISO timestamps at or after `since`. It uses only reads the adapter's
  `_run` allowlist already permits.
- **FR-004**: Deployment frequency is the deploys in `[since, until)` times 7 over the
  window's days. Lead time to deploy is, per merged item in the window with a recorded pull
  request in a configured repository, `cycle_minutes / 60` plus the hours from `merged_at`
  to that repository's first deploy at or after it; the median.
- **FR-005**: Time to restore is always `unmeasured`, reason `no on-call incident signal yet
  (#415)`.
- **FR-006**: `wuwei dora [--window DAYS]` (default 28) prints the heading and the table;
  read-only; exit 0, or 2 when a row failed or nothing could be read, with the reason.
- **FR-007**: `report.dora_lines(rows)` renders the table once; the command, the report,
  the retro and the week digest all call it.
- **FR-008**: Telemetry `METRICS` gains the five keys; `aggregate` fills them from
  `metrics.dora` over the ISO week, reading the code host only for a final week.
  `SCHEMA` and `INNER` are unchanged.
- **FR-009**: Docs: design 5.6 gains the DORA bullet, 5.13's table the five rows,
  `docs/site/concepts.md` a short `### DORA keys` entry, `docs/site/reference.md` the
  `bin/wuwei dora` row.
- **FR-010**: No new config key, no new event kind, no new refusal, no new hook step.

### Key Entities

- **DORA row**: name, value (number or `unmeasured`), source or reason, optional `failed`.
- **Deploy list**: per repository, the source (`deployments`, `releases` or none) and the
  ISO timestamps since the window start.

## Success Criteria

- **SC-001**: The issue's three acceptance lines pass as tests: local keys with unmeasured
  reasons; measured deploy keys from replayed GitHub deployments; the retro's DORA table
  beside cycle time and pace.
- **SC-002**: No key shows zero where it has no evidence: every unmeasured row carries a
  reason.
- **SC-003**: The touched test files pass; no existing report, retro, digest or telemetry
  test changes its expectation except to admit the new section or keys.

## Assumptions

- The issue file was not in the pipeline directory; the issue text was read from the
  public issue page. Its synopsis is `wuwei dora [--window 28]`; the default is 28 days.
- Lead time for changes runs from the item's cycle start (`plan.approved` or `plan.added`,
  as `cycle_minutes` does), not from the first commit: WUWEI's records start there and the
  issue names `cycle_minutes` as the source.
- Change failure rate is item-level only (5.6 escaped defects per merged item, by brief
  naming). The deployment-level view needs incident data that does not exist yet.
- Per-pace and per-tier lead time and change failure rate already exist as `by_pace` and
  `cycle_by_tier`; the issue asks for the DORA table beside them, not a new split.
- Deployments count in every environment and at creation, without reading deployment
  statuses (one call per deployment). Marked `ponytail:` with the upgrade path (filter on
  `production_environment` or read statuses) for when previews inflate the count.
- A repository that has ever had a deployment uses deployments, otherwise releases; sources
  are not mixed within one repository.
- The weekly telemetry aggregate reads deployments through the code host only when it
  finalises a week (once per week), never on the daily refresh of the current week, whose
  deploy keys stay `unmeasured` until final. It is the one 5.13 metric not read from day
  directories, and it runs in the watch sweep, never in a hook. An adapter failure there is
  `unmeasured`, never a skipped run.
- Adding five keys to the telemetry table changes no existing key or definition, so
  `SCHEMA` stays 1. A collector still on the old `telemetry.py` rejects the new keys as
  unknown until it is redeployed with this module (the week stays unsent and retries).
- The report and retro use the command's 28-day window; the digest and telemetry use the
  ISO week in `owner.timezone`.
- No guard or decision rule is added or changed, so no 9.2 invariant is added.
- `wuwei dora` belongs in `READ_ONLY` and in the Owner help group after `telemetry`; the Daily group feeds the agent guide, whose 100-line cap it would pass, and the guide still lists it as read-only.

## Deferred

- Time to restore once #415 lands an on-call incident signal.
- Deployment-level change failure rate once incident data exists.
