# Implementation Plan: the suite runs in parallel and the slow tests are cut

**Branch**: `685-parallel-tests` | **Date**: 2026-10-10 | **Spec**: `spec.md`

## Summary

Parallelism does most of the work: pytest-xdist in the dev extra, `-n auto --dist loadgroup`
in the CI `test` job, the twelve clock tests in one `xdist_group('timing')`, and a guarded
rerun of only the flagged timing tests. Five fixture or helper changes cut the repeated setup
the profile found. One stdlib script runs the tests a diff touches. No runtime code changes;
no assertion or budget changes.

## Technical Context

Runtime: Python 3.11+, stdlib only, untouched. Dev: pytest plus pytest-xdist (new, dev only).
CI: GitHub Actions `ubuntu-latest` (4 vCPUs). The builder's interpreter needs pytest-xdist
installed to run `-n auto`; the serial suite runs without it.

## Constitution Check

- I (stdlib at runtime): `cli/` and `adapters/` untouched; xdist is dev only;
  `scripts/changed_tests.py` is stdlib.
- II (exits): the script exits 0 nothing to run, 2 diff unreadable, else pytest's code.
- III (one behaviour, one function): each cut lands in the one fixture or helper all its
  tests share.
- IV (test first): workflow, marker, pyproject and script behaviours have tests written first.
  The fixture cuts are refactors under existing tests: their evidence is the unchanged tests
  passing, plus the before and after durations.
- V (ponytail): no conftest plugin, no rerun plugin, no Makefile; six inline lines over
  pytest's own last-failed cache do the rerun classification.
- #346 (never loosen a budget): no budget constant or assertion changes (SC-003).

## Design

### 1. Dependency and marker: `pyproject.toml`

```toml
[project.optional-dependencies]
dev = ["pytest", "pytest-xdist"]

[tool.pytest.ini_options]
pythonpath = ["cli", "."]
testpaths = ["tests"]
markers = ["xdist_group(name): tests that share one xdist worker; 'timing' holds the clock tests (#685)"]
```

The marker line makes `-m xdist_group` warning-free where xdist is absent (the latency job
installs only pytest). Do not add `--dist` or `-n` to `addopts`: a run without xdist would
fail on the unknown option.

### 2. CI: `.github/workflows/tests.yml`, job `test` only

```yaml
      - name: Install test dependencies
        run: python -m pip install pytest pytest-xdist
      - name: Tests in parallel
        id: suite
        continue-on-error: true
        run: python -m pytest -q -n auto --dist loadgroup
      # #685: a timing test the parallel run failed reruns alone; any other failure fails the job.
      # loadgroup records a grouped test as <nodeid>@timing, which a plain --lf cannot match.
      - name: Rerun failed timing tests alone
        if: steps.suite.outcome == 'failure'
        run: |
          python - <<'EOF'
          import json, sys, pytest
          failed = json.load(open('.pytest_cache/v/cache/lastfailed'))
          plain = [k for k in failed if not k.endswith('@timing')]
          if not failed or plain:
              sys.exit(f'not rerun: failures outside the timing group: {plain}')
          sys.exit(pytest.main(['-q', *(k.removesuffix('@timing') for k in failed)]))
          EOF
```

(Corrected by the builder: under `--dist loadgroup` xdist records a grouped failure as `<nodeid>@timing`, which a plain `--lf` run cannot match, so `--lf` fell back to every test and the collect-only guard always exited 0. See research.md, Rerun guard.)

- `continue-on-error` on the first step lets the second decide the job. If the first step
  passes, the second is skipped and the job is green.
- The step reads the cache and retries nothing unless every recorded failure is a timing
  test. A missing cache raises (exit 1); an empty one, a plain test or a collection error
  exits 1 with the list.
- Otherwise it runs the failed timing tests alone, no `-n`; its exit is the job's.
- The matrix (`3.11`, `3.12`), the job name `test` (branch protection names `test (3.11)` and
  `test (3.12)`), and the other four jobs stay as they are. No job has `needs:`, so
  `ziran-audit`, `latency`, `skill-evals` and `headless-e2e` already start beside `test`
  (issue item 3: confirmed, no change).

### 3. Timing markers

Add `@pytest.mark.xdist_group('timing')` directly above each of the twelve tests in
`research.md` (Timing tests), above any `parametrize`. One line per test; no other edit in
those tests. In `tests/test_invariants.py` that is the only change (#626 is editing `walk`).

### 4. Cuts (fixtures and helpers only)

a. `tests/test_setup.py`, `project` (line 218). Add a module-scoped `repos` fixture that
   builds the three `REMOTES` repositories once with `make_repo` into
   `tmp_path_factory.mktemp('repos')`, inside `pytest.MonkeyPatch.context()` with `HOME` set
   to a fresh temp directory and every `GIT_*` variable removed, so the developer's git
   config never reaches them (the function-scoped conftest isolation is not active at module
   setup). `project` keeps all its environment lines and replaces the `make_repo` loop with
   `shutil.copytree(repos, root, symlinks=True)`. `make_repo` itself is unchanged; other
   callers keep using it.

b. `tests/test_canary.py`, `secured` (line 13). Add a module-scoped `initialized` fixture
   that runs `init.run(SimpleNamespace(path=str(root)))` once in
   `tmp_path_factory.mktemp('secured')` under `pytest.MonkeyPatch.context()` with the same
   environment conftest gives a test: `HOME` in a temp directory, `WUWEI_WORKSPACE`,
   `GH_TOKEN`, `GITHUB_TOKEN`, `WUWEI_SESSION_ID`, `CLAUDE_ENV_FILE`,
   `SLACK_OWNER_DM_CHANNEL` and `SLACK_API_BASE` removed, cwd at the root. `secured` keeps
   its `delenv` and `chdir` and copies the tree with
   `shutil.copytree(initialized, tmp_path, symlinks=True, dirs_exist_ok=True)`.
   Exception: a test that asserts on what `init.run` printed (for example
   `test_init_random_private_material`, which checks `capsys` holds no canary) must still see
   init run inside the test. Such a test stops requesting `secured` and calls `init.run`
   itself (the same two lines the fixture had). Check every `secured` user with `capsys`.
   Before relying on the copy, compare one copied tree with one fresh per-test init (same
   file list, same modes, same content except the random material) and note it in
   `research.md`.

c. `tests/test_workspace.py`, `cli()` (line 23). Run the CLI in-process with the same
   observable contract: same signature `cli(cwd, *args, **env)`, returns
   `subprocess.CompletedProcess(args, code, stdout, stderr)`. Inside: save `os.environ` and
   the cwd; drop `WUWEI_WORKSPACE` and `WUWEI_NOW`; apply `env`; `os.chdir(cwd)`; call
   `wuwei.__main__.main(list(args))` under `contextlib.redirect_stdout` and
   `redirect_stderr` into `io.StringIO`; map a `SystemExit` to its code; restore cwd and
   environment in `finally`. `main` already wraps the current `sys.stdout`, so redaction
   still applies. `test_init_layout` (both params) keeps one real interpreter launch: keep
   the current subprocess body as `cli_process` next to `cli` and call it from that test
   only, the one smoke test of the `python -m wuwei` boundary. If any other test fails
   in-process for a reason that is process state (a module-level cache, `sys.exit`, an
   import-time read), switch that test to `cli_process` and list it in `research.md`.

d. `tests/test_reasons.py`, `all_reasons` (line 151) and `tests/test_tone.py`, `classes`
   (line 37). `all_reasons` becomes `@functools.cache` and returns a tuple built from the
   same loop. In `test_tone.py`, move the body of `classes` into a cached `_classes()` that
   returns a dict of tuples; `classes()` returns `{name: list(texts) for name, texts in
   _classes().items()}` so `test_a_long_charter_sentence_breaks_the_budget` can still append
   to its own copy.

e. `tests/test_state_allowlist.py`, `reader_inventory` (line 161): `@functools.cache`,
   returning `frozenset(keys), frozenset(kinds)`. It reads only source files, so the
   monkeypatched `OWNER_FIELDS` and `FREE_KINDS` in the widened tests do not affect it.

### 5. Changed tests: `scripts/changed_tests.py` (new)

```text
"""Run the test files a diff against origin/main touches, and the tests that import them (#685).

Usage: python3 scripts/changed_tests.py [pytest args]
Exit 0 nothing to run, 2 the diff could not be read, otherwise pytest's exit code.
"""
```

- `changed(root)`: `git diff --name-only --merge-base origin/main` plus
  `git ls-files --others --exclude-standard`, both with `cwd=root`, `check=True`,
  `capture_output=True`, `text=True`; returns the set of repository-relative paths.
- `module(path)`: the import name of a Python path or `None`: strip a leading `cli/` or
  `tests/`, strip `.py` and a trailing `/__init__`, `/` to `.`. So `cli/wuwei/heartbeat.py`
  is `wuwei.heartbeat`, `adapters/vcs/git.py` is `adapters.vcs.git`, `tests/fakes/day.py` is
  `fakes.day`, `tests/test_plan.py` is `test_plan`. Only paths under `cli/`, `adapters/` or
  `tests/` are modules.
- `imports(source)`: names from `ast.walk`: each `Import` alias name; for each `ImportFrom`
  with a module, the module and `module.alias` for each alias.
- `select(paths, root)`: returns a sorted list of test paths, or `['tests']`.
  1. Any of `tests/conftest.py`, `pyproject.toml` in `paths`: `['tests']`.
  2. Start with the changed `tests/test_*.py` files that exist.
  3. `modules` = module names of the changed Python paths; `names` = file names of the other
     changed paths.
  4. For each `tests/test_*.py`, read the source once; select it if its imports meet
     `modules` or its text contains one of `names`.
  5. Repeat step 4 with the selected test modules added to `modules` until nothing new is
     selected (test files import each other's fixtures).
  A `ponytail:` comment names the ceiling: direct imports and file-name mentions only; a
  module reached only through `wuwei.__main__` dispatch, or a file read through a glob, is
  missed; CI runs the full suite.
- `main(argv)`: `changed` raising `OSError` or `subprocess.CalledProcessError` prints
  `changed_tests: cannot read the diff against origin/main: <reason>` to stderr and returns
  2. An empty selection prints `changed_tests: no test touched by the diff` and returns 0.
  Otherwise print the selection, then return
  `subprocess.run([sys.executable, '-m', 'pytest', '-q', *argv, *files], cwd=root).returncode`.
- `if __name__ == '__main__': sys.exit(main(sys.argv[1:]))`.

Seats pass `-n auto --dist loadgroup` as extra args when the selection is large.

### 6. Docs: `CONTRIBUTING.md`

- Line 16: `pytest and pytest-xdist are dev dependencies only.`
- Line 22: the suite runs with `python3 -m pytest -q`, or in parallel with
  `python3 -m pytest -q -n auto --dist loadgroup` (the timing tests share one worker); while
  working, `python3 scripts/changed_tests.py` runs the tests the diff touches.

### Tests (new file `tests/test_dev_cycle.py`)

- Workflow pin: in the slice of `tests.yml` from `\n  test:` to `\n  ziran-audit:`, assert
  `pip install pytest pytest-xdist`, `python -m pytest -q -n auto --dist loadgroup`,
  `continue-on-error: true`, `if: steps.suite.outcome == 'failure'` and the inline rerun;
  and that no job in the file has `needs:`. The rerun's Python is extracted from the workflow
  and run against fake caches: only timing entries reruns them with the suffix removed; a
  plain entry, a mix, a collection error, an empty cache and no cache fail without a retry.
- pyproject pin: `tomllib` load; `pytest-xdist` in the dev extra; a marker starting
  `xdist_group` in `tool.pytest.ini_options.markers`.
- Timing set: an AST scan of `tests/test_*.py` collects every function decorated with
  `pytest.mark.xdist_group('timing')`; assert it equals the twelve `(file, name)` pairs from
  `research.md`.
- Script: load `scripts/changed_tests.py` with `spec_from_file_location` (as
  `tests/test_latency_report.py` loads its script). Table tests of `select` on a temporary
  tree (scenarios 4.1 to 4.5), and `main` with `changed` and `subprocess.run` replaced through
  `monkeypatch` (scenarios 4.5 to 4.7: exit 0 and pytest not called; exit 2 and the reason;
  the pytest argv and its exit code passed through).

## Must not change

- Any `assert` line or budget constant in `tests/` (SC-003); `STATUS_LINE_BUDGET_MS`, the 50 ms
  hook budget, the 1.0 s walk budget, every `< N` clock bound.
- `cli/`, `adapters/`, `bin/`, `hooks/`: no runtime change.
- The `latency`, `ziran-audit`, `skill-evals` and `headless-e2e` jobs, the job name `test` and
  its matrix values (the calibrate test and branch protection read them).
- `README.md`'s `python3 -m pytest -q`; AGENTS.md and the constitution.
- `make_repo`, `init.run`, `previous_workspace` and the other helpers the cuts call.

## Risks

- Hidden order coupling inside a module, exposed by per-test distribution: run
  `-n auto --dist loadgroup` twice; fix at the fixture, else group that module and record it.
- Tests that compare `git status --porcelain` of the repository (`test_calibrate.py`,
  `test_vcs.py`) can see another worker's write into the checkout. None was found (all writes
  go to `tmp_path`; `.pytest_cache` and `__pycache__` are ignored); a failure there means a
  test writes into the repository and that test is the bug.
- `calibrate` reads this repository's own workflow (`tests/test_calibrate.py:451`): run it
  after the workflow change.
