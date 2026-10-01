# Feature Specification: an owner interview that turns personal preferences into configuration and charter overrides

**Feature Branch**: `279-owner-interview`
**Created**: 2026-10-01
**Status**: Ready for implementation
**Input**: Issue #279, feat(calibrate). Design sections 4.6 (merge policy), 4.8 (voice),
5.4 (when the user is asked), 5.8 (decisions), 5.9 (signals), 6 and 6.8 (charter
overrides, propose and promote), 15.4 (`control_plane.content`); the outward lint; #278
calibrate (same proposal path); #280 tiered gates (`gates.floor`); #227 owner terminal
rule. Owner request 2026-10-01.

## Root cause (read on main, e4b3da0)

Every preference the issue lists already has a home, but only a hand edit reaches it, and
the calibrate proposal path cannot carry an owner answer.

- Reproduced read-only in a scratch workspace (`git init`, `bin/wuwei init .`):
  `bin/wuwei calibrate --interview` exits 2 with `unrecognized arguments: --interview`.
  `cli/wuwei/commands/calibrate.py:11-14` registers only `--repo`.
- The keys exist: `merge.auto`, `merge.soak_minutes`, `merge.quiet_hours`
  (`cli/wuwei/workspace.py:18-20`), `gates.floor` (`:46`), `deploy.deny` (`:98`),
  `control_plane.content` (`:136`). Charter overrides are `.wuwei/charters/<role>.md`
  targets of `wuwei promote` (`cli/wuwei/promotion.py:59-73`), and the voice `never` list
  the outward lint enforces is `.wuwei/memory/voice.md` (`cli/wuwei/voice.py:29-50`,
  `:56-77`), also a promote target.
- `calibrate.proposal` (`cli/wuwei/calibrate.py:413-450`) adds only absent keys and turns
  any present owner value into a hand edit; `calibrate.apply` (`:453-494`) replaces only a
  one-line `deploy.workflows` or `deploy.deny` `[]` (`:470`). An answer that changes a
  present value cannot land: the template already writes `content = "summary"`
  (`templates/workspace/config.toml:69`), so the phone question could never apply.
- `wuwei config promote` (`cli/wuwei/commands/config.py:90-135`) recomputes the proposal
  from the checkouts only; it has no input for owner answers.
- `retro.compile` (`cli/wuwei/retro.py:12-119`) reads no owner decision outcomes, and a
  merge routed to the owner has no fixed record shape (`charters/shepherd.md:18`: "route
  the merge to the owner with the decision record"), so nothing can count merge decisions
  answered the same way.
- The AskUserQuestion guard (`cli/wuwei/guards/decision.py:99-146`) admits a widget only
  when it cites a D-/C- record or starts with `Morning gate` and cites today's
  `days/<date>/plan.md`. The plan skill's widget path must use the second form; the guard
  does not change.

## User Scenarios & Testing

### User Story 1 - The owner answers once on the host terminal (Priority: P1)

The owner runs `bin/wuwei calibrate --interview` in a host terminal. It asks a short,
fixed set of questions from one table, records the answers, writes charter and voice
proposals, and prints each answer with the key or override it maps to. Nothing applies
until the owner promotes.

**Independent Test**: `python -m pytest -q tests/test_interview.py -k "terminal or promote"`.

**Acceptance Scenarios**:

1. Given a workspace with one configured repository and every question answered on this
   terminal, then `calibrate --interview` exits 0, writes
   `.wuwei/days/<date>/interview.json` and `proposals/interview-<target>.json` files, and
   prints one line per answer naming its key (for example `repos.0.merge.auto = true`) or
   its override (`.wuwei/charters/planner.md`, `.wuwei/memory/voice.md`). `config.toml`
   is unchanged.
2. Then `wuwei config promote` prints the same answer lines inside the digested summary
   and, on confirmation, writes the config keys; `wuwei promote` lands the charter and
   voice proposals; `wuwei config check` then exits 0.
3. Given no tty on stdin, then `calibrate --interview` exits 2 with
   `this is an owner action: run it in a host terminal` and writes nothing.
4. Given `--interview merge`, then only the merge question is asked and the other answers
   recorded today are kept. Given an unknown question id, exit 2 naming the valid ids;
   nothing written.
5. Given an invalid answer on the terminal, the question is asked again; end of input
   exits 2 and writes nothing.

### User Story 2 - The plan skill asks the same questions as widgets (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_interview.py -k widget`.

**Acceptance Scenarios**:

1. Given `wuwei calibrate --questions`, then it prints JSON widgets built from the same
   table: same ids, same choice labels, one widget per configured repository for a
   repository question, each with a header of at most 12 characters and 2 to 4 options.
2. Given today's `plan.md` exists, then every printed widget passes the AskUserQuestion
   guard (`check_question` exit 0) unchanged.
3. Given `wuwei calibrate --answer "merge=Auto, 30 min soak" --repo acme/widget`, then
   the answer is recorded exactly as the terminal path records it; an answer that is
   neither a choice label nor valid free text exits 2 and writes nothing.
4. `skills/wuwei-plan/SKILL.md` documents the first-day widget path and tells the planner
   to read `.wuwei/charters/planner.md` when present.

### User Story 3 - Answers apply only through the existing owner paths (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_interview.py -k "settle or apply" tests/test_calibrate.py`.

**Acceptance Scenarios**:

1. Given an answer for a key absent from `config.toml`, then promote adds it in its
   section (creating `[repos.merge]` or `[repos.gates]` after its repository when
   missing).
2. Given an answer for a key present as a one-line assignment, then promote replaces that
   line; every other owner value is preserved (`init._preserves_values`) and the result
   validates against `workspace.SCHEMA`.
3. Given an answer for a key present in any other form (multi-line array, dotted key,
   inline table), then promote changes nothing for it and lists it under
   `Config differs; edit by hand`.
4. Given a `manual` answer, then `deploy.deny` becomes the present list plus the new
   patterns; no pattern is ever removed, and a calibrate deny proposal in the same promote
   is kept.
5. Given a forged or stale `interview.json` (unknown id, unknown repository, a value that
   is not a choice or valid free text), then `config promote` exits 2 and writes nothing.
6. Given a direct agent tool write to `.wuwei/days/<date>/interview.json`, then the
   protect_state guard refuses it; the CLI is its only writer.
7. Every existing calibrate test passes unchanged.

### User Story 4 - The retro offers the merge question again (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_interview.py -k reask tests/test_report_retro.py`.

**Acceptance Scenarios**:

1. Given three owner-answered merge decisions for `acme/widget` within the last seven
   days whose chosen option's description starts with `Merge`, and `merge.auto = false`
   for that repository, then the retro has an `## Owner preferences` section proposing
   `repos.merge.auto = true` for `acme/widget`, listing the evidence (`<date> D-<n>` for
   each) and the re-ask command `bin/wuwei calibrate --interview merge --repo acme/widget`.
2. Given two such answers, or three with `merge.auto` already true, or one of the three
   eight days old, then the section says `none`.
3. Given a decision record that fails the decision lint, or a question that is not a
   merge question, then it is not evidence. An unreadable day state makes the section
   `unmeasured: <reason>`, never `none`.
4. `charters/shepherd.md` names the merge decision shape
   (`Question: Merge <owner>/<repo>#<number>?`, an option whose description starts with
   `Merge`), and the generated `agents/shepherd.md` matches it.

### User Story 5 - Off every hook path, documented next to calibrate (Priority: P3)

**Independent Test**: `python -m pytest -q tests/test_hooks.py -k calibrat tests/test_docs.py`.

**Acceptance Scenarios**:

1. Given each recorded hook payload, then `wuwei.interview` is not in `sys.modules` after
   the hook runs.
2. `docs/site/configuration.md` has an `## Owner interview` section right after
   `## Calibration` naming `calibrate --interview`, `--questions`, `--answer`,
   `interview.json`, `config promote`, `wuwei promote` and the retro re-ask;
   `docs/site/daily.md` names `bin/wuwei calibrate --interview` after calibrate and
   before `/wuwei plan`.

### Edge Cases

- Several repositories: a repository question is asked once per selected repository
  (`--repo` selects one; default all) and recorded per repository name.
- A repository question with no configured repository: exit 2 with the calibrate
  `NO_REPOS` reason.
- Same-day re-run: answers merge into `interview.json`; proposal files are rewritten from
  all of today's answers. A proposal that already landed is replaced by a new file of the
  same name.
- Re-ask on a later day: a charter override that already holds the interview block gets a
  `patch` proposal rewriting that block (lines for questions not re-asked are kept), so no
  contradictory rule is left behind (design 6.8).
- A choice with no text for an override ("Lead defaults", "Defaults only", "Any time")
  removes that question's line from the block; voice `never` lines are only added, never
  removed (the owner edits voice.md with `wuwei voice edit`).
- `merge.auto = true` takes effect only with `merge_deploys = false` declared (4.6); the
  interview never writes `merge_deploys`, and the choice description says so.
- Free text is split on commas; each item must match the calibrate `SAFE` charset and
  pass `calibrate.instruction_like`. Quiet and working hours reuse the merge quiet-hours
  validator; a time zone must be in `zoneinfo.available_timezones()`; a by-hand command
  must start with a literal executable (the `load_config` deny rule) and gets a trailing
  `*` when it has none.
- `interview.json` belongs to one day: answers not promoted that day are asked again.

## Requirements

### Functional Requirements

- **FR-001**: One new module `cli/wuwei/interview.py` holds `QUESTIONS`, the only
  definition of the question set: id, scope (`repo` or `workspace`), header, question,
  2 to 4 choices (label, description, effects) and an optional free-text parser. Effects
  are config settings (`repos.merge.auto`, `repos.merge.soak_minutes`,
  `repos.merge.quiet_hours`, `repos.gates.floor`, `control_plane.content`,
  `deploy.deny`), charter override lines (`planner`, `shepherd`, `lead`) or voice `never`
  phrases. No new config key, no new charter.
- **FR-002**: `wuwei calibrate --interview [ID ...] [--repo NAME]` asks the selected
  questions with `input()` when stdin is a tty, else exits 2 with
  `integrity.HOST_TERMINAL`. `wuwei calibrate --answer ID=VALUE [--repo NAME]`
  (repeatable) records the same answers without a terminal. `wuwei calibrate --questions`
  prints the widgets. The three flags are mutually exclusive, and none of them profiles a
  checkout or calls a port.
- **FR-003**: Recording validates every answer against the table, merges it into today's
  `interview.json` (atomic write), rewrites
  `proposals/interview-<planner|shepherd|lead|voice>.json` from all of today's answers,
  and prints one line per recorded answer with its keys or override and the next step
  (`bin/wuwei config promote` in a host terminal, then `bin/wuwei promote`).
- **FR-004**: Charter proposals carry one block `## Owner preferences (interview)` of
  `- <id>: <fixed sentence>` lines: `add` when the target override has no such block,
  `patch` (old_text = the existing block) when it has one. The voice proposal patches
  `## shared\n` in voice.md with new `- never:` lines (an `add` with the heading when the
  heading is absent). Evidence is `.wuwei/days/<date>/interview.json`.
- **FR-005**: `wuwei config promote` reads today's `interview.json` (absent: no answers),
  re-validates it, folds its settings into the calibration proposal, and adds the answer
  lines to the digested summary. Settings apply after the calibration additions: absent
  key added, equal value skipped, one-line assignment replaced, anything else a hand edit;
  `deploy` lists are merged with the present list.
- **FR-006**: `calibrate.apply` replaces any complete one-line `key = value` assignment
  of an addition's key in its section (generalising the `deploy` `[]` rule) and removes
  that key from the preservation check; calibrate's own proposal rules are unchanged.
- **FR-007**: `retro.compile` appends `## Owner preferences` from
  `interview.reask(root)`: for each configured repository with `merge.auto = false`,
  owner-answered merge decisions (`decision.answered`) in the day directories of the last
  seven days whose record passes `decision.evaluate`, whose Question is
  `Merge <owner>/<repo>#<n>?` naming that repository and whose chosen option's
  description starts with `Merge`; three or more give one proposal line with the evidence
  and the re-ask command.
- **FR-008**: `charters/shepherd.md` step 3 names the merge decision shape; `agents/` is
  regenerated with `bin/wuwei agents build`.
- **FR-009**: protect_state protects `days/<date>/interview.json` like `plan.md`.
- **FR-010**: No hook imports `wuwei.interview`; `retro` imports it inside `compile`.
- **FR-011**: Docs: `configuration.md` `## Owner interview`, the `daily.md` step, the plan
  skill's first-day widget path.

### Key Entities

- **Question**: a row of `QUESTIONS`.
- **Answers**: `days/<date>/interview.json`, `{id: label-or-text}` for workspace questions
  and `{id: {repo name: label-or-text}}` for repository questions.
- **Setting**: `(path, key, value)` in the calibrate addition shape.
- **Interview block**: the `## Owner preferences (interview)` section of a charter
  override.

## Success Criteria

- SC-001: The three acceptance bullets of issue #279 pass as tests (US1.1 with US1.2;
  US4.1; US1.3 with US2.1 and US2.2).
- SC-002: One table test covers every question: AskUserQuestion constraints, every
  choice resolves to effects that validate, every free-text parser accepts one valid and
  rejects one invalid value.
- SC-003: The full suite passes; existing tests change only by additive rows (protected
  paths, hook module list, docs phrases) and the regenerated shepherd agent.

## Assumptions

- "Same proposal path as calibrate" means config keys apply only through
  `wuwei config promote` (owner, host terminal, digest) and charter and voice changes only
  through `wuwei promote`. The interview never writes `config.toml`, a charter or
  voice.md itself.
- An owner answer may replace a present config value (that is the point of re-asking);
  calibrate's repository-derived values still never do. Only `deploy.deny` merges, so the
  interview can never remove a deployment ban pattern.
- `interview.json` is seat-writable through `--answer` (the widget path relays the owner's
  choices). It is not proof of an owner action: config changes still need the owner's
  digest, and charter or voice proposals are no more than a seat can already propose
  (6.8). Values are closed choices or charset-checked, instruction-scanned free text.
- Never-auto paths are not asked: calibrate proposes them from the checkout and the
  interview never removes one. Per-repository answers come from `--repo`; a different
  value per repository on the widget path is one `--answer` call per repository.
- Interrupt, batching and presentation preferences go to the planner override (planner
  charter step "Batch owner decisions"); page and nudge classification stays fixed by
  design 5.9. Formality and signature go to the shepherd override, the seat that writes
  outward text: tone cannot be linted (4.8) and no signature lint exists, so only words
  to avoid become lint-enforced `never` phrases.
- "Answered the same way" means the owner chose a `Merge` option. Holding a merge the
  policy did not clear agrees with the policy and is not an override; with `merge.auto`
  already true the routed merges failed another precondition, which `merge.auto` cannot
  change, so nothing is proposed. The retro proposes and offers the re-ask; it writes no
  answer.
- "A week" is the day directories from today back six days (`watch.days`), threshold
  three. Both are module constants, not config.
- On the first day the widgets run inside the morning gate (after `plan propose`, so
  `plan.md` exists) and start with `Morning gate (days/<date>/plan.md):`, which the
  existing guard accepts. AskUserQuestion's own "Other" entry carries free text.
- The notes name no dry-run failure for this issue; the reproduction is the missing flag
  in a scratch workspace.
