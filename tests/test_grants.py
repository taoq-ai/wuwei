"""#478: an owner-only action asks the owner on a decision card; the answer is the grant."""

import json
from types import SimpleNamespace

import pytest

from wuwei import grants, state, workspace


CONFIG = '''[[repos]]
name = "fixture-org/app"
path = "."
default_branch = "main"
merge_deploys = false
[deploy]
workflows = ["deploy-production.yml"]
'''
DEPLOY = 'gh workflow run deploy-production.yml -R fixture-org/app'


@pytest.fixture
def root(tmp_path, monkeypatch):
    from fakes.integrity import seed
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(CONFIG)
    seed(tmp_path)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-10-04T09:00:00Z')
    return tmp_path


def config(root):
    return workspace.load_config(root)


@pytest.mark.parametrize('rule,action', [
    ('release create', 'release'), ('tag push', 'release'), ('release API', 'release'),
    ('tag or branch ref API', 'release'), ('deploy.deny: make publish*', 'publish'),
    ('deploy.workflows', 'deploy'), ('environment branch push', 'deploy'), ('tofu apply', 'deploy'),
])
def test_action(rule, action):
    assert grants.action(rule) == action


def test_target(root, tmp_path_factory):
    outside = tmp_path_factory.mktemp('elsewhere')
    assert grants.target(root, config(root), str(outside), 'fixture-org/app') == 'repo:fixture-org/app'
    assert grants.target(root, config(root), str(root), None) == 'repo:fixture-org/app'
    assert grants.target(root, config(root), str(outside), None) is None
    assert grants.target(root, config(root), str(root), 'fixture-org/a b') is None
    assert grants.target(root, config(root), str(root), '$REPO') is None


def run(root, command=DEPLOY, **extra):
    from wuwei.guards import deploy
    return deploy.check({'cwd': str(root), 'tool_name': 'Bash', 'hook_event_name': 'PreToolUse',
                         'session_id': 'seat-1', 'agent_type': 'wuwei:builder',
                         'tool_input': {'command': command}, **extra})


def card_reason(identifier, posture='guarded', command=DEPLOY):
    return (f'publish: {command} on fixture-org/app is a deploy (deploy.workflows), owner-only under '
            f'{posture}; the owner decides: bin/wuwei decision show {identifier} --widget')


def records(root):
    return sorted(path.name for path in (workspace.day_dir(root) / 'decisions').glob('D-*.md'))


def events(root, kind):
    path = workspace.day_dir(root) / 'events.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    return [row['payload'] for row in rows if row['kind'] == kind]


def labels(root):
    from wuwei.commands import decision
    code, text = decision.show(SimpleNamespace(id='D-1', widget=True, full=False))
    assert code == 0, text
    return [option['label'] for option in json.loads(text)[0]['options']]


def test_refusal_writes_one_card(root):
    from wuwei import decision
    assert run(root) == (1, card_reason('D-1'))
    path = workspace.day_dir(root) / 'decisions/D-1.md'
    assert decision.lint(path.read_text())[0] == 0
    data = state.read_state(root)
    assert data['grants']['D-1'] == {
        'action': 'deploy', 'target': 'repo:fixture-org/app', 'rule': 'deploy.workflows',
        'command': DEPLOY, 'item': None, 'seat': 'wuwei:builder', 'planned': False,
        'answered': None, 'spent': False}
    assert 'D-1' in data['decision_routes']
    assert events(root, 'grant.asked')[0]['id'] == 'D-1'
    assert 'Allow deploy on fixture-org/app?' in path.read_text()
    assert run(root) == (1, card_reason('D-1')) and records(root) == ['D-1.md']
    assert labels(root) == ['Keep owner-only (Recommended)', 'Allow once', 'Allow today', 'Always allow']


def test_strict_card_offers_no_always(root):
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('[security]\nposture = "strict"\n')
    assert run(root) == (1, card_reason('D-1', 'strict'))
    assert labels(root) == ['Keep owner-only (Recommended)', 'Allow once', 'Allow today']


def test_no_card_for_heartbeat_or_host_rule(root):
    code, reason = run(root, session_id='wuwei-heartbeat')
    assert code == 1 and 'owner-only under guarded; ask the owner' in reason
    code, reason = run(root, 'terraform apply -auto-approve')
    assert code == 1 and 'the workspace permissions deny it' in reason
    assert not (workspace.day_dir(root) / 'decisions').exists()


LINE = '{action = "deploy", target = "repo:fixture-org/app", scope = "always", decision = "D-3", date = "2026-10-04"}'


def standing(root, line=LINE):
    (root / '.wuwei/config.toml').write_text(CONFIG + f'[grants]\nstanding = [{line}]\n')


def test_standing_config(root):
    assert config(root)['grants'] == {'standing': []}
    standing(root)
    assert config(root)['grants']['standing'] == [{
        'action': 'deploy', 'target': 'repo:fixture-org/app', 'scope': 'always', 'decision': 'D-3',
        'date': '2026-10-04'}]
    standing(root, LINE.replace('fixture-org/app', 'fixture-org/*'))
    assert config(root)['grants']['standing'][0]['target'] == 'repo:fixture-org/*'


@pytest.mark.parametrize('old,new', [
    ('repo:fixture-org/app', 'fixture-org/app'), ('D-3', 'X-1'), ('2026-10-04', 'today'),
    ('"deploy"', '"merge"')])
def test_standing_config_rejects(root, old, new):
    standing(root, LINE.replace(old, new))
    with pytest.raises(workspace.ConfigError, match='grants.standing.0'):
        config(root)


@pytest.fixture
def answer(monkeypatch):
    from wuwei import integrity
    from wuwei.commands import decision
    monkeypatch.setattr(integrity, '_host_confirm', lambda *args, **kwargs: True)
    return lambda root, option, identifier='D-1': decision.owner_outcome(
        SimpleNamespace(id=identifier, option=option), root=root)


def test_allow_today_until_close(root, answer):
    run(root)
    assert answer(root, 'Allow today') == (0, 'today')
    assert state.read_state(root)['grants']['D-1']['answered'] == 'today'
    assert run(root) == (0, '') and run(root) == (0, '')
    used = events(root, 'grant.used')
    assert len(used) == 2 and used[0]['decision'] == 'D-1' and used[0]['scope'] == 'today'
    state._write_state(lambda data: data.update(close_requested=True), root, reserved=False)
    assert run(root) == (1, card_reason('D-2'))


def test_allow_once(root, answer):
    run(root)
    assert answer(root, 'Allow once') == (0, 'once')
    assert run(root) == (0, '')
    assert state.read_state(root)['grants']['D-1']['spent'] is True
    assert [row['scope'] for row in events(root, 'grant.used')] == ['once']
    assert run(root) == (1, card_reason('D-2'))


@pytest.mark.parametrize('command', [
    'cd other && gh workflow run deploy-production.yml',
    'cd other && git push origin HEAD:production',
    'git -C other push origin HEAD:production',
    'GIT_DIR=other/.git git push origin HEAD:production',
    'git -c remote.origin.url=https://github.com/fixture-org/other.git push origin HEAD:production',
])
def test_grant_never_clears_a_command_that_moved(root, answer, command):
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('[environments]\nproduction = "prod"\n')
    run(root)
    answer(root, 'Allow today')
    assert run(root, 'gh workflow run deploy-production.yml') == (0, '')
    assert run(root, 'git push origin HEAD:production') == (0, '')
    assert run(root, command)[0] != 0
    assert len(events(root, 'grant.used')) == 2


def test_refused_compound_spends_no_grant(root, answer):
    run(root)
    answer(root, 'Allow once')
    code, _ = run(root, f'{DEPLOY} && gh workflow run deploy-production.yml -R fixture-org/other')
    assert code == 1
    assert state.read_state(root)['grants']['D-1']['spent'] is False
    assert events(root, 'grant.used') == []
    assert run(root) == (0, '')


def test_keep_owner_only(root, answer):
    run(root)
    assert answer(root, 'Keep owner-only') == (0, 'keep')
    code, reason = run(root)
    assert code == 1 and reason.endswith('the owner kept it owner-only (D-1): ask the owner to run it in a host terminal')
    assert records(root) == ['D-1.md']


def strict(root):
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('[security]\nposture = "strict"\n')


def test_always_allow(root, answer, monkeypatch):
    run(root)
    assert answer(root, 'Always allow') == (0, 'always')
    assert config(root)['grants']['standing'] == [{
        'action': 'deploy', 'target': 'repo:fixture-org/app', 'scope': 'always', 'decision': 'D-1',
        'date': '2026-10-04'}]
    monkeypatch.setenv('WUWEI_NOW', '2026-10-05T09:00:00Z')
    assert run(root) == (0, '')
    assert events(root, 'grant.used') == [{'decision': 'D-1', 'action': 'deploy', 'target': 'repo:fixture-org/app',
                                           'scope': 'always', 'session': 'seat-1', 'item': None}]
    strict(root)
    assert run(root) == (1, card_reason('D-1', 'strict'))


def test_always_allow_refused_under_strict(root, answer, capsys):
    run(root)
    strict(root)
    before = (root / '.wuwei/config.toml').read_text()
    code, _ = answer(root, 'Always allow')
    assert code == 1 and (root / '.wuwei/config.toml').read_text() == before
    assert 'not offered under strict' in capsys.readouterr().err
    assert state.read_state(root)['grants']['D-1']['answered'] is None


def cli(*args):
    from wuwei.__main__ import main
    return main(['grants', *args])


def test_grants_command(root, answer, capsys, monkeypatch):
    assert cli() == 0 and capsys.readouterr().out == 'No grants.\n'
    run(root)
    answer(root, 'Always allow')
    run(root, 'git push origin v1.2.0')
    answer(root, 'Allow once', 'D-2')
    capsys.readouterr()
    assert cli() == 0
    assert capsys.readouterr().out == ('1. deploy repo:fixture-org/app always (D-1, 2026-10-04)\n'
                                       'today: release repo:fixture-org/app once (D-2)\n')
    strict(root)
    assert cli() == 0
    assert '(D-1, 2026-10-04) (ignored under strict)' in capsys.readouterr().out
    assert cli('revoke', '2') == 1
    assert 'no standing grant 2' in capsys.readouterr().err
    assert cli('revoke', '1') == 0
    assert config(root)['grants']['standing'] == []
    assert events(root, 'grant.revoked') == [{'decision': 'D-1', 'action': 'deploy',
                                              'target': 'repo:fixture-org/app'}]
    assert run(root) == (1, card_reason('D-3', 'strict'))


def test_seat_cannot_revoke_or_set_grants(root):
    from wuwei.guards.protect_state import GUARD_CONFIG, check_bash
    payload = {'cwd': str(root), 'session_id': 'seat-1'}
    code, reason = check_bash({**payload, 'tool_input': {'command': 'bin/wuwei grants revoke 1'}})
    assert code == 1 and 'bin/wuwei grants revoke <n> in a host terminal' in reason
    code, reason = check_bash({**payload, 'tool_input': {'command': "bin/wuwei config set grants.standing '[]'"}})
    assert code == 1 and GUARD_CONFIG in reason
    assert check_bash({**payload, 'tool_input': {'command': 'bin/wuwei grants'}}) == (0, '')


@pytest.mark.parametrize('option,expected', [('Allow today', (0, '')), ('Ask when it happens', None)])
def test_planned_card_is_the_day_grant(root, answer, option, expected):
    from test_plan import deploying
    from wuwei import plan
    (root / '.wuwei/memory').mkdir()
    (root / '.wuwei/memory/goals.md').write_text(
        '# Goals\n## G-1\noutcome: Ship\nmeasure: shipped\ntarget: 1\ndate: 2026-10-30\npriority: 1\n')
    plan.propose(deploying(), root)
    answer(root, option)
    assert run(root) == (expected or (1, card_reason('D-2')))
    if expected:
        assert events(root, 'grant.used')[0]['decision'] == 'D-1'


MISSING = 'fast check "unit" has not passed for HEAD aaaaaaaaaaaa; run bin/wuwei build check DIV-1'
PUSH = 'git push origin HEAD:refs/heads/div-1'


def evidence(root, record=False, command=PUSH):
    payload = {'cwd': str(root), 'session_id': 'seat-1', 'agent_type': 'wuwei:builder',
               'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'tool_input': {'command': command}}
    return grants.evidence(payload, root, config(root), command.split(), MISSING, 'fixture-org/app',
                           record=record)


def posture(root, name):
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write(f'[security]\nposture = "{name}"\n')


@pytest.mark.parametrize('rule,action', [('evidence: ' + MISSING, 'evidence')])
def test_evidence_action(rule, action):
    assert grants.action(rule) == action


def test_evidence_warns_under_observe(root, capsys):
    # #530: a missing check warns under observe; the hook records it, a CLI caller records it here.
    posture(root, 'observe')
    assert evidence(root) == (1, MISSING)
    assert evidence(root, record=True) == (0, None)
    [event] = events(root, 'guard.would_refuse')
    assert (event['guard'], event['level'], event['reason']) == ('pr', 'warn', MISSING)
    assert 'warning: ' + MISSING in capsys.readouterr().err
    assert not (workspace.day_dir(root) / 'decisions').exists()


def test_evidence_refuses_under_strict(root):
    posture(root, 'strict')
    assert evidence(root) == (1, MISSING) and evidence(root, record=True) == (1, MISSING)
    assert not (workspace.day_dir(root) / 'decisions').exists()


def test_evidence_card_under_guarded(root, answer):
    code, reason = evidence(root)
    assert code == 1 and reason.startswith('publish: ') and 'bin/wuwei build check DIV-1' in reason
    assert reason.endswith('the owner decides: bin/wuwei decision show D-1 --widget')
    assert 'host terminal' not in reason
    text = (workspace.day_dir(root) / 'decisions/D-1.md').read_text()
    assert 'bin/wuwei build check DIV-1' in text and 'host terminal' not in text
    assert labels(root) == ['Defer until the check passes (Recommended)', 'Allow once', 'Allow today']
    assert state.read_state(root)['grants']['D-1']['action'] == 'evidence'
    assert answer(root, 'Allow once') == (0, 'once')
    code, use = evidence(root)
    assert code == 0 and state.read_state(root)['grants']['D-1']['spent'] is False
    use()
    assert state.read_state(root)['grants']['D-1']['spent'] is True
    # An evidence grant never lifts a deploy on the same repository.
    assert run(root)[0] == 1


def test_evidence_today_and_keep(root, answer):
    evidence(root)
    answer(root, 'Allow today')
    assert evidence(root)[0] == 0 and evidence(root)[0] == 0
    state._write_state(lambda data: data.update(close_requested=True), root, reserved=False)
    evidence(root)
    assert answer(root, 'Defer until the check passes', 'D-2') == (0, 'keep')
    code, reason = evidence(root)
    assert code == 1 and 'asked for the check first (D-2)' in reason
    assert 'bin/wuwei build check DIV-1' in reason and 'host terminal' not in reason


@pytest.mark.parametrize('command,step', [
    ('gh workflow run deploy-production.yml', 'so the owner can decide on a card'),
    ('git push origin', 'a publish step then asks the owner on a card')])
def test_refusal_names_the_seat_step_not_a_host_terminal(root, command, step):
    # #530: no repository target, or a call the deploy guard cannot inspect: the seat names the
    # repository or writes plain commands; the reason never sends it to a host terminal.
    import re
    code, reason = run(root, command, cwd='/')
    assert code in (1, 2) and step in reason, reason
    assert not re.search(r'host terminal|ask the owner|only the owner|by hand', reason), reason
