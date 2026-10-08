# Implementation Plan: Latency headroom and a regression report

**Branch**: `562-latency-headroom` | **Date**: 2026-10-08 | **Spec**: `spec.md`

## Summary

Remove work the hot paths do not need (status line fields it never renders, a module-level
`registry` import, per-call keyword pattern building, repeated state and event reads at
SessionStart), make the invariant walk cheaper without dropping a case, and give the
latency job a per-probe artifact plus a report against the last green run on main.

## Technical Context

Stdlib-only Python 3.11+ runtime; pytest dev-only. The job runs Python 3.12 on a 2-CPU
`ubuntu-latest` runner. Measure CPU, not wall, on this shared host: take a baseline of
each probe on the worktree before the first change and after each change at the same load,
with the `python3 -I` floor printed beside it (`assert_latency_budget` already prints it).

## Constitution Check

Test first per behaviour; stdlib only; no new refusal under observe or guarded (#530); no
planner action changes (#551); no budget, probe or job setting loosened (#346); every
command keeps exits 0, 1, 2. `scripts/latency_report.py` is dev tooling, not runtime, and
uses only the stdlib. Pass.

## Method (binding, from #346)

1. Baseline: `WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py -k latency -s` on the
   unchanged worktree; keep the printed figures.
2. Profile each path before editing it: `python3 -X importtime` on the launcher line of
   `bin/wuwei` and cProfile over 60 runs with the latency fixtures (`subprocess_plugin`,
   `seeded_workspace`). The hook and status processes leave through `os._exit`, so profile
   in-process (`status.snapshot`, `hook.run` with a `SimpleNamespace`) or dump stats from
   an `atexit` handler.
3. Cut, re-measure, keep only cuts that remove work.

## Changes

### 1. `status --line` (FR-001), `cli/wuwei/commands/status.py`

- `snapshot(directory, line=False)`: when `line` is true skip the live sessions count
  (keep `'sessions': 0`), the seats per goal (`state.running_by_goal`, #487), the reply
  and meeting loop, `cruise.label`, `integrity.version`, `template_version` and the
  calendar adapter block. Keep `restart`, `posture`, `decisions`, `phases`, `cap`,
  `cap_bound`, `gate_approved`, `plan`, `running`, `pages`, `nudges` and the scan. `run(args)` passes `line=args.line`.
- Load the config once: `snapshot` loads it before `scan` and passes it as a new keyword
  `scan(directory, classified_state=None, config=None)`; `scan` uses it for the shadow
  nudge and the remote pin and loads it itself only when `None` (callers in
  `guards/lifecycle.py` and `attention` are unchanged).
- Must not change: `_groups`, `line`, `full`, `--json` output, the scan regex and its
  semantics, the `WUWEI ? unmeasured` path.

### 2. `cli/wuwei/integrity.py` (FR-002)

Move `from wuwei import registry` and `from wuwei.registry import Result` into the
functions that use them (`registry.load` at line 21, `registry.together` and
`registry.load('vcs', ...)` at lines 143-145, `Result` at 148-190). `version`, `restart`,
`other_versions` and `newer_template` stay import-free. No test patches
`integrity.registry` or `integrity.Result` today (checked); fakes patch `wuwei.registry`.

### 3. `cli/wuwei/outward.py` `_topics` (FR-003)

Add `@functools.lru_cache(maxsize=64)` helper `_keyword_pattern(words: tuple)` returning one
compiled `(?<!\w)(?:w1|w2|...)(?!\w)` of `re.escape(_normalize(word))` (or a tuple of
compiled patterns, one per word, if the builder finds an alternation edge case); `_topics`
calls it with `tuple(rules['sensitive_keywords'])` and searches
`normalized.replace('_', ' ')` once. Same for the three pattern lists if profiling shows
`re._compile` cost there. Empty keyword list: no pattern, no match (as today, `any([])`).

### 4. SessionStart (FR-004), `cli/wuwei/guards/lifecycle.py` `session_start`

- One `day = state.read_state(root)` reused by `memory.constraints` (line 68) and the
  continuity block (line 96).
- One read of today's events for the clock stamps: `watch._day_rows` (or `watch.records`)
  once, collect `ts` of `watch: clock` and `listen: clock` rows, pass them as `clocks` to
  both `watch.health(root, clocks, name=...)` calls, matching what `watch.health` collects
  itself at `watch.py:70`. Read `watch.health` fully first: the stamps it collects must be
  the same rows. If the one read raises, pass `None` so `watch.health` reads and reports
  the broken file exactly as today.
- Then profile SessionStart in `seeded_workspace` and take the next largest removable cost
  (candidates: `next.py` module-level imports of `brief`, `integrity`, `decision` that
  `step` does not need on this day; `memory.lint` and `memory.session_payload` reading the
  same notes twice). Record each cut and its measured effect in the PR body, not in code.
- Must not change: the orientation text, the order of lines, exit codes, the
  `together` overlap with the integrity guard in `commands/hook.py:84-88`.

### 5. PreToolUse and push (FR-005)

Items 2 and 3 apply to both. Then profile `PreToolUse` (`tests/payloads/PreToolUse/bash.json`)
and the `push` probe of `seeded_workspace` and remove the largest work that the call does
not need (module imports pinned by the existing deny-list tests in `tests/test_hooks.py`
lines 280-330 are the pattern to extend). Do not reorder or drop a guard; do not change
`guards/__init__.py` `MODULES` semantics.

### 6. Latency artifact (FR-006), `tests/test_hooks.py` `assert_latency_budget`

Before the budget check, when `os.environ.get('WUWEI_LATENCY_OUT')` is set, append one
line `json.dumps({...}) + '\n'` with the fields of FR-006 (`budget_ms` 50 and `measure`
`cpu` when `wall_budget is None`, else `wall_budget` and `wall`). Nothing else in the
function changes.

### 7. Report (FR-007), new `scripts/latency_report.py`

About 60 lines, stdlib only. `read(path)` returns `{probe: row}` from JSON lines (later
row of the same probe wins), raising `ValueError` on a malformed line. `main(argv)`:
current unreadable or malformed: print reason to stderr, return 2. Previous missing or
malformed: note one line, treat as empty. Print a table: probe, measure, now, last green,
change ms, change percent, budget, margin. "moved most": among probes present in both, the
largest `(now - last) / last` of the budgeted measure when positive; print
`moved most: <probe> +<ms> ms (+<pct>%)`. Margin: `budget - now` under 10 (cpu) or 20
(wall) prints `margin short: <probe> <margin> ms` ; a figure at or above budget prints
`over budget: <probe>`. Return 1 when any line of those printed, else 0. Also print the
floor and load of both runs on one line so the reader sees whether the runner was slower.

### 8. Job (FR-008), `.github/workflows/tests.yml` latency job

Add `WUWEI_LATENCY_OUT: latency.jsonl` to the job env, `permissions: {contents: read,
actions: read}` on the job, and after the pytest step, each with `if: always()`:

```yaml
      - uses: actions/upload-artifact@v4
        with:
          name: latency
          path: latency.jsonl
          if-no-files-found: ignore
      - name: Fetch the last green figures
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          id=$(gh run list -R "$GITHUB_REPOSITORY" -w tests.yml -b main -s success -L 1 --json databaseId -q '.[0].databaseId')
          [ -n "$id" ] && gh run download "$id" -R "$GITHUB_REPOSITORY" -n latency -D previous || echo "no last green figures"
      - name: Compare with the last green run
        run: python scripts/latency_report.py latency.jsonl previous/latency.jsonl
```

Under 40 added lines. The job keeps `continue-on-error: true`.

### 9. Invariant walk (FR-009), `tests/test_invariants.py`

- Move `from test_grants import run`, `from test_decision import draft_question` and
  `from wuwei.__main__ import main` to module level (or into the `world` fixture) so they
  import before the timed region.
- `CASES = math.prod(len(v) for v in DIMENSIONS.values())`; `test_invariants_hold` asserts
  `len(cases) == CASES` and `CASES >= 18000`.
- `READS = {'I1': (0, 1, 2, 3, 4, 5, 6), 'I2': (0, 1, 2, 3, 5, 6), 'I3': (0,), ...}`: the
  indices each invariant reads (derive from each function and the rules it calls; I11 reads
  none). `walk` groups cases by projection per invariant: it calls the invariant once per
  distinct projection with a case where unread positions hold `UNREAD`, an object whose
  `__eq__`, `__ne__`, `__hash__`, `__str__`, `__format__`, `__bool__` and `__iter__` raise
  `AssertionError(f'{name} reads an undeclared dimension')`; a failure is reported once per
  full case tuple that maps to it, so the printed lines are the same as today.
- Restore `assert elapsed < 1.0` and drop the `3.0` ponytail comment.
- `test_broken_rule_is_caught` and `test_table_matches_the_checks` unchanged.

### 10. Docs (FR-010)

`docs/site/reference.md#hook-latency-budget`: one short paragraph: the latency job writes
one JSON row per probe, uploads it as the `latency` artifact, and prints each probe against
the last green main run with the probe that moved most and any probe short of margin
(10 ms CPU, 20 ms wall). Do not change the budgets text. Add the local before and after
figures only if measured on a quiet host.

## Shared helpers reused

`workspace.load_config` (cache), `watch._day_rows` and `watch.health(clocks=...)`,
`state.read_state`, `startup_floor` and `assert_latency_budget` in `tests/test_hooks.py`,
the `LAUNCHER_MODULES` deny-list test pattern, `Rules.memo` in `tests/test_invariants.py`.

## What must not change

Budgets (50 ms CPU; 100 ms wall workspace; 200 ms heartbeat), probe fixtures (10000
events, 60 runs under `WUWEI_BENCH`), `startup_floor`, `continue-on-error` on the job, any
guard result or refusal, the status line text, `status` and `status --json` output,
SessionStart output, the 9.2 invariant table.

## Files

- `cli/wuwei/commands/status.py`, `cli/wuwei/integrity.py`, `cli/wuwei/outward.py`,
  `cli/wuwei/guards/lifecycle.py` (plus whatever profiling of item 4 and 5 names)
- `tests/test_hooks.py`, `tests/test_invariants.py`, `tests/test_outward.py`,
  `tests/test_signal_status.py`, `tests/test_sessions.py` (or the file holding `session_start` tests) if a read-count
  test fits there better than `tests/test_hooks.py`, new `tests/test_latency_report.py`
- new `scripts/latency_report.py`, `.github/workflows/tests.yml`, `docs/site/reference.md`
