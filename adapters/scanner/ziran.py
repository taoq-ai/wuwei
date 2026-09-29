"""S4 JSON CLI boundary; incompatible ZIRAN versions remain unmeasured."""

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from wuwei.registry import Result, record_none


LEVELS = ('critical', 'high', 'medium', 'low')


def traces(file, *, root=None):
    return record_none('scanner', 'traces', root)


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
                or not isinstance(finding.get('check_id'), str)
                or not re.fullmatch(r'[A-Za-z0-9_.-]+', finding['check_id'])
                or not isinstance(finding.get('file_path'), str)
                or not re.fullmatch(r'[A-Za-z0-9_./ -]+\.[A-Za-z]+', finding['file_path'])
                or '..' in Path(finding['file_path']).parts
                or type(finding.get('line_number')) is not int or finding['line_number'] < 1
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


def audit(path, *, root=None):
    try:
        target = Path(path).resolve(strict=True)
        code, data = _execute(['ziran', 'audit', str(target), '--format', 'json'])
        _report(data)
        if code == 1 and not data['findings']:
            raise ValueError('nonzero audit without findings')
        return Result(int(bool(data['findings'])), data)
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
        return _unmeasured('audit', exc)


def gate(result, threshold, *, root=None):
    try:
        _report(result)
        if threshold not in LEVELS:
            raise ValueError('invalid severity threshold')
        with tempfile.TemporaryDirectory(prefix='wuwei-ziran-') as directory:
            report = Path(directory) / 'audit.json'
            report.write_text(json.dumps(result), encoding='utf-8')
            code, data = _execute(['ziran', 'ci', str(report), '--severity-threshold', threshold,
                                   '--format', 'json'])
        failed = any(LEVELS.index(f['severity']) <= LEVELS.index(threshold)
                     for f in result['findings'])
        if type(data.get('passed')) is not bool or data['passed'] != (code == 0) or code != int(failed):
            raise ValueError('inconsistent CI measurement')
        return Result(code, data)
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
        return _unmeasured('ci', exc)
