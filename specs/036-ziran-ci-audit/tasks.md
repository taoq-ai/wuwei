# Tasks: ZIRAN role audit in CI

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Phase 1: Setup

- [X] T001 Read the generator, workflow, constitution and S1 contract; create
  `specs/036-ziran-ci-audit/spec.md` and `plan.md`.
- [X] T002 Inspect the v0.40.0 action/baseline contract and install the real
  release into a throwaway environment for baseline generation.

## Phase 2: Tests before baseline (US1 and US2)

- [X] T003 [US2] Write the version/agent/tool golden test in
  `tests/test_ziran_ci_audit.py`; confirm failure before baseline generation.
- [X] T004 [US1] Write the real clean/widened audit test in
  `tests/test_ziran_ci_audit.py`; confirm missing baseline fails with ZIRAN on PATH.

## Phase 3: US1 - Audit reviewed grants

- [X] T005 [US1] Generate `agents/ziran-baseline.json` using the real v0.40.0
  CLI, verify deterministic bytes and rerun the baseline and boundary tests.
- [X] T006 [US1] Add the pinned action to `.github/workflows/tests.yml`, preserve
  exit 1/2 failure, default SARIF and job permissions, and run the real tests there.

## Phase 4: US2 - Reviewed regeneration loop

- [X] T007 [US2] Document pinned installation, generation and baseline review in
  `agents/README.md` and `docs/site/security.md`.

## Phase 5: Verification

- [X] T008 Run the full prescribed pytest suite and inspect all changed files
  for whitespace, absolute local paths, em-dashes and emojis; record results here.

## Dependencies and execution

T001 -> T002 -> T003/T004 -> T005 -> T006 -> T007 -> T008.
US1's clean and widening cases share one parametrized external boundary test.
US2's offline golden is independent of scanner installation. Tests precede the
baseline they exercise. Documentation could run independently after T005, but
this small change is executed sequentially. No runtime implementation is needed.

## Validation evidence

- Red: golden test failed for missing baseline; with ZIRAN present, both real
  cases failed with exit 2 for the same missing baseline.
- F1 red: with ZIRAN 0.40.0 on PATH, the existing acceptance test reproduced
  `1 failed, 2 passed in 5.45s`: the widened builder had no CC001 row.
  Baseline application emits BL003 for new chains, including `Read -> WebFetch`.
- F1 green: require a builder BL003 row containing WebFetch, matching the pinned
  release's baseline contract. Golden, clean and widened audit tests pass:
  `3 passed in 5.33s`. T005 is complete.
- F2: document the scanner's required `agents` directory name at the copy site.
- Local installation: sandbox DNS prevented PyPI access. Built an offline wheel
  from the clean v0.40.0 tag (e0d1b8bf364fa2873a3af6940aff44de0e9fddeb),
  installed `ziran==0.40.0` in a throwaway venv and reused cached dependencies.
  No baseline data was handwritten. PyPI availability and hosted Actions execution
  cannot be verified from this sandbox; CI retains the requested PyPI pin.

- Determinism: a second real `--write-baseline` run produced identical bytes
  for nine agents and 56 dangerous chains.
- Action-equivalent audit: `--baseline`, `--severity high` and `--sarif` returned
  0 with valid SARIF 2.1.0. Missing baseline returned 2 during the red test.
- Workflow inspected with a YAML parser: both triggers, release/package pins,
  baseline path, high severity, job permissions, default SARIF and unsuppressed
  failure propagation match the issue.
- Pre-flight: no runtime, guard, parser, state producer or adapter changed;
  workspace scope, relevance, reserved state and core subprocess checks are
  inapplicable. The real-tool boundary has a 60-second timeout. Existing agent
  generation is reused. All nine changed/added files are ASCII and contain no
  absolute local paths; `git diff --check` passes.
- Full prescribed pytest run after F1/F2 with ZIRAN 0.40.0 on PATH:
  `4927 passed, 3 skipped in 97.55s (0:01:37)`.
  The three skips are existing performance checks under host load.
  No commit, push or hosted CI run.
