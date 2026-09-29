"""S2 and S4 JSON CLI boundary; incompatible ZIRAN versions remain unmeasured."""

import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from wuwei.registry import Result, record_none


LEVELS = ('critical', 'high', 'medium', 'low')


def traces(file, *, root=None):
    try:
        target = Path(file).resolve(strict=True)
        _version()
        with tempfile.TemporaryDirectory(prefix='wuwei-ziran-') as directory:
            process = subprocess.run(['ziran', 'analyze-traces', '--source', 'otel',
                '--input', str(target), '--out', directory, '--format', 'json'],
                timeout=60, capture_output=True, text=True)
            if process.returncode not in (0, 1):
                raise ValueError(f'command exited {process.returncode}')
            data = json.loads((Path(directory) / 'trace_analysis.json').read_text(encoding='utf-8'))
        measured = _trace_report(data)
        if process.returncode != int(data['critical_chain_count'] > 0):
            raise ValueError('inconsistent trace measurement')
        return Result(process.returncode, measured)
    except (OSError, ValueError, TypeError, OverflowError, subprocess.SubprocessError) as exc:
        return _unmeasured('analyze-traces', exc)


def _trace_report(data):
    _object(data)
    metadata = data.get('metadata')
    _object(metadata)
    count, sessions = data.get('critical_chain_count'), metadata.get('sessions_analyzed')
    chains = data.get('dangerous_tool_chains')
    if (type(count) is not int or count < 0 or type(sessions) is not int or sessions < 1
            or not isinstance(chains, list)):
        raise ValueError('invalid trace measurement')
    findings, critical = [], 0
    for chain in chains:
        _object(chain)
        tools, risk, score = chain.get('tools'), chain.get('risk_level'), chain.get('risk_score')
        if (not isinstance(tools, list) or not tools or any(
                not isinstance(tool, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]+', tool) for tool in tools)
                or risk not in LEVELS or type(score) not in (int, float) or not math.isfinite(score)
                or not isinstance(chain.get('vulnerability_type'), str) or not chain['vulnerability_type']):
            raise ValueError('invalid trace chain')
        evidence = chain.get('evidence')
        _object(evidence)
        rows = evidence.get('sessions')
        if not isinstance(rows, list) or not rows:
            raise ValueError('missing trace session evidence')
        critical += int(risk == 'critical')
        for row in rows:
            _object(row)
            session, commands = row.get('session_id'), row.get('commands')
            if (not isinstance(session, str) or not session.strip() or len(session) > 2048
                    or not isinstance(commands, list) or any(not isinstance(c, str) for c in commands)):
                raise ValueError('invalid trace session evidence')
            if risk == 'critical':
                finding = {'chain': tools, 'risk_level': risk, 'session_id': session}
                if finding not in findings:
                    findings.append(finding)
    if count != critical:
        raise ValueError('inconsistent critical chain count')
    return {'sessions_analyzed': sessions, 'findings': findings}


def mcp(servers, *, root=None):
    return record_none('scanner', 'mcp', root)


def _unmeasured(operation, exc):
    reason = f'ziran {operation}: unmeasured: {type(exc).__name__}'
    if isinstance(exc, ValueError) and not isinstance(exc, (UnicodeError, json.JSONDecodeError)):
        reason += ': ' + str(exc)
    print(reason, file=sys.stderr)
    return Result(2, reason=reason)


def _object(data):
    if not isinstance(data, dict) or any(key in data for key in ('error', 'errors')):
        raise ValueError('invalid or error report')


def _report(data):
    _object(data)
    if (type(data.get('files_analyzed')) is not int or data['files_analyzed'] < 1
            or not isinstance(data.get('findings'), list)):
        raise ValueError('invalid or empty audit measurement')
    for finding in data['findings']:
        _object(finding)
        if (finding.get('severity') not in LEVELS
                or not isinstance(finding.get('rule'), str)
                or not re.fullmatch(r'[A-Za-z0-9_.-]+', finding['rule'])
                or not isinstance(finding.get('file'), str)
                or not re.fullmatch(r'[A-Za-z0-9_./ -]+\.[A-Za-z]+', finding['file'])
                or '..' in Path(finding['file']).parts
                or type(finding.get('line')) is not int or finding['line'] < 1
                or not isinstance(finding.get('message'), str) or not finding['message'].strip()
                or type(finding.get('trust_boundary', False)) is not bool):
            raise ValueError('invalid audit finding')
    return data


def _execute(argv):
    process = subprocess.run(argv, timeout=60, capture_output=True, text=True)
    if process.returncode not in (0, 1):
        raise ValueError(f'command exited {process.returncode}')
    data = json.loads(process.stdout)
    _object(data)
    return process.returncode, data


def _version():
    process = subprocess.run(['ziran', '--version'], timeout=60, capture_output=True, text=True)
    match = re.fullmatch(r'(?:ziran,? (?:version )?)([0-9]+)\.([0-9]+)\.([0-9]+)\s*',
                         process.stdout, re.I)
    if (process.returncode != 0 or not match
            or tuple(map(int, match.groups())) < (0, 39, 0)):
        raise ValueError('ZIRAN >= 0.39.0 required; version unavailable or unsupported')


def audit(path, *, root=None):
    try:
        target = Path(path).resolve(strict=True)
        _version()
        code, data = _execute(['ziran', 'audit', str(target), '--format', 'json',
                               '--severity', 'low'])
        _report(data)
        if code != int(bool(data['findings'])):
            raise ValueError('inconsistent audit measurement')
        return Result(code, data)
    except (OSError, ValueError, TypeError, OverflowError, subprocess.SubprocessError) as exc:
        return _unmeasured('audit', exc)


def gate(result, threshold, *, root=None):
    try:
        _report(result)
        if threshold not in LEVELS:
            raise ValueError('invalid severity threshold')
        failed = any(LEVELS.index(f['severity']) <= LEVELS.index(threshold)
                     for f in result['findings'])
        return Result(int(failed), {'passed': not failed})
    except (ValueError, TypeError) as exc:
        return _unmeasured('gate', exc)
