"""S2 and S4 JSON CLI boundary; incompatible ZIRAN versions remain unmeasured."""

import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from wuwei.registry import Result


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
    """One file per invocation; descriptions remain only in retained reports."""
    from wuwei import workspace

    measured = {'findings': [], 'reports': []}
    code, reasons = 0, []
    try:
        root = workspace.find_workspace() if root is None else Path(root).resolve()
        base = root / '.wuwei/ziran'
        if base.resolve() != base:
            raise ValueError('registry storage must not use symlinks')
        base.mkdir(exist_ok=True)
        timeout = workspace.load_config(root)['scanner']['mcp']['timeout_seconds']
        _version()
        for file in servers:
            # A failed run must not replace this file's approved baseline with what it saw.
            saved, snapshots = Path(tempfile.mkdtemp(prefix='snapshot-', dir=base)) / 'copy', None
            try:
                target = Path(file).resolve(strict=True)
                config = json.loads(target.read_text(encoding='utf-8'))
                _object(config)
                entries = config.get('mcpServers', config)
                if not isinstance(entries, dict) or any(not isinstance(v, dict) for v in entries.values()):
                    raise ValueError('invalid MCP config')
                key = hashlib.sha256(str(target).encode()).hexdigest()
                snapshots = base / 'snapshots' / key
                if snapshots.resolve() != snapshots:
                    raise ValueError('registry snapshots must not use symlinks')
                if snapshots.exists():
                    shutil.copytree(snapshots, saved)
                snapshots.mkdir(parents=True, exist_ok=True)
                output = Path(tempfile.mkdtemp(prefix='report-', dir=base))
                measured['reports'].append(str((output / 'registry-watch-report.json').relative_to(root)))
                process = subprocess.run(['ziran', 'watch-registry', '--from-claude-config', str(target),
                    '--snapshot-dir', str(snapshots), '--out', str(output), '--format', 'json'],
                    timeout=timeout, capture_output=True, text=True)
                if process.returncode not in (0, 1, 2):
                    raise ValueError(f'command exited {process.returncode}')
                data = json.loads((output / 'registry-watch-report.json').read_text(encoding='utf-8'))
                findings = _mcp_report(data)
                measured['findings'].extend(findings)
                high = any(row['severity'] in ('critical', 'high') for row in findings)
                if process.returncode != 2 and process.returncode != int(high):
                    raise ValueError('inconsistent registry measurement')
                code = max(code, process.returncode)
                if process.returncode == 2:
                    reasons.append('watch-registry: unmeasured: registry check incomplete (exit 2)')
                    _rollback(snapshots, saved)
            except (OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
                code = 2
                reasons.append(_unmeasured('watch-registry', exc).reason)
                if snapshots is not None:
                    _rollback(snapshots, saved)
            finally:
                shutil.rmtree(saved.parent, ignore_errors=True)
        return Result(code, measured, '; '.join(reasons))
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
        return _unmeasured('watch-registry', exc)


def _rollback(snapshots, saved):
    shutil.rmtree(snapshots, ignore_errors=True)
    if saved.exists():
        shutil.copytree(saved, snapshots)


def _mcp_report(data):
    if not isinstance(data, list):
        raise ValueError('invalid registry report')
    result = []
    for row in data:
        _object(row)
        if (row.get('drift_type') not in ('tool_added', 'tool_removed', 'description_changed',
                'schema_changed', 'permission_changed', 'typosquat', 'tool_poisoning')
                or row.get('severity') not in LEVELS
                or not isinstance(row.get('server_name'), str) or not row['server_name'].strip()
                or 'tool_name' not in row
                or row['tool_name'] is not None and not isinstance(row['tool_name'], str)):
            raise ValueError('invalid registry finding')
        result.append({key: row[key] for key in ('server_name', 'drift_type', 'severity', 'tool_name')})
    return result


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
