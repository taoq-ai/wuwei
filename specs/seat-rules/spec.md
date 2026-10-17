# Feature Specification: gate verdicts for a head go to the builder together, parser changes carry a generated probe, equivalence needs a differential probe, and repo lessons have a home

**Feature branch**: `claude/seat-rules`
**Item**: seat-rules, tier full, goal G-1
**Input**: gate rounds on guard parsing are the largest cost under G-1. Hand-typed probes missed
spelling classes, gates called code deletable on a surviving mutant alone, fixes started before
the last gate returned, and lessons about one repository's code were proposed as charter rules.

## The promise in my words

Six charter rules, built into `agents/` and the vendored `.claude/` copies. Runtime lines: 0.

1. `planner.md`: the planner holds the gate verdicts for one head until the last gate for that
   head returns, then sends them all to the builder at once. The builder starts fixing only then.
2. `_gate.md`: when a change makes more commands unreadable or rewrites a parser, the gates also
   probe the checks that do not depend on door words (a leak check on network programs, an ask
   rule for infrastructure commands) with the new command shape.
3. `builder.md` and `_gate.md`: a change to guard parsing comes with a generated combinatorial
   probe (operator or spelling classes x positions x targets), run under real bash with a stub
   program on PATH. The PR or the verdict reports three counts: commands generated, commands that
   really ran the door program, and the holes. A gate round on a parser re-runs the probe and adds
   a class for each hole it finds.
4. `_gate.md`: a gate calls code equivalent or deletable only after a generated differential probe
   between the head and the change shows 0 differences. A surviving mutant alone is untested.
5. `steward.md`: a lesson about one repository's code goes in that repository's standards lines
   (`.wuwei/standards.md`); a lesson about how seats work anywhere is a charter proposal.
6. `builder.md` and `_gate.md`: probe fixtures holding JSON escapes are written by code
   (`json.dumps` or a Python literal), never typed into a shell.

Outside: the Stop hook wording (#1099) and the #1078 attestation path.

The acceptance scenarios, restated:

1. At the head, `bin/wuwei agents build` leaves git status clean and the drift test passes.
2. `agents/builder.md` and `agents/sentinel-security.md` each name the generated combinatorial
   probe under real bash with a stub on PATH and its three counts (generated, ran, holes).
3. `agents/sentinel-quality.md` says equivalent or deletable needs a generated differential probe
   with 0 differences, and a surviving mutant alone is untested.
4. `charters/planner.md` says the verdicts for one head go to the builder together after the last
   gate for that head returns.
5. `charters/steward.md` names `.wuwei/standards.md` for one repository's code and a charter
   proposal for lessons about seats.

## How this fails

1. A gate on a docs-only parser item spends a round building a generated probe the change does not
   need. Held: the rule binds a change to guard parsing (how a guard reads a command), not every
   parser in a repository, and a gate already decides which probes a diff needs.
2. A planner holds verdicts for a head while one gate hangs, and the builder idles. The rule ties
   the forward to the last gate for that head returning; a gate that never returns is already a
   blocker the planner handles as a failed seat, so the wait is bounded by that seat.
3. The equivalence rule makes every surviving mutant a blocking demand for a differential probe.
   Held: a surviving mutant alone is reported as untested, which rule 3 already classes as
   `[low] blocks: no` unless the gate names a concrete bad input; only a claim of equivalence or
   deletability needs the probe.

## Clarifications

### Session 2026-10-17

- Q: Where do the parser and fixture rules go in `_gate.md`? A: A new rule 4 after the mutant rule;
  the old rules 4 to 6 become 5 to 7. A grep of charters, docs, cli and skills found no citation
  of `_gate.md` rules by number.
- Q: The promise names "door program" and "door words", which are WUWEI's terms. A: The doors are
  the plugin's own refusals, present in every workspace; the charter glosses "door program" as the
  guarded program the stub stands for, and gives the door-word-free checks as examples.
- Q: Where does the builder rule live? A: In the VAL sweep line, which already covers changed
  parsers, so the builder reports it with the sweep.
- Q: `planner.md` and `steward.md` acceptance read charters; `steward.md` is also built into
  `agents/`. A: Tests read the charter for both, as the acceptance lines say.

## User Scenarios & Testing

### US1: the built agents match the charters (P1)

Acceptance 1, held by `test_the_generated_agents_match_the_charters` and
`test_the_vendored_plugin_matches_the_tree_it_was_copied_from`.

### US2: the parser rule and its counts (P1)

Acceptance 2. Red: `test_the_parser_rule_names_the_generated_probe_and_its_three_counts` fails for
builder and sentinel-security; `test_every_gate_reruns_the_parser_probe_and_probes_checks_without_door_words`
fails for the sentinels.

### US3: equivalence needs a differential probe (P1)

Acceptance 3. Red: `test_equivalence_needs_a_differential_probe_with_0_differences`.

### US4: verdicts for one head go together (P1)

Acceptance 4. Red: `test_the_planner_forwards_the_verdicts_for_one_head_together`.

### US5: lessons have a home (P2)

Acceptance 5. Red:
`test_the_steward_files_a_repository_lesson_in_its_standards_and_a_seat_lesson_as_a_proposal`.

## Requirements

- FR-001: `planner.md` Running the work 2 holds the together-forward rule (promise 1).
- FR-002: `_gate.md` rule 4 holds the door-word-free probe (promise 2).
- FR-003: `builder.md` VAL and `_gate.md` rule 4 hold the generated combinatorial probe, its three
  counts and the re-run with a class per hole (promise 3).
- FR-004: `_gate.md` rule 3 holds the differential-probe rule for equivalence (promise 4).
- FR-005: `steward.md` rule 4 holds the lesson placement (promise 5).
- FR-006: `builder.md` VAL and `_gate.md` rule 4 hold the fixture rule (promise 6).
- FR-007: `agents/` rebuilt and `.claude/` re-vendored; runtime lines unchanged.

## Assumptions

- Renumbering `_gate.md` rules 4 to 6 is safe: no citation by number was found
  (`grep -rn "_gate.md\` rule" charters docs cli skills`). Overturned if a seat brief cites a gate
  rule by number.
- The fixture rule binds builders and gates only, the seats that write probes. Overturned if
  another seat starts writing probe fixtures.

- Arch review at bec74db: the door-word-free probe binds only a change to guard parsing, and
  "door words" is glossed in place; there is one standards file per workspace, so a repository
  lesson is a line that names its repository; a lesson that fits both homes is a charter proposal;
  the older equivalent-mutant sentence is merged into the differential-probe rule, and untested is
  `[low] blocks: no`.

## Rollback

Rollback: revert the commit, then run `bin/wuwei agents build` and `setup.vendor('.')`. Charter
text only; no runtime, config, ledger or file format change.
