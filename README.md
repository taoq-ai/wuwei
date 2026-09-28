# WUWEI

Autonomous delivery where the safe path is the default one.

WUWEI is a Claude Code plugin by TaoQ AI Labs. This foundation release provides
plugin metadata; delivery commands and agents will follow.

Install in Claude Code:

```text
/plugin marketplace add taoq-ai/wuwei
/plugin install wuwei@wuwei
```

For a local clone, replace `taoq-ai/wuwei` with the clone's absolute path.

Development requires Python 3.11+:

```sh
python -m pip install pytest
python -m pytest -q
```

Use conventional commits (`feat:`, `fix:`). Release-please opens release PRs on
`main` and updates `.claude-plugin/plugin.json`. GitHub Actions must be allowed
to create pull requests in repository settings. Python package installation is
not available in this scaffold.

See the [design](docs/specs/2026-09-24-wuwei-design.md).
Licensed under [Apache 2.0](LICENSE); see [NOTICE](NOTICE).
