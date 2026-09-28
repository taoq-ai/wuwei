# Tasks: Repository scaffold

## Setup

- [X] T001 Read main, design and constitution; create specs/001-scaffold/spec.md and plan.md.

## US1: Install the plugin

Independent test: JSON contract test plus Claude manifest validation.

- [X] T002 [US1] Write tests/test_manifest.py and confirm failure for missing manifests.
- [X] T003 [US1] Add .claude-plugin/plugin.json and .claude-plugin/marketplace.json; rerun test.
- [X] T004 [US1] Add full LICENSE, NOTICE and README.md installation stub.

## US2: Validate and release changes

Independent check: parse config, inspect matrix/updater, run pytest.

- [X] T005 [US2] Before configuration exists, check pyproject.toml and release/workflow files and confirm absence; define expected matrix 3.11/3.12 and updater $.version.
- [X] T006 [US2] Add pyproject.toml and .github/workflows/tests.yml using the manifest test as the initial suite.
- [X] T007 [US2] Add .github/workflows/release.yml, release-please-config.json and .release-please-manifest.json.

## Verification

- [X] T008 Validate .claude-plugin manifests and isolated installation; run full pytest and inspect configuration and prohibited characters in all added files.

## Dependencies and delivery

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008.
US1 is the installation MVP; US2 follows with CI and release automation.
License/README work could run independently of workflow configuration, but this
small feature is implemented sequentially. No parallel agents are required.

## Verification evidence

- Red: specified Python command failed with FileNotFoundError for plugin.json.
- Green: specified Python command reported `1 passed in 0.00s`.
- Both manifests passed `claude plugin validate` without warnings.
- Isolated CLAUDE_CONFIG_DIR: marketplace add and plugin install succeeded;
  plugin list reported wuwei@wuwei 0.1.0 enabled.
- TOML/JSON contract checks and ASCII scan passed; workflows inspected for
  matrix, triggers, permissions and updater settings.
- Hosted Actions and release PR creation were not executed locally.

## Adversarial review fixes

- [X] T009 [US2] Prefer RELEASE_PAT with GITHUB_TOKEN fallback so release PRs can trigger Tests.
- [X] T010 [US2] Start release state at 0.0.0 and update the spec assumptions.
- [X] T011 [US1] Reject undefined plugin keys and absent component paths, including path lists.
- [X] T012 [US2] Remove the unsupported dynamic Python version; retain dev extra and pythonpath.
- Regression checks added first: `4 failed, 1 passed`; after fixes: `5 passed`.
- Mutation check covers undefined keys and missing string/list paths for commands,
  agents, skills, hooks and mcpServers. Inline configurations remain supported.
- Hosted release behavior remains untested locally; RELEASE_PAT must be configured
  for release PRs to trigger Tests.
