# Feature Specification: decisions and done stated once, repository lessons out of the charters, an architect's arch gate, and fitness tests on the charters and skills

**Feature branch**: `claude/focused-hopper-90dros`
**Item**: charter-review, tier full, goal G-1
**Input**: the owner's review of the charters and skills against agentskills.io (best practices and
description optimisation), mgechev/skills-best-practices and arXiv 2606.17819. It found the core
rules stated in four places and already drifted, this repository's guard-testing lessons in the
charters every workspace loads, an architecture gate that duplicated the security and goal gates,
no external frameworks named, no negative triggers on the skills, and sentences over the charters'
own 35-word cap.

## The promise in my words

Charter, skill, test and docs text only. Runtime lines: 0 (2,976 before and after).

1. `_common.md` is the one statement of Decisions and Done. It carries the thresholds the code
   holds (a 20-line delta, a 15 percent change failure rate over 28 days, the 400-line batch, three
   days stale), and says which of these are safety and which are process fit. `_way.md`,
   `planner.md` and the `wuwei-rules` skill point to it instead of restating it. The
   contradiction in `wuwei-rules` (a requested reviewer and staleness listed among what holds a
   merge) goes.
2. The lessons about this repository's guards (the route corpus, the generated combinatorial probe
   and its three counts, door-word-free checks, fixtures by code, normalisation classes, the
   main-versus-head differential) move out of `_gate.md`, `builder.md`, `planner.md` and
   `sentinel-security.md` into `AGENTS.md` under "Testing the guards" and into this workspace's
   `.wuwei/standards.md`. The charters keep one generic rule: a parser or guard change carries the
   probes the repository's own process names.
3. `sentinel-arch.md` reviews as an architect: conformance to the named design and ADRs,
   dependencies and coupling, contracts, quality attributes, fitness functions (budgets), settled
   decisions, Breaking. Trust boundaries go to the security gate; the open-measure defect goes to
   the goal gate.
4. Each gate names the frameworks it stands on in one line (OWASP, CWE, mutation testing, C4 or
   arc42, ADRs, fitness functions, SAFe WSJF). The security gate defines "the repository's own
   scanner" and reads the supply chain. The quality gate reads test quality. The lead caps work in
   progress.
5. Every skill description carries a negative trigger (`Not for ...`). A trigger set
   (`tests/fixtures/skill-triggers.json`) holds at least eight should and eight should-not queries
   per skill, with near misses from the other skills.
6. Fitness tests in `tests/test_charters.py`: no sentence over 35 words in a charter or skill,
   each generated agent under 2,250 words, no issue number or file of this repository in a charter,
   the planner's rules numbered in order, "door" never used for a decision, the steward allowed to
   propose charter deletions.
7. Generic lines the model already follows (SOLID, clean code, most of the humanizer checklist)
   are cut; the planner's numbering is fixed; issue numbers and dated conditions leave the charters.

Outside: runtime code, the verdict format (`verdict.FORMAT` and the hook that lints it), the
doors, the agents' tool grants, the design's gate table.

The acceptance scenarios, restated:

1. Given the charters at the head, when the suite runs, then every charter and skill sentence is 35
   words or fewer and each generated agent is under the word ceiling.
2. Given `AGENTS.md` at the head, when a seat looks for the guard probe rules, then it finds them
   under "Testing the guards" and no charter names `guards.py`, `hook.py`, `routes.json` or an
   issue number.
3. Given `_common.md`, when a seat reads Decisions and Done, then it finds the four thresholds
   once, and `_way.md`, `planner.md` and `wuwei-rules` point to it.
4. Given `sentinel-arch.md`, when the arch gate reads it, then it reviews conformance, dependencies
   and coupling, contracts, quality attributes, fitness functions, settled decisions and Breaking,
   and leaves trust boundaries to the security gate.
5. Given the five skills, when their descriptions are read, then each says when to use it and when
   not, and the trigger set holds at least eight should and eight should-not queries per skill with
   near misses from the other skills.

## How this fails

1. A workspace other than this one loses the guard-probe rules its gates relied on. Held: those
   rules bind a change to `cli/wuwei/guards.py`, which exists only in this repository; the generic
   rule still sends a gate to the repository's own process for any parser change, and this
   workspace's `.wuwei/standards.md` carries the lines into every brief.
2. The sentence test rejects a correct charter edit because of the splitter, and a seat "fixes" it
   by cutting a rule. Held: the splitter counts a code span as one word, treats list items,
   headings and placeholders as their own blocks, and splits at semicolons; the failure message
   prints the sentence, so the fix is a split, not a cut. The steward's rule 9 names deletion as a
   proposal, never a quiet edit.
3. The arch gate, now told that trust boundaries belong to security, passes a change at `standard`
   where only arch runs (a contract file) and a trust defect slips. Held: `evidence.needed` adds
   security for any risky path at `standard`, so a trust path never runs arch alone; and the arch
   charter still says to name a trust finding in a note.

## Clarifications

### Session 2026-10-17

- Q: The seat-rules item (merged this week) placed the parser-probe rules in the generic charters
  on the argument that the doors exist in every workspace. A: The doors do; changes to their parser
  do not. Only this repository edits `guards.py`, so the rules are a repository lesson by the
  steward's own placement rule, and they move. Recorded under Assumptions.
- Q: `.wuwei/standards.md` is not tracked in git. Where is the committed home? A: `AGENTS.md`
  "Testing the guards", which the builder reads in the tree; the standards lines point there and
  reach the gates through the planner's brief. `wuwei sync` carries the standards to `wuwei/state`.
- Q: The tests in `tests/test_setup.py` asserted the probe rules in the agents. A: They now assert
  them in `AGENTS.md`, and assert that the generic agents name the repository's process instead
  and hold none of this repository's file names.
- Q: The word ceiling. A: 2,250 words per generated agent; the largest (sentinel-arch) is about
  2,200 after this change. The steward's rule 9 lowers it by proposal, never raises it in passing.
- Q: Does the arXiv paper's full text inform anything here? A: Only its headline result (adherence
  to skill instructions varies widely across models), which argues for shorter, single-source
  charters on the Sonnet quality gate. The full text was unreachable from the session.

## User Scenarios & Testing

### US1: the charters hold their own tone rule (P1)

Acceptance 1. Red before the rewrite: `test_no_sentence_is_over_35_words` failed on 16 of 19
files; `test_a_generated_agent_stays_under_the_word_ceiling` failed on 5 of 8 agents at the old
ceiling check. Green at the head.

### US2: repository lessons have one home (P1)

Acceptance 2. Red: `test_a_generic_charter_names_the_repository_process_for_parser_probes_not_this_repository`
failed for all five roles before the move; `test_the_guard_probe_rules_are_this_repository_lessons_in_agents_md`
failed before `AGENTS.md` gained the section.

### US3: decisions and done once (P1)

Acceptance 3. `test_decisions_and_done_are_stated_once_in_common` and
`test_a_requested_reviewer_and_staleness_are_process_fit_everywhere`.

### US4: an architect's gate (P1)

Acceptance 4. `test_the_arch_gate_reviews_as_an_architect`, `test_each_gate_names_the_frameworks_it_stands_on`,
`test_the_security_gate_defines_its_scanner_and_reads_the_supply_chain`.

### US5: skills say when not (P2)

Acceptance 5. `test_every_skill_description_says_when_to_use_it_and_when_not` and
`test_the_trigger_set_covers_every_skill_with_near_misses`.

## Requirements

- FR-001: `_common.md` holds Decisions and Done with the four thresholds; `_way.md`, `planner.md`
  and `wuwei-rules` point to it (promise 1).
- FR-002: no charter or skill names `guards.py`, `hook.py`, `routes.json` or an issue number;
  `AGENTS.md` holds "Testing the guards" with the moved rules (promise 2).
- FR-003: `sentinel-arch.md` holds the seven architect rules and hands trust to security (promise 3).
- FR-004: each gate names its frameworks; security defines its scanner and reads the supply chain;
  quality reads test quality; the lead caps work in progress (promise 4).
- FR-005: every skill description has `Not for`; `tests/fixtures/skill-triggers.json` covers every
  skill with eight and eight and near misses (promise 5).
- FR-006: `tests/test_charters.py` holds the fitness tests (promise 6).
- FR-007: `agents/` rebuilt and `.claude/` re-vendored; runtime lines unchanged (2,976).
- FR-008: `docs/design.md` section 9 and `docs/site/concepts/team.md` name the charter ceiling and
  the lesson placement (promise 7).

## Assumptions

- Reversing the seat-rules placement of the parser-probe rules is a two-way choice: the text moves
  to `AGENTS.md` and `.wuwei/standards.md`, and a revert restores it. Overturned if a workspace
  other than this one changes WUWEI's guard parser.
- The 35-word cap is read by a splitter, not a parser; a semicolon list counts as separate
  sentences. Overturned if a charter edit needs a 36-word sentence with no honest split, in which
  case the test, not the rule, is wrong.
- Frameworks are named, not linked: seats have no network tool, and a name is enough to activate
  what the model already knows. Overturned if a gate cites a framework rule that does not exist.
- The lead's default capacity of four seats stands until a brief names another. Overturned by a
  planner that runs more builders at once by default.

## Rollback

Rollback: revert the commit, then run `bin/wuwei agents build` and `setup.vendor('.')`. Charter,
skill, test and docs text only; no runtime, config, ledger or file format change. The workspace's
`.wuwei/standards.md` lines stay valid either way.
