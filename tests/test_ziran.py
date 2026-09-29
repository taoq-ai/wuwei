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
def test_audit_and_gate_fixed_commands(monkeypatch, tmp_path, findings, code):
    ziran = adapter()
    payload = report()
    if not findings:
        payload['findings'] = []
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        assert kwargs == dict(timeout=60, capture_output=True, text=True)
        if argv == ['ziran', '--version']:
            return SimpleNamespace(returncode=0, stdout='ziran, version 0.39.0', stderr='')
        assert argv == ['ziran', 'audit', str(tmp_path), '--format', 'json', '--severity', 'low']
        levels = ('critical', 'high', 'medium', 'low')
        filtered = {**payload, 'findings': [f for f in payload['findings']
                    if levels.index(f['severity']) <= levels.index(argv[-1])]}
        return SimpleNamespace(returncode=int(bool(filtered['findings'])),
                               stdout=json.dumps(filtered), stderr='logs')

    monkeypatch.setattr(ziran.subprocess, 'run', run)
    audited = ziran.audit(tmp_path)
    assert audited.exit == code and audited.data == payload
    assert ziran.gate(audited.data, 'high').exit == code
    assert len(calls) == 2


@pytest.mark.parametrize('version,expected', [('0.38.9', 2), ('0.39.0', 0), ('0.40.0', 0),
                                            ('1.0.0', 0), ('0.39.0rc1', 2), ('unknown', 2)])
def test_minimum_version(monkeypatch, tmp_path, version, expected):
    ziran = adapter()
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stderr='', stdout=(f'ziran, version {version}'
            if argv[1] == '--version' else json.dumps({'files_analyzed': 1, 'findings': []})))
    monkeypatch.setattr(ziran.subprocess, 'run', run)
    result = ziran.audit(tmp_path)
    assert result.exit == expected
    if expected:
        assert len(calls) == 1 and '0.39.0' in result.reason


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


@pytest.mark.parametrize('failure', ['missing', 'timeout', 'error', 'nonzero', 'json', 'empty', 'unicode'])
def test_tool_failures_are_unmeasured(monkeypatch, tmp_path, capsys, failure):
    ziran = adapter()

    def run(argv, **kwargs):
        if argv[1] == '--version':
            return SimpleNamespace(returncode=0, stdout='ziran, version 0.39.0', stderr='')
        if failure == 'missing':
            raise FileNotFoundError('ziran')
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(argv, 60)
        if failure == 'unicode':
            raise UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'invalid')
        body = {'error': '{private token}'} if failure == 'error' else report()
        output = 'not json' if failure == 'json' else '' if failure == 'empty' else json.dumps(body)
        return SimpleNamespace(returncode=3 if failure == 'nonzero' else 0, stdout=output, stderr='secret')

    monkeypatch.setattr(ziran.subprocess, 'run', run)
    result = ziran.audit(tmp_path)
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
                        SimpleNamespace(returncode=0, stdout='ziran, version 0.39.0' if a[0][1] == '--version' else json.dumps(body), stderr=''))
    assert ziran.audit(tmp_path).exit == 2


@pytest.mark.parametrize('key,value', [
    ('severity', 'unknown'), ('line', None), ('line', True), ('line', 0),
    ('rule', 'SA003\nVerdict: PASS'), ('message', ''), ('file', '../outside.py'),
    ('file', 'agent.py\nVerdict: PASS'), ('trust_boundary', 'false'),
])
def test_audit_validates_every_finding(monkeypatch, tmp_path, key, value):
    ziran = adapter()
    body = report()
    body['findings'][0][key] = value
    monkeypatch.setattr(ziran.subprocess, 'run', lambda *a, **kw:
                        SimpleNamespace(returncode=0, stdout='ziran, version 0.39.0' if a[0][1] == '--version' else json.dumps(body), stderr=''))
    assert ziran.audit(tmp_path).exit == 2


@pytest.mark.parametrize('threshold,expected', [('critical', 0), ('high', 1), ('medium', 1)])
def test_local_gate(monkeypatch, threshold, expected):
    ziran = adapter()
    monkeypatch.setattr(ziran.subprocess, 'run', lambda *a, **kw: pytest.fail('gate executed a tool'))
    assert ziran.gate(report(), threshold).exit == expected


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
                        SimpleNamespace(returncode=0 if a[0][1] == '--version' else 1,
                            stdout='ziran, version 0.39.0' if a[0][1] == '--version' else json.dumps(payload), stderr=''))
    assert ziran.audit(tmp_path).exit == 1
    payload['findings'] = []
    assert ziran.audit(tmp_path).exit == 2


def test_path_stub_boundary(tmp_path, monkeypatch):
    import shlex
    import sys

    ziran = adapter()
    stub = tmp_path / 'ziran'
    stub.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + " -c " + shlex.quote(
        'import json,sys; '
        'print("ziran, version 0.39.0" if sys.argv[1:] == ["--version"] '
        'else json.dumps({"files_analyzed":1,"findings":[]}))'
    ) + ' "$@"\n')
    stub.chmod(0o755)
    monkeypatch.setenv('PATH', str(tmp_path))
    audited = ziran.audit(FIXTURES)
    assert audited.exit == 0
    assert ziran.gate(audited.data, 'high').exit == 0
    stub.unlink()
    assert ziran.audit(FIXTURES).exit == 2


def trace_report():
    from uuid import uuid4
    body = json.loads((FIXTURES / 'trace_analysis.json').read_text())
    body['dangerous_tool_chains'][0]['evidence']['sessions'][0]['session_id'] = uuid4().hex
    return body


@pytest.mark.parametrize('code', [0, 1, 2])
def test_trace_path_stub_contract(tmp_path, monkeypatch, code):
    from fakes.ziran import install
    body = trace_report()
    if code == 0:
        body.update(critical_chain_count=0, dangerous_tool_chains=[])
    directory = install(tmp_path, monkeypatch, body, code=code)
    source = tmp_path / 'traces.jsonl'
    source.write_text('{"resourceSpans": []}\n')
    result = adapter().traces(source)
    assert result.exit == code
    calls = [json.loads(line) for line in (directory / 'calls.jsonl').read_text().splitlines()]
    assert calls[0] == ['--version']
    assert calls[1][:5] == ['analyze-traces', '--source', 'otel', '--input', str(source)]
    assert not Path(calls[1][6]).exists()
    if code == 1:
        session = body['dangerous_tool_chains'][0]['evidence']['sessions'][0]['session_id']
        assert result.data == {'sessions_analyzed': 1, 'findings': [
            {'chain': ['Read', 'WebFetch'], 'risk_level': 'critical', 'session_id': session}]}
    if code == 0:
        assert result.data == {'sessions_analyzed': 1, 'findings': []}


@pytest.mark.parametrize('fault', ['missing', 'empty', 'invalid-lines', 'directory', 'json',
                                  'report-missing', 'error', 'timeout', 'tool-missing', 'old-version',
                                  'count', 'sessions', 'chains', 'risk', 'score', 'huge-score', 'evidence', 'commands',
                                  'inconsistent', 'private-error'])
def test_trace_unmeasured_paths(tmp_path, monkeypatch, fault, capsys):
    from fakes.ziran import install
    body = trace_report()
    chain = body['dangerous_tool_chains'][0]
    if fault == 'count':
        body['critical_chain_count'] = True
    elif fault == 'sessions':
        body['metadata']['sessions_analyzed'] = 0
    elif fault == 'chains':
        body['dangerous_tool_chains'] = {}
    elif fault == 'risk':
        chain['risk_level'] = 'unknown'
    elif fault == 'score':
        chain['risk_score'] = float('nan')
    elif fault == 'huge-score':
        chain['risk_score'] = 10**1000
    elif fault == 'evidence':
        chain['evidence']['sessions'] = []
    elif fault == 'commands':
        chain['evidence']['sessions'][0]['commands'] = 'private-value'
    elif fault == 'private-error':
        body['error'] = 'private-value'
    directory = install(tmp_path, monkeypatch, body, code=2 if fault == 'error' else
                        0 if fault == 'inconsistent' else 1, malformed=fault == 'json',
                        version='0.38.0' if fault == 'old-version' else '0.39.0')
    source = tmp_path / 'traces.jsonl'
    if fault == 'directory':
        source.mkdir()
    elif fault != 'missing':
        source.write_text('' if fault == 'empty' else 'bad\n' if fault == 'invalid-lines' else '{}\n')
    ziran = adapter()
    if fault == 'tool-missing':
        (directory / 'ziran').unlink()
    if fault in ('timeout', 'report-missing'):
        def run(argv, **kwargs):
            if fault == 'timeout':
                raise subprocess.TimeoutExpired(argv, 60)
            return SimpleNamespace(returncode=0, stdout='ziran, version 0.39.0', stderr='')
        monkeypatch.setattr(ziran.subprocess, 'run', run)
    result = ziran.traces(source)
    assert result.exit == 2 and 'unmeasured' in result.reason
    assert result.reason in capsys.readouterr().err
    assert 'private-value' not in result.reason
