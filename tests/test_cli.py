"""Exercise real CLI processes using commands installed only in a temporary plugin."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def plugin(tmp_path):
    root = tmp_path / "plugin with spaces"
    root.mkdir()
    shutil.copytree(ROOT / "cli", root / "cli")
    commands = root / "cli/wuwei/commands"
    (commands / "probe.py").write_text('''
from wuwei.exits import CLEAN, FINDINGS, UNRUN


def register(subparsers):
    parser = subparsers.add_parser("probe")
    parser.add_argument("action")
    parser.add_argument("--message", default="a command reason")
    parser.set_defaults(func=run)


def run(args):
    if args.action == "raise":
        raise RuntimeError(args.message)
    if args.action == "empty":
        raise RuntimeError()
    if args.action == "exit":
        raise SystemExit(0)
    if args.action == "interrupt":
        raise KeyboardInterrupt()
    return {"clean": CLEAN, "findings": FINDINGS, "unrun": UNRUN,
            "none": None, "bool": False, "outside": 3}[args.action]
''')
    shutil.copytree(ROOT / ".claude-plugin", root / ".claude-plugin")
    return root


def run_cli(plugin, *args):
    return subprocess.run(
        [sys.executable, "-S", "-m", "wuwei", *args],
        cwd=plugin.parent,
        env={**os.environ, "PYTHONPATH": str(plugin / "cli")},
        capture_output=True, text=True,
    )


@pytest.mark.parametrize("action,code", [("clean", 0), ("findings", 1), ("unrun", 2)])
def test_command_results(plugin, action, code):
    result = run_cli(plugin, "probe", action)
    assert result.returncode == code, result.stderr
    assert result.stdout == result.stderr == ""


@pytest.mark.parametrize("action,reason", [
    ("raise", "a command reason"), ("empty", "RuntimeError"),
    ("exit", "0"), ("interrupt", "KeyboardInterrupt"),
])
def test_command_exceptions(plugin, action, reason):
    result = run_cli(plugin, "probe", action)
    assert result.returncode == 2, result.stderr
    assert "probe" in result.stderr and reason in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""


def test_argument_converter_error(plugin):
    (plugin / "cli/wuwei/commands/probe.py").write_text('''
def convert(value):
    raise OSError("conversion failed")

def register(subparsers):
    parser = subparsers.add_parser("probe")
    parser.add_argument("value", type=convert)
''')
    result = run_cli(plugin, "probe", "value")
    assert result.returncode == 2, result.stderr
    assert result.stderr == "wuwei: conversion failed\n"


@pytest.mark.parametrize("action", ["none", "bool", "outside"])
def test_invalid_command_result(plugin, action):
    result = run_cli(plugin, "probe", action)
    assert result.returncode == 2, result.stderr
    assert "probe" in result.stderr and "invalid exit status" in result.stderr


@pytest.mark.parametrize("args", [(), ("missing",), ("probe",), ("probe", "clean", "--bad")])
def test_usage_errors(plugin, args):
    result = run_cli(plugin, *args)
    assert result.returncode == 2
    assert "usage:" in result.stderr


def test_help(plugin):
    result = run_cli(plugin, "--help")
    assert result.returncode == 0, result.stderr
    assert "probe" in result.stdout
    assert result.stderr == ""


def test_registration_error(plugin):
    (plugin / "cli/wuwei/commands/probe.py").write_text('raise RuntimeError("broken registration")\n')
    result = run_cli(plugin, "probe", "clean")
    assert result.returncode == 2
    assert "wuwei" in result.stderr and "broken registration" in result.stderr
    assert "Traceback" not in result.stderr


def test_private_command_module(plugin):
    (plugin / "cli/wuwei/commands/_common.py").write_text(
        'raise RuntimeError("helper must not be discovered")\n'
    )
    result = run_cli(plugin, "probe", "clean")
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == ""


def test_version(plugin):
    manifest = plugin / ".claude-plugin/plugin.json"
    data = json.loads(manifest.read_text())
    data["version"] = "9.8.7"
    manifest.write_text(json.dumps(data))
    result = run_cli(plugin, "--version")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "9.8.7\n"
    assert result.stderr == ""


@pytest.mark.parametrize("content", [None, '{"version": 1}', '{"version": ""}'])
def test_invalid_version_metadata(plugin, content):
    manifest = plugin / ".claude-plugin/plugin.json"
    if content is None:
        manifest.unlink()
    else:
        manifest.write_text(content)
    result = run_cli(plugin, "--version")
    assert result.returncode == 2
    assert "wuwei" in result.stderr
    assert "Traceback" not in result.stderr
    assert "unrecognized arguments" not in result.stderr
    assert "usage:" not in result.stderr
    assert result.stdout == ""


@pytest.mark.parametrize("args,code,output", [
    (("--version",), 0, ""),
    (("--help",), 0, "usage:"),
    (("missing",), 2, "invalid choice"),
    (("probe", "findings"), 1, ""),
    (("probe", "raise", "--message", "shim reason with spaces"), 2, "shim reason with spaces"),
])
def test_shim(plugin, args, code, output):
    shim = ROOT / "bin/wuwei"
    assert shim.is_file(), "bin/wuwei must exist"
    shutil.copytree(ROOT / "bin", plugin / "bin")
    result = subprocess.run(
        [str(plugin / "bin/wuwei"), *args],
        cwd=plugin.parent,
        env={**os.environ, "PYTHONPATH": "/unused/inherited/path"},
        capture_output=True, text=True,
    )
    assert result.returncode == code, result.stderr
    assert output in result.stdout + result.stderr
    if args == ("--version",):
        version = json.loads((plugin / ".claude-plugin/plugin.json").read_text())["version"]
        assert result.stdout == version + "\n"
        assert result.stderr == ""


@pytest.mark.parametrize("missing", ["python3", "cli", "dirname"])
def test_shim_missing_dependency(plugin, tmp_path, missing):
    shutil.copytree(ROOT / "bin", plugin / "bin")
    path = tmp_path / "path"
    path.mkdir()
    for name in ("dirname", "python3"):
        if name != missing:
            (path / name).symlink_to(shutil.which(name))
    if missing == "cli":
        shutil.rmtree(plugin / "cli")
    result = subprocess.run(
        [str(plugin / "bin/wuwei"), "--version"],
        cwd=plugin.parent,
        env={**os.environ, "PATH": str(path), "PYTHONPATH": ""},
        capture_output=True, text=True,
    )
    assert result.returncode == 2, result.stderr
    assert "wuwei:" in result.stderr
