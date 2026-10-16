"""Every recorded case under tests/replay/ still gives the gaps it gave when it was recorded."""

import datetime
import json
from pathlib import Path
import shutil

import pytest

from conftest import make_pr, verdict_text, write_plan
from wuwei import evidence, gh, replay, ws

CASES = sorted(p.parent for p in (Path(__file__).parent / 'replay').glob('*/case.json'))


def replay_case(directory, scratch, monkeypatch):
    """The gaps a recorded case gives today, with the recorded clock and code-host answers."""
    case = json.loads((Path(directory) / 'case.json').read_text(encoding='utf-8'))
    root = Path(scratch) / 'workspace'
    shutil.copytree(Path(directory) / 'workspace', root)

    def answer(args, timeout=30):
        found = case['gh'].get(json.dumps(args))
        if found is None:
            raise AssertionError(f'the recorded case has no answer for gh {args}')
        if 'error' in found:
            raise gh.GhError(found['error'])
        return found['out']
    monkeypatch.setattr(gh, 'run', answer)
    monkeypatch.setattr(ws, 'now', lambda: datetime.datetime.fromisoformat(case['now']))
    return evidence.gaps(root, case['repo'], case['number']), case['expected']


@pytest.mark.parametrize('case', CASES, ids=[c.name for c in CASES])
def test_a_recorded_case_gives_the_same_gaps(case, tmp_path, monkeypatch):
    found, expected = replay_case(case, tmp_path, monkeypatch)
    keep = lambda gaps: [(g['text'], g['actionable'], g['owner']) for g in gaps]  # noqa: E731
    assert keep(found) == keep(expected)


def test_record_then_replay_round_trips(root, fake, tmp_path, monkeypatch):
    import hashlib
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light'}])
    fake.prs['42'] = make_pr(files=('src/app.py',))
    path = root / ws.DIR / 'verdicts' / 'I-1' / 'quality.md'
    path.parent.mkdir(parents=True)
    path.write_text(verdict_text())
    ws.record(root, 'attest', {'path': str(path.relative_to(root)), 'item': 'I-1', 'gate': 'quality',
                               'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    recorded = replay.record(root, 'acme/app', 42, tmp_path / 'case')
    assert [g['text'] for g in recorded] == ['no test in the diff']
    monkeypatch.undo()
    found, expected = replay_case(tmp_path / 'case', tmp_path / 'scratch', monkeypatch)
    assert found == expected == recorded


def test_no_runtime_module_defines_the_moved_or_folded_helpers():
    import re
    runtime = Path(__file__).parent.parent / 'cli' / 'wuwei'
    found = [f'{p.name}: {m[0]}' for p in sorted(runtime.glob('*.py'))
             for m in re.finditer(r'^def (?:replay|_list|items_named)\(', p.read_text(encoding='utf-8'), re.M)]
    assert found == []


def test_evidence_record_writes_the_case(root, fake, tmp_path, monkeypatch):
    from wuwei import __main__ as cli
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light'}])
    fake.prs['42'] = make_pr(files=('src/app.py',))
    monkeypatch.chdir(root)
    assert cli.main(['evidence', 'acme/app#42', '--record', str(tmp_path / 'case')]) == 1
    assert json.loads((tmp_path / 'case' / 'case.json').read_text())['number'] == 42
