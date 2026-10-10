# Feature Specification: generated and data lines never count, and an analysis-only change gets one reviewer

**Feature Branch**: `657-generated-lines`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #657 (owner, 2026-10-10, items 13 and 35; the #631 point from the day
before, still open in 0.24.1): a 789-line analysis item with no trust boundary got a full
security reviewer; another item counted as 5000 changed lines, almost all a generated
manifest; a PR went over `max_changed_lines` only because of a pilot manifest, which forced a
decision. Deliver: `dispatch.tier` and the merge size cap count the same lines, with
generated and data paths excluded and the excluded total named in the reason; an item whose
diff touches only analysis, documents or data, with no trust surface, gets the docs gate
(#631), never security; the planner sees the counted lines per item.

## Root cause

Reproduced in-process on `main` (66b3720) with `dispatch.tier` and a stubbed
`dispatch._changes`, repository floor `standard`, no lead flags, track SLICE:

| Diff | Today | Wanted |
|---|---|---|
| `src/app.py` 200 lines, `pilot/manifest.json` 4800 lines | standard, reason `5000 changed lines over light_max_lines 100` | standard by the 200, reason `5000 changed lines, 4800 generated or data excluded, 200 count, over light_max_lines 100` |
| `docs/analysis.md` 120, `study/results/scores.csv` 600, `study/results/summary.json` 69 | standard, arch + quality + security, `789 changed lines over light_max_lines 100` | light, one reviewer (goal) |
| `analysis/eval.ipynb` 789 | standard, three gates | light, one reviewer (goal) |
| `corpus/runs/r1.jsonl` 3000 with `data_paths = ["corpus/runs/"]` | standard, three gates | light, one reviewer (goal) |
| `docs/analysis.md` 10, `study/results/x.parquet` binary | standard, `study/results/x.parquet binary change` | light, one reviewer (goal) |

In `cli/wuwei/dispatch.py`:

- `tier()` lines 78-79: `total` sums the additions and deletions of every changed path; no
  path is ever excluded, so a generated manifest or a data file counts like source.
- `tier()` lines 95-96: a binary change raises to standard even when the file is data
  (`.parquet`).
- `tier()` line 97 with `_docs_role()` lines 52-59: a diff is docs-only only when every path
  is `.md`, `.rst` or a `.txt` under `docs/` or `specs/`; one CSV, JSON or notebook in an
  analysis diff makes it code, so it gets arch, quality and security.
- `tier()` lines 98-101: the line-count reason is recorded only when the size rule fires or
  the computed tier is light, so a standard item raised by its floor or a path shows no line
  count.

In `cli/wuwei/merge.py` lines 269-273: the size cap excludes only the owner's
`repos.merge.size_exclude` globs (#615). It knows no lockfile, data file, `.gitattributes`
`linguist-generated` path or data directory, and `dispatch.tier` does not read
`size_exclude` at all, so the tier and the cap count different lines.

`cli/wuwei/workspace.py` lines 72-77 (`repos.gates`): no key names data directories.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Which changed files never count? A: A changed file is uncounted when every path it names
  (its path, and its previous path on a rename) is generated or data:
  - generated: a lockfile (`*.lock`, `bun.lock*`, `package-lock.json`,
    `npm-shrinkwrap.json`, `pnpm-lock.yaml`, `go.sum`), a `repos.merge.size_exclude` glob
    (#615), or a glob the repository's root `.gitattributes` marks `linguist-generated`
    (or `linguist-generated=true`);
  - data: a `repos.gates.data_paths` entry, or a `.json`, `.jsonl`, `.csv` or `.parquet`
    file whose change is binary or over 200 changed lines.
- Q: How are `data_paths` entries matched? A: Like every other path glob in WUWEI
  (`merge.matched`, on any path suffix). An entry ending in `/` is a directory: `corpus/runs/`
  matches every file under it.
- Q: Which `.gitattributes`? A: The root `.gitattributes` of the configured repository
  checkout (`repos.path`), the same file for the tier and the merge cap. A diff that changes
  `.gitattributes` itself gets no `linguist-generated` exclusion, so a change cannot declare
  its own lines generated. A missing file excludes nothing; an unreadable one fails closed
  (the tier records `diff unmeasured`, the merge check exits 2).
- Q: Do uncounted files skip the other tier rules? A: Only the line count and the binary
  rule. A trust path, a never-auto path (lockfiles are never-auto by default) and a FULL-track
  pattern still raise the tier for them, and never-auto paths still refuse an automatic merge.
- Q: What does the reason say? A: When some lines are excluded:
  `5000 changed lines, 4800 generated or data excluded, 200 count, over light_max_lines 100`
  (or `within`). With nothing excluded the text is today's (`101 changed lines over
  light_max_lines 100`). The size rule compares the counted lines.
- Q: What is an analysis-only diff? A: The #622 docs-only rule widened: every path is a
  document (today's rule), a notebook (`.ipynb`), or data (above). No agent instruction file,
  and nothing else raised the tier (a lead flag including `trust_surface`, track FULL, a
  trust, never-auto or FULL-pattern path, a counted binary change, a `full` floor). It gets
  the existing docs gate: one reviewer, `quality` when a path is a spec or
  pre-registration, else `goal`; never security. The reason text stays
  `docs-only: 1 reviewer (<role>)`.
- Q: Does a generated file make a diff analysis-only? A: No. Generated files are often code;
  they only stop counting. A diff with a lockfile is raised by its never-auto path anyway.
- Q: What about analysis scripts in `.py`? A: They are source. A repository that keeps
  analysis scripts in a directory with no trust boundary lists it in
  `repos.gates.data_paths`; there is no separate code-paths setting.
- Q: Where does the planner see the counted lines? A: The line-count reason is recorded for
  every measured diff that is not docs-only, whatever raised it, so it is in the tier record
  `dispatch next` returns with its gates action, in `bin/wuwei why <item>` (from
  `gate.tiered`) and in the report's `## Review seats`.
- Q: What does the merge cap say? A: `diff exceeds max changed lines: 600 count over 400
  (4800 generated or data excluded)`; the parenthesis only when something was excluded.

## User Scenarios and Testing

### User Story 1 - The tier and the cap count only source lines (Priority: P1)

The planner and the owner see a tier and a size decision driven by the lines a reviewer reads,
not by a generated manifest or a results file.

**Independent Test**: `dispatch.tier` and `merge.check` on a diff with a large generated file.

**Acceptance Scenarios**:

1. **Given** a diff of 200 source lines and a 4800-line generated manifest
   (`pilot/manifest.json`), **When** `dispatch next` tiers it, **Then** the tier is standard
   by the 200 (over `light_max_lines` 100) and the reason reads
   `5000 changed lines, 4800 generated or data excluded, 200 count, over light_max_lines 100`.
2. **Given** 80 source lines and the same manifest at floor light, **Then** the tier is light
   and the reason ends `80 count, within light_max_lines 100`.
3. **Given** a PR of 200 source lines and the 4800-line manifest with `max_changed_lines`
   400, **When** `merge check` runs, **Then** the size cap is not exceeded.
4. **Given** a PR of 600 source lines and the manifest, **Then** the check refuses with
   `diff exceeds max changed lines: 600 count over 400 (4800 generated or data excluded)`.
5. **Given** `repos.gates.data_paths = ["corpus/runs/"]`, **Then** files under `corpus/runs/`
   are excluded from both counts; without the setting they count.
6. **Given** a root `.gitattributes` with `dist/* linguist-generated`, **Then** `dist/app.js`
   is excluded; **Given** the same diff also changes `.gitattributes`, **Then** it counts.
7. **Given** a lockfile change, **Then** its lines are excluded and its never-auto path still
   raises the tier and still refuses an automatic merge.
8. **Given** a small `config.json` (10 lines), **Then** it counts.

### User Story 2 - An analysis-only item gets one reviewer, never security (Priority: P1)

**Acceptance Scenarios**:

1. **Given** an analysis-only item with `trust_surface: false` (`docs/analysis.md`,
   `study/results/scores.csv` 600 lines, `analysis/eval.ipynb`) at the default floor,
   **When** `dispatch next` tiers it, **Then** the record is tier light, roles `['goal']`,
   reason `docs-only: 1 reviewer (goal)`, and no security reviewer is launched.
2. **Given** the same diff with `trust_surface: true`, or a trust path, or track FULL, or
   floor `full`, **Then** arch, quality and security, as today.
3. **Given** a document and a binary `study/results/x.parquet`, **Then** one reviewer; a
   binary `logo.png` still raises to standard.
4. **Given** a data-only diff under `corpus/runs/` with that `data_paths` entry, **Then** one
   reviewer (goal).

### User Story 3 - The planner sees the counted lines (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a code diff raised to standard by a trust path or the floor, **Then** its tier
   record still carries the line-count reason (`... within light_max_lines 100` or `over`).
2. **Given** an unreadable `.gitattributes`, **Then** the tier is standard with a
   `diff unmeasured: ...` reason, and `merge check` exits 2.

### Edge Cases

- Rename from a data path to a source path: counts (not every path is uncounted), as #615.
- A data-suffix file at exactly 200 changed lines counts; at 201 it does not.
- An empty diff: light with `quality`, as today.
- Agent instruction files (`AGENTS.md`, `.claude/*`, `charters/*`) never make a diff
  analysis-only, even when they are JSON over 200 lines; their lines may still be excluded
  from the count.

## Requirements

### Functional Requirements

- **FR-001**: One function, `merge.uncounted`, decides which changed files do not count
  (Clarifications) and whether each is generated or data; `dispatch.tier` and `merge.check`
  both call it.
- **FR-002**: `dispatch.tier` compares the counted lines with `light_max_lines` and names
  the changed, excluded and counted totals in its reason when something was excluded.
- **FR-003**: `dispatch.tier` skips the binary-change rule for an uncounted file; every other
  path rule still applies to it.
- **FR-004**: `merge.check` compares the counted lines with `max_changed_lines` and names the
  counted and excluded totals in its refusal.
- **FR-005**: `repos.gates.data_paths` is a list of path globs, default empty; an entry ending
  in `/` matches everything under that directory.
- **FR-006**: The docs-only rule (#622) accepts notebooks (`.ipynb`) and data files as well as
  documents; everything that raises the tier today still raises it.
- **FR-007**: Every measured diff that is not docs-only records the line-count reason.
- **FR-008**: A diff that changes the root `.gitattributes` gets no `linguist-generated`
  exclusion; an unreadable `.gitattributes` fails closed.
- **FR-009**: Invariants: the I34 row covers the widened docs-only rule; a new I42 row and
  check hold the shared count (design spec 9.2, `tests/test_invariants.py`).

### Key Entities

- `repos.gates.data_paths` (config, per repository): list of path globs, default `[]`.
- Tier record (`gate.tiered` payload): unchanged shape; only its reason strings change.

## Success Criteria

- **SC-001**: The five root-cause diffs above record the wanted tier and roles.
- **SC-002**: For any diff, the lines the tier compares and the lines the merge cap compares
  are the same number.
- **SC-003**: The full suite passes, including I34 and the new I42.

## Assumptions

- No orchestrator notes exist for this issue and no dry-run workspace was named; the failure
  was reproduced in-process on `main` with a stubbed `dispatch._changes`, as #622 did.
- "Over a size" for data files is a fixed 200 changed lines (`DATA_LINES`), not a setting; a
  binary change of a data file is always data. The owner's case (a 4800-line manifest) is far
  above it.
- `gates.data_paths` lives per repository, beside `trust_paths` and `light_max_lines`
  (`repos.gates.data_paths`), because the paths are repository-relative.
- `repos.merge.size_exclude` (#615) stays as it is and now also stops counting toward the
  tier, so the tier and the cap read the same lines.
- `.gitattributes` patterns are matched with `merge.matched` after stripping a leading `/` or
  `**/`, not with full gitattributes semantics; only `linguist-generated` and
  `linguist-generated=true` exclude, every other attribute and macro is ignored.
- `.gitattributes` is read from the repository checkout, which a seat running as the owner
  could edit outside the diff (design 9.1); a generated file only lowers the line count, it
  never makes a diff docs-only, and never-auto and trust paths still apply to it.
- "plan shows the counted lines" is read as the tier record the planner receives from
  `dispatch next` and `bin/wuwei why`; the morning plan has no diff to count.
- The docs-only reason text is kept (`docs-only: 1 reviewer (goal)`) for analysis and data
  diffs, so the report, why and the invariants keep reading it.
- The relayed owner request for this run also lists items 29 to 31 (merge soak, the merge
  check message, launch prompt matching); they are not this issue and are not covered here.

## Deferred

- A profile can carry `repos.gates.data_paths` without a refusal, as it can carry
  `trust_paths`, `light_max_lines` and `size_exclude` today; refusing review-lowering list
  keys in `profiles.DENIED` is a separate issue.
