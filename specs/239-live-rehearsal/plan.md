# Implementation Plan: The delivery journey is the release criterion

**Branch**: `239-live-rehearsal` | **Date**: 2026-09-30 | **Spec**: `specs/239-live-rehearsal/spec.md`

## Summary

Two parts. First, the product owns the last phase move the scripted day still made by
hand: `dispatch.receive` moves `gate` to `fix` in the write that completes the initial
round with a FIX, so the fixture's `day.transition('fix')` becomes an assertion and the
planner skill stops telling the planner to transition. Second, the existing opt-in runner
`scripts/headless_e2e.py` gains a `--rehearsal` mode that reuses its signed build, scratch
HOME, observer shim, `check_result` and `validate` style to drive one real item through a
test repository on the code host, and prints interventions, elapsed time, cost and
refusals next to a three-state verdict. Skips become unmeasured (exit 2) in both modes.
No new module, state key, event kind, configuration key or workflow.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime; the scripts are dev tooling
**Testing**: pytest in process. Existing fixtures: `tests/test_dispatch.py` `root` and
`record`; `tests/fakes/day.py` `Day`; `tests/test_headless_e2e.py` `load`, `evidence`;
`tests/test_docs.py` `SITE`
**Constraints**: three-state exits (0 pass, 1 fail, 2 unmeasured); no network in tests;
no absolute local paths in the repository; no emojis or em-dashes

## Constitution Check

- One behaviour, one function: the gate-to-fix rule lives in `dispatch.receive`, next to
  the verdict it depends on; phase legality stays `state._move` / `_check_transition`.
- Reuse: `state._move` (as `record_pr` does), `dispatch._record`, `dispatch.ROLES`;
  in the runner `prepare`, `check_result`, `checked`, `adapter.run`,
  `adapter.claude_command`, the observer log and the `validate` pattern.
- Test first: tasks.md orders every test before its change.
- No forgeable trust: the phase moves inside the `gate.received` write, a reserved event
  produced only by `wuwei dispatch receive` (`commands/event.py` `EVENT_PRODUCERS`).
  The rehearsal's measurements are a test oracle, never a product trust record.
- Fail closed: every missing precondition, error result or unreadable evidence in the
  rehearsal is exit 2 with the reason.

## Changes by file

### Part 1: the product moves `gate` to `fix`

#### `cli/wuwei/dispatch.py`

- `receive`, inside the `update(fresh)` closure, after
  `fresh['gate_verdicts'][key] = value`: when `round_name == 'initial'`, read the three
  initial records from `fresh` with `_record(fresh, item, role, 'initial')` for `ROLES`;
  if all are present, any verdict is `FIX` and none is `PARK` or `ESCALATE`, call
  `state._move(fresh, item, 'fix')`. `_write_state` then adds
  `phase_changes: {item: 'fix'}` to the `gate.received` event by itself.
- Must not change: `next_step` (its `gate` branch still returns `fix`, which stays correct
  for a partially written day), the receive checks, the `kind` and `payload` of the
  write, the scanner branch, `discovery`, `tracker_call`.

#### `skills/wuwei-plan/SKILL.md` (line 48)

- Replace "For `action: fix`, transition the item to `fix`, give the builder" with "For
  `action: fix` (the item is already in `fix`; `dispatch receive` moved it when the last
  initial verdict arrived), give the builder". Nothing else in the paragraph changes.

#### `docs/site/reference.md` (line 95, "Automatic phases" row)

- Replace "`gate` to `fix` stays a planner transition." with "`dispatch receive` moves
  `gate` to `fix` when the last initial verdict arrives and one of them is FIX (none PARK
  or ESCALATE)."

#### `tests/test_dispatch.py`

- Delete the redundant `state.transition('A', 'fix', root)` that directly follows the
  third initial `record(...)` in `test_fix_pass_then_only_quality_delta` (line 74),
  `test_blocking_delta_escalates_and_bad_verdict_is_unmeasured` (92),
  `test_delta_nonblocking_residual_becomes_review_note` (140),
  `test_delta_refuses_role_that_already_passed` (158), and the two at lines 325 and 514
  (`test_agent_surface_delta_rescans_and_keeps_manual_findings`,
  `test_continued_sentinel_delta_head_matches_seat_head`); replace each with
  `assert state.read_state(root)['items']['A']['phase'] == 'fix'`. Keep the later
  `state.transition('A', 'fix', root)` calls from `delta` (lines 79 and 147): they
  deliberately open a second fix round to test `escalate`.

#### `tests/test_e2e_day.py` and `tests/fakes/day.py`

- `tests/test_e2e_day.py:34`: `day.transition('fix')` becomes
  `assert day.data['items']['A']['phase'] == 'fix'`.
- `tests/fakes/day.py`: delete `Day.transition`. In `Day.gate`, keep the stdout of
  `runtime dispatch` for an initial round in a `self.jobs` dict keyed by seat name, and for
  the delta pass `self.jobs[name]` to `runtime continue` instead of
  `json.dumps({'id': name})`.

### Part 2: the rehearsal

#### `scripts/headless_adapter.py`

- `claude_command(plugin, *, turns=48, budget=3, resume=None)`: the two limit values
  come from the parameters (as strings); when `resume` is set append
  `['--resume', resume]`. Default output is byte-identical to today.

#### `scripts/headless_e2e.py`

- `check_result(result)` returns the parsed result dict (today it returns nothing), so
  callers read `total_cost_usd` and `session_id`.
- `main`: add `--rehearsal`. Credential line: without `ANTHROPIC_API_KEY` and without
  `--local-login`, print `headless e2e unmeasured: ANTHROPIC_API_KEY is not set` (default
  mode) and return 2. In rehearsal mode, call `rehearse(local_login=...)` and let it do its
  own precondition checks and printing.
- New constant `REHEARSAL = {'first': (turns, usd, seconds), 'second': (...)}` with initial
  values `(150, 15, 1800)` and `(40, 5, 600)`, and a `# ponytail:` comment that these are
  the owner's calibration knob.
- New `preconditions(local_login, tty=...)` returning the first missing reason or `None`,
  in this order: Claude credential (`ANTHROPIC_API_KEY` or `--local-login`),
  `WUWEI_REHEARSAL_REPO` (must match `owner/name`), `GH_TOKEN`, host terminal
  (`open('/dev/tty')` succeeds; injectable for tests). No subprocess before this returns
  `None`.
- `prepare(scratch, *, local_login=False, repo=None, url=None)`. The shared part (scratch
  HOME, signed build through `scripts/build-release.py`, observer shim, `wuwei init`) is
  unchanged. When `repo` is set:
  - keep `GH_TOKEN` in `env`; do not set `WUWEI_NOW` (the merge soak and host timestamps
    need the real clock); write `home/.gitconfig` with a `gh auth git-credential` helper
    for `https://github.com` and a user name and email, and point `GIT_CONFIG_GLOBAL` at it
    (the Git adapter strips `GIT_CONFIG*` and then reads the same file from `HOME`);
  - read the owner's login with `gh api user --jq .login` through `checked`;
  - `git clone` `url` (default `https://github.com/<repo>.git`, overridable for offline
    tests with a local bare repository) into `root / 'repo'` and keep `origin`; read the
    default branch from `refs/remotes/origin/HEAD`;
  - write a `config.toml` with `[owner] handles = [<login>]`, one `[[repos]]` entry
    (`name = repo`, `path = "repo"`, the default branch, `merge_deploys = false`,
    `[repos.merge] auto = true`, `soak_minutes = 0`, and one fast check), `[brief] remote =
    "origin"`, `[shepherd] min_reviewers = 0`, `[host] free_memory_mb = 0`,
    `[adapters] code_host = "github"` and `chat = "none"`;
  - the fast check requires the line `checked: <token>` in `REHEARSAL.md` and, when it is
    missing, prints `REHEARSAL.md must contain the line: checked: <token>` and exits 1
    (`secrets.token_hex(4)` per run). The builder brief never names it, so the first
    iteration fails and the loop's `continue` feedback carries the line;
  - goals and a one-candidate proposal (item `A`, SLICE, no flags) as the default fixture
    writes them; no `park.md`.
  Otherwise the existing fixture tail runs unchanged. Return `root, plugin, env` as today.
- New `rehearsal_prompt(plugin, stage, pr=None)` for the two sessions, in the style of
  `prompt`:
  - `first`: invoke `wuwei:wuwei-plan`; the fixture owner approves the supplied proposal;
    `mcp check`, `plan propose`, `plan approve --items A --goals-confirmed`;
    `worktree add A`; builder brief: "Add REHEARSAL.md with a line `status: draft`,
    commit it on the item branch" (it must not mention the check line); run the `build
    next` step loop exactly as the skill says; gates through `dispatch next`, with the
    quality brief carrying the rehearsal rule "return FIX with one `blocks: yes` finding if
    REHEARSAL.md lacks the line `reviewed: quality`, else PASS"; follow `action: fix` and
    the delta exactly as the skill says; push the item branch to `origin` and `pr raise`
    with `--item A`; write `D-1` (Decided-by: owner, one-way: "merge the rehearsal PR
    today or defer") from `decision template`, `decision route D-1`, and end the turn,
    ending again if the Stop hook blocks for the pending decision. No `state transition`,
    `state set` or direct file edits under `.wuwei/`.
  - `second` (resumed session, after the owner answered): `merge <pr>`; `pr state` until it
    reports `merged`; `report`; `retro`; `close --check retro`; `close`.
- New `owner_decision(root, plugin, env)`: read the `Recommendation:` option from today's
  `decisions/D-1.md`, print one line telling the operator to confirm on this terminal, and
  run `bin/wuwei decision outcome D-1 <option>` through `adapter.run(...,
  own_group=False)` so the child keeps the controlling terminal for `_host_confirm`. A
  non-zero exit is a finding. Record it as the planned intervention
  `decision outcome D-1 (planned, host terminal)`.
- New `rehearsal_findings(data, events, hooks)` in the style of `validate`, one finding
  per missing step: a `build next A` result with `action: continue`; an initial FIX and a
  delta PASS for the same role in `gate.received`; a `pr.raised` event and one entry in
  `raised_prs`; a `decision.decided` event for `D-1`; a `merge.auto` event; item `A`
  phase `merged`; the `phase_changes` sequence for `A` equals
  `['implement', 'gate', 'fix', 'delta', 'raised', 'merged']`; `close_requested`; every
  seat `stopped`. It also adds `manual repair: <args>` for each observer row whose `args`
  start with `state transition`, `state set` or `state recover`.
- New `measure(events, hooks, results, planned)` (as built: `rehearse` computes
  `elapsed_seconds` itself) returning the result fields:
  `interventions` = planned owner actions plus the manual repairs above; `refusals` =
  the `reason` of every `hook.refusal` event plus `wuwei <args[:2]>: exit 2` for observer
  `cli` rows that exited 2 (hook rows excluded, they are covered by the events);
  `cost_usd` = sum of `total_cost_usd` over the session results, `None` if any lacks it;
  `elapsed_seconds` = `round(time.monotonic() - started)`.
- New `rehearse(*, local_login=False)`: start the clock; `preconditions`; if missing,
  print and return 2 via `report`. Otherwise in a `tempfile.TemporaryDirectory`: `prepare`
  with the repo, run session one with `adapter.claude_command(plugin, turns=..,
  budget=.., )` and the `first` bounds, `check_result`; `owner_decision`; run session two
  with `resume=<session_id of the first result>` and the `second` bounds, `check_result`;
  read state and events from the single directory under `.wuwei/days/` and the observer
  log; `rehearsal_findings`; `measure`; `report`. Errors listed in `main`'s `except` are
  unmeasured (exit 2) with the reason, and still print the JSON line with what was
  measured so far.
- New `report(verdict, fields)`: print `rehearsal <verdict>: interventions N, elapsed Ns,
  cost USD X (or cost unmeasured), refusals N`, then each finding, then the JSON object on
  the last line (`sort_keys=True`). Return 0, 1 or 2 for pass, fail, unmeasured.

Must not change in the runner: the default-mode prompt, `validate`, the observer
(`headless_adapter.observe`), `adapter.run` semantics, the scratch HOME isolation, the
default `claude_command` argv, and `.github/workflows/tests.yml`.

#### `docs/site/rehearsal.md` (new) and `docs/site/index.md`

- Page with the site front matter. Sections: when to run (before each release; the
  scripted day runs on every PR); prerequisites (Python 3.11+, Git, `ssh-keygen`, Claude
  Code, `gh`); the test repository (disposable, owned by the operator, no required reviews
  or checks, merging deploys nothing, a default branch with one commit); variables
  (`ANTHROPIC_API_KEY` or `--local-login`, `WUWEI_REHEARSAL_REPO=owner/name`, `GH_TOKEN`
  scoped to that repository only, and why it reaches the session); the command
  `python3 scripts/headless_e2e.py --rehearsal`; the digest prompt for `D-1` and how to
  answer it; the bounds; the output (verdict line, findings, last JSON line and its
  fields); exit codes 0 pass, 1 fail, 2 unmeasured; what stays on the test repository.
- `index.md`: one bullet `[Release rehearsal](rehearsal.html)`.

#### `docs/headless-e2e.md`

- "Exit 0 means measured success or an explicitly printed credential skip." becomes exit 0
  measured success only, and a missing credential joins the exit 2 list. Add one line
  pointing at `docs/site/rehearsal.md` for the PR, fix round and merge journey.

## Result contract (for `_pipeline/release.sh`)

The last stdout line of `--rehearsal` is one JSON object:
`{"cost_usd": 4.21 | null, "elapsed_seconds": 1260, "findings": [...], "interventions":
[...], "pr": "owner/name#12" | null, "refusals": [...], "verdict": "pass" | "fail" |
"unmeasured"}`. Exit code matches the verdict (0, 1, 2).

## Deferred

- Returning launch or resume actions for gates from `dispatch next` (review point 1,
  "canonical launch/resume instructions") is a separate change.
- Keeping `GH_TOKEN` out of seat environments (review point 2).
- A restart-and-continue rehearsal beyond the resumed second session.
