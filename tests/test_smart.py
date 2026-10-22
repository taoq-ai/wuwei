"""The smart tier (item smart-tier): the lead's Cynefin domain sets each item's gates, measured signals at the head raise them."""
import json

import pytest

from conftest import HEAD, make_pr, write_plan
from test_evidence import attest, forget, texts
from wuwei import evidence, guards, plan, ws

BASE = 'c' * 40
PLAIN = '@@ -1,4 +1,6 @@ def run(x):\n     if x == 0:\n+    if x == 9:\n+        return 9\n     return 0'


def branchy(n, name='run'):
    """A function with n decision nodes (n if statements)."""
    return f'def {name}(x):\n' + ''.join(f'    if x == {i}:\n        return {i}\n' for i in range(n)) + '    return -1\n'


def smart(root, domain='clear: one module, a known fix with a known answer', **extra):
    write_plan(root, [{'id': 'I-1', 'title': 'change', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'smart', 'domain': domain, **extra}])


def pr_with(fake, changed):
    """PR 42 at HEAD on base BASE; changed maps a path to (patch, text at the base or None, text at the head or None)."""
    pr = make_pr(files=tuple(changed))
    pr['baseRefOid'] = BASE
    for f in pr['files']:
        patch, was, now = changed[f['path']]
        f['patch'] = patch
        fake.files.update({f'{f["path"]}@{ref}': text for ref, text in ((BASE, was), (HEAD, now)) if text is not None})
    fake.prs['42'] = pr
    return pr


TESTS = {'tests/test_app.py': ('@@ -1,2 +1,3 @@\n+def test_run():\n+    assert run(9) == 9', '', 'def test_run():\n    assert True\n')}


def owed(root):
    return [t for t in texts(evidence.gaps(root, 'acme/app', 42)) if t.startswith('gates missing')]


def test_acceptance_1_a_clear_item_on_plain_code_owes_only_quality(root, fake):
    smart(root)
    pr_with(fake, {'src/app.py': (PLAIN, branchy(3), branchy(4)), **TESTS})
    assert owed(root) == ['gates missing at head aaaaaaa: quality']
    attest(root, 'quality')
    assert evidence.gaps(root, 'acme/app', 42) == []


def test_acceptance_2_a_clear_item_whose_branch_raises_complexity_on_a_risky_path_owes_security(root, fake):
    smart(root)
    pr_with(fake, {'src/token.py': (PLAIN, branchy(9), branchy(10)), **TESTS})
    assert owed(root) == ['gates missing at head aaaaaaa: quality, security']


@pytest.mark.parametrize('was,now,gates', [
    (branchy(9), branchy(10), 'quality, security'),  # rises to McCabe's 10 (complexity 11)
    (branchy(3), branchy(9), 'quality'),  # rises, still under the threshold
    (branchy(12), branchy(12), 'quality'),  # complex already, not raised
    (branchy(12), branchy(13), 'quality, security'),
    (None, branchy(10), 'quality, security'),  # a new file: every function is new
    (branchy(9), None, 'quality, security'),  # the head unread: unmeasured is never clean
    (branchy(9), branchy(9) + 'def broken(:\n', 'quality, security'),  # the head does not parse
    (branchy(9), branchy(10, 'run') + branchy(0, 'run'), 'quality, security'),  # a second def of the name hides nothing
    (branchy(3), 'class A:\n' + branchy(10).replace('\n', '\n    ').replace('def run(x)', '    async def run(x)'), 'quality, security'),
])
def test_a_complexity_rise_read_with_ast_raises_security_off_risky_paths(root, fake, was, now, gates):
    smart(root)
    pr_with(fake, {'src/app.py': (PLAIN, was, now), **TESTS})
    assert owed(root) == [f'gates missing at head aaaaaaa: {gates}']


@pytest.mark.parametrize('node', [
    '    y = 1 if x == {i} else 0\n',
    '    for _ in x:\n        pass\n',
    '    async for _ in x:\n        pass\n',
    '    while x == {i}:\n        break\n',
    '    try:\n        pass\n    except E{i}:\n        pass\n',
    '    assert x != {i}\n',
    '    y = x and {i}\n',
    '    y = [a for a in x]\n',
    '    match x:\n        case {i}:\n            pass\n',
])
def test_every_decision_node_counts_toward_the_complexity_rise(root, fake, node):
    smart(root)
    pr_with(fake, {'src/app.py': (PLAIN, 'async def run(x):\n    return -1\n',
                                  'async def run(x):\n' + ''.join(node.format(i=i) for i in range(10))), **TESTS})
    assert owed(root) == ['gates missing at head aaaaaaa: quality, security']


def test_a_head_too_deep_to_parse_counts_as_a_rise(root, fake, monkeypatch):
    def deep(*args, **kwargs):
        raise RecursionError('maximum recursion depth exceeded during compilation')
    monkeypatch.setattr(evidence.ast, 'parse', deep)
    smart(root)
    pr_with(fake, {'src/app.py': (PLAIN, branchy(1), branchy(2)), **TESTS})
    assert owed(root) == ['gates missing at head aaaaaaa: quality, security']

def test_a_complexity_read_without_a_head_sha_counts_as_a_rise(root, fake):
    smart(root)
    files = [{'path': 'src/app.py', 'additions': 2, 'deletions': 0, 'patch': PLAIN}]
    assert evidence.needed(root, 'smart', files, plan.find(root, 'I-1'), lambda: evidence.rose('acme/app', {}, files)) == (
        'quality', 'security')
    assert not [c for c in fake.calls if '/contents/' in ' '.join(c)]  # no default branch read stands in for a head


def test_acceptance_3_a_complicated_item_that_changes_what_a_guard_waives_owes_arch(root, fake):
    smart(root, 'complicated: two modules and a rule; experts can work it out')
    waive = '@@ -10,3 +10,4 @@ def excepted(root, ref, head, found):\n     kept = []\n+    kept += found\n     return kept'
    pr_with(fake, {'src/app.py': (waive, branchy(1), branchy(1)), **TESTS})
    assert owed(root) == ['gates missing at head aaaaaaa: arch, quality']


@pytest.mark.parametrize('patch', [
    '@@ -1,3 +1,3 @@ def door(cmd):\n-    return deny(cmd)\n+    return None',
    "@@ -3,2 +3,2 @@\n-        return {'decision': 'ask'}\n+        return {'decision': 'allow'}",
    '@@ -39,2 +39,2 @@\n PROCESS = re.compile(r"^(specs/|"\n-    r"|open [0-9]+ days")\n+    r"|open [0-9]+ days|CI")',
    '@@ -1,2 +1,2 @@\n-WAIVED = 1\n+WAIVED = 2',

    '@@ -1,1 +1,1 @@\n-x = 1\n+x = deny',
    '@@ -1,1 +1,1 @@\n-x = 1\n+x = denied',
    '@@ -1,1 +1,1 @@\n-x = 1\n+x = refuse',
    '@@ -1,1 +1,1 @@\n-x = 1\n+x = refused',
    '@@ -1,1 +1,1 @@\n-x = 1\n+x = refuses',
    '@@ -1,1 +1,1 @@\n-x = 1\n+x = ask',
    '@@ -1,1 +1,1 @@\n-x = 1\n+x = allow',
    '@@ -1,1 +1,1 @@\n-x = 1\n+x = allowed',
    '@@ -1,1 +1,1 @@\n-x = 1\n+x = allows',
    '@@ -1,1 +1,1 @@\n-x = 1\n+x = waive',
    '@@ -1,1 +1,1 @@\n-x = 1\n+x = waived',
    '@@ -1,1 +1,1 @@\n-x = 1\n+x = waives',
    '@@ -1,1 +1,1 @@\n-x = 1\n+x = excepted',
    '@@ -1,1 +1,1 @@\n-x = 1\n+x = exception',
    '@@ -1,1 +1,1 @@\n-x = 1\n+x = exceptions',
    '@@ -1,1 +1,1 @@\n-x = 1\n+x = permissionDecision',
    '@@ -1,1 +1,1 @@\n-x = 1\n+x = PROCESS',
    '@@ -1,1 +1,1 @@\n-x = 1\n+x = DUTY',
])
def test_a_clear_classification_on_a_guard_change_still_owes_arch(root, fake, patch):
    """The lead says clear; the diff changes what a guard waives or refuses: the measured signal raises."""
    smart(root)
    pr_with(fake, {'src/app.py': (patch, branchy(1), branchy(1)), **TESTS})
    assert owed(root) == ['gates missing at head aaaaaaa: arch, quality']


@pytest.mark.parametrize('patch', [
    '@@ -4,4 +4,5 @@\n     try:\n         x = load()\n+        y = x + 1\n     except Exception:\n         pass',
    '@@ -4,2 +4,4 @@\n     x = load()\n+    try:\n+        y = x + 1\n+    except Exception:\n+        pass',
    '@@ -4,3 +4,4 @@\n     # ask the user before they allow or deny\n     x = load()\n+    y = x + 1',
])
def test_a_guard_word_only_in_unchanged_lines_or_pythons_exception_class_raises_nothing(root, fake, patch):
    """Smart is never slower than standard on an ordinary diff: context lines and except Exception are no guard change."""
    smart(root)
    pr_with(fake, {'src/app.py': (patch, branchy(1), branchy(1)), **TESTS})
    assert owed(root) == ['gates missing at head aaaaaaa: quality']


def test_a_clear_plan_field_on_an_owner_path_still_owes_security(root, fake):
    ws.write_config(root, {**ws.DEFAULTS, 'repos': ['acme/app'], 'owner_paths': ['src/core/*']})
    smart(root)
    pr_with(fake, {'src/core/rules.py': (PLAIN, branchy(1), branchy(2)), **TESTS})
    assert owed(root) == ['gates missing at head aaaaaaa: quality, security']


def test_a_code_file_with_no_patch_is_unmeasured_and_owes_arch(root, fake):
    smart(root)
    pr_with(fake, {'src/app.py': (None, branchy(1), branchy(2)), **TESTS})
    assert owed(root) == ['gates missing at head aaaaaaa: arch, quality']


@pytest.mark.parametrize('domain', ['complicated: one rule', 'clear: a typo'])
def test_a_trust_path_owes_arch_from_complicated_up(root, fake, domain):
    smart(root, domain)
    pr_with(fake, {'src/session.py': (PLAIN, branchy(1), branchy(2)), **TESTS})
    want = 'arch, quality, security' if domain.startswith('complicated') else 'quality, security'
    assert owed(root) == [f'gates missing at head aaaaaaa: {want}']


@pytest.mark.parametrize('domain', ['complex: a new protocol nobody has run', '', 'Clear: shouted', 'clear', None, 'chaotic: x'])
def test_a_complex_or_unclassified_item_owes_quality_security_and_arch(root, fake, domain):
    smart(root, domain)
    pr_with(fake, {'src/app.py': (PLAIN, branchy(1), branchy(2)), **TESTS})
    assert owed(root) == ['gates missing at head aaaaaaa: arch, quality, security']


def test_goal_runs_only_when_the_promise_is_in_doubt(root, fake):
    smart(root, in_doubt=True)
    pr_with(fake, {'src/app.py': (PLAIN, branchy(1), branchy(2)), **TESTS})
    assert owed(root) == ['gates missing at head aaaaaaa: quality, goal']


def test_docs_alone_need_no_gate_at_smart(root):
    smart(root, 'complex: x', in_doubt=True)
    assert evidence.needed(root, 'smart', [{'path': 'README.md', 'additions': 900, 'deletions': 0}], plan.find(root, 'I-1')) == ()


def test_acceptance_4_a_full_item_keeps_its_gates(root, fake):
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'full', 'domain': 'clear: x'}])
    pr_with(fake, {'src/app.py': (PLAIN, branchy(1), branchy(2)), **TESTS})
    assert owed(root) == ['gates missing at head aaaaaaa: arch, quality, security, goal']


def test_spec_artifacts_are_owed_only_by_a_complex_item_and_hold_its_merge(root, fake):
    fake.paths.add('.specify')
    smart(root)
    pr_with(fake, {'src/app.py': (PLAIN, branchy(1), branchy(2)), **TESTS})
    attest(root, 'quality')
    assert evidence.gaps(root, 'acme/app', 42) == []
    smart(root, 'complex: x')
    for gate in ('arch', 'security'):
        attest(root, gate)
    found = evidence.gaps(root, 'acme/app', 42)
    assert [(g['text'], g['kind']) for g in found] == [('no spec in the diff (the repository uses .specify)', 'safety')]


def test_an_error_budget_overrun_raises_smart_to_standards_full_set(root, fake):
    smart(root)
    pr_with(fake, {'src/app.py': (PLAIN, branchy(1), branchy(2)), **TESTS})
    for n, title in enumerate(['feat: a', 'feat: b', 'Revert "feat: a"', 'feat: c', 'Revert "feat: c"'], 1):
        merged = make_pr(number=n, state='MERGED')
        merged.update(title=title, mergedAt=ws.now().isoformat(timespec='seconds'))
        fake.prs[str(n)] = merged
    assert owed(root) == ['gates missing at head aaaaaaa: arch, quality, security (tier raised to standard: change failure rate 40% '
                          'over 28 days)']


def test_an_error_budget_overrun_keeps_every_gate_the_unraised_item_owed(root, fake):
    smart(root, in_doubt=True)
    pr_with(fake, {'src/app.py': (PLAIN, branchy(1), branchy(2)), **TESTS})
    for n, title in enumerate(['feat: a', 'feat: b', 'Revert "feat: a"', 'feat: c', 'Revert "feat: c"'], 1):
        merged = make_pr(number=n, state='MERGED')
        merged.update(title=title, mergedAt=ws.now().isoformat(timespec='seconds'))
        fake.prs[str(n)] = merged
    assert owed(root)[0].startswith('gates missing at head aaaaaaa: arch, quality, security, goal (tier raised to standard')


def test_the_create_door_reads_the_complexity_at_the_branch_head(root, fake, monkeypatch):
    monkeypatch.setattr(guards, 'origin', lambda cwd: 'acme/app')
    monkeypatch.setattr(guards, 'current_branch', lambda cwd: 'i-1-change')
    smart(root)
    fake.branches['i-1-change'], fake.merge_base = HEAD, BASE
    fake.deltas[('main', 'i-1-change')] = [{'path': 'src/app.py', 'additions': 2, 'deletions': 0, 'patch': PLAIN},
                                           {'path': 'tests/test_app.py', 'additions': 2, 'deletions': 0, 'patch': TESTS['tests/test_app.py'][0]}]
    fake.files.update({f'src/app.py@{BASE}': branchy(3), f'src/app.py@{HEAD}': branchy(4)})
    attest(root, 'quality')
    payload = {'tool_name': 'Bash', 'cwd': '/repo','session_id': 's1', 'tool_input': {'command': 'gh pr create --title x --body "WUWEI-Item: I-1"'}}
    assert guards.pre_tool(root, payload)['decision'] == 'note'
    fake.files[f'src/app.py@{HEAD}'] = branchy(10)
    forget(root)
    decision = guards.pre_tool(root, payload)
    assert decision['decision'] == 'deny' and 'gates missing at head aaaaaaa: security' in decision['reason']


def test_plan_add_defaults_to_smart_and_records_the_domain_and_doubt(root, monkeypatch, capsys):
    from wuwei import __main__ as cli
    monkeypatch.chdir(root)
    args = ['plan', 'add', 'I-7', 'item', '--goal', 'G-1', '--repo', 'acme/app', '--value', '5', '--time', '3', '--risk', '2', '--size', '2']
    assert cli.main(args + ['--domain', 'complicated: a rule two seats read differently', '--in-doubt']) == 0
    item = plan.find(root, 'I-7')
    assert (item['tier'], item['domain'], item['in_doubt']) == ('smart', 'complicated: a rule two seats read differently', True)
    for bad in ('clear', 'chaotic: x', 'clear:  ', 'clear: two\nlines'):
        assert cli.main(args + ['--domain', bad]) == 2
    assert 'domain' in capsys.readouterr().err
    for tier in ('light', 'standard', 'full'):
        assert plan.add(root, 'I-8', 't', 'G-1', 'acme/app', tier, {'value': 1, 'time': 1, 'risk': 1, 'size': 1})['tier'] == tier


def test_the_lead_file_carries_domain_and_doubt_and_defaults_to_smart(root, tmp_path):
    lead = tmp_path / 'candidates.json'
    lead.write_text(json.dumps([{'id': 'C-1', 'title': 't', 'value': 8, 'time': 5, 'risk': 3, 'size': 2, 'domain': 'clear: a typo', 'in_doubt': True}]))
    [item] = plan.add_from(root, lead)
    assert (item['tier'], item['domain'], item['in_doubt']) == ('smart', 'clear: a typo', True)
