# Implementation Plan: The scripted day runs every call through the hooks with the real launcher

**Branch**: `212-e2e-through-hooks` | **Date**: 2026-09-30 | **Spec**: `spec.md`

## Summary

Tests only. The shared spot is the `Day` helper in `tests/fakes/day.py`: every test that
uses `Day.run` gets the PreToolUse check for free. Add the missing joints to the scripted
day in `tests/test_e2e_day.py`, one short solo-owner test, and one fault-injection test that
reintroduces each bug and expects the day to fail naming the step.

## Technical Context

Python 3.11+, pytest (dev only), in process. No production code, no new files, no new
dependencies. The day must stay deterministic and fast (under 30 s for the file; about 2 s
today). Probes during specification confirmed every step below works on main (all current
day calls pass the hook with exit 0; solo raise, continuation, owner decision and dead
watch behave as the spec states).

## Constitution Check

- I stdlib only: no runtime change. Pass.
- II fail closed: no guard changes. Pass.
- III one behaviour one test: reuses `wuwei hook` and existing CLI commands; nothing
  reimplemented. Pass.
- IV test first: the new day steps are written first and must fail on a tree with the bug
  (fault-injection test) before the helper change makes the rest green. Pass.
- V ponytail: one helper change, one kwarg on the fake runtime, one config switch. Pass.

## Changes

### `tests/fakes/day.py`

1. Module constant `LAUNCHER = Path(__file__).resolve().parents[2] / 'bin/wuwei'` (the
   plugin launcher that `wuwei.shell._launcher` recognises). Import `shlex`.
2. Split `Day.run` into a private in-process runner and the planner wrapper:
   - `_main(self, args, expected, stdin, step)`: the current body of `run`; its assertion
     message is `(step, code, out, err)`.
   - `run(self, *args, expected=0, stdin='')`: `self.bash(args)` (PreToolUse must exit 0),
     then `self._main(args, expected, stdin, args)`.
   - `owner(self, *args, expected=0)`: `self.bash(args, expected=2)` (agent tools are
     refused the owner action), then `self._main(args, expected, '', args)`.
   - `bash(self, args, expected=0)`: `self.hook('PreToolUse', expected, tool_name='Bash',
     tool_input={'command': shlex.join([str(LAUNCHER), *map(str, args)])})`.
   - `hook(self, event, expected=0, **fields)`: builds the same payload as today and calls
     `self._main(('hook', event), expected, json.dumps(payload), ('hook', event, fields))`
     so a failing hook names its event and fields (Bash command, `stop_hook_active`).
   `hook` never goes through `run`, so there is no recursion.
3. `Runtime.dispatch(..., *, root=None, resume=None)`: when `resume` is set, add
   `'resume': resume` to the Agent `tool_input`. Everything else unchanged.
4. `Runtime.continue_job(self, job, feedback, *, root=None)`: read the stopped seat
   `self.day.data['seats'][job['id']]` and return `self.dispatch(seat['role'],
   self.day.root / seat['brief'], self.day.repo, False, root=root, resume=job['id'])`
   (the fake's SubagentStop records `agent_id = path.stem`, which is the seat name).
5. `Day.gate`: when `round_name == 'delta'`, continue the initial seat instead of writing a
   new brief: `name = f'{role}-initial'`, set `self.runtime.verdict`, run
   `self.run('runtime', 'continue', json.dumps({'id': name}), 'Check the delta')`, then
   `dispatch receive A <role> <name> --round delta` as today.
6. `Day.__init__(self, root, monkeypatch, solo=False)`: with `solo`, the `[shepherd]`
   block is `min_reviewers = 0` plus `[adapters] chat = "none"` (no `review_channel`,
   `lead_login` or `authors`), and `vcs.results['authorship']` is
   `[{'email': 'builder@example.test', 'commits': 2}]` (the owner's own email, resolved
   through the fake `author_login` to `builder`, the PR author, so excluded).

### `tests/test_e2e_day.py`

`test_scripted_day` additions (everything else unchanged):

- The delta line stays `day.gate('quality', 'PASS', round_name='delta')`; it now continues
  `quality-initial`. Assert `'quality-delta' not in day.data['seats']`. The asserted
  `gate.received` list keeps `('quality', 'delta', 'PASS')`.
- After `pr ping` and before the first `close`:
  - Dead watch: `state.append_event('watch: clock', {}, day.root)`, then
    `day.patch.setenv('WUWEI_NOW', '2026-09-29T12:30:00Z')` (past the 1200 s default), assert
    `json.loads(day.run('nudges'))` has one row with source `watch: health` and tier
    `page`; append a fresh clock line and assert `nudges` has no `watch: health` row.
  - Owner decision: write `decisions/D-1.md` from `test_decision.VALID` with
    `Reversibility: one-way` and `Decided-by: owner`; `day.run('decision', 'route', 'D-1')`.
- First `close` (expected 1): assert `'D-1: pending owner decision'` in its output. After
  the first Stop block, add `day.hook('Stop', stop_hook_active=True)` (exit 0, prints
  nothing).
- After `close --check retro`: `day.patch.setattr('wuwei.integrity._host_confirm', lambda
  value, **kwargs: True)` and `day.owner('decision', 'outcome', 'D-1', 'A')`; the second
  `close` (expected 1) output no longer contains `D-1`.
- After `report`: assert `'- D-1: A'` in `report.md`.

New tests:

- `test_solo_owner_raise(tmp_path, monkeypatch)`: `Day(..., solo=True)`; plan, approve,
  `plan session planner`, build, three PASS gates, `next() == {'action': 'raise', 'notes':
  []}`, `raise_pr()` exit 0; assert `pr_reviewers[ref] == []`, one `create_pr`, no
  `request_reviewers`, `day.chat.calls == []`.
- `test_day_names_the_reintroduced_bug(day, monkeypatch, mutation, match)` parametrized:
  - `launcher`: `monkeypatch.setattr(deploy, 'GUARDS', [*deploy.GUARDS, Guard('PreToolUse',
    'Bash', refuse)])` where `refuse` returns `(2, 'opaque script command')` when
    `str(LAUNCHER)` is in the command, else `(0, '')`; expect `AssertionError` matching
    `wuwei rank` (the first planner call, as the joined launcher command).
  - `close_trap`: `monkeypatch.setattr(stop, 'GUARDS', [Guard('Stop', None, lambda p:
    stop.check({**p, 'stop_hook_active': False}))])`; expect `AssertionError` matching
    `'stop_hook_active': True`.
  Each case runs `test_scripted_day(day)` inside `pytest.raises`.

## Reused, not rebuilt

- `wuwei hook` (`cli/wuwei/commands/hook.py`) through `Day.hook` for every PreToolUse.
- `test_decision.VALID` for the decision record; `state.append_event` for clock lines;
  `wuwei.guards.Guard` and module `GUARDS` lists for fault injection (as
  `tests/test_guard_mutation.py` does).
- `runtime continue` CLI and the agent-launch continuation rule from #208.

## Must not change

- Any file under `cli/`, `adapters/`, `hooks/`, `bin/`, `skills/` or `docs/`.
- The fake git refusing `git var`, the network ban, the port fakes and the recorded
  integrity setup in `Day.__init__`.
- Existing assertions in `test_scripted_day` (transition list, gate list, event order, usage
  and retro counts, metrics, time budget) and the other two tests' behaviour.
- `_pipeline/release.sh` (outside the repository).

## Risks

- Moving `WUWEI_NOW` to 12:30 for the rest of the day: later steps compare against the
  12:00 merge time and the brief/seat times; probes showed no effect, but if a step
  depends on it, append the clock lines at 12:00 and set 12:30 only around the first
  `nudges`, then set it back to 12:00 before the fresh clock line.
