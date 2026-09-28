"""Check the repository's Claude Code installation contract."""

import json
from pathlib import Path
import re


def test_manifest():
    root = Path(__file__).resolve().parents[1]
    plugin = json.loads((root / ".claude-plugin/plugin.json").read_text())
    marketplace = json.loads((root / ".claude-plugin/marketplace.json").read_text())

    # https://code.claude.com/docs/en/plugins-reference#fields
    assert plugin.keys() <= {
        "$schema", "name", "displayName", "version", "description", "author",
        "homepage", "repository", "license", "keywords", "metadata",
        "defaultEnabled", "dependencies", "settings", "userConfig", "channels",
        "commands", "agents", "skills", "hooks", "mcpServers", "lspServers",
        "outputStyles", "workflows", "experimental",
    }
    for field in ("commands", "agents", "skills", "hooks", "mcpServers"):
        values = plugin.get(field, [])
        if not isinstance(values, list):
            values = [values]
        for value in values:
            if isinstance(value, str):
                assert value.startswith("./"), (field, value)
                path = (root / value).resolve()
                assert path.is_relative_to(root) and path.exists(), (field, value)

    assert plugin["name"] == "wuwei"
    assert re.fullmatch(r"\d+\.\d+\.\d+", plugin["version"])
    assert plugin["author"]["name"] == "TaoQ AI Labs"
    assert marketplace["name"] == "wuwei"
    assert marketplace["owner"]["name"] == "TaoQ AI Labs"
    assert len(marketplace["plugins"]) == 1
    entry = marketplace["plugins"][0]
    assert entry["name"] == plugin["name"]
    assert entry["source"] == "./"
    assert "version" not in entry
    assert (root / entry["source"] / ".claude-plugin/plugin.json").is_file()


def test_release_configuration():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/release.yml").read_text()
    assert "token: ${{ secrets.RELEASE_PAT || secrets.GITHUB_TOKEN }}" in workflow


def test_initial_release_state():
    root = Path(__file__).resolve().parents[1]
    assert json.loads((root / ".release-please-manifest.json").read_text()) == {".": "0.0.0"}


def test_release_pre_major_bump_options():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "release-please-config.json").read_text())
    package = config["packages"]["."]
    assert package.get("initial-version") == "0.1.0"
    assert package.get("bump-minor-pre-major") is True
    assert package.get("bump-patch-for-minor-pre-major", False) is False


def test_python_metadata():
    import tomllib

    root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((root / "pyproject.toml").read_text())
    assert "version" not in config["project"].get("dynamic", [])


def test_manifest_rejects_invalid_references(monkeypatch):
    import pytest

    read_text = Path.read_text
    for field in ("undefined", "commands", "agents", "skills", "hooks", "mcpServers"):
        for value in ("./missing-component", ["./missing-component"]):
            def mutated(path, *args, **kwargs):
                content = read_text(path, *args, **kwargs)
                if path.name == "plugin.json":
                    plugin = json.loads(content)
                    plugin[field] = value
                    return json.dumps(plugin)
                return content

            monkeypatch.setattr(Path, "read_text", mutated)
            with pytest.raises(AssertionError):
                test_manifest()
