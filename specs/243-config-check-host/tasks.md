# Tasks: config check verifies the host protections and seat credential layout

Test first: every implementation task follows the test task that must fail before it.
Run tests with `python -m pytest -q <file>` from the repository root.

## Setup

- [X] T001 Reproduce read-only in a scratch workspace: `config check` exits 0 with a
  configured repository and `GH_TOKEN` in `.wuwei/env`, and calls only `gh auth status`.
- [X] T002 Write spec.md, plan.md and tasks.md.
- [X] T003 In `tests/conftest.py`, scrub `GH_TOKEN` and `GITHUB_TOKEN` in an autouse
  fixture; run the full suite and confirm it is still green before any other change.

## US3: the port reads what the check needs

- [X] T004 Test: in `tests/test_adapters.py` add `('code_host', 'token_scopes',
  ('variable',), True)` to `CALLS`; run it and see the contract tests fail.
- [X] T005 Implement: `cli/wuwei/registry.py` (`PARAMETERS['code_host']['token_scopes']`),
  `adapters/code_host/none.py` (`token_scopes`, unmeasured), a `token_scopes` stub in
  `adapters/code_host/github.py` that raises, and `tests/fakes/code_host.py`
  (`token_scopes`); T004 passes.
- [X] T006 Test: in `tests/test_code_host.py`, replay tests for `github.token_scopes`:
  argv is `['api', '--include', 'user', '--hostname', 'github.com']`; the child env
  passed to `subprocess.run` holds `GH_TOKEN` equal to the measured variable's value and
  no `GITHUB_TOKEN`; `X-OAuth-Scopes: repo, read:org` returns
  `{'scopes': ['repo', 'read:org']}`; a missing header, an empty header, a non-zero exit
  and an unsupported or unset variable are exit 2 and the token value is absent from the
  reason and stderr. Also a `_run` rejection case for `['api', '--include', 'user']`
  with a payload. Run and see them fail.
- [X] T007 Implement `token_scopes`, the `env` parameter, the `api --include user`
  allowlist case and the raw-stdout return in `adapters/code_host/github.py`; T006
  passes.
- [X] T008 Test: in `tests/test_merge_ports.py` add rules cases where `non_fast_forward`
  and `deletion` rules set `allow_force_pushes` and `allow_deletions` to false over a
  classic body that allows both; in `tests/fixtures/code_host/recordings.json` add
  `allow_force_pushes` and `allow_deletions` (`{"enabled": false}`) to the protection
  stdout and `false` to its data; in `tests/test_code_host.py` add a protection case
  missing `allow_deletions` (exit 2), a 404 with `gh: Not Found (HTTP 404)` (exit 2
  without `branch protection absent`); in `tests/test_shepherd.py:544-550` change the
  stderr to `gh: Branch not protected (HTTP 404)`. Run and see the new cases fail.
- [X] T009 Implement the two protection booleans, the two rule kinds and the narrowed
  404 check in `adapters/code_host/github.py`; T008 and the existing merge, shepherd and
  code_host tests pass.

## US1: host protections per repository

- [X] T010 Test in `tests/test_env_credentials.py` with the fake code_host and a
  `[[repos]]` entry for `acme/widget` on `main`:
  - `protection` returns exit 2 `branch protection absent`: exit 1, output names `main`
    and `protected ref: missing`;
  - `protection` returns exit 2 with another reason (permission): exit 2, output says
    `unmeasured`, the reason is on stderr;
  - a fully protected result: exit 0, five `ok` lines;
  - table cases, one gap each (no required checks, a `review_required_checks` name
    absent, approvals 0, force pushes allowed, deletions allowed): exit 1 and the
    matching `missing` line names `main` and the setting;
  - approvals 0 with `[shepherd] min_reviewers = 0`: exit 0 and the line names the solo
    owner exemption;
  - a malformed protection result (missing key): exit 2, unmeasured;
  - two repositories, one missing and one unmeasured: exit 2.
  Run and see them fail.
- [X] T011 Implement the `Host protections:` section and `_protection` in
  `cli/wuwei/commands/config.py`; T010 passes.
- [X] T012 Test: in `tests/test_workspace.py` `test_all_config_fields` expects
  `config check` exit 2 and `unmeasured` in stdout (its repos are not `owner/repo`);
  confirm it passes with T011 and that the other workspace config check tests still
  exit 0.

## US2: seat credentials

- [X] T013 Test in `tests/test_env_credentials.py` with the fake code_host:
  - `GH_TOKEN` in `.wuwei/env` with scopes `['repo']`: exit 1, output names `GH_TOKEN`
    and `.wuwei/env`, the value is absent from all output;
  - `GITHUB_TOKEN` in the process environment with scopes `['repo', 'workflow']`: exit
    1, output names `GITHUB_TOKEN` and the environment;
  - scopes `['read:org']`: exit 0, `read-only`;
  - `token_scopes` exit 2: exit 2, `unmeasured`;
  - neither set: exit 0, both `not set`, and the fake recorded no `token_scopes` call.
  Run and see them fail.
- [X] T014 Implement the `Seat credentials:` section and `_token` in
  `cli/wuwei/commands/config.py`; T013 passes.

## US4: init and docs

- [X] T015 Test in `tests/test_env_credentials.py`: a fresh `main(['init', <tmp>])`
  prints the layout (mentions a protected `default_branch`, `GH_TOKEN` and
  `wuwei config check`); `init --upgrade` output does not. Run and see it fail.
- [X] T016 Implement the `LAYOUT` print in `cli/wuwei/commands/init.py` (fresh init
  only); T015 passes.
- [X] T017 Test in `tests/test_docs.py`: `docs/site/configuration.md` names
  `Host protections`, `Seat credentials`, `ok`, `missing`, `unmeasured`, exits 0, 1 and
  2, and cites design 4.5 and 9.1. Run and see it fail.
- [X] T018 Write the subsection in `docs/site/configuration.md` and the one-sentence
  addition in `docs/site/adapters.md:56`; T017 passes.

## Polish

- [X] T019 Rerun the scratch reproduction from T001 (code_host `none` or a `gh` stub,
  never the real `gh`): it now exits non-zero and names `GH_TOKEN`.
- [X] T020 Run the full suite; check every changed file for em-dashes, emojis and
  absolute local paths.

## Review fixes

- [X] T021 (review F1) Test in `tests/test_env_credentials.py`: `GH_TOKEN` set in both
  the environment and `.wuwei/env` with different values reports `unmeasured` and exits
  2 without printing either value. Run and see it fail. Record shadowed names in
  `env.load` (`env._shadowed`) and report them unmeasured in `_token`; the test passes.

## Dependencies

T003 first. T004-T009 (port) before T010-T014 (config check uses the port and the fake).
T010-T012 before T013-T014 only because both edit `config.py`. T015-T018 are independent
of the port work.
