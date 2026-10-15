"""Every recorded case under tests/replay/ still gives the gaps it gave when it was recorded."""

from pathlib import Path

import pytest

from conftest import make_pr, verdict_text, write_plan
from wuwei import replay, ws

CASES = sorted(p.parent for p in (Path(__file__).parent / 'replay').glob('*/case.json'))


@pytest.mark.parametrize('case', CASES, ids=[c.name for c in CASES])
def test_a_recorded_case_gives_the_same_gaps(case, tmp_path, monkeypatch):
    found, expected = replay.replay(case, tmp_path, monkeypatch)
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
    found, expected = replay.replay(tmp_path / 'case', tmp_path / 'scratch', monkeypatch)
    assert found == expected == recorded
