# Tasks: gate probes leave no files in the builder's worktree

Test first: each test task runs and fails for the expected reason before its implementation
task. Tests are in-process with fakes for the VCS (no git, no network), except the one
bytecode smoke, which runs `sys.executable` in a `tmp_path` tree. Paths come from
`tmp_path`. Run only the touched test files, then the full suite with
`python -m pytest -q` from the repository root.

## Phase 1: the gate brief names the probe environment (FR-001, US1)

- [X] T001 Test in `tests/test_brief.py`: with fixture `day`, parametrized over `quality`,
  `arch`, `security` and `goal`, `brief(monkeypatch, 'Review it.', role, 'X', 'g', '--gate',
  '--worktree', 'tree')` exits 0 and the header of `briefs/g.md` (text before the first blank
  line) has exactly one line starting `Probe env: PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=`
  that names `.wuwei/scratch/X/sentinel-<role>/pycache` and contains
  `run every probe, test and mutant in a copy of the worktree under your scratch directory`.
  A `builder` brief on `X` and `writer.write('steward', 'X', 's', 'body', root=day[0])` have no
  `Probe env:` line. Fails: no such line today.
- [X] T002 Test in `tests/test_brief.py` (acceptance smoke): from the `quality` gate brief's
  `Probe env:` line, take `shlex.split(line.removeprefix('Probe env: ').split('; ', 1)[0])`,
  build an environment from `os.environ` plus those two assignments, write
  `tmp_path/probe/pkg/__init__.py` and `pkg/mod.py`, run
  `subprocess.run([sys.executable, '-c', 'import pkg.mod'], cwd=tree, env=env, check=True)`
  and assert `list(tree.rglob('__pycache__')) == []`. Fails: no line to read today.
- [X] T003 In `cli/wuwei/brief.py` `write`, right after the `Scratch:` append (line 426),
  append the `Probe env:` line when `gate` is true, with
  `shlex.quote(str(scratch / 'pycache'))` as the prefix value (plan.md, Design). T001 and T002
  pass; the rest of `tests/test_brief.py` stays green.

## Phase 2: receive names what the round left (FR-002, US2)

- [X] T004 Update the two fakes in `tests/test_dispatch.py` that define only `head` so they
  answer `status` with `Result(0, [])`: the local `class VCS` in
  `test_receive_accepts_short_current_worktree_head` and the `SimpleNamespace` vcs in
  `agent_gate` (plan.md, Existing tests). They stay green before and after T006.
- [X] T005 Test in `tests/test_dispatch.py`: with fixture `root`, `WUWEI_WORKSPACE` set to it,
  a brief `briefs/arch.md` reading `Head: abc1234\nWorktree: <root>/tree\n` (tree created),
  `decisions/gate-arch.md` holding `PASS`, a stopped `sentinel-arch` seat `arch` on item `A`,
  and `registry.load` patched to a fake whose `head` returns `{'sha': 'abc1234'}` and whose
  `status` returns, by parameter:
  (a) `[{'path': 'pkg/__pycache__/mod.cpython-311.pyc', 'index': '?', 'worktree': '?',
  'original_path': None}, {'path': 'probe.py', 'index': '?', 'worktree': '?',
  'original_path': None}]`: `main(['dispatch', 'receive', 'A', 'arch', 'arch'])` exits 0,
  stdout JSON has `verdict` `PASS`, `gate_verdicts['A:arch:initial']` is recorded, and stderr
  is one line starting `warning: ` that names the tree, `pkg/__pycache__/mod.cpython-311.pyc`
  and `probe.py`;
  (b) `[]`: exits 0 and stderr is empty;
  (c) `Result(2, reason='git status failed')`: exits 2, stderr names `git status failed`, and
  `gate_verdicts` is empty.
  Fails: (a) prints no warning today.
- [X] T006 In `cli/wuwei/dispatch.py` `receive`: `left = []` before the `Worktree:` block,
  load the VCS once in that block, read
  `left = [row['path'] for row in brief.status(vcs, str(tree), root)]` after the HEAD
  refusal, and after the `gate.received` state write print the `warning:` line to stderr
  when `left` is not empty, with the `ponytail:` comment on ignored files (plan.md, Design).
  T005 passes; the rest of `tests/test_dispatch.py` stays green.

## Phase 3: the charter rule (FR-003, US3)

- [X] T007 Test in `tests/test_charters.py`: add the `RULES` row
  `("clean probes", "_common.md", "runs every probe, test and mutant in a copy under its `Scratch:` directory")`
  and a test that each of `agents/sentinel-arch.md`, `sentinel-quality.md`,
  `sentinel-security.md` and `sentinel-goal.md` contains that anchor. Fails: the sentence is
  absent.
- [X] T008 In `charters/_common.md`, bump `version: 1.9.0` to `1.10.0` and append the
  sentence from plan.md to Write and action boundary rule 1; run `bin/wuwei agents build`,
  then `bin/wuwei agents check`. T007 and the rest of `tests/test_charters.py` and
  `tests/test_agents.py` pass.

## Phase 4: docs and the full suite (FR-004)

- [X] T009 Add the `Gate probes` row after the `Scratch directory` row of the "Seat briefs
  and the build loop" table in `docs/site/reference.md` (plan.md, Design); run
  `tests/test_docs.py` and `tests/test_docs_system.py`.
- [X] T010 Run `python -m pytest -q`; check every file written for em-dashes, emojis and
  absolute local paths.
