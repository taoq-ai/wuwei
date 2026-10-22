import contextlib
import json

import pytest

from wuwei import ws


def test_ledger_chains_and_detects_a_rewrite(root):
    ws.record(root, 'ruling', {'text': 'always squash'})
    ws.record(root, 'attest', {'gate': 'quality'})
    assert ws.verify(root) == []
    path = root / ws.DIR / 'ledger' / f'{ws.clone(root)}.jsonl'
    path.write_text(path.read_text().replace('always squash', 'never squash'))
    assert ws.verify(root) == [f'ledger/{ws.clone(root)}.jsonl:1']


def test_config_keeps_only_the_six_keys(root):
    (root / ws.DIR / 'config.toml').write_text('repos = ["a/b"]\nretired_key = 3\n')
    assert ws.config(root) == {**ws.DEFAULTS, 'repos': ['a/b']}
    ws.write_config(root, ws.raw_config(root))
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


def test_a_linked_cache_folder_is_never_read_written_or_pruned(root, tmp_path_factory):
    outside = tmp_path_factory.mktemp('outside')
    (outside / 'pr-x.json').write_text('{"kept": 1}')
    (root / ws.DIR / 'cache').symlink_to(outside, target_is_directory=True)
    assert ws.cache_get(root, 'pr-x', float('inf')) is None
    ws.cache_prune(root, -1, 'pr-*')
    assert ws.cache_put(root, 'board', 1) == 1
    assert sorted(path.name for path in outside.iterdir()) == ['pr-x.json']


def test_a_linked_cache_entry_reads_as_absent_and_is_never_pruned_through(root, tmp_path_factory):
    outside = tmp_path_factory.mktemp('outside') / 'secret.json'
    outside.write_text('{"secret": 1}')
    ws.cache_put(root, 'board', None)
    (root / ws.DIR / 'cache' / 'pr-x.json').symlink_to(outside)
    assert ws.cache_get(root, 'pr-x', float('inf')) is None
    ws.cache_prune(root, -1, 'pr-*')
    assert outside.read_text() == '{"secret": 1}'


@pytest.mark.parametrize('name', ['../esc', 'a/../../esc', '..//esc', 'a/./../../esc', 'a/b/../../../esc', '%2e%2e/esc', '/esc'])
def test_a_name_never_leaves_the_cache_folder(root, name):
    (root / ws.DIR / 'esc.json').write_text('1')
    assert ws.cache_put(root, name, 2) == 2 and ws.cache_get(root, name, float('inf')) is None
    with contextlib.suppress(NotImplementedError):  # glob refuses an absolute pattern: nothing is deleted
        ws.cache_prune(root, -1, name)
    assert (root / ws.DIR / 'esc.json').read_text() == '1' and [p.name for p in root.rglob('esc.json')] == ['esc.json']
    assert not list((root / ws.DIR / 'cache').glob('**/esc.json')) and not (root.parent / 'esc.json').exists()


def test_a_cache_folder_linked_to_itself_reads_as_empty(root):
    (root / ws.DIR / 'cache').symlink_to('cache')
    assert ws.cache_put(root, 'board', 1) == 1 and ws.cache_get(root, 'board', float('inf')) is None
    ws.cache_prune(root, -1, '*')


@pytest.mark.parametrize('op', ['get', 'put', 'prune'])
def test_a_linked_workspace_folder_is_never_read_written_or_pruned(tmp_path, op):
    root, outside = tmp_path / 'ws', tmp_path / 'outside'
    (outside / 'cache').mkdir(parents=True)
    (outside / 'cache' / 'pr-x.json').write_text('"secret"')
    root.mkdir()
    (root / ws.DIR).symlink_to(outside, target_is_directory=True)
    got = {'get': lambda: ws.cache_get(root, 'pr-x', float('inf')), 'put': lambda: ws.cache_put(root, 'pr-x', 'planted'),
           'prune': lambda: ws.cache_prune(root, -1, 'pr-*')}[op]()
    assert got != 'secret' and (outside / 'cache' / 'pr-x.json').read_text() == '"secret"'


@pytest.mark.parametrize('link', ['entry', 'folder'])
def test_a_linked_clone_id_never_steers_the_ledger(root, tmp_path_factory, link):
    outside = tmp_path_factory.mktemp('outside')
    (outside / 'clone').write_text('../../escape\n')
    if link == 'folder':
        (root / ws.DIR / 'cache').symlink_to(outside, target_is_directory=True)
    else:
        (root / ws.DIR / 'cache').mkdir()
        (root / ws.DIR / 'cache' / 'clone').symlink_to(outside / 'clone')
    with pytest.raises(OSError, match='link'):
        ws.record(root, 'probe', {})
    assert not list(root.rglob('*.jsonl')) and not list(outside.rglob('*.jsonl')) and (outside / 'clone').read_text() == '../../escape\n'


def test_a_clone_id_that_is_no_plain_token_is_replaced_and_the_ledger_stays_in_its_folder(root):
    (root / ws.DIR / 'cache').mkdir()
    (root / ws.DIR / 'cache' / 'clone').write_text('../../escape\n')
    ws.record(root, 'probe', {})
    assert [p.parent for p in root.rglob('*.jsonl')] == [root / ws.DIR / 'ledger'] and ws.clone(root).isalnum()
