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


def _append(root, n):
    for i in range(n):
        ws.record(root, 'seat.started', {'n': i})


def test_seats_starting_at_once_keep_one_chain(root):
    import multiprocessing
    ws.clone(root)
    procs = [multiprocessing.get_context('fork').Process(target=_append, args=(root, 25)) for _ in range(8)]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join()
    assert len(ws.ledger(root)) == 200
    assert ws.verify(root) == []


def _mine(root):
    path = root / ws.DIR / 'ledger' / f'{ws.clone(root)}.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def test_record_chains_past_a_last_line_that_is_not_a_row(root):
    bads = ('[1]', '5', 'null', '{"a": 1}', '{"hash": null}', '{"hash": 5}')
    for bad in bads:
        first = ws.record(root, 'note', {})
        with open(_mine(root), 'a', encoding='utf-8') as handle:
            handle.write(bad + '\n')
        assert ws.record(root, 'note', {})['prev'] == first['hash'], bad
    assert ws.verify(root) == [f'ledger/{_mine(root).name}:{3 * n + 2}' for n in range(len(bads))]


def test_readers_skip_rows_with_malformed_fields_and_verify_names_them(root):
    path = _mine(root)
    good = ws.record(root, 'note', {})
    bad = ['{"kind": [1]}', '{"ts": 5, "kind": "x"}', '{"ts": "2020-01-01", "kind": "note", "data": [1]}']
    with open(path, 'a', encoding='utf-8') as handle:
        handle.write('\n'.join(bad) + '\n')
    assert ws.ledger(root) == [good] and ws.rows(root, 'note') == [good] and ws.rows(root, 'x') == []
    assert ws.verify(root) == [f'ledger/{path.name}:{n}' for n in (2, 3, 4)]


def test_traces_skip_lines_that_are_not_rows(root):
    path = root / ws.DIR / 'traces.jsonl'
    path.write_text('[1]\n{"ts": 5}\nnot json\n{"ts": "2020-01-01T00:00:00+00:00", "tool": "Bash"}\n')
    assert ws.traces(root) == ws.traces(root, '2020-01-01') == [{'ts': '2020-01-01T00:00:00+00:00', 'tool': 'Bash'}]
    assert ws.traces(root, '2021-01-01') == []
