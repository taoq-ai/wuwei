# Implementation Plan: one approval at the morning gate, and no second interview on the first day

**Branch**: `365-one-gate-question` | **Spec**: `specs/365-one-gate-question/spec.md`

## Summary

One code change at the shared spot, one line in setup, then text:

1. `interview.widgets` (`cli/wuwei/interview.py:447-454`), the only producer of
   `calibrate --questions`, drops every (question, repository) pair a recorded
   `interview.json` already answers. A new private helper `_recorded(root)` in the same
   module reads the answer files.
2. `commands/setup.py:286-287` records `posture = Observe` when `--shadow` skipped that
   question, so the first day's `--questions` really is `[]`.
3. Text: plan skill step 4 and 5, planner charter (and the regenerated `agents/planner.md`),
   `daily.md`, `agent.md`, `configuration.md`, the `wuwei next` gate row, one eval case.

## Technical Context

Python 3.11+, stdlib only (`json`). Tests: pytest, in process. Reuse the `offline` fixture,
`main`, `DAY` (`.wuwei/days/2026-10-01`, two repositories `acme/widget` and `acme/gadget`)
and `interview()` helpers of `tests/test_interview.py`; the `project`, `host`, `terminal`,
`run_setup`, `Confirm` and `DAY` (`.wuwei/days/2026-10-03`) helpers of `tests/test_setup.py`;
`ROOT` and `SITE` in `tests/test_docs.py`; `calibrated`, `planned`, `row` in
`tests/test_next.py`. No subprocess, no network, no terminal.

## Constitution Check

- I stdlib only: yes, `json` only.
- II exits: `calibrate --questions` keeps 0 printed, 2 could not run. A broken or
  symlinked answer file is exit 2 with the file named (the existing
  `except (OSError, ValueError)` in `commands/calibrate.py:117-119` prints it).
- III one behaviour, one function: which questions are still open is decided once, in
  `interview.widgets`; the skill only reacts to `[]`.
- IV test first: every pair in `tasks.md`.
- V ponytail: no new command, no new widget printer, no new state key, file or event. The
  gate question lives in the skill text; the guards already accept it. No re-validation of
  old answers (membership only).
- VII security: `--questions` stays read-only. Symlinked answer files are refused as
  `interview.load` already refuses today's. The `Goals` header (which lets the planner
  record goals through `record_gate` and `protect_state._gate_edits`) is used only when the
  approval question shows provisional goals; every other morning uses `Plan`, so the
  planner gains no goals-record permission it does not have today.

## Design

### 1. `cli/wuwei/interview.py`: `_recorded` and `widgets`

Add above `widgets`:

```python
def _recorded(root):
    """(question id, repository or None) for every answer any day's or archived day's
    interview.json records; membership only, so an answer from an older table still counts."""
    found = set()
    for base in ('days', 'archive'):
        for path in sorted((root / '.wuwei' / base).glob('*/interview.json')):
            name = path.relative_to(root / '.wuwei').as_posix()
            if path.is_symlink():
                raise ValueError(f'{name} must not be a symlink')
            try:
                answers = json.loads(path.read_text(encoding='utf-8'))
            except ValueError as exc:  # JSONDecodeError and UnicodeDecodeError
                raise ValueError(f'{name}: {exc}') from None
            if not isinstance(answers, dict):
                raise ValueError(f'{name}: expected an object')
            for qid, value in answers.items():
                found |= {(qid, repo) for repo in value} if isinstance(value, dict) else {(qid, None)}
    return found
```

In `widgets`, compute `done = _recorded(root)` once and add
`if (row['id'], repo) not in done` to the comprehension over `_selected([], repos)`. Update
its docstring: "The unanswered questions as AskUserQuestion widgets for the morning gate."
Output order and widget shape are unchanged. `commands/calibrate.py` needs no change: it
already prints `json.dumps(widgets)` (so `[]`) and maps `ValueError` to exit 2.

Do not change `load`, `record`, `settings`, `ask` or `parse`: `calibrate --interview <id>`
on a host terminal stays the way to answer a question again.

### 2. `cli/wuwei/commands/setup.py:286-287`

```python
        picked = interview.ask(
            [row['id'] for row in interview.QUESTIONS if not (args.shadow and row['id'] == 'posture')], names)
        if args.shadow:
            picked['posture'] = 'Observe'  # the flag answered it (#365)
        interview.record(root, staged_cfg, picked)
```

Effect on the digest: `interview.settings` yields `security.posture = "observe"` (and
`guards.shadow_since` when the staged config has none), which `config.proposal` already
lets win over the identical `extra` rows (`commands/config.py:160-164`). The config result
is the same; the summary gains one `- posture: Observe -> ...` line.

### 3. `skills/wuwei-plan/SKILL.md` step 4 and step 5

Replace step 4 with (keep the numbering; wording may be tightened, the named phrases must
stay):

> 4. Run the morning gate as one question. Ask it with AskUserQuestion: question
> `Morning gate (days/<date>/plan.md): Approve today's plan as proposed?`, header `Goals`
> when `plan.md` marks the goals provisional (show the proposed goal blocks in the question)
> and `Plan` otherwise, and two options: `Approve`, whose description lists what it approves
> (the goals, the queue ids in order, CAP, seat policy, envelope and, when proposed, the
> carry-over of unfinished prior-day items), and `Change something`. On `Approve` with
> provisional goals, record them with `wuwei goals edit --file .wuwei/days/<date>/goals.md`;
> under the strict posture the hook refuses and prints the command, so show that line to
> the owner for a host terminal. Only on `Change something` or an Other answer, ask the
> separate questions, one AskUserQuestion each, each starting with `Morning gate` and citing
> `days/<date>/plan.md`, recommended choice first: goals (header `Goals`), queue, seat
> policy, CAP, envelope and carry-over as needed. Ask voice lines the lead proposed with
> header `Voice` and record approved ones with `wuwei voice edit --file <draft>`; only the
> `Goals` and `Voice` headers let you record those answers. If the owner edits the
> proposal, update the lead JSON, rerun `wuwei plan propose` and ask the one approval
> question again. Never ask the owner to write a record by hand. Do not infer approval from
> silence. On the first day (no earlier day directory under `.wuwei/days/`), after the gate,
> run `wuwei calibrate --questions`. It prints only questions no recorded answer covers;
> when it prints `[]` (setup already asked them), skip the rest of this paragraph.
> Otherwise ask the printed widgets with AskUserQuestion, at most four per call, passing
> `question`, `header`, `options` and `multiSelect` unchanged, record each answer with the
> widget's `record` command (`wuwei calibrate --answer`), then tell the owner to run
> `bin/wuwei config promote` in a host terminal and `bin/wuwei promote`.

Step 5 first sentence becomes: "After the owner approves the plan (`Approve`, on the
original or the re-proposed plan), call `wuwei plan approve --items <approved IDs>
--goals-confirmed`, adding `--import-yesterday` only when the approved plan included the
carry-over." The rest of step 5 is unchanged.

Phrases existing tests pin and that must stay in the skill: `calibrate --questions`,
`calibrate --answer`, `.wuwei/charters/planner.md`, `AskUserQuestion`, `record`,
`decision route`, `--widget`, `Seats never ask the owner`, `wuwei mcp check --widget`,
`wuwei_board`, `humanizer`, `decision show`, `Writing for a person`, `` `wuwei next` `` in
the opening paragraph, no `$(`.

### 4. `charters/planner.md` "Morning plan" step 2, and `agents/planner.md`

Replace the sentence "Seat policy is set at the morning gate: ..." with: "The morning gate
is one question, `Approve today's plan as proposed?`, with `Change something` as the other
option; ask goals, queue, seat policy, CAP, envelope and carry-over separately only after
`Change something`. Seat policy is set at that gate: record model and runtime for each role
in day state, along with the owner's approved goals, queue and CAP." Keep "Do not dispatch
before that gate." and the `version: 1.0.0` frontmatter. Then run `bin/wuwei agents build`
from the repository root (no workspace there, so it regenerates the plugin's `agents/`);
only `agents/planner.md` should change.

### 5. Docs

- `docs/site/daily.md` section 3, the sentence at lines 202-204 ("It then asks you one
  `Morning gate` question per decision: goals, queue, seat policy, CAP, envelope and
  carry-over."): it now asks one `Morning gate` question, `Approve today's plan as
  proposed?`; `Change something` brings the separate questions on goals, queue,
  [seat](concepts.html#seat) policy, [CAP](concepts.html#cap),
  [envelope](concepts.html#envelope) and [carry-over](concepts.html#carry). Keep those four
  links. In the next sentence, "the goals question shows the blocks" becomes "the approval
  question shows the blocks". Keep the rest of the section.
- `docs/site/agent.md:45`: "3. Morning gate: one AskUserQuestion, `Morning gate
  (days/<date>/plan.md): Approve today's plan as proposed?`; the separate questions only
  after `Change something`." Keep line 46.
- `docs/site/configuration.md:291`, the sentence "On the first day the plan skill asks the
  same questions ...": the plan skill runs `bin/wuwei calibrate --questions` on the first
  day, which prints only the questions no recorded `interview.json` answers (`[]` after
  setup) as `Morning gate` widgets, and records each answer with
  `bin/wuwei calibrate --answer <id>=<choice or text>`. Keep the phrases `--questions`,
  `--answer`, `interview.json` (pinned by `test_owner_interview_is_documented_next_to_calibration`).

### 6. `cli/wuwei/commands/next.py:57-59`, the `gate` row

Step text: `Morning gate open: ask the owner the one Morning gate question, "Approve today's
plan as proposed?", citing days/<date>/plan.md, and approve only on the owner's answer.`
State `gate` and command `/wuwei:wuwei-plan` unchanged. It stays well inside the 4096-byte
SessionStart budget (`tests/test_next.py::test_issue_acceptance_session_start_budget`).

### 7. `evals/wuwei-plan-positive-06`

`prompt.md`:

```
---
name: wuwei-plan-positive-06
tags: [should-trigger, wuwei-plan]
---

Plan today on the proposed defaults. I only want to approve the day once, not answer a separate question for every setting.
```

`graders/skill.md`: the exact grader of `wuwei-plan-positive-01` with `name:
wuwei-plan-positive-06-skill`.

## What must not change

- `guards/decision.py` (`gate_question`, `record_gate`, `check_question`) and
  `guards/protect_state.py`: they already accept the one question.
- `plan.propose`, `plan.approve` and `plan.md` format; `wuwei plan approve` flags.
- `interview.load`, `interview.record`, `QUESTIONS` and option texts (the #366 docs issue
  owns option wording), the `calibrate --interview` and `--answer` paths.
- `decision.widget`, `decision.gate`.
- `tests/test_skill_evals.py` contract (still one Skill grader per case).

## Risks

- `tests/test_interview.py::test_widgets_come_from_the_table_and_pass_the_question_guard`
  runs with no recorded answer, so it still expects every widget; it must keep passing.
- A day directory left by an earlier test fixture with an `interview.json` would now hide
  questions; the new tests write their own files under the fixture's `tmp_path`.
- `test_setup.py` asserts on digest text by membership (`'+posture = "observe"' in out`),
  so the extra interview summary line does not break it; rerun the whole file.
