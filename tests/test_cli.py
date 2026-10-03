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
    parser = subparsers.add_parser("probe", help="Exercise the exit contract")
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
    assert "Exercise the exit contract" in result.stdout
    assert result.stdout.index("\nOther") < result.stdout.index("  probe ")
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


def test_shim_requires_python_311():
    assert "exec python3 -I -P -S -c " in (ROOT / "bin/wuwei").read_text()


@pytest.mark.parametrize("args, fast", [(["hook", "PreToolUse"], True), (["status", "--line"], True),
                                        (["--workspace", "/w", "hook", "PreToolUse"], True),
                                        (["--workspace", "/w", "status", "--line"], True),
                                        (["--version"], False)])
def test_hooks_and_status_line_skip_collector_and_teardown(tmp_path, args, fast):
    # #346: the per-call processes run without the cyclic collector and leave through
    # os._exit after atexit handlers and a flush; every other command exits as before.
    script = ("import atexit, gc, os, runpy, sys\n"
              "real = os._exit\n"
              "def fast(code):\n"
              "    print(f'fast exit {code} gc {gc.isenabled()}', file=sys.stderr)\n"
              "    real(code)\n"
              "os._exit = fast\n"
              "atexit.register(lambda: print('atexit ran', file=sys.stderr))\n"
              "sys.path[:0] = sys.argv[1:3]\n"
              "del sys.argv[1:3]\n"
              "runpy.run_module('wuwei', run_name='__main__', alter_sys=True)\n")
    payload = {**json.loads((ROOT / "tests/payloads/PreToolUse/bash.json").read_text()), "cwd": str(tmp_path)}
    env = {key: value for key, value in os.environ.items() if not key.startswith(("WUWEI_", "GIT_"))}
    result = subprocess.run([sys.executable, "-I", "-P", "-S", "-c", script, str(ROOT / "cli"), str(ROOT), *args],
                            input=json.dumps(payload), cwd=tmp_path, env=env, capture_output=True, text=True)
    lines = result.stderr.splitlines()
    assert "atexit ran" in lines, result.stderr
    if fast:
        assert lines[-1] == f"fast exit {result.returncode} gc False", result.stderr
    else:
        assert result.returncode == 0 and "fast exit" not in result.stderr, result.stderr


def test_shim_ignores_python_environment(plugin, tmp_path):
    shutil.copytree(ROOT / "bin", plugin / "bin")
    hostile = tmp_path / "hostile"
    (hostile / "wuwei").mkdir(parents=True)
    for name in ("wuwei/__init__.py", "wuwei/__main__.py", "json.py", "startup.py"):
        (hostile / name).write_text(
            'from pathlib import Path\n'
            f'Path({(Path(name).stem + ".ran")!r}).touch()\n'
            'raise RuntimeError("hostile code executed")\n'
        )
    userbase = tmp_path / "userbase"
    path = tmp_path / "path"
    path.mkdir()
    (path / "python3").symlink_to(sys.executable)
    venv = tmp_path / "hostile-venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin/python3").symlink_to(sys.executable)
    (venv / "pyvenv.cfg").write_text("include-system-site-packages = false\n")
    venv_site = venv / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
    venv_site.mkdir(parents=True)
    (venv_site / "hostile.pth").write_text(
        'import pathlib; pathlib.Path("venv.ran").touch()\n'
    )
    env = {**os.environ, "PATH": str(path) + os.pathsep + os.environ["PATH"],
           "PYTHONPATH": str(hostile), "PYTHONSTARTUP": str(hostile / "startup.py"),
           "PYTHONUSERBASE": str(userbase), "PYTHONINSPECT": "1",
           "PYTHONEXECUTABLE": str(venv / "bin/python3")}
    site = Path(subprocess.run(
        [sys.executable, "-S", "-c", "import site; print(site.getusersitepackages())"],
        env=env, capture_output=True, text=True, check=True, input="",
    ).stdout.strip())
    site.mkdir(parents=True)
    (site / "usercustomize.py").write_text(
        'from pathlib import Path\nPath("usercustomize.ran").touch()\n'
    )
    result = subprocess.run(
        [str(plugin / "bin/wuwei"), "--version"], cwd=tmp_path,
        env=env, capture_output=True, text=True, input="",
    )
    assert not list(tmp_path.glob("*.ran")), result.stderr
    assert result.returncode == 0, result.stderr
    version = json.loads((plugin / ".claude-plugin/plugin.json").read_text())["version"]
    assert result.stdout == version + "\n"
    assert result.stderr == ""


@pytest.mark.parametrize('args,code', [(('probe', 'clean'), 0),
                                      (('probe', '--help'), 0),
                                      (('--version',), 0)])
def test_dispatch_does_not_import_other_commands(plugin, args, code):
    (plugin / 'cli/wuwei/commands/unrelated.py').write_text(
        'raise RuntimeError("unrelated command imported")\n')
    result = run_cli(plugin, *args)
    assert result.returncode == code, result.stderr
    assert 'unrelated command imported' not in result.stderr


def test_hyphenated_command_dispatch_stays_lazy(plugin):
    commands = plugin / 'cli/wuwei/commands'
    probe = commands / 'probe.py'
    (commands / 'scan_probe.py').write_text(probe.read_text().replace('"probe"', '"scan-probe"'))
    probe.write_text('raise RuntimeError("unrelated command imported")\n')
    result = run_cli(plugin, 'scan-probe', 'clean')
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == ''


@pytest.mark.parametrize('candidate_exists', [False, True])
def test_dispatch_falls_back_to_discovery(plugin, candidate_exists):
    commands = plugin / 'cli/wuwei/commands'
    probe = commands / 'probe.py'
    source = probe.read_text()
    probe.write_text(source.replace('"probe"', '"scan-probe"'))
    if candidate_exists:
        (commands / 'scan_probe.py').write_text(source.replace('"probe"', '"other"'))
    result = run_cli(plugin, 'scan-probe', 'findings')
    assert result.returncode == 1, result.stderr
    assert result.stdout == result.stderr == ''


def test_issue_acceptance_grouped_help(capsys):
    import re
    from wuwei.__main__ import main
    names = lambda text: re.findall(r'^  ([a-z-]+) ', text, re.M)
    assert main(['--help']) == 0
    out = capsys.readouterr().out
    daily, owner, recovery = (out.index(f'\n{name}') for name in ('Daily', 'Owner', 'Recovery'))
    assert daily < out.index('\n  next ') < owner < out.index('\n  setup ') < recovery < out.index('\n  doctor ')
    assert '\nPlumbing' not in out and '\nOther' not in out and '{agents,' not in out
    assert not {'hook', 'event', 'git-hook', 'payload', 'signal', 'board'} & set(names(out))
    assert 'bin/wuwei --help --all' in out
    assert main(['-h']) == 0 and capsys.readouterr().out == out
    modules = {path.stem.replace('_', '-') for path in (ROOT / 'cli/wuwei/commands').glob('*.py')
               if not path.stem.startswith('_')}
    for argv in (['--help', '--all'], ['--all', '--help'], ['--all']):
        assert main(argv) == 0
        out = capsys.readouterr().out
        assert '\nPlumbing' in out
        assert sorted(names(out)) == sorted(modules)
