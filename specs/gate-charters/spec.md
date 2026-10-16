# Feature Specification: a gate never edits a written verdict, each seat has its own scratch folder, and Codex jobs are not seats

**Feature branch**: `claude/gate-charters`
**Item**: gate-charters, tier full, goal G-1
**Input**: process findings from the seats on 2026-10-16, and the docs half of #1078 (a verdict
written by a `codex-companion` task job is never attested, so the gate silently counts as missing).

## The promise in my words

Docs only, no runtime lines. Four rules, written where the seats read them:

1. `charters/_gate.md`: a gate never edits a verdict file once written. WUWEI counts the bytes it
   attested, so an edit uncounts the verdict. When the file exists (another seat, same head) or its
   shape was refused, the gate writes the next free `<gate>-<sha7>-2.md` and names that file in its
   `Verdict file:` line. The wording follows `hook._verdict_problem`: "Write yours to ...-2.md beside
   it (the next free number) and end with its Verdict file: line."
2. `charters/_common.md`: each seat writes scratch files only under `<scratchpad>/<role>-<item>/`.
3. `charters/planner.md`: a gate brief for a change to `guards.py` or `hook.py` asks for the
   main-versus-head differential over `tests/fixtures/routes.json`. A gate counts only when its
   seat's SubagentStop (or hand-back) attests it, so a `codex-companion` task job is not a seat. The
   Codex gate route follows codex-attest-probe's outcome (#1078).
4. `docs/site/reference.md` shows `<file>:<line>` as optional on a non-blocking note, as
   `verdict.FORMAT` does. `docs/site/concepts/codex.md` says how a gate on Codex counts.

Then `bin/wuwei agents build` rebuilds `agents/`, and `setup.vendor('.')` re-vendors `.claude/`.

The acceptance scenarios, restated:

1. After the charter edits, `bin/wuwei agents build` runs and the suite's drift tests read `agents/`
   and `.claude/` as matching.
2. A sentinel reading `charters/_gate.md` finds that a written verdict is never edited and the -2
   rule, in the words the hook's refusal uses.
3. `docs/site/reference.md` and `verdict.FORMAT` both mark `<file>:<line>` optional on a note and
   required on a blocking finding.
4. The planner briefing a gate on a `guards.py` change names the differential over
   `tests/fixtures/routes.json` and the `codex-companion` limit.

## How this fails

1. A gate reads "never edit" as "never fix" and hands back a refused verdict as plain text. The
   charter says in the same paragraph to write the corrected verdict to the next free `-2.md` and
   hand back again; the hook's refusal names the format.
2. A planner briefs the differential before `tests/fixtures/routes.json` exists (it lands with the
   route-fixtures item). The gate then cannot run it and writes `not run` with the reason, as the
   gate charter already asks for any probe it cannot run.
3. A planner reads the Codex rule as a ban and never runs Codex gates even after the probe records
   an attested seat. The rule names the probe as the switch, and the codex page says the same.

## Clarifications

### Session 2026-10-16

- Q: Does "never edit" also cover the gate's own malformed file, which was never attested? A: Yes.
  One rule is easier to follow than two, and the hook accepts a new path from the same seat. The
  stray malformed file only surfaces in `wuwei evidence` when a gate is missing, as a reason.
- Q: What is `<scratchpad>`? A: The session's scratchpad directory the harness gives each agent;
  the role is the seat's role (`builder`, `sentinel-quality`), the item its plan id.
- Q: The promise says SubagentStop attests; since #1082 the hand-back also attests. Which does the
  charter name? A: Both, SubagentStop first, as the hook does both through `_verdict_problem`.
- Q: codex-attest-probe is parked (no Codex CLI in the cloud). What does the planner do meanwhile?
  A: Run gates as Claude seats; a Codex-native seat counts only once the probe records an attested
  seat.
- Q: Does any test change? A: No. The existing drift tests (`test_the_generated_agents_match_the_charters`,
  `test_the_vendored_plugin_matches_the_tree_it_was_copied_from`) hold acceptance 1; 2 to 4 are
  wording, checked by reading the files.

## User Scenarios & Testing

### US1: built agents match the edited charters (P1)

Acceptance 1. Red: with `agents/builder.md` held at main in a scratch copy, both drift tests fail.
Green: after the build and vendor, the full suite passes.

### US2: a gate keeps written verdicts (P1)

Acceptance 2, read in `charters/_gate.md` and the built `agents/sentinel-*.md`.

### US3: the docs show the verdict shape the parser takes (P2)

Acceptance 3, `docs/site/reference.md` against `cli/wuwei/verdict.py` FORMAT.

### US4: the planner briefs guard changes and Codex gates right (P2)

Acceptance 4, read in `charters/planner.md`.

## Requirements

- FR-001: `charters/_gate.md` says a written verdict is never edited and names the next free
  `-2.md` rule for both a taken file and a refused shape, in the hook's words.
- FR-002: `charters/_common.md` limits scratch files to `<scratchpad>/<role>-<item>/`.
- FR-003: `charters/planner.md` names the routes differential for `guards.py` and `hook.py` changes,
  the attestation rule, the `codex-companion` limit and the probe as the Codex route switch.
- FR-004: `docs/site/reference.md` verdict format matches FORMAT on findings and notes;
  `docs/site/concepts/codex.md` explains gates on Codex.
- FR-005: `agents/` rebuilt and `.claude/` re-vendored; no runtime line changes.

## Assumptions

- `tests/fixtures/routes.json` does not exist on main yet; the route-fixtures item adds it. The rule
  names it now so it applies the day the fixture lands. Overturned if route-fixtures is dropped.
- The scratch folder rule binds all seats, the planner's own scratch aside. Overturned if the
  steward wants the planner bound too.
- Boundaries items 2 to 4 in `_common.md` shift to 3 to 5; no file cites them by number (grep for
  "Boundaries [0-9]" found none).

## Rollback

Revert the commit, then run `bin/wuwei agents build` and `setup.vendor('.')`. No runtime, config,
ledger or file format changes.
