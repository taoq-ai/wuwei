# Feature Specification: one approval at the morning gate, and no second interview on the first day

**Feature Branch**: `365-one-gate-question`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #365, "feat(plan): one approval at the morning gate, and no second
interview on the first day". From the UX adoption sweep of 2026-10-03, findings F7 and F22.
Owner's brief: "I want the adoption to be easiest as possible. The workflow should coach
people with less experience instead of simply blocking." Coaching means: what happened, why,
and the one command with real values; never a bare refusal. Prefer doing it for the owner
and saying so over asking, and asking over refusing. Depends on #358 (`wuwei next`,
orientation) and #359 (owner questions as widgets), both on main.

## Findings (from the sweep)

| Id | Step | What happens now | Coaching version | Proposed default |
|---|---|---|---|---|
| F7 | first plan | Setup records 14 answers. On the first day the plan skill still runs `calibrate --questions`, which returns all 14 again (checked after promote), so the owner answers the interview twice. | `--questions` returns only unanswered or unpromoted ids; the skill skips the block when it is empty. | Ask once |
| F22 | morning gate | The plan skill asks one question each for goals, queue, seat policy, CAP, envelope and carry-over every morning, although most answers are the defaults. | One `Approve today's plan as proposed?` with `Change something` as the other option. Ask the separate questions only after that. | One question |

The sweep catalogue (section d) has no row for these two findings: both are skill and
command behaviour, not reason strings. The catalogue rows for `cli/wuwei/interview.py`
(`:27`, `:34`, `:45`, `:194`, `:273`, `:278`, `:393`) belong to the reason-format issue
(sweep proposal 3) and stay unchanged here.

## Root cause (read and reproduced on main, 8083971)

The notes name no dry-run workspace. Reproduced read-only in a scratch workspace outside the
repository (one repository `acme/widget`, `WUWEI_NOW=2026-10-01`): every interview question
except `posture` (which `setup --shadow` skips) was answered with
`calibrate --answer <id>=<first choice>`, as setup records them, then `calibrate --questions`
ran:

```
answer exit 0
questions exit 0 count 18 ['merge', 'gates', 'quiet', 'interrupt', 'decisions', 'phone', 'hours',
  'avoid', 'formality', 'signature', 'risk', 'manual', 'verbosity', 'posture', 'tracker', 'chat',
  'review_bot', 'reviewers']
recorded ['avoid', 'chat', 'decisions', 'formality', 'gates', 'hours', 'interrupt', 'manual',
  'merge', 'phone', 'quiet', 'review_bot', 'reviewers', 'risk', 'signature', 'tracker', 'verbosity']
```

- `cli/wuwei/interview.py:447-454` (`widgets`) builds the widget list from
  `_selected([], repos)`, which is every row of `QUESTIONS` for every repository. It never
  reads a recorded answer, so the output is the same before and after setup.
- `cli/wuwei/commands/setup.py:285-287` records the interview into today's
  `days/<date>/interview.json` and skips `posture` under `--shadow` without recording the
  answer the flag gave. So even with the filter above, `posture` would still come back on the
  first day of the recommended `setup --shadow` path.
- `skills/wuwei-plan/SKILL.md:21` (step 4) runs the first-day block on every first day
  ("no earlier day directory under `.wuwei/days/`"), which is the same date setup ran on, so
  the owner answers the interview a second time.
- `skills/wuwei-plan/SKILL.md:21` (step 4) also says "Run the morning gate with one
  AskUserQuestion per decision ... Ask separately for goals, queue, seat policy, CAP,
  envelope and carry-over", and `charters/planner.md:11`, `docs/site/daily.md:202-204`,
  `docs/site/agent.md:45` and the `gate` row of `cli/wuwei/commands/next.py:57-59` ("ask the
  owner the Morning gate questions") repeat it. Nothing in the CLI requires separate
  questions: `guards/decision.py:105-116` (`gate_question`) accepts any question that starts
  `Morning gate` and cites today's `plan.md`, and `record_gate` (`:122-150`) lets the planner
  record goals after any such question with header `Goals`.

## User Scenarios & Testing

### User Story 1 - The first day asks the interview once (Priority: P1)

The owner runs `bin/wuwei setup --shadow`, answers the interview, then runs
`/wuwei:wuwei-plan` the same day. The plan skill runs `wuwei calibrate --questions`, gets
`[]` and moves on without a second interview.

**Why this priority**: answering the same 14 to 18 questions twice in the first hour is the
F7 wall.

**Independent Test**: `python -m pytest -q tests/test_interview.py -k questions_skip tests/test_setup.py -k shadow_records_posture`.

**Acceptance Scenarios**:

1. **Given** today's `interview.json` answers every question for every configured
   repository, **When** `calibrate --questions` runs, **Then** it exits 0 and prints `[]`.
2. **Given** today's `interview.json` answers `merge` for `acme/widget` only and `phone`,
   with repositories `acme/widget` and `acme/gadget`, **When** `calibrate --questions` runs,
   **Then** the output has no `phone` widget and no `merge` widget for `acme/widget`, still
   has the `merge` widget for `acme/gadget`, and every other question in table order.
3. **Given** the answers were recorded on an earlier day (`days/<earlier>/interview.json`)
   or in an archived day (`.wuwei/archive/<date>/interview.json`) and today has none,
   **When** `calibrate --questions` runs, **Then** those answered questions are left out too.
4. **Given** no recorded answer anywhere, **When** `calibrate --questions` runs, **Then** the
   output is unchanged from today: every question for every repository, in table order.
5. **Given** an `interview.json` that is not JSON, not a JSON object, or a symlink, **When**
   `calibrate --questions` runs, **Then** it exits 2 and the reason names that file's day
   path; nothing is printed on stdout.
6. **Given** `setup --shadow` on a new workspace, **When** setup finishes, **Then** today's
   `interview.json` records `"posture": "Observe"` next to the asked answers, the posture
   question is still not asked (existing test), and the config digest is unchanged in
   effect (`security.posture = "observe"`, `guards.shadow_since` today).
7. **Given** `skills/wuwei-plan/SKILL.md`, **Then** its first-day paragraph runs
   `wuwei calibrate --questions` and says to skip the rest of the block when it prints `[]`.

### User Story 2 - The morning gate is one question (Priority: P1)

On a default morning the planner asks one AskUserQuestion:
`Morning gate (days/<date>/plan.md): Approve today's plan as proposed?` with options
`Approve` (recommended, its description listing what it approves) and `Change something`.
On `Approve` it records the gate. Only on `Change something` (or an Other answer) does it ask
goals, queue, seat policy, CAP, envelope and carry-over one by one.

**Why this priority**: six questions every morning for defaults is the F22 wall.

**Independent Test**: `python -m pytest -q tests/test_docs.py -k one_gate_question tests/test_next.py -k morning_rows tests/test_agents.py`.

**Acceptance Scenarios**:

1. **Given** `skills/wuwei-plan/SKILL.md` step 4, **Then** it names the question
   `Approve today's plan as proposed?` with `Change something` as the other option, and the
   goals, queue, seat policy, CAP, envelope and carry-over questions appear only in the text
   after `Change something`; the phrase `one AskUserQuestion per decision` and
   `Ask separately` are gone.
2. **Given** step 4, **Then** the one question's header is `Goals` when `plan.md` marks the
   goals provisional (the proposed blocks are shown in it, and `Approve` lets the planner run
   `wuwei goals edit --file .wuwei/days/<date>/goals.md`) and `Plan` otherwise.
3. **Given** step 4, **Then** `Approve`'s description lists the goals, the queue ids in order,
   CAP, seat policy, envelope and, when proposed, the carry-over of unfinished prior-day
   items, so step 5 may add `--import-yesterday` on `Approve`.
4. **Given** `charters/planner.md`, **Then** "Morning plan" step 2 states the same one
   question and `Change something` path, and `agents/planner.md` is regenerated from it
   (`agents check` exits 0).
5. **Given** `docs/site/daily.md` section 3 and `docs/site/agent.md` "The day in order"
   step 3, **Then** both describe the one approval question and `Change something`, and
   neither says a question per decision.
6. **Given** a proposed plan and no gate approval, **When** `wuwei next` runs, **Then** the
   `gate` row's step names `Approve today's plan as proposed?` and still cites
   `days/<date>/plan.md`.

### User Story 3 - An eval case covers a default morning (Priority: P2)

**Why this priority**: the issue asks for an eval case; the live suite then also exercises
the plan skill on a default-morning request.

**Independent Test**: `python -m pytest -q tests/test_skill_evals.py tests/test_docs.py -k one_gate_question`.

**Acceptance Scenarios**:

1. **Given** `evals/wuwei-plan-positive-06/prompt.md`, **Then** it is a should-trigger case
   for `wuwei-plan` whose query asks to plan a default morning and approve it with one
   question, with the standard Skill grader, and `test_skill_evals` passes.

### Edge Cases

- A repository answered on an earlier day but not today still counts as answered; a
  repository added later has no answer and is asked.
- An earlier day's answer whose label no longer exists in the table (an upgrade renamed a
  choice) still counts as answered: `--questions` checks only that an answer was recorded.
  Re-asking is the owner's `bin/wuwei calibrate --interview <id>` on a host terminal, as
  today.
- Answers recorded but not yet applied by `bin/wuwei promote` count as answered: re-asking
  would not apply them, and setup's `Optional:` line already names `bin/wuwei promote`.
- `--repo <name>` narrows the repository widgets as before; the answered filter applies on
  top.
- With no configured repository and a repo-scoped question unanswered, `--questions` keeps
  its existing `calibrate.NO_REPOS` refusal (unchanged).
- `Change something` with edits: the planner updates the lead JSON, reruns
  `wuwei plan propose` and asks the one approval question again on the new plan.
- No AskUserQuestion (headless): approval is never inferred from silence (unchanged).
- Voice lines proposed by the lead are not part of `plan.md`; they keep their own question
  with header `Voice` when there are any. A default morning has none.
- Outside a workspace nothing here applies; `calibrate --questions` fails as today.

## Requirements

### Functional Requirements

- **FR-001**: `calibrate --questions` MUST leave out every (question, repository) pair, and
  every workspace question, that any `interview.json` under `.wuwei/days/*/` or
  `.wuwei/archive/*/` records an answer for. Membership only: the recorded value is not
  re-validated.
- **FR-002**: When nothing is left, `calibrate --questions` MUST print `[]` and exit 0.
- **FR-003**: An unreadable, non-object or symlinked `interview.json` MUST make
  `calibrate --questions` exit 2 with a reason naming the file (fail closed).
- **FR-004**: `setup --shadow` MUST record `posture = Observe` with the interview answers it
  records, since the flag answered that question.
- **FR-005**: The plan skill's first-day block MUST skip the interview when
  `calibrate --questions` prints `[]`.
- **FR-006**: The plan skill, the planner charter, `docs/site/daily.md`,
  `docs/site/agent.md` and the `wuwei next` gate row MUST describe the morning gate as one
  question, `Approve today's plan as proposed?`, with `Change something` as the other option;
  the separate questions come only after `Change something`.
- **FR-007**: `docs/site/configuration.md` "Owner interview" MUST say that
  `calibrate --questions` prints only questions with no recorded answer and `[]` when none
  are left.
- **FR-008**: One new eval case `evals/wuwei-plan-positive-06` covers a default morning.

### Key Entities

- `days/<date>/interview.json` (and `archive/<date>/interview.json`): existing per-day answer
  file, `{question id: label or text}` for workspace questions and
  `{question id: {repository: label or text}}` for repository questions. Read, never
  written, by `--questions`.

## Success Criteria

- **SC-001**: After `setup --shadow` answers the interview, `calibrate --questions` the same
  day prints `[]`, so the first plan asks no interview question.
- **SC-002**: A default morning is approved with one owner answer.
- **SC-003**: The full suite passes.

## Assumptions

- The notes name no dry-run workspace; the failure was reproduced in a scratch workspace
  outside the repository with the worktree's CLI.
- "No promoted answer" is read as "no recorded answer". Setup's one digest applies the
  config keys of the answers; the charter and voice effects wait as proposals for
  `bin/wuwei promote`, which setup already names on its `Optional:` line. Requiring a
  promoted charter would re-ask about seven questions on the first day and re-answering
  would promote nothing, which defeats "Ask once" (F7's proposed default).
- Answers are found in every day directory and in archived days, not only today's, so the
  command stays right after day one; the skill still runs it on the first day only.
- `posture` under `--shadow` is recorded as `Observe` in setup (one line in
  `commands/setup.py`), outside the issue's named scope, because without it the recommended
  first-day path would still ask one interview question.
- The approval question is printed by `wuwei plan gate` through the shared widget printer
  (`decision.widget`), like the other owner questions from #359, so the question, header,
  Approve description and approve command come from today's `proposal.json` rather than the
  planner's own wording. Carry-over is the planner's proposal, so it is passed as
  `--import-yesterday`; provisional goals are read from the day's `goals.md`, which
  `plan propose` writes only for them.
- Header `Goals` only when the goals are provisional keeps the planner's goals-record
  permission (`record_gate`) to days whose approval actually showed goals; other days use
  `Plan`.
- The option label is `Approve`; the issue fixes the question text and the other option's
  label only.
- The eval harness (`claude plugin eval`) grades Skill tool use from a prompt with no
  workspace, and `tests/test_skill_evals.py` allows only the Skill grader. The eval case is
  therefore a should-trigger case for a default-morning request; the one-question behaviour
  itself is pinned offline by the skill-text test of US2.
- The `wuwei next` gate row wording (`cli/wuwei/commands/next.py`) is outside the named
  scope; it is changed so the orientation does not tell the session to ask several
  questions.

## Deferred

- Making `bin/wuwei promote` part of setup's digest so charter answers apply on day one.
