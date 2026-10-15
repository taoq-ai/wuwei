import json

from wuwei import ws


def test_ledger_chains_and_detects_a_rewrite(root):
    ws.record(root, 'ruling', {'text': 'always squash'})
    ws.record(root, 'attest', {'gate': 'quality'})
    assert ws.verify(root) == []
    path = root / ws.DIR / 'ledger' / f'{ws.clone(root)}.jsonl'
    path.write_text(path.read_text().replace('always squash', 'never squash'))
    assert ws.verify(root) == [f'ledger/{ws.clone(root)}.jsonl:1']


def test_config_keeps_only_the_five_keys(root):
    (root / ws.DIR / 'config.toml').write_text('repos = ["a/b"]\nretired_key = 3\n')
    assert ws.config(root) == {**ws.DEFAULTS, 'repos': ['a/b']}


def test_config_set_parses_lists_and_switches(root):
    ws.set_config(root, 'owner_paths', 'infra/**, .github/**')
    ws.set_config(root, 'telemetry', 'off')
    data = ws.config(root)
    assert data['owner_paths'] == ['infra/**', '.github/**'] and data['telemetry'] is False


def test_ledger_rows_carry_their_format_version(root):
    assert ws.record(root, 'note', {})['v'] == ws.FORMAT


def _row(kind, ts):
    row = {'v': 1, 'ts': ts, 'kind': kind, 'data': {}, 'prev': ws.GENESIS}
    return json.dumps({**row, 'hash': ws._digest(row)}) + '\n'


def test_each_clone_chains_its_own_ledger_file_and_reads_every_file(root):
    (root / ws.DIR / 'ledger.jsonl').write_text(_row('old', '2020-01-01T00:00:00+00:00'))
    (root / ws.DIR / 'ledger').mkdir()
    (root / ws.DIR / 'ledger' / 'feedbeef.jsonl').write_text(_row('theirs', '2030-01-01T00:00:00+00:00'))
    first = ws.record(root, 'mine', {})
    second = ws.record(root, 'mine', {})
    assert first['prev'] == ws.GENESIS and second['prev'] == first['hash']
    assert [r['kind'] for r in ws.ledger(root)] == ['old', 'mine', 'mine', 'theirs']
    assert ws.verify(root) == []
