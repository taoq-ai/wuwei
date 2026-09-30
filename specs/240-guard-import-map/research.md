# Research: Where a hook's time goes

## Method

M-series host, 10 CPUs, host load 5 to 7 during the runs (so absolute wall numbers are
high; relative costs are what matter). Python 3.12 for the benchmark suite, Python 3.14
as `python3` for the single-shot probes. All probes ran from a scratch directory outside
the repository against this worktree's `cli/`, with a scratch workspace (`.wuwei/config.toml`
empty, integrity verdict seeded as `tests/fakes/integrity.seed` does).

1. Baseline benchmarks: `WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py -k latency`.
2. Guard import cost: in a fresh interpreter, import `wuwei.commands.hook`, `wuwei.env`
   and `wuwei.workspace` (what every hook imports first), then time `discover()` or the
   import of a chosen set of guard modules with `time.perf_counter`.
3. Which guard modules end up loaded: run `hook.run` in process with `hook.discover`
   replaced by an import of only the modules an event needs, then list
   `wuwei.guards.*` in `sys.modules`.
4. Repeats of config, scope and parse work: `cProfile` over one `hook.run` for call
   counts, then `time.perf_counter` over 200 calls of each function for real cost.

`python -X importtime` is not usable for step 2: `importlib.import_module` goes through
`importlib._bootstrap._gcd_import`, which does not emit importtime lines, so the guard
modules are missing from its output.

## Baseline (before)

`WUWEI_BENCH=1` report lines, p95 over 60 runs, startup floor (`python3 -I -c pass`) CPU
11.6 ms, wall 13.3 ms:

| Path | CPU p95 | Wall p95 |
| --- | --- | --- |
| PreToolUse `npm test` (irrelevant Bash) | 45.3 ms | 52.0 ms |
| PostToolUse (Write) | 50.0 ms | 58.0 ms |
| Stop in a workspace | 49.4 ms | 58.6 ms |
| SubagentStop in a workspace | 56.8 ms | 111.2 ms |
| SessionStart in a workspace | 114.9 ms | 127.3 ms |
| `git commit` check in a workspace (relevant Bash) | 119.2 ms | 88.8 ms |
| `git push` check in a workspace | 244.0 ms | 169.9 ms |

Stage costs, three runs each:

| Stage | Cost |
| --- | --- |
| Interpreter start (`-I`, no imports) | 12 to 13 ms |
| `wuwei.commands.hook`, `wuwei.env`, `wuwei.workspace` imports | 16 to 21 ms |
| `discover()`, all twelve guard modules | 11.1 to 13.4 ms |
| `pkgutil.iter_modules` over the guard package | 0.07 ms |

Guard import cost per event if only the needed modules were imported:

| Selection | Modules | Import cost | Saving vs all |
| --- | --- | --- | --- |
| Stop | lifecycle, stop | 6.6 to 7.4 ms | about 5 ms |
| PostToolUse | decision, traces, verdict | 1.0 to 1.6 ms | about 10 ms |
| PreToolUse Bash | commit_push, deploy, integrity, outward, pr, protect_state | 5.7 to 6.0 ms | about 6 ms |
| PreToolUse Write or Edit | integrity, outward, protect_state | 4.6 to 5.0 ms | about 7 ms |
| SubagentStop | agent_launch, verdict | 0.3 ms | about 11 ms |
| SessionStart | integrity, lifecycle | 5.7 to 6.4 ms | about 6 ms |
| PreCompact | lifecycle | 5.5 to 6.2 ms | about 6 ms |

Bash guard modules still loaded with only the needed modules imported (step 3): Stop with
`stop_hook_active` false, PostToolUse, SessionStart and PreCompact each end with
`wuwei.guards.commit_push` loaded, through `workspace.guard_scope` into `workspace.scope`
(`cli/wuwei/workspace.py:215`, `from wuwei.guards.commit_push import data`).

Config, scope and parse repeats in one invocation (step 4):

| Call | Calls per hook | Real cost per call |
| --- | --- | --- |
| `workspace.load_config` (cached per content since #211) | 2 to 5 | 0.055 ms |
| `workspace.find_workspace` | 5 to 12 | 0.017 ms |
| `workspace.scope` | 1 to 3 | 0.105 ms |
| `shell.normalize` | 1 to 3 | 0.024 ms (`ls -la`) to 0.1 ms (`git commit && git push`) |

## Decisions

- Map from module to `{event: tool pattern}`, checked before each import, keeping the
  directory listing. Rejected: replacing the listing with a fixed module list (breaks the
  hook tests that install guard modules into a swapped package path, and a new module
  would silently not run); an event-to-modules map (needs a second lookup to tell an
  unmapped module from a skipped one); deriving the map at run time (needs the imports it
  is meant to avoid).
- The pattern for an event is the `|`-join of the module's matchers for that event in
  `GUARDS` order, or `None` if any of them is `None`. `re.fullmatch` of an alternation
  matches exactly when one branch does, so skipping a module whose pattern does not match
  cannot skip a guard that would have run. A table test pins the map to the `GUARDS`
  lists.
- The hook's `(event, tool)` reaches `discover()` through a `ContextVar`. Rejected:
  `discover(event, tool)` parameters (fourteen zero-argument stubs of `hook.discover` in
  six existing test files would need editing, against the acceptance); a plain module
  global (same size, but a `ContextVar` token restores the previous value exactly and
  cannot leak across threads).
- Move `data` into `wuwei.registry` next to `Result`, and re-export it from
  `commit_push`. Rejected: inlining the check in `workspace.scope` (a copy); leaving it
  (Stop and PostToolUse keep loading the commit guard).
- No invocation-scoped cache for config, scope or parse: the total repeat cost is under
  1 ms per hook, below benchmark noise, and a cache is new state to invalidate. Config is
  already cached per content (#211).
- No daemon, no compiled dispatcher, no change to `bin/wuwei` or `hooks/hooks.json`.

## Measuring after the change

Run on the same host, back to back with the baseline where possible, on a quiet host:

1. `WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py -k latency`, twice; report the
   lower p95 of each path. PreToolUse `npm test` is the irrelevant command, `commit in a
   workspace` the relevant one.
2. The stage probe from Method step 2 with the selection set, per event.
3. Audit counts for PreToolUse `ls -la` in a workspace: a `sys.addaudithook` that counts
   `open` and `subprocess.Popen` events after `discover()` returns (the #222 review
   measured 6 opens and 0 subprocesses); before and after must match or drop.

## After the change

- The `WUWEI_BENCH=1` suite on a host at load 5 to 8 moves by more than the saving between
  runs of the same tree, so the before and after hook figures come from an interleaved
  probe instead: the same payloads against a copy of the pre-change `cli/` and this tree,
  alternating per call, 100 runs each, twice. Every measured path (PreToolUse `npm test`,
  `ls -la` and Write, PostToolUse, Stop) is 2 to 6 ms lower at CPU and wall p95 in both
  runs; the figures are in `docs/site/reference.md` "Where hook time goes". The
  `git commit` and `git push` checks save about 2 ms on guard imports, inside the spread
  of their `git` subprocesses.
- Audit counts for PreToolUse `ls -la`: opens of workspace files after `discover()` stay
  at 5 and subprocesses at 0. Counting every `open` after `discover()` goes from 5 to 10,
  because five module `.pyc` loads (`wuwei.security` and the stdlib modules it imports)
  that an unselected guard module used to pull in during discovery now happen when the
  guard that needs them runs. Over the whole hook run, opens drop from 71 to 52. The
  #222 figure of 6 was taken with a different probe; this probe counts 5 on the
  unchanged tree.
