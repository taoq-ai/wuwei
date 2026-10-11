# Implementation Plan: about 20 commands, init --upgrade removes every obsolete file, docs rewritten

**Branch**: `b9-cleanup` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

Built after part 23 on the same branch. Line numbers are at 71d3f06b; locate by name where
part 23 moved code.

## Summary

Cut the listed commands from 36 to 20 by deleting duplicates and folding single jobs into the
command that owns them; make `init --upgrade` remove every obsolete workspace file and key;
land the goals-block, redactor and verbosity follow-ups; name the seven defect classes in the
sentinel charters; rewrite the docs site and README; rebuild the agents.

## Technical Context

Stdlib-only Python 3.11+, pytest dev-only. Net deletion: about 700 lines of command code (the
folded code moves), about 150 collected tests (the tests of deleted duplicates). Three keys
retire. Run only the touched test files; CI runs the suite.

## Constitution Check

- I: nothing added.
- III: each moved job keeps one function (`brief.write`, `specmode` analysis writer,
  `dispatch.classes`, `promotion.land`, `metrics.collect`), now reached from one command.
- IV: red tests first: the help list, each fold's new path, the upgrade fixture, the goals
  replacement, the lead brief's candidates.
- V: deletion and folding; no new module.
- VII: no guard changes; integrity stays a SessionStart warning and a doctor row.

## Command set after this part

| Group | Listed command | Kept or folded jobs |
| --- | --- | --- |
| Setup | `init`, `config` | `init --upgrade` removals |
| Recovery | `doctor`, `why` | `doctor --fix --apply integrity-reconfirm` (from `integrity reconfirm`) |
| Loop | `next`, `plan`, `seat`, `build`, `dispatch`, `worktree`, `pr`, `merge`, `duty`, `tracker`, `close` | `seat brief` (from `brief`), `seat note` (from `note`), `build analysis` (from `spec analysis`), `build classes` (from `sweep classes`) |
| Owner's outcomes | `report`, `retro`, `telemetry`, `dora` | `report --week` (from `metrics --week`), `retro --promote` (from `promote`) |
| Plugin | `agents` | |
| Plumbing (unlisted) | `hook`, `status` | `status --line` only |

## Process control: what each removed unit was

| Unit | Kind | Where its job goes |
| --- | --- | --- |
| `verdict lint` | (b) verdict format | PostToolUse and SubagentStop lint, `dispatch receive`, `seat stop` already run it |
| `integrity check`, `integrity reconfirm` | kept by the lead (SessionStart warning) | SessionStart guard and doctor row; `doctor --fix --apply integrity-reconfirm` on the Owner step card |
| `steward run` | (a) | `close` runs the steward |
| `discover` | (a) a preview the lead ran by hand | the lead brief carries the candidates; `plan propose` records discovery |
| `goals`, `payload`, `memory export`, `index` | (a) duplicates | SessionStart shows goals and memory; promotion exports and writes the index |
| `status` plain and `--json` | (a) a second board | `next` |
| `pr ping-check`, `pr reviewers`, `tracker done` | (a) no caller | `pr ping`, `tracker move <item> done` |
| `adapters.redactor`, `adapters/redactor/` | (a) unread | `cli/wuwei/redact.py` (unchanged) |
| `owner.verbosity.decisions`, `retro.repo` | (a) unread | nowhere |

No (b) check is lost.

## Files to delete (code 16, tests about 6)

- `cli/wuwei/commands/brief.py`, `note.py`, `spec.py`, `sweep.py`, `promote.py`, `metrics.py`,
  `integrity.py`, `verdict.py`, `steward.py`, `discover.py`, `goals.py`, `index.py`,
  `memory.py`, `payload.py` (14 command modules; their library modules stay)
- `adapters/redactor/builtin.py` and the `adapters/redactor/` directory
- Tests wholly about a deleted command: `tests/test_runtime_cli.py` is already gone; delete the
  command-only cases in `tests/test_verdict.py` (`verdict lint` CLI), `tests/test_steward.py`
  (`steward run` CLI), `tests/test_linear_loop.py` (`discover` CLI cases move to the lead brief
  test), `tests/test_memory.py` (`memory export`, `index` CLI), `tests/test_goals_rank.py`
  (`goals` CLI), `tests/test_integrity.py` (`integrity` CLI; keep the library and doctor cases).

## Files to edit, code (about 30)

### Folds

- `cli/wuwei/commands/seat.py`: add `brief <role> <item> <name> [--worktree --pr --gate
  --track --body --file]` (the parser and `run` of `commands/brief.py`, moved) and
  `note --fix <title>` (from `commands/note.py`). Help: "Brief, record, recover or stop a seat".
- `cli/wuwei/commands/build.py`: add `analysis <item> [--file]` (from `commands/spec.py`) and
  `classes <worktree>` (from `commands/sweep.py:classes`).
- `cli/wuwei/commands/retro.py`: add `--promote` (runs `promotion` as `commands/promote.py` did,
  then `memory.export` and `memory.write_index`).
- `cli/wuwei/commands/report.py`: add `--week [W]` (the output of `metrics --week`).
- `cli/wuwei/commands/hook.py`, `cli/wuwei/commands/status.py`: `add_parser` without `help`;
  `status` drops the plain and `--json` modes (`status.py:304-372`) and keeps `--line`,
  `--width`.
- `cli/wuwei/commands/pr.py`: delete `ping-check` and `reviewers`; `cli/wuwei/commands/tracker.py`:
  delete `done` (38-42).
- `cli/wuwei/promotion.py`: after a landing, call `memory.write_index(root)` (FR-006).
- `cli/wuwei/brief.py`: the lead brief body gains `Candidates:` lines from
  `discovery.discover(root)` with each source (an unreachable source is written as
  `unmeasured: <reason>`, never dropped).

### Every printed command name (FR-004)

Replace, then grep (SC-003):

- `wuwei brief ` with `wuwei seat brief `: `commands/next.py:186`, `dispatch.py:633,781,826`,
  `guards/agent_launch.py:61,86,174-260`, `commands/build.py:229`.
- `wuwei note --fix` with `wuwei seat note --fix`: `charters/builder.md:6`, `charters/lead.md:12`.
- `wuwei spec analysis` with `wuwei build analysis`: `specmode.py:27,368`,
  `charters/builder.md:10`.
- `wuwei sweep classes` with `wuwei build classes`: `brief.py:41`, `charters/builder.md:20`.
- `wuwei promote` with `wuwei retro --promote`: `commands/next.py:262`, `closing.py:87`,
  `charters/_common.md:28`, `charters/_common-authoring.md:13`, `charters/steward.md:13`,
  `skills/wuwei-retro/SKILL.md:14`.
- `wuwei metrics --week` with `wuwei report --week`: `charters/steward.md:11`,
  `telemetry.py:256,308-339`, `metrics.py:465`.
- `wuwei integrity reconfirm` with `wuwei doctor --fix --apply integrity-reconfirm`:
  `integrity.py:214,244,295,317,338,389`, `guards/protect_state.py:110`.
- `wuwei verdict lint`: `dispatch.py:1081` names `wuwei dispatch receive`.
- `wuwei discover`: `charters/lead.md:11` reads "Read the candidates in your brief".
- `wuwei status` (plain, "lists them"): `plan.py:370,404,586,645`, `commands/spec.py:34`
  (moved), `tracker.py:187`, `commands/build.py:272`, `commands/why.py:124,205` name
  `wuwei next`.
- `wuwei memory export`: `memory.py:110,122` name `wuwei retro --promote`.
- `wuwei steward run`: `skills/wuwei-retro/SKILL.md:12` sentence goes.

### Goals block (FR-009)

- `cli/wuwei/goals.py:68-94` (`proposed`): when `goals` is a non-empty list of dicts, render and
  validate it whether or not `text` has goals (a replacement); ids only keep today's rule.
- `cli/wuwei/plan.py:359-362` (`approve`): `provisional = (directory / 'goals.md').is_file()`;
  `plan.py:296-300` (`propose`) writes the draft for a replacement too and unlinks it only for
  ids.
- `cli/wuwei/guards/protect_state.py:106-108`: the goals hint says "goals change through the
  plan's goals block: propose new blocks, the gate card approves them".
- `charters/lead.md:12`: "While `memory/goals.md` has none, or when the owner changed the goals,
  write each goal in `goals` as a block". `charters/planner.md`: on the owner's goals change,
  pass the new blocks to the lead JSON at the next gate.

### Init upgrade (FR-007, FR-008)

- `cli/wuwei/commands/init.py`:
  - `RETIRED_FILES` becomes the one list of obsolete paths under `.wuwei/`: today's six memory
    files, `graph.json`, part 23's watch and shepherd lock and log files, `git-hooks/`, plus
    `memory/voice.md` (part 13), `ziran/` (part 18's MCP reports and snapshots), and every
    generated copy of a deleted skill or agent under `generated/` that `write_workspace` no
    longer writes. Directories are removed with `shutil.rmtree` only after checking the path is
    inside `.wuwei/`, not a symlink and not under `days/`.
  - One removal loop prints `Upgraded workspace: remove .wuwei/<path> (no longer read)` or
    `Would remove ...`; a symlinked or outside path prints `left .wuwei/<path>: <reason>`.
  - The `graph.json` special case (406-407, 437-438) folds into the loop.
  - Writes `memory/index.md` once (`memory.write_index`).
- `cli/wuwei/workspace.py`: `SURFACES` drops `decisions`; SCHEMA `adapters.redactor` and
  `retro.repo` go; `RETIRED` gains `'adapters.redactor'`, `'owner.verbosity.decisions'`,
  `'retro.repo'`; bump `CONFIG_CACHE_VERSION`.
- `cli/wuwei/registry.py:18`: drop `redactor` from `PARAMETERS`.
- `cli/wuwei/telemetry.py:46`: drop `redactor` from the adapter allow-list (stored weeks keep
  validating: keep it in a `RETIRED_ADAPTERS` constant if a stored row carries it).
- `cli/wuwei/commands/config.py:66,172`: the per-adapter loops follow SCHEMA (no edit if
  generic).
- `cli/wuwei/guards/protect_state.py:71`: the `ziran` tail goes once the directory is removed.
- `templates/workspace/config.toml:48,64` and the `[adapters]` redactor line: delete.

### Charters (FR-010) and agents

Append one ordered step to each sentinel charter (bump each `version` minor):

- `charters/sentinel-arch.md`: "8. Defect classes the gates caught on real days: an
  implementation or text that contradicts a rule the project already fixed in its spec,
  invariants or registered plan. A measure or rule fixed in advance whose computation is left
  open (an unpinned code path, an undefined producer, a wrongly scoped exclusion, an unrecorded
  deviation), so a choice can still be made after the result is seen. A merge or
  branch-protection setting that lets automation merge a change the owner must review and
  merge."
- `charters/sentinel-quality.md`: "7. Defect classes the gates caught on real days: an error
  path that ends a long-running job on a temporary or rate-limit failure instead of waiting and
  retrying, so the work done so far is lost. A headline, number or uncertainty statement that
  the data at the reviewed commit does not support."
- `charters/sentinel-security.md`: "7. Defect classes the gates caught on real days: a secret or
  token that reaches an unintended host, follows a redirect, or is echoed into a log, error
  message or output file. Untrusted files or text that can crash the tool, exhaust memory,
  write through a planted link outside the working area, or steer a model prompt."

Then `bin/wuwei agents build` (never edit `agents/*.md` by hand).

### Docs and README (FR-011)

Rewrite each page for what remains, keeping file names and `mkdocs.yml` nav:

- `docs/site/reference.md`: the command table equals `--help` (20 rows); one section per
  command with its subcommands; a "Plumbing" section for `hook` and `status --line`; no
  host-terminal section (lines ~235 and ~389 at 71d3f06b describe `/dev/tty` prompts; the
  #840 review asked for this) and no duplicated rows (`mcp`, `decide`, the security
  paragraph; the lead's note).
- `docs/site/concepts.md`: the loop (next derives the day from the log, worktrees, verdicts
  and the PR listing), gates, fix rounds, Owner step cards, duties, the edges, records; no
  host terminal (line ~80 at 71d3f06b).
- `docs/site/daily.md`: a day walked through `next` only.
- `docs/site/configuration.md`: every SCHEMA section and template key (tests pin both).
- `docs/site/recovery.md`: `doctor`, `why`, `seat stop`, a damaged log line, integrity
  reconfirm through doctor.
- `docs/site/index.md`, `agent.md`, `adapters.md`, `security.md`, `integrity.md`,
  `charter-overrides.md`, `rehearsal.md`: each follows the command set and the deleted units.
- `README.md`: what WUWEI is, the loop, the 20 commands, install, upgrade; no redactor row.
- `scripts/build-hero.py:23,66,208`: hero text without the heartbeat and the overnight
  shepherd; regenerate `docs/site/assets/hero-light.svg` and `hero-dark.svg`
  (`tests/test_docs.py::test_hero_files_match_their_generator`).
- `docs/headless-e2e.md`, `scripts/headless_e2e.py`: command names follow the folds.
- `docs/specs/2026-09-24-wuwei-design.md`: command names follow the folds (Assumption 11).

## Files to edit, tests (about 25)

- `tests/test_cli.py::test_help`: the 20 names, `hook` and `status` absent from the listing but
  runnable; the deleted names refuse (red first).
- `tests/test_docs.py`: unchanged rules; the rewritten pages satisfy them.
- `tests/test_config_transition.py`: the 0.27.0 fixture: a config holding every key the 0.27.0
  template wrote plus the retired ones, and a `.wuwei/` holding every `RETIRED_FILES` path
  (files and directories), one symlinked path, and a `days/<date>/state.snapshot.json`; after
  `init --upgrade` none is left except the symlink and the day file, and one line per removal
  was printed; `--dry-run` changes nothing (red first).
- `tests/test_plan.py`, `tests/test_goals_rank.py`: the replacement goals block from propose to
  approve to `memory/goals.md` committed; ids-only unchanged (red first).
- `tests/test_brief.py`: the lead brief lists the discovered candidates with sources and an
  unmeasured source (red first); builder and gate briefs through `seat brief`.
- `tests/test_promotion.py`: `retro --promote` lands, exports and writes `memory/index.md`.
- `tests/test_metrics.py`, `tests/test_report_retro.py`: `report --week`.
- `tests/test_spec_mode.py`, `tests/test_process_depth.py`: `build analysis`, `build classes`.
- `tests/test_note_fix.py`: `seat note --fix`.
- `tests/test_integrity.py`, `tests/test_doctor.py`: reconfirm through doctor's fix.
- `tests/test_adapters.py:18,219`, `tests/test_outward.py:573`: the redactor adapter cases go.
- `tests/test_workspace.py`, `tests/test_config_writer.py`: retired keys.
- `tests/test_charters.py`, `tests/test_agents.py`, `tests/test_tone.py`: charters and agents
  after the rebuild.
- Every test that runs a renamed command: `grep -rln "'brief'\|'note'\|'spec'\|'sweep'\|'promote'\|'metrics'\|'integrity'\|'verdict'\|'steward'\|'discover'\|'goals'\|'index'\|'payload'" tests`.

## RETIRED (base has `workspace.RETIRED`)

Add `'adapters.redactor'`, `'owner.verbosity.decisions'`, `'retro.repo'`.
