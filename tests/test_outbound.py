"""Outbound tiers use in-process ports and never send during classification."""

import io
import json
import sys

import pytest

from fakes.code_host import Fake as CodeHost
from fakes.vcs import Fake as VCS
from wuwei import outward, registry, workspace
from wuwei.registry import Result


@pytest.fixture
def configured(tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('''
[owner]
name = "Pat Example"
pronouns = "they/them"
[[repos]]
name = "acme/app"
path = "repos/app"
default_branch = "main"
[outbound]
work_channels = ["Cwork", "Cshared", "Cclient"]
external_channels = ["Cshared", "Cclient"]
company_domains = ["acme.test"]
code_host_orgs = ["acme"]
[outbound.people."github:dev"]
email = "dev@acme.test"
org = "acme"
[outbound.people."slack:dev"]
email = "dev@acme.test"
[outbound.people."slack:U123"]
email = "dev@acme.test"
[outbound.people."slack:visitor"]
email = "visitor@elsewhere.test"
org = "outside"
''')
    from fakes.integrity import seed
    seed(tmp_path)
    vcs = VCS({'resolve': Result(0, {'sha': 'abc1234' + '0' * 33})})
    host = CodeHost({'pr': Result(0, {'repo': 'acme/app', 'number': 7, 'author': 'dev'}),
                     'reviews': Result(0, []),
                     'threads': Result(0, {'comments': [
                         {'id': 123, 'author': 'dev', 'body': 'Is the cache thread safe?'}], 'threads': []})})
    original = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: (
        {'vcs': vcs, 'code_host': host}[kind] if kind in ('vcs', 'code_host')
        else original(kind, config)))
    return tmp_path, vcs, host


def tier(configured, text, context=None, kind='chat'):
    root, _, _ = configured
    return outward.classify(text, root, workspace.load_config(root),
                            {'channel': 'Cwork'} if context is None else context, kind=kind)


@pytest.mark.parametrize('text,context,expected', [
    ('fixed in abc1234', {'channel': 'Cwork'}, (0, 'send')),
    ('fixed in abc1234', {'channel': 'Cwork', 'thread_ts': '1234567890.123456'}, (1, 'draft')),
    ('fixed in abc1234', {'channel': 'Cwork', 'thread': '1234567890.123456'}, (1, 'draft')),
    ('happy to give feedback on your performance review', {'channel': 'Cwork'}, (1, 'draft')),
    ("I'll add that in a follow-up", {'channel': 'Cwork'}, (1, 'draft')),
    ('Thanks!', {'channel': 'Cwork'}, (0, 'send')),
    ('ack', {'channel_id': 'Cwork'}, (0, 'send')),
    ('Tests passed.', {'channel': 'Cwork'}, (0, 'send')),
    ('Build failed.', {'channel': 'Cwork'}, (0, 'send')),
    ('The cache is thread safe.', {'channel': 'Cwork'}, (1, 'draft')),
    ('fixed in abc1234', {}, (1, 'draft')),
    ('Thanks', {'channel': 'unknown'}, (1, 'draft')),
    ('Thanks', {'channel': 'Cshared'}, (1, 'draft')),
    ('Thanks', {'channel': 'Cclient'}, (1, 'draft')),
    ('Thanks', {'channel': 'D123'}, (1, 'draft')),
    ('Thanks', {'channel': 'Cwork', 'channel_type': 'dm'}, (1, 'draft')),
    ('Thanks', {'channel': 'Cwork', 'is_dm': True}, (1, 'draft')),
    ('Thanks', {'channel': 'Cwork', 'is_shared': True}, (1, 'draft')),
    ('Thanks', {'channel': 'Cwork', 'is_connected': True}, (1, 'draft')),
    ('Thanks', {'channel': 'Cwork', 'is_client': True}, (1, 'draft')),
    ('Thanks', {'channel': 'Cwork', 'is_external': True}, (1, 'draft')),
    ('Thanks', {'channel': 'Cwork', 'recipient': 'DEV@ACME.TEST'}, (0, 'send')),
    ('Thanks', {'channel': 'Cwork', 'recipient': 'dev@acme.test.evil'}, (1, 'draft')),
    ('Thanks', {'channel': 'Cwork', 'recipient': 'nobody'}, (1, 'draft')),
    ('Thanks', {'channel': 'Cwork', 'recipients': ['dev', 'visitor']}, (1, 'draft')),
    ('Thanks', {'channel': 'Cwork', 'recipient_org': 'outside'}, (1, 'draft')),
    ('Thanks', {'channel': 'Cwork', 'channel_id': 'Cclient'}, (1, 'draft')),
    ('Thanks', {'channel': 'Cwork', 'is_dm': 'false'}, (2, 'draft')),
    ('Thanks', {'channel': 'Cwork', 'recipients': 'dev'}, (2, 'draft')),
    ('Thanks', {'channel': 'Cwork', 'approved': True}, (0, 'send')),
    ('Thanks', {'channel': 'Cwork', 'in_scope': True}, (0, 'send')),
    ('Thanks', {'channel': 'Cwork', 'issue_key': 'DEMO-12'}, (0, 'send')),
    ('Thanks', {'channel': 'Cwork', 'repo': 'Dashboard'}, (0, 'send')),
    ('', {'channel': 'Cwork'}, (1, 'draft')),
    (None, {'channel': 'Cwork'}, (2, 'draft')),
])
def test_acceptance_and_audience(configured, text, context, expected):
    assert tier(configured, text, context) == expected


@pytest.mark.parametrize('text', [
    'Thanks for the feedback', 'performance review complete', 'Compensation updated',
    'Hiring is done', 'My health is fine', 'Personal update', 'Legal approved',
    'HR is ready', 'Conflict resolved', 'I disagree', "You're wrong", 'I will fix it',
    "We can deliver tomorrow", 'Done by Friday', "I'll add that in a follow-up",
    'fixed in abc1234\nI will add more', 'Thanks; ship it', 'arbitrary prose',
    'Thanks @unknown', 'Thanks <@UNKNOWN>',
    'Thanks\u200b for the feedback', 'Thanks _feedback_',
])
def test_risky_or_unclassifiable_drafts(configured, text):
    assert tier(configured, text) == (1, 'draft')


@pytest.mark.parametrize('text,expected', [
    ('Thanks @dev', (0, 'send')), ('Thanks <@U123>', (0, 'send')),
    ('Thanks @visitor', (1, 'draft')), ('Thanks <@visitor>', (1, 'draft')),
])
def test_mentions_are_audience(configured, text, expected):
    assert tier(configured, text) == expected


@pytest.mark.parametrize('people,expected', [
    ({'dev': {'email': 'dev@acme.test'}}, 1),
    ({'slack:dev': {'email': 'dev@acme.test'}}, 1),
    ({'email:dev@acme.test': {'email': 'dev@acme.test'}}, 1),
    ({'github:dev': {'email': 'dev@acme.test'}}, 1),
    ({'github:dev': {'org': 'other'}}, 1),
    ({'github:dev': {'org': 'acme'}}, 0),
])
def test_code_host_identity_requires_namespace_and_matching_org(configured, people, expected):
    root, _, _ = configured
    config = workspace.load_config(root)
    config['outbound']['people'] = people
    config['outbound']['code_host_orgs'].append('other')
    assert outward.classify('Thanks', root, config, {'ref': 'acme/app#7'}, kind='code_host')[0] == expected


@pytest.mark.parametrize('people,expected', [
    ({'dev': {'org': 'acme'}}, 1),
    ({'github:dev': {'org': 'acme'}}, 1),
    ({'slack:dev': {'email': 'dev@acme.test'}}, 0),
])
def test_chat_identity_does_not_use_code_host_login(configured, people, expected):
    root, _, _ = configured
    config = workspace.load_config(root)
    config['outbound']['people'] = people
    assert outward.classify('Thanks @dev', root, config, {'channel': 'Cwork'})[0] == expected


def test_config_defaults_and_extensions(configured):
    root, _, _ = configured
    config = workspace.load_config(root)
    rules = config['outbound']
    assert 'feedback' in rules['sensitive_keywords']
    assert rules['commitment_patterns'] and rules['disagreement_patterns']
    rules['sensitive_keywords'].append('thanks')
    assert outward.classify('Thanks', root, config, {'channel': 'Cwork'}) == (1, 'draft')
    assert 'thanks' not in workspace.load_config(root)['outbound']['sensitive_keywords']
    config['outbound']['sensitive_keywords'] = []
    config['outbound']['sensitive_patterns'] = ['thanks']
    assert outward.classify('Thanks', root, config, {'channel': 'Cwork'}) == (1, 'draft')
    config['outbound']['sensitive_patterns'] = ['[']
    assert outward.classify('Thanks', root, config, {'channel': 'Cwork'}) == (2, 'draft')


@pytest.mark.parametrize('text,context,expected', [
    ('fixed in abc1234', {'ref': 'acme/app#7'}, (0, 'send')),
    ('Thanks', {'owner': 'acme', 'repo': 'app', 'pull_number': 7}, (0, 'send')),
    ('The cache is thread safe.', {'ref': 'https://github.com/acme/app/pull/7'}, (0, 'send')),
    ('The cache uses a lock.', {'ref': 'acme/app#7'}, (0, 'send')),
    ('The database uses a lock.', {'ref': 'acme/app#7'}, (1, 'draft')),
    ("I'll add that in a follow-up", {'ref': 'acme/app#7'}, (1, 'draft')),
    ('Thanks', {'ref': 'outside/app#7'}, (1, 'draft')),
    ('Thanks', {'ref': 'acme/unconfigured#7'}, (1, 'draft')),
    ('Thanks', {'ref': 'acme/app#7', 'recipient': 'visitor'}, (1, 'draft')),
    ('Thanks', {'channel': 'Cwork'}, (1, 'draft')),
    ('Thanks', {'ref': 'acme/app#7', 'owner': 'outside', 'repo': 'app', 'pull_number': 7}, (1, 'draft')),
])
def test_team_pr_scope(configured, text, context, expected):
    assert tier(configured, text, context, 'code_host') == expected


@pytest.mark.parametrize('operation,result,expected', [
    ('pr', Result(2, None, 'unavailable'), (2, 'draft')),
    ('pr', Result(1), (1, 'draft')),
    ('pr', Result(0, {}), (2, 'draft')),
    ('pr', Result(0, {'repo': 'outside/app', 'number': 7, 'author': 'dev'}), (2, 'draft')),
    ('pr', Result(0, {'repo': 'acme/app', 'number': 8, 'author': 'dev'}), (2, 'draft')),
    ('pr', Result(0, {'repo': 'acme/app', 'number': 7, 'author': 'visitor'}), (1, 'draft')),
    ('pr', Result(0, {'repo': 'acme/app', 'number': 7, 'author': None}), (1, 'draft')),
    ('threads', Result(2), (2, 'draft')),
    ('threads', Result(0, {}), (2, 'draft')),
    ('threads', Result(0, {'comments': [{'author': 'visitor', 'body': 'cache'}], 'threads': []}), (1, 'draft')),
    ('threads', Result(0, {'comments': [], 'threads': [{'comments': [{'author': 'unknown', 'body': 'cache'}]}]}), (1, 'draft')),
    ('threads', Result(0, {'comments': [], 'threads': []}), (1, 'draft')),
])
def test_pr_evidence_failures(configured, operation, result, expected):
    configured[2].results[operation] = result
    assert tier(configured, 'The cache is thread safe.', {'ref': 'acme/app#7'}, 'code_host') == expected


@pytest.mark.parametrize('code', [0, 1, 2])
def test_commit_resolution_preserved(configured, code):
    configured[1].results['resolve'] = Result(code, {'sha': 'abc1234' + '0' * 33})
    assert tier(configured, 'fixed in abc1234') == (code, 'draft' if code else 'send')


def test_restricted_tier_skips_external_reads(configured):
    assert tier(configured, 'fixed in abc1234', {'channel': 'Cwork', 'recipient': 'visitor'}) == (1, 'draft')
    assert not configured[1].calls and not configured[2].calls


def call(root, inputs, tool='mcp__slack__post_message'):
    return {'cwd': str(root), 'tool_name': tool, 'tool_input': inputs,
            'hook_event_name': 'PreToolUse', 'session_id': 'test',
            'transcript_path': str(root / 'transcript.jsonl'), 'tool_use_id': 'test'}


@pytest.mark.parametrize('tool,inputs,code', [
    ('mcp__slack__post_message', {'text': 'Thanks', 'channel': 'Cwork'}, 0),
    ('mcp__slack__send_dm', {'text': 'Thanks', 'channel': 'Cwork'}, 1),
    ('mcp__slack__send_direct_message', {'text': 'Thanks', 'channel': 'Cwork'}, 1),
    ('mcp__slack__post_message', {'text': 'Thanks', 'channel': 'Cwork', 'is_dm': True}, 1),
    ('mcp__linear__create_comment', {'body': 'fixed in abc1234', 'channel': 'Cwork'}, 1),
    ('mcp__linear__create_comment', {'body': 'fixed in abc1234', 'issue_id': 'issue'}, 1),
    ('mcp__github__add_issue_comment', {'body': 'Thanks', 'owner': 'acme', 'repo': 'app', 'issue_number': 7}, 0),
    ('mcp__slack__post_message', {'text': 'Thanks', 'channel': 'Cwork', 'body': "I'll add that"}, 1),
    ('mcp__slack__post_message', {'text': 'Thanks', 'channel': 'Cwork', 'draft': {'recipient': 'visitor'}}, 1),
    ('mcp__slack__post_message', {'draft': {'text': 'Thanks', 'channel': 'Cwork', 'recipient': 'visitor'}}, 1),
    ('mcp__slack__post_message', {'text': 'Thanks', 'channel': 'Cwork', 'draft': {'is_dm': True}}, 1),
    ('mcp__slack__post_message', {'text': 'Thanks', 'channel': 'Cwork', 'blocks': []}, 0),
    ('mcp__slack__post_message', {'text': 'Thanks', 'channel': 'Cwork', 'approved': True}, 0),
    ('mcp__slack__post_message', {'text': 'Thanks', 'channel': 'Cwork', 'is_shared': 'false'}, 2),
    ('mcp__unknown__send_message', {'text': 'Thanks', 'channel': 'Cwork'}, 2),
    ('Bash', {'command': 'for x in a; do echo "$x"; done'}, 0),
    ('Bash', {'command': 'python3 -m pytest -q'}, 0),
    ('Bash', {'command': 'export X=1'}, 0),
])
def test_guard_tiers_and_bypasses(configured, tool, inputs, code):
    from wuwei.guards.outward import check_tier as check
    result = check(call(configured[0], inputs, tool))
    assert result[0] == code
    if code == 1:
        assert result[1].startswith('outward: draft ') and 'bin/wuwei drafts show' in result[1]


@pytest.mark.parametrize('profile,expected', [('strict', 1), ('standard', 0)])
def test_tier_precedes_lint_and_preserves_it(configured, monkeypatch, profile, expected):
    root, _, _ = configured
    config = workspace.load_config(root)
    config['profile'] = profile
    config['outward']['max_length'] = {'slack': 3}
    assert outward.check_call({'text': 'Thanks', 'channel': 'Cwork'}, root, config, {'slack'})[0] == expected
    monkeypatch.setattr(outward, 'lint', lambda *a: pytest.fail('draft should not run lint'))
    assert outward.check_call({'text': 'Thanks', 'channel': 'Cclient'}, root, config, {'slack'})[0] == 1


@pytest.mark.parametrize('kind,operation,inputs,expected', [
    ('chat', 'post', {'channel': 'Cwork', 'text': 'Thanks', 'thread': None}, 0),
    ('chat', 'post', {'channel': 'Cwork', 'text': 'Thanks', 'thread': '1234567890.123456'}, 1),
    ('chat', 'dm', {'text': 'Thanks'}, 1),
    ('tracker', 'create', {'draft': {'title': 'Thanks'}}, 1),
    ('tracker', 'create', {'draft': {'title': 'Thanks', 'channel': 'Cwork'}}, 1),
    ('code_host', 'comment', {'ref': 'acme/app#7', 'text': 'Thanks', 'thread': 123}, 0),
    ('chat', 'post', {'channel': 'Cwork', 'text': "I'll add that", 'thread': None}, 1),
])
def test_port_policy_no_side_effects_on_refusal(configured, kind, operation, inputs, expected):
    performed = []
    # Keep the real decorator with the operation's actual signature, fake only its sink.
    functions = {
        'post': lambda channel, text, thread, root=None: performed.append(text) or Result(0),
        'dm': lambda text, root=None: performed.append(text) or Result(0),
        'create': lambda draft, root=None: performed.append(draft) or Result(0),
        'comment': lambda ref, text, thread, root=None: performed.append(text) or Result(0),
    }
    functions[operation].__name__ = operation
    result = registry.outward_operation(kind)(functions[operation])(**inputs, root=configured[0])
    assert result.exit == expected
    assert bool(performed) == (expected == 0)


@pytest.mark.parametrize('inputs,expected', [
    ({'text': 'Thanks', 'channel': 'Cwork'}, 0),
    ({'text': 'Thanks', 'channel': 'Cwork', 'recipient': 'visitor'}, 1),
    ({'kind': 'code_host', 'body': 'The cache is thread safe.', 'ref': 'acme/app#7'}, 0),
    ({'text': 'Thanks'}, 1),
    ({'text': 'Thanks', 'approved': True}, 1),
    ([], 2),
])
def test_cli_tier(configured, monkeypatch, capsys, inputs, expected):
    from wuwei.__main__ import main
    monkeypatch.chdir(configured[0])
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(inputs)))
    try:
        actual = main(['outbound', 'tier'])
    except SystemExit as exc:
        actual = exc.code
    assert actual == expected
    output = capsys.readouterr()
    assert json.loads(output.out) == {'tier': 'draft' if expected else 'send', 'exit': expected}
    assert 'Thanks' not in output.err
    if expected:
        assert output.err


@pytest.mark.parametrize('raw', ['{', 'null', '{"text": "Thanks", "text": "hidden"}'])
def test_cli_invalid_json(configured, monkeypatch, capsys, raw):
    from wuwei.__main__ import main
    monkeypatch.chdir(configured[0])
    monkeypatch.setattr(sys, 'stdin', io.StringIO(raw))
    try:
        code = main(['outbound', 'tier'])
    except SystemExit as exc:
        code = exc.code
    assert code == 2
    output = capsys.readouterr()
    assert json.loads(output.out)['tier'] == 'draft'
    assert output.err and raw not in output.err


@pytest.mark.parametrize('code', [0, 1, 2])
def test_hook_translation(configured, monkeypatch, capsys, code):
    from wuwei.commands.hook import run
    from types import SimpleNamespace
    inputs = {'text': 'Thanks', 'channel': 'Cwork'}
    if code == 1:
        inputs['recipient'] = 'visitor'
    if code == 2:
        inputs['is_shared'] = 'false'
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(call(configured[0], inputs))))
    assert run(SimpleNamespace(event='PreToolUse')) == (2 if code else 0)
    output = capsys.readouterr()
    if code:
        assert json.loads(output.out)['hookSpecificOutput']['permissionDecision'] == 'deny'
    else:
        assert output.out == output.err == ''


@pytest.mark.parametrize('location,expected', [('workspace', 1), ('repo', 1), ('outside', 0), ('target', 1)])
def test_guard_workspace_scope(configured, monkeypatch, tmp_path, location, expected):
    from wuwei.guards.outward import check_tier as check
    root, _, _ = configured
    outside = tmp_path / 'outside'
    root = root / 'managed'
    root.mkdir()
    (configured[0] / '.wuwei').rename(root / '.wuwei')
    repo = tmp_path / 'checkout'
    repo.mkdir()
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text().replace('repos/app', '../checkout'))
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    cwd = {'workspace': root, 'repo': repo, 'outside': outside, 'target': outside}[location]
    inputs = {'text': 'Thanks', 'channel': 'Cclient'}
    if location == 'target':
        inputs['repo'] = str(repo)
    assert check(call(cwd, inputs))[0] == expected


@pytest.mark.parametrize('kind', ['outward', 'pr'])
def test_anchored_worktree_scope(configured, monkeypatch, tmp_path, kind):
    from wuwei.guards import outward as outward_guard, pr
    root = configured[0] / 'managed'
    root.mkdir()
    (configured[0] / '.wuwei').rename(root / '.wuwei')
    tree = tmp_path / 'tree'
    tree.mkdir()
    gitdir = tmp_path / 'gitdir'
    gitdir.mkdir()
    (tree / '.git').write_text(f'gitdir: {gitdir}\n')
    (gitdir / 'wuwei-workspace').write_text(str(root) + '\n')
    if kind == 'pr':
        assert pr.check(call(tree, {'command': 'gh pr review --approve'}, 'Bash'))[0] == 1
    else:
        assert outward_guard.check_tier(call(tree, {'text': 'Thanks', 'channel': 'Cclient'}))[0] == 1


@pytest.mark.parametrize('evidence,expected', [('same', 1), ('different', 0), ('unavailable', 2)])
def test_outward_worktree_common_directory(configured, monkeypatch, tmp_path, evidence, expected):
    from wuwei.guards.outward import check_tier as check
    root, vcs, _ = configured
    root = root / 'managed'
    root.mkdir()
    (configured[0] / '.wuwei').rename(root / '.wuwei')
    tree = tmp_path / 'tree'
    tree.mkdir()
    (tree / '.git').write_text('gitdir: unused-by-core')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    common = str(root / 'repos/app/.git')

    def repo_context(path, root=None):
        if evidence == 'unavailable':
            return Result(2, None, 'unavailable')
        return Result(0, {'common_dir': str(tree / '.git')
                         if evidence == 'different' and path == str(tree) else common})

    monkeypatch.setattr(vcs, 'repo_context', repo_context)
    assert check(call(tree, {'text': 'Thanks', 'channel': 'Cclient'}))[0] == expected


@pytest.mark.parametrize('tool', ['mcp__sentry__search_issues', 'mcp__slack__post_message'])
def test_bad_target_outside_workspace_is_skipped(monkeypatch, tool):
    from pathlib import Path
    from wuwei.guards.outward import check_tier as check
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert check(call(Path('/tmp'), {'path': '~nosuchuser9/x'}, tool)) == (0, '')


def test_irrelevant_tool_does_not_compute_scope(configured, monkeypatch):
    from wuwei.guards import outward as guard
    monkeypatch.setattr(workspace, 'guard_scope', lambda *a: pytest.fail('irrelevant tool computed scope'))
    assert guard.check_tier(call(configured[0], {'path': '~nosuchuser9/x'},
                            'mcp__sentry__search_issues')) == (0, '')


@pytest.mark.parametrize('data', [None, {}, {'sha': 'bad'}, {'sha': 'd' * 40}])
def test_malformed_resolution_cannot_send(configured, data):
    configured[1].results['resolve'] = Result(0, data)
    assert tier(configured, 'fixed in abc1234') == (2, 'draft')


@pytest.mark.parametrize('thread,expected', [(123, 1), (456, 0), (999, 1)])
def test_technical_subject_belongs_to_target_thread(configured, thread, expected):
    configured[2].results['threads'] = Result(0, {'comments': [], 'threads': [
        {'id': 'database', 'comments': [{'id': 123, 'author': 'dev', 'body': 'database'}]},
        {'id': 'cache', 'comments': [{'id': 456, 'author': 'dev', 'body': 'cache'}]},
    ]})
    assert tier(configured, 'The cache is thread safe.',
                {'ref': 'acme/app#7', 'thread': thread}, 'code_host')[0] == expected


@pytest.mark.parametrize('channel_type', ['group', 'im', 'mpim', 'unknown'])
def test_unknown_or_direct_channel_types_draft(configured, channel_type):
    assert tier(configured, 'Thanks', {'channel': 'Cwork', 'channel_type': channel_type}) == (1, 'draft')


@pytest.mark.parametrize('extra', [
    {'owner': 'outside'}, {'repo': 'elsewhere'},
    {'owner': 'acme', 'repo': 'app', 'pull_number': 7, 'issue_number': 8},
])
def test_conflicting_pr_aliases_draft(configured, extra):
    assert tier(configured, 'Thanks', {'ref': 'acme/app#7', **extra}, 'code_host') == (1, 'draft')


@pytest.mark.parametrize('result,expected', [
    (Result(0, [{'author': 'visitor', 'body': 'Fine', 'state': 'approved'}]), 1),
    (Result(0, [{'author': 'unknown', 'body': '', 'state': 'changes_requested'}]), 1),
    (Result(0, [{'author': 'dev', 'body': 'Fine', 'state': 'approved'}]), 0),
    (Result(0, [{}]), 2), (Result(0, None), 2), (Result(2), 2),
])
def test_overall_reviewers_are_audience(configured, result, expected):
    configured[2].results['reviews'] = result
    assert tier(configured, 'Thanks', {'ref': 'acme/app#7'}, 'code_host')[0] == expected


@pytest.mark.parametrize('ref', ['app#7', '#7', 'acme/app/extra#7', 'acme/app#0'])
def test_malformed_pr_reference_drafts(configured, ref):
    assert tier(configured, 'Thanks', {'ref': ref}, 'code_host') == (1, 'draft')


@pytest.mark.parametrize('kind', [None, [], {}])
def test_malformed_transport_is_unrun(configured, kind):
    assert tier(configured, 'Thanks', kind=kind) == (2, 'draft')
