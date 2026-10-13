# Verification: 977-test-budget

## Budget and collection

- CI regex definitions: 3037 at branch baseline, 2809 after consolidation. The new regression test adds one definition before the reduction.
- Pytest items: 7859 at baseline, 7860 after consolidation. The extra item is the budget regression.
- Deleted exact duplicates: none.
- All original test bodies and parameter rows in changed files were compared against the branch baseline with AST. No assertion body or input row was lost.

## Commands and results

- Regression red: `1 failed, 15 deselected in 5.01s` with `assert 3038 < 2810`.
- CI regex count: `2809 test functions`.
- `../_pipeline/venv/bin/python -m pytest --collect-only -q -p no:cacheprovider tests/test_*.py`: `7860 tests collected in 5.63s`.
- `../_pipeline/venv/bin/python -m pytest -q -p no:cacheprovider tests/test_*.py`: `7860 passed in 466.76s (0:07:46)`.
- Source audit: `2354 original test bodies checked; 2809 CI regex definitions; 0 lost bodies or parameter rows`.
- `git diff --check`: clean. No runtime files changed, no new skips, and no local absolute paths in the feature artifacts.

## Per-file collected items

| File | Before | After |
|------|-------:|------:|
| `tests/test_adapters.py` | 107 | 107 |
| `tests/test_agent_launch.py` | 171 | 171 |
| `tests/test_brief.py` | 116 | 116 |
| `tests/test_build_next.py` | 87 | 87 |
| `tests/test_calibrate.py` | 70 | 70 |
| `tests/test_card_confirms.py` | 36 | 36 |
| `tests/test_close_branches.py` | 117 | 117 |
| `tests/test_code_host.py` | 267 | 267 |
| `tests/test_config_set.py` | 41 | 41 |
| `tests/test_config_transition.py` | 61 | 61 |
| `tests/test_derive.py` | 31 | 31 |
| `tests/test_dev_cycle.py` | 15 | 16 |
| `tests/test_dispatch.py` | 329 | 329 |
| `tests/test_doctor.py` | 106 | 106 |
| `tests/test_edges.py` | 318 | 318 |
| `tests/test_env_credentials.py` | 86 | 86 |
| `tests/test_fast_checks.py` | 41 | 41 |
| `tests/test_handback.py` | 46 | 46 |
| `tests/test_hooks.py` | 290 | 290 |
| `tests/test_hygiene.py` | 3 | 3 |
| `tests/test_integrity.py` | 91 | 91 |
| `tests/test_linear_loop.py` | 10 | 10 |
| `tests/test_loop.py` | 46 | 46 |
| `tests/test_merge.py` | 247 | 247 |
| `tests/test_merge_ports.py` | 16 | 16 |
| `tests/test_next.py` | 90 | 90 |
| `tests/test_outcome_metrics.py` | 19 | 19 |
| `tests/test_outward.py` | 575 | 575 |
| `tests/test_parallel_dispatch.py` | 28 | 28 |
| `tests/test_plan.py` | 131 | 131 |
| `tests/test_pr_actions.py` | 72 | 72 |
| `tests/test_pr_ownership.py` | 98 | 98 |
| `tests/test_protect_state.py` | 763 | 763 |
| `tests/test_reasons.py` | 16 | 16 |
| `tests/test_reference_adapters.py` | 36 | 36 |
| `tests/test_report_retro.py` | 24 | 24 |
| `tests/test_runtime.py` | 31 | 31 |
| `tests/test_sessions.py` | 12 | 12 |
| `tests/test_shell.py` | 425 | 425 |
| `tests/test_shepherd.py` | 95 | 95 |
| `tests/test_signal_status.py` | 98 | 98 |
| `tests/test_skill_evals.py` | 2 | 2 |
| `tests/test_spec_mode.py` | 40 | 40 |
| `tests/test_state.py` | 62 | 62 |
| `tests/test_traces.py` | 191 | 191 |
| `tests/test_tracker_adapters.py` | 41 | 41 |
| `tests/test_vcs.py` | 122 | 122 |
| `tests/test_vcs_guard.py` | 49 | 49 |
| `tests/test_verdict.py` | 279 | 279 |
| `tests/test_why.py` | 47 | 47 |
| `tests/test_workspace.py` | 180 | 180 |
| `tests/test_worktree_command.py` | 39 | 39 |
