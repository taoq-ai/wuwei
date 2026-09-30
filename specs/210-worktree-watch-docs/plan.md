# Implementation Plan: Worktree command, watch install safety and operator docs

**Branch**: `210-worktree-watch-docs` | **Spec**: `specs/210-worktree-watch-docs/spec.md`

## Summary

Four small changes at the shared spots the dry run exposed: a thin CLI caller for the existing `workspace.create_worktree`, a reordered watch installer with one teardown helper shared by uninstall and failed install, live `watch.health` inside the shared `status.attention`, and reference documentation checked by tests against the code it describes.

## Technical Context

Python 3.11+ stdlib only, pytest for tests. No new modules outside one command file, no new adapter operations, no new configuration keys, no new events or state keys.

## Constitution Check

- I Stdlib only: yes. II Three-state exits: gate refusal 1, every other failure 2 with reason; uninstall's exit 0 on stop failure is the issue's explicit requirement and prints the failure. III One behaviour, one function: worktree creation stays in `create_worktree`, watch health stays in `watch.health`, attention stays in `status.attention`. IV Test first: every task below pairs a failing test with its implementation. V Ponytail: one new command file, one private helper, no config. VII Security: the anchor is still written only by `git_hook.install`; no guard is loosened.

## Changes

### 1. `wuwei worktree add` (new file `cli/wuwei/commands/worktree.py`)

Commands are auto-discovered by `cli/wuwei/__main__.py`; no registration elsewhere.

- `register(subparsers)`: parser `worktree`, required sub-action `add` with positional `item` and optional `--repo NAME`.
- `run(args)`:
  1. `root = workspace.find_workspace()`; `config = workspace.load_config(root)`.
  2. `brief.identifier(args.item)` to validate the item (reuse, do not copy the regex).
  3. Pick the repo: `--repo` matches `repos[].name`; without it exactly one configured repo is required, else `ValueError('several repositories configured; pass --repo <name>')`; unknown name or no repos is a `ValueError`.
  4. `repo_path = (root / Path(repo['path']).expanduser()).resolve()` (same resolution as `workspace.scope`).
  5. `result = workspace.create_worktree(repo_path, args.item.lower(), root / 'worktrees' / args.item, root, registry.load('vcs', config))`.
  6. Print `json.dumps(result)`; return 0.
  7. Catch `state.StateError` only: print `wuwei worktree: <reason>` to stderr, return 1. Everything else propagates to `__main__`, which prints the reason and returns 2.
- Do not change `workspace.create_worktree`, `git_hook.install`, `adapters/vcs/git.py:worktree_add`, the vcs allowlist or recordings.

### 2. Watch installer (`cli/wuwei/commands/watch.py`)

- Add `--dry-run` to the `install` sub-parser only.
- Extract one private helper `_remove(path, platform, service)` from the current uninstall body (lines 43-49): stop (`launchctl bootout` or `systemctl --user disable --now`), `path.unlink(missing_ok=True)`, and on Linux `daemon-reload`. Each service call is wrapped so an `OSError` or `ValueError` is printed as `wuwei watch: warning: <reason>` on stderr and does not stop the next step. Returns nothing.
- `uninstall`: if the unit is absent return 0 (unchanged); otherwise `_remove(...)`, print `watch uninstalled: <label>`, return 0.
- `install`: keep the existing already-installed check, template render and value escaping unchanged. Then:
  - Build the list of service argv for the platform (the same argv as today).
  - If `args.dry_run`: print `unit: <path>`, the rendered text, and each argv as `$ <joined argv>`; return 0. No `mkdir`, no write, no service call.
  - Otherwise write the unit (`atomic_write`, unchanged) and run the argv list inside `try`; on `OSError` or `ValueError` call `_remove(...)` and re-raise so `__main__` returns 2 with the original reason.
- Do not change `adapters/watch_service.py` (the allowlist already covers every command used) or the templates.

### 3. Live watch health in attention (`cli/wuwei/commands/status.py`)

- In `attention(directory, classified_state=None)`, after the event loop and before the escalated-items loop:
  - `code, message = watch.health(directory.parents[2])` (reuse; same root derivation `snapshot` already uses).
  - Drop every key whose first two parts are `('watch: sweep', 'watch')` (the sweep's `watch_dead` rows).
  - If `code == 1` add key `('watch: health',)` with `{'tier': 'page', 'source': 'watch: health', 'lane': 'Work', 'reason': message}`; if `code == 2` the same with tier `nudge`.
- `status.scan` reads the event stream once, collects today's `watch: clock` stamps and passes them to `watch.health(root, clocks)` only when there are any, so the status line never reads events twice. It returns the rows and the watch state: `dead` (page), `unmeasured` (nudge), `alive`, or `off` when no clock line exists today (no row). `attention` returns the rows; `snapshot` takes both.
- `watch.health` reads only today's clock lines. Fresh is alive; stale is dead. With none today it checks `workspace.watch_unit(root)`, the unit path `watch install` and `uninstall` now share: installed is dead, otherwise `(0, 'watch off: ...')`. `status.scan` does that one existence check itself when there is no clock line and imports `wuwei.watch` only when a clock line exists or the unit is installed.
- In `run`, for `--line`, append `watch off`, `watch dead` or `watch unmeasured` right after the nudges part when `data['watch'] != 'alive'`.
- `nudges` and the cockpit (`commands/dashboard.py`) need no change; they call `attention` and `snapshot`.
- Import `watch` inside `attention` (as `snapshot` imports `registry`) to keep command import light.
- Do not change `watch.sweep`, `obligations.sweep`, `signal.classify` or the sweep row fields.

### 4. Documentation

- `docs/site/reference.md`, new sections:
  - **Item worktrees**: `bin/wuwei worktree add <item> [--repo <name>]`, after the morning gate; path `worktrees/<item>`, branch `<item lowercased>` from the repository's current HEAD; installs the managed pre-commit and pre-push hooks and the workspace anchor; prints `branch` and `path` JSON; pass `path` to `brief --worktree`. A worktree made with raw `git worktree add` has no anchor and its pushes outside the Claude Bash hook are unguarded.
  - **Seat briefs**: `bin/wuwei brief <charter> <item> <name> [--worktree PATH] [--gate] [--track SLICE|FULL] [--pr OWNER/REPO#N] < body.md`. Body is read from stdin. The role is a charter name (`lead`, `builder`, `shepherd`, `sentinel-arch`, `sentinel-quality`, `sentinel-security`, `sentinel-goal`, `steward`); `dispatch next` and `dispatch receive` use the gate role (`arch`, `quality`, `security`, `goal`). Gate bodies must not ask for an inline verdict or restate the verdict path. A `Paths:` line lists extra paths for the SLICE protected-path check. The command prints the brief path; one brief per name.
  - **Item phase order**: a table `| phase | legal next phases |` with one row per key of `state.PHASES`, in `state.PHASES` order, next phases joined with `, ` exactly as in the code (for example `| `planned` | spec, implement, parked, escalated |`). Note that `parked` and `escalated` resume only to the recorded prior phase.
  - **Gate verdict layout**: one fenced example (a FIX quality verdict with one finding, `Head:`, `Probe:`, `Simplicity:`, `Design:`, class-sweep lines and the retro keys; model it on the accepted dry-run verdict), then the rules: exactly one `Verdict: PASS|FIX|PARK|ESCALATE` line; one `Head: <7 to 40 hex>` row; a `Probe:` or `Mutation:` line; `Blocked:`, `Gap:`, `Change:` once each; quality adds one `Simplicity:` and one `Design:`; arch, quality and security add `CLASS: PASS|N.A.|FINDING` lines; a non-PASS verdict needs at least one finding; a finding starts on a bullet or table row, a line beginning with the severity, a `Severity:` line, or a numbered or `F1` line; each finding carries a severity (P0 to P3, critical, high, medium, low, info), a `file:line` (or `Lnn` for docs), `blocks: yes|no`, and a failure scenario (for example "fails when", "would", "impact"). Name `bin/wuwei verdict lint FILE --role <charter>` for a local check.
- `docs/site/configuration.md`, section "Running the watch": add `watch install --dry-run`, failed install removes the unit so a retry works, `watch uninstall` always exits 0 and prints stop failures as warnings, and a dead watch appears as `watch dead` in `status --line` and as a `watch: health` page in `wuwei nudges`.
- `skills/wuwei-plan/SKILL.md`, "Item dispatch and receive": create the item's worktree with `wuwei worktree add <item>` (with `--repo <name>` when several repositories are configured) and pass the printed `path` to `wuwei brief builder <item> <name> --worktree <path>`; never create item worktrees with `git worktree add`.

## Tests (all fast, in-process except one real Git boundary)

- `tests/test_worktree_command.py` (new): real Git end-to-end acceptance (reuse the `git clone --shared` and stub-executable pattern from `tests/test_git_hook.py::test_managed_worktree_isolation_and_runtime_pointer`, and `adapter()` from `tests/test_vcs.py`); fake-vcs table for gate refusal (exit 1, no vcs call), repo selection (one repo default, two repos without `--repo` exit 2, named repo, unknown repo exit 2), invalid item exit 2, JSON output. Use `tests/fakes/vcs.py` for the fakes.
- `tests/test_quiet_sweeps.py`: new watch install tests next to the existing ones (dry run writes nothing and calls nothing; failed load removes the unit and the retry works on both platforms; uninstall with failing stop exits 0 and removes the unit). Update `test_mac_watch_installer_escapes_values_and_reports_service_failure` (its uninstall-failure tail now expects 0, warning text on stderr and no unit). Add the dead-watch attention tests here.
- Existing fixtures that expect empty attention or exact counts get a fresh `watch: clock` event: `tests/test_quiet_sweeps.py::test_nudges_show_current_conditions`, `::test_nudges_clear_pr_action_and_mcp_finding`, `::test_three_sweep_obligations_make_three_nudges`, `tests/test_signal_status.py::test_status_line_and_json_share_snapshot`, `::test_status_counts_escalation_from_current_state`. A prototype of change 3 run against the full suite failed exactly these five. In `tests/test_signal_status.py` the two fixtures also need an empty `.wuwei/config.toml` and complete event records (`payload` and `ts`), because `watch.health` reads the config and treats incomplete records as unmeasured. `tests/test_env_credentials.py::test_entry_paths[watch]` calls `watch.run` with a hand-built `Namespace` and gains `dry_run=False`.
- `tests/test_docs.py`: extend or add tests that extract the fenced verdict example from `reference.md` and assert `verdict.lint(example, quality=True, class_sweep=True)[0] == 0`; assert each `state.PHASES` row appears; assert `worktree add`, `stdin`, `--dry-run` phrases in the pages and `worktree add` in the plan skill.

## Must not change

`workspace.create_worktree`, `workspace.worktree_workspace`, `git_hook.install` and the shim text, `adapters/vcs/git.py`, `adapters/watch_service.py`, the watch templates, `watch.health`, `watch.sweep`, `obligations.sweep`, `signal.classify`, `state.PHASES`, `verdict.lint`, and the reserved state and event lists.
