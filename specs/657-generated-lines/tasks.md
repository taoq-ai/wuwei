# Tasks: generated and data lines never count, and an analysis-only change gets one reviewer

Test first: each test task runs and fails for the expected reason before its implementation
task. Diffs come from the fake VCS through the `tiered` helper in `tests/test_dispatch.py`
(its `extra` argument continues the `[repos.gates]` table) and from the fake code host in
`tests/test_merge.py` (`case`, `config_change`); no test reaches git or the network. Run the
touched test files after each phase, then the full suite with `python -m pytest -q`.

## Phase 1: what never counts (FR-001, FR-005, FR-008; US1.5 to US1.8)

- [X] T001 Tests in `tests/test_merge.py`: a parametrized table on `merge.uncounted(root,
  settings, files)` with the `case` fixture's settings (`workspace.load_config(root)['repos'][0]`)
  and hand-built rows: `pilot/manifest.json` 4800 lines is `data`; `small/config.json` 10
  lines and one at exactly 200 lines are absent, 201 lines is `data`;
  `study/results/x.parquet` with `None` additions is `data`; `uv.lock` and
  `package-lock.json` are `generated`; `results/a.txt` with `size_exclude =
  ["results/*.txt"]` is `generated`; `corpus/runs/a/b.log` with `data_paths =
  ["corpus/runs/"]` under `[repos.gates]` is `data` and absent without it; a rename
  `src/run.txt` from `pilot/manifest.json` is absent; `src/app.py` is absent.
- [X] T002 Tests in `tests/test_merge.py`: with `repo/.gitattributes` holding
  `dist/* linguist-generated`, `dist/app.js` is `generated`; with
  `dist/* -linguist-generated` or `dist/* linguist-generated=false` it is absent; with the
  first file and a changed `.gitattributes` row in `files`, it is absent; with
  `repo/.gitattributes` a directory, `uncounted` raises `OSError`.
- [X] T003 Add `"data_paths": [(str, None)]` to `repos.gates` in `cli/wuwei/workspace.py`.
- [X] T004 Implement `LOCKFILES`, `DATA_SUFFIXES`, `DATA_LINES` and `uncounted` in
  `cli/wuwei/merge.py` (plan, Design). T001 and T002 pass.

## Phase 2: the merge cap counts the same lines (FR-004; US1.3, US1.4, US1.7)

- [X] T005 Tests in `tests/test_merge.py`: move cases 2 and 4 of
  `test_size_exclude_counts_only_the_files_it_does_not_match` to `.txt` paths (plan, Tests
  that change on purpose). Add: a 4800-line `pilot/manifest.json` beside the fixture's files
  and 200 source lines passes the cap (exit 0); with 600 source lines the check exits 1 and
  the reason contains `diff exceeds max changed lines: 600 count over 400 (4800 generated or
  data excluded)` (adjust the source count for the fixture's own lines); a 4800-line
  `deps/big.lock` still exits 1 with `never-auto path`; an unreadable `repo/.gitattributes`
  (a directory) exits 2.
- [X] T006 Replace the #615 sum in `merge.check` in `cli/wuwei/merge.py` with
  `uncounted` and the new refusal text. T005 passes.

## Phase 3: the tier counts the same lines and says so (FR-002, FR-003, FR-007; US1.1, US1.2, US3)

- [X] T007 Tests in `tests/test_dispatch.py`: `src/app.py` 200 lines plus
  `pilot/manifest.json` 4800 at floor `standard` records standard with the reason
  `5000 changed lines, 4800 generated or data excluded, 200 count, over light_max_lines 100`;
  `src/app.py` 80 plus the manifest at floor `light` records light, roles `['quality']`, and
  a reason ending `80 count, within light_max_lines 100`; `src/app.py` 3 plus
  `corpus/runs/r1.log` 3000 with `extra='data_paths = ["corpus/runs/"]\n'` records light, and
  without `extra` standard.
- [X] T008 Tests in `tests/test_dispatch.py`: `cli/wuwei/guards/pr.py` 2 lines (trust path)
  records `2 changed lines within light_max_lines 100` among its reasons; `src/app.py` plus
  a 4800-line `uv.lock` records standard with a reason starting `uv.lock matches never-auto path` and
  the excluded count; a `repo/.gitattributes` directory records standard with a reason starting
  `diff unmeasured:`.
- [X] T009 Implement the `tier()` changes in `cli/wuwei/dispatch.py` (plan, Design: `skip`,
  `excluded`, the binary rule, the size rule and its `elif`). T007 and T008 pass, and
  `test_size_and_binary_diffs_stay_standard` still passes unchanged.

## Phase 4: an analysis-only item gets one reviewer (FR-006; US2)

- [X] T010 Tests in `tests/test_dispatch.py`, all at floor `standard`: `docs/analysis.md`
  120, `study/results/scores.csv` 600 and `analysis/eval.ipynb` 69 record tier light, roles
  `['goal']`, reasons `['docs-only: 1 reviewer (goal)']`, and `dispatch.next_step` asks for
  the `goal` seat only (no `security`); `docs/analysis.md` plus a binary
  `study/results/x.parquet` records `['goal']`; `corpus/runs/r1.jsonl` 3000 with the
  `data_paths` entry records `['goal']`. Extend `test_code_or_trust_surface_keeps_three_gates`
  with the analysis diff under each lead flag, track FULL, floor `full`, plus
  `cli/wuwei/guards/pr.py`, plus `logo.png` binary, and a 300-line `.claude/settings.json`;
  each keeps the three roles.
- [X] T011 Implement `DOC_SUFFIXES` with `.ipynb` and `_docs_role(paths, data=())`, and pass
  the data paths from `tier()`, in `cli/wuwei/dispatch.py`. T010 passes.
- [X] T011a Review F1: a `.json` that is data only by suffix may be executable config, so
  `tier()` passes it to `_docs_role` only when `data_paths` names it. I34 adds a 250-line
  `.devcontainer/devcontainer.json` alone (three roles) and the same file under
  `data_paths` (goal).

## Phase 5: invariants and documents (FR-009)

- [X] T012 Tests in `tests/test_invariants.py`: extend `i34` with the document plus data
  case; add `i42`, `READS['I42'] = ()` and the `INVARIANTS` entry (plan, Invariants). Prove
  each bites: temporarily make `uncounted` return `{}` and see I42 fail, and drop `data`
  from `_docs_role` and see I34 fail; restore.
- [X] T013 Add the widened I34 text and the I42 row to the 9.2 table in
  `docs/specs/2026-09-24-wuwei-design.md`.
- [X] T014 Update `docs/site/configuration.md` (`repos.gates.data_paths` row,
  `size_exclude` and `light_max_lines` rows) and the Review tiers section of
  `docs/site/concepts.md`. `tests/test_docs.py` passes.

## Phase 6: verify

- [X] T015 Run `python -m pytest -q` from the repository root; everything passes. Check the
  changed files for em-dashes, emojis and absolute local paths.
