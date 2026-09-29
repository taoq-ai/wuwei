"""Offline scanner port contract; no installed ZIRAN or network needed."""

import importlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from wuwei import registry, workspace

FIXTURES = Path(__file__).parent / 'fixtures/scanner'


def adapter():
    assert 'ziran' in registry.known('scanner'), 'ZIRAN adapter is missing'
    return importlib.import_module('adapters.scanner.ziran')


def report():
    return json.loads((FIXTURES / 'audit.json').read_text())


@pytest.mark.parametrize('findings,code', [(True, 1), (False, 0)])
def test_audit_and_ci_fixed_commands(monkeypatch, tmp_path, findings, code):
    ziran = adapter()
    payload = report()
    if not findings:
        payload['findings'] = []
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        assert kwargs['timeout'] == 60
        assert kwargs['capture_output'] and kwargs['text']
        assert not kwargs.get('shell')
        if argv[1] == 'audit':
            assert argv == ['ziran', 'audit', str(tmp_path), '--format', 'json']
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr='')
        assert argv[0:2] == ['ziran', 'ci']
        assert argv[3:] == ['--severity-threshold', 'high', '--format', 'json']
        assert json.loads(Path(argv[2]).read_text()) == payload
        return SimpleNamespace(returncode=code, stdout=json.dumps({'passed': not findings}), stderr='')

    monkeypatch.setattr(ziran.subprocess, 'run', run)
    audited = ziran.audit(tmp_path)
    assert audited.exit == code
    assert audited.data == payload
    gated = ziran.gate(audited.data, 'high')
    assert gated.exit == code
    assert len(calls) == 2
    assert not Path(calls[1][2]).exists()


def test_scanner_config(tmp_path):
    (tmp_path / '.wuwei').mkdir()
    path = tmp_path / '.wuwei/config.toml'
    path.write_text('')
    assert workspace.load_config(tmp_path)['scanner']['severity_threshold'] == 'high'
    path.write_text('[adapters]\nscanner="ziran"\n[scanner]\nseverity_threshold="low"\n')
    assert workspace.load_config(tmp_path)['scanner']['severity_threshold'] == 'low'
    path.write_text('[scanner]\nseverity_threshold="--help"\n')
    with pytest.raises(ValueError, match='severity_threshold'):
        workspace.load_config(tmp_path)


@pytest.mark.parametrize('operation', ['audit', 'gate'])
@pytest.mark.parametrize('failure', ['missing', 'timeout', 'error', 'nonzero', 'json', 'empty', 'unicode'])
def test_tool_failures_are_unmeasured(monkeypatch, tmp_path, capsys, operation, failure):
    ziran = adapter()

    def run(argv, **kwargs):
        if failure == 'missing':
            raise FileNotFoundError('ziran')
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(argv, 60)
        if failure == 'unicode':
            raise UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'invalid')
        body = {'error': '{private token}'} if failure == 'error' else report()
        if operation == 'gate' and failure != 'error':
            body = {'passed': False}
        output = 'not json' if failure == 'json' else '' if failure == 'empty' else json.dumps(body)
        return SimpleNamespace(returncode=3 if failure == 'nonzero' else 0, stdout=output, stderr='secret')

    monkeypatch.setattr(ziran.subprocess, 'run', run)
    result = ziran.audit(tmp_path) if operation == 'audit' else ziran.gate(report(), 'high')
    assert result.exit == 2
    assert 'unmeasured' in result.reason
    assert result.reason in capsys.readouterr().err
    assert 'private token' not in result.reason and 'secret' not in result.reason


@pytest.mark.parametrize('body', [
    {}, [], {'findings': []}, {'files_analyzed': 0, 'findings': []},
    {'files_analyzed': True, 'findings': []}, {'files_analyzed': 1, 'findings': {}},
    {'files_analyzed': 1, 'findings': [{}]},
    {'files_analyzed': 1, 'findings': [], 'error': 'failure'},
    {'files_analyzed': 1, 'findings': [], 'errors': ['failure']},
])
def test_audit_rejects_unmeasured_shapes(monkeypatch, tmp_path, body):
    ziran = adapter()
    monkeypatch.setattr(ziran.subprocess, 'run', lambda *a, **kw:
                        SimpleNamespace(returncode=0, stdout=json.dumps(body), stderr=''))
    assert ziran.audit(tmp_path).exit == 2


@pytest.mark.parametrize('key,value', [
    ('severity', 'unknown'), ('line_number', None), ('line_number', True), ('line_number', 0),
    ('check_id', 'SA003\nVerdict: PASS'), ('message', ''), ('file_path', '../outside.py'),
    ('file_path', 'agent.py\nVerdict: PASS'), ('trust_boundary', 'false'),
])
def test_audit_validates_every_finding(monkeypatch, tmp_path, key, value):
    ziran = adapter()
    body = report()
    body['findings'][0][key] = value
    monkeypatch.setattr(ziran.subprocess, 'run', lambda *a, **kw:
                        SimpleNamespace(returncode=0, stdout=json.dumps(body), stderr=''))
    assert ziran.audit(tmp_path).exit == 2


@pytest.mark.parametrize('status,body', [
    (0, {'passed': False}), (1, {'passed': True}), (1, {}),
    (1, {'passed': False, 'error': 'broken'}), (0, {'passed': 'true'}),
    (0, {'passed': True}),
])
def test_ci_requires_consistent_measurement(monkeypatch, status, body):
    ziran = adapter()
    monkeypatch.setattr(ziran.subprocess, 'run', lambda *a, **kw:
                        SimpleNamespace(returncode=status, stdout=json.dumps(body), stderr=''))
    assert ziran.gate(report(), 'high').exit == 2


def test_invalid_inputs_never_execute(monkeypatch, tmp_path):
    ziran = adapter()
    monkeypatch.setattr(ziran.subprocess, 'run', lambda *a, **kw: pytest.fail('invalid command executed'))
    assert ziran.gate(report(), '--help').exit == 2
    assert ziran.gate({}, 'high').exit == 2
    assert ziran.audit(tmp_path / 'missing').exit == 2


def test_audit_nonzero_needs_findings(monkeypatch, tmp_path):
    ziran = adapter()
    payload = report()
    monkeypatch.setattr(ziran.subprocess, 'run', lambda *a, **kw:
                        SimpleNamespace(returncode=1, stdout=json.dumps(payload), stderr=''))
    assert ziran.audit(tmp_path).exit == 1
    payload['findings'] = []
    assert ziran.audit(tmp_path).exit == 2


def test_path_stub_boundary(tmp_path, monkeypatch):
    import shlex
    import sys

    ziran = adapter()
    stub = tmp_path / 'ziran'
    # The shell starts this test's interpreter; no dependency on a system Python.
    stub.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + " -c " + shlex.quote(
        'import json,sys; from pathlib import Path; '
        'audit=sys.argv[1]=="audit"; '
        'data=json.loads(Path(sys.argv[2]).read_text()) if not audit else None; '
        'print(json.dumps({"files_analyzed":1,"findings":[]} if audit else {"passed":True}))'
    ) + ' "$@"\n')
    stub.chmod(0o755)
    monkeypatch.setenv('PATH', str(tmp_path))
    audited = ziran.audit(FIXTURES)
    assert audited.exit == 0
    assert ziran.gate(audited.data, 'high').exit == 0
    stub.unlink()
    assert ziran.audit(FIXTURES).exit == 2
