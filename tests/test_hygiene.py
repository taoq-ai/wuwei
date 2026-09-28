"""Keep machine-specific absolute paths out of tracked text."""

from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile('|'.join((r'/Users/[^/]+/', r'/home/[^/]+/',
                               '/private/' + 'tmp/', '/tmp/' + 'claude',
                               r'C:\\' + r'Users\\')))


def test_tracked_text_has_no_machine_paths():
    try:
        paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT,
                                        stderr=subprocess.DEVNULL).split(b'\0')
    except subprocess.CalledProcessError:
        pytest.skip('not inside a git checkout')
    findings = []
    for raw in filter(None, paths):
        path = ROOT / raw.decode()
        if path == Path(__file__).resolve() or not path.is_file():
            continue
        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except UnicodeDecodeError:
            continue
        findings.extend(f'{path.relative_to(ROOT)}:{number}'
                        for number, line in enumerate(lines, 1) if PATTERN.search(line))
    assert not findings, '\n'.join(findings)


def test_hygiene_skips_its_own_source(monkeypatch):
    monkeypatch.setattr(subprocess, 'check_output',
                        lambda *args, **kwargs: b'tests/test_hygiene.py\0')
    test_tracked_text_has_no_machine_paths()


def test_hygiene_skips_outside_git_checkout(monkeypatch):
    def no_checkout(*args, **kwargs):
        raise subprocess.CalledProcessError(128, args[0])

    monkeypatch.setattr(subprocess, 'check_output', no_checkout)
    with pytest.raises(pytest.skip.Exception):
        test_tracked_text_has_no_machine_paths()
