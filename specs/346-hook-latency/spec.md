# Feature Specification: Hook, status line and heartbeat under their latency budgets

**Feature Branch**: `346-hook-latency`
**Created**: 2026-10-03
**Status**: Ready for implementation
**Input**: Issue #346, perf(hooks): bring the hook, status line and heartbeat under their
latency budgets on the CI runner without touching the budgets. Design sections 2 (language
decision) and 10.6 (latency budget). Owner instruction, 2026-10-03: "I want you to reduce
the latency, not change the pipeline or loosen the tests up."

## Hard constraint

Reduce latency in the code. Do not change `.github/workflows/tests.yml`, any budget, any
existing test body, any run count, or `bin/wuwei`. New tests are allowed. Every existing
test passes unchanged.

## Root cause (reproduced read-only in this worktree)

Measured on the owner's machine class (M-series, 10 CPUs, host load 4.5 to 7, Python 3.12
venv, `python3 -I` floor 12 to 14 ms) with `WUWEI_BENCH=1 python -m pytest -q
tests/test_hooks.py -k latency`, `-X importtime` and cProfile through the launcher's own
`python3 -I -P -c runpy` line. Method and numbers are in `research.md`.

Most of a hook's CPU above the interpreter floor is module import and module-level regex
compilation the call never uses:

1. `cli/wuwei/__main__.py:3-11` imports `argparse`, `json`, `pkgutil` and
   `wuwei.workspace` for every call, and `_main` (lines 27, 37-40, 42-46) builds the
   argparse parser, reads `.claude-plugin/plugin.json` and lists the 57 command modules
   with `pkgutil.iter_modules` before it dispatches `hook`.
2. `cli/wuwei/env.py:9` imports `wuwei.workspace` at module level, used only by
   `initialize` (line 92). `wuwei.workspace` (`cli/wuwei/workspace.py:3-10`) imports
   `tomllib` (which imports `typing`), `datetime`, `tempfile` and `copy` at module level.
3. `cli/wuwei/redact.py:3-6` imports `hashlib` and `urllib.parse` and compiles five
   patterns at import (lines 51-71), 3.4 ms of regex compilation, although the CLI output
   wrapper `redact.Output` needs none of it.
4. `pkgutil.iter_modules` imports `inspect` (with `ast`, `dis`, `tokenize`, `linecache`)
   and, through its `singledispatch` registration, `typing`: 3.4 ms plus 1.5 ms. Two
   callers pay it on every call: `guards.discover` (`cli/wuwei/guards/__init__.py:88`) for
   every hook that reaches a workspace, and `__main__._main` for every other command,
   `status --line` included.
5. `cli/wuwei/registry.py:3,108` uses `@dataclass(frozen=True)` for `Result`; importing
   `dataclasses` imports `inspect` too. `registry` loads on every config read
   (`workspace.load_config`, `cli/wuwei/workspace.py:491`).
6. `cli/wuwei/guards/__init__.py:8,67` imports `typing` for `Guard(NamedTuple)` on every
   hook, inside a workspace or not.
7. `workspace.scope` (`cli/wuwei/workspace.py:256-257`) imports `registry` before it
   knows it needs it; `load_config` (line 484) imports `wuwei.decision` (with `outward`,
   `state`, `verdict`, `hashlib`) to validate `decisions.cruise.levels` even when no level
   is set.
8. `cli/wuwei/outward.py:26` compiles ten style-tell patterns at import (2.1 ms); only
   `tells()` uses them. `cli/wuwei/security.py:6` imports `secrets` (with `random`,
   `base64`, `hmac`) for `initialize` only; `cli/wuwei/verdict.py:3` imports `hashlib` for
   one function (line 160).

`status --line` additionally decodes the whole day: `commands/status.py:44` runs
`json.loads` on every line of `events.jsonl` and line 51 parses every timestamp, even for
the silent kinds the scan then drops at its `SILENT` check. 10,000 events cost about 10 ms
of the 51 ms.

The heartbeat tick's wall time is its slowest launcher child: the `refused` probe
(`git push --force origin main`) takes about 95 ms median against 45 to 50 ms for the
others, because `guards/commit_push.check` reads the Git context through the VCS adapter
(`context()` at `cli/wuwei/guards/commit_push.py:398`) before it returns the force-push
refusal (line 413). The in-process probes take 12 to 17 ms in parallel and are not on the
critical path. On the 4-CPU runner, four launcher children plus Git subprocesses compete
for CPU, so every millisecond cut from a child's start shortens the tick.

Prototype of fixes 1 to 8 plus the status prefilter, in a scratch copy (same machine, same
load band): `PreToolUse` CPU p95 43.9 to 30.6 ms, `PostToolUse` 38.3 to 32.9 ms,
`status --line` 51.2 to 40.9 ms, a hook outside any workspace 44 to 60 down to 20 to 30 ms,
heartbeat tick wall 135.5 to 122.5 ms (load 7). That prototype also replaced
`pkgutil.iter_modules` in `discover()` with `os.listdir`, which two existing tests forbid
(see Assumptions); with the listing kept, alternating runs at load 9 gave `PreToolUse` in
a workspace 67 to 57 ms and outside one 57 to 32 ms. The suite passes on the prototype
apart from tests that need the repository's own Git history. The launcher shell (`sh` plus `dirname`,
about 4 ms) and `pathlib` (about 3 ms, imports `urllib.parse` itself) are floors this issue
cannot move: `tests/test_cli.py` pins the launcher's text and its `dirname` dependency.

## User Scenarios & Testing

### User Story 1 - A hook pays only for what it uses (Priority: P1)

Every Claude Code tool call on the owner's machine runs `wuwei hook`, inside a WUWEI
workspace or not. Outside one (#323) the hook does nothing, so it must cost little more
than the interpreter start; inside one it imports only the modules the reached guards use.

**Independent Test**: run `main(['hook', 'PreToolUse'])` with the bash fixture in a fresh
`python3 -I -P` interpreter and read `sys.modules`.

**Acceptance Scenarios**:

1. Given the bash `PreToolUse` fixture with a cwd outside any workspace and no
   `WUWEI_WORKSPACE`, when the hook runs in a fresh interpreter, then none of `tomllib`,
   `hashlib`, `argparse`, `dataclasses`, `inspect`, `typing`, `datetime`, `subprocess` is
   in `sys.modules`, and the hook exits 0 with no output.
2. Given the same fixture inside a workspace with a `config.toml`, when the hook runs in a
   fresh interpreter, then none of `argparse`, `dataclasses`, `subprocess` is in
   `sys.modules`; the config is still read and validated.
3. Given `hook PreToolUse` with the bash payload on the CI runner, when the existing
   `test_hook_latency` runs, then p95 CPU is under 40 ms (20 percent under the budget).
4. Given a hook payload that needs config inside a workspace, when the hook runs, then the
   config loads and a broken config still gets the #326 answer; only the timing of the
   imports moves.
5. Given `wuwei hook` with no event or an unknown event, when it runs, then it answers as
   today (argparse usage error, exit 2).

### User Story 2 - The status line reads only what it shows (Priority: P1)

**Independent Test**: count the event lines `status.scan` JSON-decodes over a day whose
events are mostly silent producer lines.

**Acceptance Scenarios**:

1. Given a day of producer-written events of silent kinds the scan takes no action on,
   when `status --line` runs, then those lines are not JSON-decoded and the line is the
   same as today.
2. Given a day with clock, decision, draft, wake, steward and acknowledgement events (the
   silent kinds the scan does act on), a torn last line and a non-silent event, when the
   scan runs, then attention rows, watch and listen health, heartbeat health and loop
   count are exactly as today (the existing status tests prove it).
3. Given `status --line` with 10,000 events on the CI runner, then p95 CPU is under
   40 ms.

### User Story 3 - The heartbeat tick fits its budget (Priority: P2)

**Independent Test**: the existing `test_heartbeat_latency`, unchanged.

**Acceptance Scenarios**:

1. Given `heartbeat tick` on the CI runner, then p95 wall is under 150 ms.
2. Given the existing heartbeat tests, when the suite runs, then every probe still runs
   through the same launcher calls and reports the same results and values (the
   heartbeat event keeps its shape, the status line probe still records its wall ms).

### User Story 4 - Nothing else changes (Priority: P1)

**Acceptance Scenarios**:

1. Given the `latency` job on the PR (ubuntu-latest, Python 3.12, `WUWEI_BENCH=1`), then
   all 17 latency tests pass with no budget, test body, run count or job definition
   changed.
2. Given the full suite, when it runs, then it passes unchanged apart from the new tests;
   no guard's behaviour changes (the guard tests are the proof).
3. Given a guard module under `cli/wuwei/guards/`, when its source is parsed, then it
   imports none of `tomllib`, `datetime`, `subprocess`, `hashlib` at module level.

### Edge Cases

- A hook payload whose command names a path inside a workspace from a cwd outside one:
  scope resolution may load the config (and `tomllib`); that is the payload reaching a
  guard that needs it, not a regression.
- `wuwei hook PreToolUse --extra` or any argv other than exactly `hook <known event>`
  takes the argparse path and answers as today.
- A guard raising inside the fast path: same `wuwei hook: <reason>` and exit 2 as today.
- A credential loaded into `redact.VALUES` still redacts hook stdout and stderr: the
  `redact.Output` wrappers and `env.session()` stay around the fast path.
- `events.jsonl` with a hand-edited or torn line whose prefix looks like a silent kind:
  only a line that starts with the producer's `{"kind": "` form and ends with `}` is
  skipped undecoded; anything else is decoded as today and a torn line still reads as an
  unreadable event.
- A command name with no module file of its own (`scan-probe` registered by `probe.py`,
  `--help`, an unknown command) still falls back to listing the commands package.
- `adapters/redactor/builtin.py` builds on `redact.SECRET.pattern` and
  `redact.PHONE.pattern`; with those names as pattern strings it reads them directly.

## Requirements

### Functional Requirements

- **FR-001**: `wuwei hook <event>` with exactly a known event dispatches to
  `commands.hook.run` without importing `argparse`, reading `plugin.json` or listing the
  commands package, inside the same `env.session()`, redacting output wrappers, exit
  status validation and exception-to-exit-2 handling as every other command.
- **FR-002**: `cli/wuwei/redact.py`, `env.py`, `workspace.py`, `security.py`,
  `verdict.py`, `outward.py` and `guards/agent_launch.py` import the standard library
  modules named in the root cause inside the functions that use them; module-level regex
  patterns used only by those functions compile on first use.
- **FR-003**: `__main__` imports a named command directly from its module file and keeps
  `pkgutil` for the fallback listing only. `guards/__init__.py` imports `pkgutil` on first
  use (inside `discover()`), so a hook that never reaches a workspace never loads it;
  `discover()` keeps calling `pkgutil.iter_modules`, which `tests/test_profiles.py:92`
  pins through `guards.pkgutil`.
- **FR-003a**: names that existing tests address keep resolving: `workspace.tomllib`
  (`tests/test_workspace.py:798`) and `guards.pkgutil` (`tests/test_profiles.py:92`) are
  served by a module-level `__getattr__` that imports the module on first access.
- **FR-004**: `registry.Result` and `guards.Guard` become `collections.namedtuple`
  records with the same fields, defaults, positional and keyword construction, equality
  and immutability.
- **FR-005**: `workspace.scope` imports `registry` only for the external-worktree branch;
  `load_config` imports `wuwei.decision` only when `decisions.cruise.levels` has an entry.
- **FR-006**: `status.scan` skips, without decoding, a producer-form line whose kind is a
  silent kind the scan takes no action on; every other line is handled exactly as today.
- **FR-007**: The heartbeat keeps all four launcher probes as child processes and its
  event shape; it gets faster only through FR-001 to FR-006.
- **FR-008**: A new test proves FR-001 to FR-005 by `sys.modules` in a fresh interpreter
  (outside and inside a workspace); a new test proves no guard module imports `tomllib`,
  `datetime`, `subprocess` or `hashlib` at module level; a new test proves FR-006 by
  counting decoded lines.

### Key Entities

- `registry.Result(exit, data=None, reason='')`: the adapter result record.
- `guards.Guard(event, matcher, check, profile_relaxable=False)`: the guard record.
- `status.SKIP`: the silent kinds `scan` drops without action, derived from
  `signal.SILENT` minus the kinds `scan` acts on.

## Success Criteria

### Measurable Outcomes

- **SC-001**: On the PR's `latency` job: `test_hook_latency[PreToolUse]` p95 CPU under
  40 ms; `test_status_line_latency` p95 CPU under 40 ms; `test_heartbeat_latency` p95 wall
  under 150 ms; all 17 latency tests pass. The PR body carries the job's printed figures
  and the local before and after.
- **SC-002**: On the owner's machine class, alternating runs against the baseline in the
  same session: a hook inside a workspace drops by at least 15 percent p95 CPU, a hook
  outside any workspace by at least 40 percent, `status --line` by at least 20 percent.
- **SC-003**: `python -m pytest -q` passes with no existing test edited.

## Assumptions

- The import checks read `sys.modules` from a fresh interpreter (the pattern
  `test_hook_imports_only_needed_guards` already uses) instead of parsing `-X importtime`
  output; same signal, less parsing.
- `urllib` is left off the deny list: on Python 3.11 and 3.12 `pathlib` imports
  `urllib.parse` itself, so no change in this repository can keep it out.
- `inspect` and `typing` are left off the in-workspace deny list: `tomllib` imports
  `typing`, and `pkgutil.iter_modules` (pinned by `tests/test_profiles.py:92`) imports
  `inspect` when `discover()` lists the guards. Replacing the listing with `os.listdir`
  would save about 3 ms more per in-workspace hook but needs that test changed; it is a
  follow-up for the owner if the job is still red.
- `workspace.tomllib` and `guards.pkgutil` stay addressable through a module
  `__getattr__` (four lines each) instead of a module-level import, because existing tests
  monkeypatch through those names and may not change.
- The issue's "run the probes that do not need process isolation in-process through
  `commands.hook.run`" is not done. It would change five existing heartbeat tests
  (`test_measure_every_probe_ok`, `test_launcher_probe_outcomes`,
  `test_adapter_failure_leaves_in_process_probes_measured`,
  `test_allow_all_guard_fails_the_refused_probe`, `test_heartbeat_command`), which pin all
  four probes to the launcher, and an in-process probe would stop proving the installed
  files (the mutation test shows it). The owner's instruction and the Acceptance's "suite
  passes unchanged" win over that Deliver bullet. "Record the measured tick time in the
  heartbeat event as today" then holds with no change.
- Moving the force-push refusal in `commit_push.check` ahead of the Git context read would
  cut the heartbeat's critical path by about half, but it changes the guard's answer (the
  reason, and exit 1 versus 2 outside a configured repository). It is out of scope; if the
  PR's job still shows the heartbeat over 150 ms, raise it with the owner as a follow-up.
- Rounds one and two left `bin/wuwei` as it was. Round three (owner's go-ahead) adds `-S`
  and updates `tests/test_cli.py`'s pin to `exec python3 -I -P -S -c`; the `dirname`
  dependency stays pinned, so a `dirname`-free root is still not available.
- Skipping the `plugin.json` version read on the hook path means a missing or invalid
  manifest no longer fails every hook with exit 2; `--version` and every other command
  still read and validate it, and the integrity check covers a damaged install.
- Lines in `events.jsonl` are written by `state._append_jsonl` (`json.dumps` of
  `{'kind', 'payload', 'ts'}`), so a producer line starts `{"kind": "<kind>", ` and ends
  with `}`; the prefilter trusts only that form.
- The 40 ms and 150 ms runner targets cannot be measured from this machine; the PR's own
  `latency` job is the measurement, and local figures only show the direction (SC-002).
  If the job is still red after this change, the next levers, each needing the owner
  because it edits a test or a guard's answer, are, by expected gain: in-process heartbeat
  probes, the force-push refusal before the Git read, `os.listdir` in `discover()`.
- The compiled hook dispatcher of design section 2 stays out of scope; this issue exhausts
  the Python fixes first.
