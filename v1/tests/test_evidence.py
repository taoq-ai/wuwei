import hashlib

from conftest import HEAD, OLD, make_pr, verdict_text, write_plan
from wuwei import evidence, ws


def attest(root, gate, head=HEAD, verdict='PASS', item='I-1'):
    path = root / ws.DIR / 'verdicts' / item / f'{gate}-{head[:7]}.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(verdict_text(gate=gate, verdict=verdict, head=head, item=item))
    ws.record(root, 'attest', {'path': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                               'gate': gate, 'item': item, 'head': head, 'role': f'sentinel-{gate}', 'agent': 'x'})
    return path


def standard(root):
    write_plan(root, [{'id': 'I-1', 'title': 'change', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'standard'}])


def texts(gaps):
    return [gap['text'] for gap in gaps]


def test_complete_evidence_has_no_gaps(root, fake):
    standard(root)
    fake.prs['42'] = make_pr()
    for gate in ('arch', 'quality', 'security'):
        attest(root, gate)
    assert evidence.gaps(root, 'acme/app', 42) == []


def test_missing_gates_tests_and_link_are_named(root, fake):
    fake.prs['42'] = make_pr(files=('src/app.py',), body='')
    found = texts(evidence.gaps(root, 'acme/app', 42))
    assert 'not linked to a plan item (add WUWEI-Item: <id> to the PR body)' in found
    assert 'no test in the diff' in found
    assert any(text.startswith('gates missing at head') for text in found)


def test_a_verdict_counts_only_when_attested(root, fake):
    standard(root)
    fake.prs['42'] = make_pr()
    for gate in ('arch', 'quality', 'security'):
        attest(root, gate)
    path = root / ws.DIR / 'verdicts' / 'I-1' / f'quality-{HEAD[:7]}.md'
    path.write_text(path.read_text() + '\nedited\n')
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['gates missing at head aaaaaaa: quality']


def test_earlier_passes_hold_when_one_gate_passed_at_the_head(root, fake):
    standard(root)
    fake.prs['42'] = make_pr()
    fake.ancestors.add((OLD, HEAD))
    attest(root, 'quality', OLD)
    attest(root, 'security', OLD)
    attest(root, 'arch', HEAD)
    assert evidence.gaps(root, 'acme/app', 42) == []


def test_old_passes_alone_do_not_cover_a_moved_head(root, fake):
    standard(root)
    fake.prs['42'] = make_pr()
    fake.ancestors.add((OLD, HEAD))
    for gate in ('arch', 'quality', 'security'):
        attest(root, gate, OLD)
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['no gate passed at head aaaaaaa (a delta review)']


def test_a_fix_verdict_is_not_a_pass(root, fake):
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light'}])
    fake.prs['42'] = make_pr()
    attest(root, 'quality', verdict='FIX')
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['gates missing at head aaaaaaa: quality']


def test_ci_threads_and_reviews(root, fake):
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light'}])
    fake.prs['42'] = make_pr(checks='FAILURE', requests=())
    fake.threads['42'] = [{'isResolved': False, 'comments': {'nodes': [{'author': {'login': 'alice'}}]}},
                          {'isResolved': False, 'comments': {'nodes': [{'author': {'login': 'wuwei-bot'}}]}}]
    attest(root, 'quality')
    gaps = evidence.gaps(root, 'acme/app', 42)
    assert texts(gaps) == ['CI failing: test', '1 review thread unanswered', 'no reviewer requested']
    assert all(gap['actionable'] for gap in gaps)


def test_waiting_states_are_not_actionable(root, fake):
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light'}])
    pr = make_pr(files=('infra/main.tf', 'tests/test_x.py'))
    pr['statusCheckRollup'] = [{'name': 'test', 'conclusion': '', 'status': 'IN_PROGRESS'}]
    fake.prs['42'] = pr
    attest(root, 'quality')
    gaps = evidence.gaps(root, 'acme/app', 42)
    assert texts(gaps) == ['CI running', 'owner review needed (owner_paths: infra/main.tf)']
    assert not any(gap['actionable'] for gap in gaps)
    assert gaps[1]['owner']


def test_owner_approval_closes_owner_paths(root, fake):
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light'}])
    fake.prs['42'] = make_pr(files=('infra/main.tf', 'tests/test_x.py'), reviews=(('owner', 'APPROVED'),))
    attest(root, 'quality')
    assert evidence.gaps(root, 'acme/app', 42) == []


def test_spec_required_when_the_repo_has_a_spec_engine(root, fake):
    standard(root)
    fake.paths.add('.specify')
    fake.prs['42'] = make_pr()
    for gate in ('arch', 'quality', 'security'):
        attest(root, gate)
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['no spec in the diff (the repository uses .specify)']


def test_docs_only_change_needs_no_test(root, fake):
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light'}])
    fake.prs['42'] = make_pr(files=('README.md', 'docs/guide.md'))
    attest(root, 'quality')
    assert evidence.gaps(root, 'acme/app', 42) == []


def test_an_unreadable_pr_is_a_gap_never_clean(root, fake):
    gaps = evidence.gaps(root, 'acme/app', 7)
    assert texts(gaps) == ['evidence unreadable: no pull requests found']
