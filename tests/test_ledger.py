from wuwei import ws


def test_ledger_chains_and_detects_a_rewrite(root):
    ws.record(root, 'ruling', {'text': 'always squash'})
    ws.record(root, 'attest', {'gate': 'quality'})
    assert ws.verify(root) == []
    path = root / ws.DIR / 'ledger.jsonl'
    path.write_text(path.read_text().replace('always squash', 'never squash'))
    assert ws.verify(root) == [1]


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
