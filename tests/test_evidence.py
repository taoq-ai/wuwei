import pytest
import hashlib

from conftest import HEAD, OLD, make_pr, verdict_text, write_plan
from wuwei import evidence, gh, ws


def attest(root, gate, head=HEAD, verdict='PASS', item='I-1', name=None):
    path = root / ws.DIR / 'verdicts' / item / (name or f'{gate}-{head[:7]}.md')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(verdict_text(gate=gate, verdict=verdict, head=head, item=item))
    ws.record(root, 'attest', {'path': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                               'gate': gate, 'item': item, 'head': head, 'verdict': verdict, 'role': f'sentinel-{gate}', 'agent': 'x'})
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
    assert 'not linked to a plan item (end the PR body with the WUWEI footer naming its item)' in found
    assert 'no test in the diff' in found
    assert any(text.startswith('gates missing at head') for text in found)


def test_a_verdict_counts_only_when_attested(root, fake):
    standard(root)
    fake.prs['42'] = make_pr()
    for gate in ('arch', 'quality', 'security'):
        attest(root, gate)
    path = root / ws.DIR / 'verdicts' / 'I-1' / f'quality-{HEAD[:7]}.md'
    path.write_text(path.read_text() + '\nedited\n')
    found = texts(evidence.gaps(root, 'acme/app', 42))
    assert found[0] == 'gates missing at head aaaaaaa: quality'
    assert found[1].startswith(f'verdict .wuwei/verdicts/I-1/quality-{HEAD[:7]}.md not counted: ')


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
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['no gate passed at head aaaaaaa (a delta review by quality)']


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
    pr = make_pr(files=('infra/main.tf', 'tests/test_x.py'), body='WUWEI-Item: I-1\nRollback: revert the PR')
    pr['statusCheckRollup'] = [{'name': 'test', 'conclusion': '', 'status': 'IN_PROGRESS'}]
    fake.prs['42'] = pr
    attest(root, 'quality')
    gaps = evidence.gaps(root, 'acme/app', 42)
    assert texts(gaps) == ['CI running', 'owner review needed (owner_paths: infra/main.tf)']
    assert not any(gap['actionable'] for gap in gaps)
    assert gaps[1]['owner']


GATE = 'https://github.com/acme/app/actions/runs/'


def review_gate(root, fake, state, reviews=()):
    """ai-stacks' Review Gate as 1067-probe read it: a status whose target_url names a pull_request run of a
    workflow the repository also runs on pull_request_review; every check run has completed."""
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light'}])
    attest(root, 'quality')
    fake.runs.update({'7': ('.github/workflows/review-gate.yml', 'pull_request'),
                      '8': ('.github/workflows/review-gate.yml', 'pull_request_review'),
                      '9': ('.github/workflows/ci.yml', 'pull_request')})
    pr = make_pr(reviews=reviews)
    pr['statusCheckRollup'].append({'context': 'Review Gate', 'state': state, 'url': GATE + '7'})
    fake.prs['42'] = pr


def test_a_pending_status_from_a_review_triggered_workflow_waits_on_review(root, fake):
    review_gate(root, fake, 'PENDING')
    gaps = evidence.gaps(root, 'acme/app', 42)
    assert texts(gaps) == ['waiting on review: Review Gate']
    assert gaps[0]['actionable'] and gaps[0]['kind'] == 'safety'


def test_a_failing_review_status_is_a_change_request_not_a_red_build(root, fake):
    review_gate(root, fake, 'FAILURE', reviews=(('alice', 'APPROVED'), ('bob', 'CHANGES_REQUESTED')))
    gaps = evidence.gaps(root, 'acme/app', 42)
    assert texts(gaps) == ['change request outstanding: Review Gate']
    assert gaps[0]['actionable'] and gaps[0]['kind'] == 'safety'


def test_a_failing_status_from_an_ordinary_workflow_is_still_ci(root, fake):
    review_gate(root, fake, 'SUCCESS')
    fake.prs['42']['statusCheckRollup'].append({'context': 'lint', 'state': 'FAILURE', 'url': GATE + '9'})
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['CI failing: lint']


def test_a_head_without_commit_statuses_makes_no_actions_read(root, fake):
    review_gate(root, fake, 'PENDING')
    fake.prs['42']['statusCheckRollup'].pop()
    assert evidence.gaps(root, 'acme/app', 42) == []
    assert not any('/actions/' in ' '.join(call) for call in fake.calls)


@pytest.mark.parametrize('url', [None, '', 'https://ci.example.com/build/7', 'https://github.com/acme/other/actions/runs/7',
                                 'https://github.com/acme/app/actions/workflows/review-gate.yml'])
def test_a_status_without_a_run_of_this_repo_stays_ci_unread(root, fake, url):
    review_gate(root, fake, 'PENDING')
    fake.prs['42']['statusCheckRollup'][-1]['url'] = url
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['CI running']
    assert not any('/actions/' in ' '.join(call) for call in fake.calls)


@pytest.mark.parametrize('state, text', [('PENDING', 'CI running'), ('FAILURE', 'CI failing: Review Gate')])
def test_an_unreadable_actions_host_leaves_the_status_ci(root, fake, state, text):
    review_gate(root, fake, state)
    fake.runs = None
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [text]


def test_a_failing_review_gate_still_names_an_approval_at_an_older_commit(root, fake):
    review_gate(root, fake, 'FAILURE', reviews=(('alice', 'APPROVED', OLD),))
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [
        'change request outstanding: Review Gate',
        'the approval from alice is for bbbbbbb, not the head aaaaaaa: re-request review if a check wants it at the head']


def test_a_repo_without_review_workflows_reads_no_run(root, fake):
    review_gate(root, fake, 'PENDING')
    del fake.runs['8']
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['CI running']
    assert not any('actions/runs/7' in ' '.join(call) for call in fake.calls)


@pytest.mark.parametrize('reply, url', [({'workflow_runs': None}, GATE + '7'), ({'workflow_runs': []}, 7),
                                        ('not json', GATE + '7'), ({'id': 7}, GATE + '7')])
def test_an_oddly_shaped_actions_reply_leaves_the_status_ci(root, monkeypatch, reply, url):
    from wuwei import gh
    monkeypatch.setattr(gh, 'run', lambda args, timeout=30: reply)
    rollup = [{'context': 'Review Gate', 'state': 'PENDING', 'url': url}]
    assert evidence.review_contexts(root, 'acme/app', rollup) == set()


def test_the_review_workflows_are_read_once_a_day(root, fake):
    review_gate(root, fake, 'PENDING')
    evidence.gaps(root, 'acme/app', 42)
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['waiting on review: Review Gate']
    assert sum('event=pull_request_review' in ' '.join(call) for call in fake.calls) == 1


def test_owner_approval_closes_owner_paths(root, fake):
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light'}])
    fake.prs['42'] = make_pr(files=('infra/main.tf', 'tests/test_x.py'), reviews=(('owner', 'APPROVED'),),
                             body='WUWEI-Item: I-1\nRollback: revert the PR')
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
    assert texts(gaps) == ['evidence unreadable: HTTP 404: Not Found']


def light(root, tier='light'):
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': tier}])


def test_a_big_batch_asks_to_split_or_say_why(root, fake):
    light(root)
    fake.prs['42'] = make_pr(lines=300)
    attest(root, 'quality')
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['600 changed lines: split it, or add a Size: <reason> line']
    fake.prs['42'] = make_pr(lines=300, body='WUWEI-Item: I-1\nSize: one generated migration')
    assert evidence.gaps(root, 'acme/app', 42) == []


def test_lockfiles_and_generated_files_do_not_count_toward_size(root, fake):
    light(root)
    fake.prs['42'] = make_pr(files=('uv.lock', 'src/app.py', 'tests/test_app.py'), lines=180)
    attest(root, 'quality')
    assert evidence.gaps(root, 'acme/app', 42) == []


def test_full_tier_and_owner_paths_need_a_rollback_line(root, fake):
    light(root, 'full')
    fake.prs['42'] = make_pr()
    for gate in ('arch', 'quality', 'security', 'goal'):
        attest(root, gate)
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['no Rollback: line (how to undo this change)']
    fake.prs['42'] = make_pr(body='WUWEI-Item: I-1\nRollback: revert the PR; the column is additive')
    assert evidence.gaps(root, 'acme/app', 42) == []


def test_a_stale_pr_is_named(root, fake):
    import datetime
    light(root)
    old = (ws.now() - datetime.timedelta(days=5)).isoformat(timespec='seconds')
    fake.prs['42'] = make_pr(created=old)
    attest(root, 'quality')
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['open 5 days: finish, rebase or close']


def test_the_repository_pr_template_is_honoured(root, fake):
    light(root)
    fake.files['.github/pull_request_template.md'] = '## Summary\n\n<!-- what -->\n\n## Testing\n'
    fake.prs['42'] = make_pr()
    attest(root, 'quality')
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [
        "PR body misses the repository template's sections: Summary, Testing"]
    fake.prs['42'] = make_pr(body='WUWEI-Item: I-1\n## Summary\nx\n## Testing\ny')
    assert evidence.gaps(root, 'acme/app', 42) == []


def test_an_owner_exception_covers_one_gap_at_one_head(root, fake):
    light(root)
    fake.prs['42'] = make_pr(files=('src/app.py',))
    attest(root, 'quality')
    ws.record(root, 'ruling', {'kind': 'exception', 'pr': 'acme/app#42', 'head': 'aaaaaaa',
                               'gap': 'no test in the diff', 'approved': True})
    assert evidence.gaps(root, 'acme/app', 42) == []
    fake.prs['42'] = make_pr(files=('src/app.py',), head=OLD)
    attest(root, 'quality', head=OLD)
    assert 'no test in the diff' in texts(evidence.gaps(root, 'acme/app', 42))


def test_an_error_budget_overrun_raises_the_tier(root, fake):
    light(root)
    fake.prs['42'] = make_pr()
    for n, title in enumerate(['feat: a', 'feat: b', 'Revert "feat: a"', 'feat: c', 'Revert "feat: c"'], 1):
        merged = make_pr(number=n, state='MERGED')
        merged.update(title=title, mergedAt=ws.now().isoformat(timespec='seconds'))
        fake.prs[str(n)] = merged
    attest(root, 'quality')
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [
        'gates missing at head aaaaaaa: arch, security (tier raised to standard: change failure rate 40% over 28 days)']


SPEC = 'specs/7-rate-limits'
DONE = '- [x] T001 write the failing test\n- [x] T002 implement\n'


def speckit(fake, **override):
    fake.paths.add('.specify')
    files = {f'{SPEC}/spec.md': '# Spec\n\n## Clarifications\n- none open\n', f'{SPEC}/plan.md': '# Plan\n',
             f'{SPEC}/tasks.md': DONE, f'{SPEC}/analysis.md': '| ID | Severity | Summary |\n|---|---|---|\n| C1 | LOW | wording |\n',
             f'{SPEC}/checklists/requirements.md': '- [x] every requirement is testable\n'}
    files.update(override)
    fake.files.update({k: v for k, v in files.items() if v is not None})
    return [k for k, v in files.items() if v is not None]


def full_gates(root):
    for gate in ('arch', 'quality', 'security', 'goal'):
        attest(root, gate)


def test_a_complete_speckit_feature_passes_at_standard(root, fake):
    standard(root)
    fake.prs['42'] = make_pr(files=(*speckit(fake), 'src/app.py', 'tests/test_app.py'))
    for gate in ('arch', 'quality', 'security'):
        attest(root, gate)
    assert evidence.gaps(root, 'acme/app', 42) == []


def test_spec_files_are_read_at_the_head_not_only_from_the_diff(root, fake):
    standard(root)
    speckit(fake)
    fake.prs['42'] = make_pr(files=(f'{SPEC}/spec.md', 'src/app.py', 'tests/test_app.py'))
    for gate in ('arch', 'quality', 'security'):
        attest(root, gate)
    assert evidence.gaps(root, 'acme/app', 42) == []
    assert any('?ref=' + HEAD in call[1] for call in fake.calls if call[0] == 'api' and SPEC in call[1])


def test_missing_steps_and_unfinished_tasks_are_named(root, fake):
    standard(root)
    files = speckit(fake, **{f'{SPEC}/plan.md': None, f'{SPEC}/tasks.md': '- [x] T001\n- [ ] T002\n- [ ] T003\n'})
    fake.prs['42'] = make_pr(files=(*files, 'src/app.py', 'tests/test_app.py'))
    for gate in ('arch', 'quality', 'security'):
        attest(root, gate)
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [
        f'{SPEC}/plan.md missing: run the spec engine step that writes it',
        f'{SPEC}/tasks.md has 2 unchecked items']


def test_full_tier_needs_clarify_a_clean_analysis_and_checked_checklists(root, fake):
    light(root, 'full')
    files = speckit(fake, **{
        f'{SPEC}/spec.md': '# Spec\n',
        f'{SPEC}/analysis.md': '| ID | Severity | Summary |\n|---|---|---|\n| A1 | HIGH | FR-2 has no task |\n',
        f'{SPEC}/checklists/requirements.md': '- [x] testable\n- [ ] measurable\n'})
    fake.prs['42'] = make_pr(files=(*files, 'src/app.py', 'tests/test_app.py'), body='WUWEI-Item: I-1\nRollback: revert')
    full_gates(root)
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [
        f'{SPEC}/spec.md has no ## Clarifications section: run clarify',
        f'{SPEC}/analysis.md has an open CRITICAL or HIGH finding: | A1 | HIGH | FR-2 has no task |',
        f'{SPEC}/checklists/requirements.md has 1 unchecked item']


def test_a_clean_full_tier_speckit_feature_passes(root, fake):
    light(root, 'full')
    fake.prs['42'] = make_pr(files=(*speckit(fake), 'src/app.py', 'tests/test_app.py'), body='WUWEI-Item: I-1\nRollback: revert')
    full_gates(root)
    assert evidence.gaps(root, 'acme/app', 42) == []


def test_an_openspec_change_needs_its_proposal_specs_and_tasks(root, fake):
    standard(root)
    fake.paths.add('openspec')
    change = 'openspec/changes/add-rate-limits'
    fake.files.update({f'{change}/proposal.md': '# Why\n', f'{change}/tasks.md': DONE,
                       f'{change}/specs/limits/spec.md': '## ADDED Requirements\n'})
    fake.prs['42'] = make_pr(files=(f'{change}/tasks.md', f'{change}/specs/limits/spec.md', 'src/app.py', 'tests/test_app.py'))
    for gate in ('arch', 'quality', 'security'):
        attest(root, gate)
    assert evidence.gaps(root, 'acme/app', 42) == []
    del fake.files[f'{change}/proposal.md']
    ws.cache_put(root, 'spec-acme__app', None)
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [f'{change}/proposal.md missing: run the spec engine step that writes it']


def test_an_old_feature_the_pr_only_amends_is_not_held_to_the_full_spec_set(root, fake):
    light(root, 'full')
    files = speckit(fake)
    old = 'specs/2-identity'
    fake.files[f'{old}/contracts/api.yaml'] = 'openapi: 3.1.0\n'
    fake.prs['42'] = make_pr(files=(*files, f'{old}/contracts/api.yaml', 'src/app.py', 'tests/test_app.py'),
                             body='WUWEI-Item: I-1\nRollback: revert')
    full_gates(root)
    assert evidence.gaps(root, 'acme/app', 42) == []


def test_a_pr_that_only_amends_a_spec_still_counts_as_touching_the_spec(root, fake):
    standard(root)
    speckit(fake)
    fake.prs['42'] = make_pr(files=(f'{SPEC}/tasks.md', 'src/app.py', 'tests/test_app.py'))
    for gate in ('arch', 'quality', 'security'):
        attest(root, gate)
    assert evidence.gaps(root, 'acme/app', 42) == []


def test_gaps_are_classed_as_process_or_safety(root, fake):
    light(root)
    fake.prs['42'] = make_pr(files=('src/app.py',), lines=500, requests=(), body='')
    fake.prs['42']['headRefName'] = 'hotfix'
    kinds = {g['text']: g['kind'] for g in evidence.gaps(root, 'acme/app', 42)}
    assert kinds == {'not linked to a plan item (end the PR body with the WUWEI footer naming its item)': 'process',
                     'no test in the diff': 'safety', '500 changed lines: split it, or add a Size: <reason> line': 'process',
                     'gates missing at head aaaaaaa: arch, quality': 'safety', 'no reviewer requested': 'process'}


def test_in_a_cloud_session_threads_come_from_the_ccr_route(root, fake):
    light(root)
    fake.graphql = False
    fake.prs['42'] = make_pr()
    fake.ccr['42'] = [{'is_resolved': False, 'comments': [{'user': {'login': 'alice'}}]},
                      {'is_resolved': True, 'comments': [{'user': {'login': 'alice'}}]}]
    attest(root, 'quality')
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['1 review thread unanswered']


def test_without_graphql_or_ccr_threads_fall_back_to_review_comments(root, fake, monkeypatch):
    light(root)
    fake.graphql = False
    fake.prs['42'] = make_pr()
    original = fake.__call__

    def no_ccr(args, timeout=30):
        if len(args) > 1 and args[1].endswith('/ccr/review_threads'):
            raise evidence.gh.GhError('HTTP 404: Not Found')
        return original(args, timeout)
    monkeypatch.setattr(evidence.gh, 'run', no_ccr)
    fake.comments['42'] = [{'id': 1, 'user': {'login': 'alice'}}, {'id': 2, 'in_reply_to_id': 1, 'user': {'login': 'wuwei-bot'}},
                           {'id': 3, 'user': {'login': 'bob'}}]
    attest(root, 'quality')
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['1 review thread unanswered']


def test_a_verdict_that_does_not_count_says_why_on_the_board(root, fake):
    light(root)
    fake.prs['42'] = make_pr()
    flat = root / ws.DIR / 'verdicts' / 'I-1-quality-aaaaaaa.md'
    flat.parent.mkdir(parents=True, exist_ok=True)
    flat.write_text(verdict_text().replace('Confidence: high', 'Confidence: sure'))
    found = texts(evidence.gaps(root, 'acme/app', 42))
    assert found[0].startswith('gates missing at head aaaaaaa: quality')
    assert any(t.startswith('verdict .wuwei/verdicts/I-1-quality-aaaaaaa.md not counted: Confidence') for t in found)


def test_a_wellformed_verdict_nobody_attested_says_how_to_fix_it(root, fake):
    light(root)
    fake.prs['42'] = make_pr()
    path = root / ws.DIR / 'verdicts' / 'I-1' / 'quality-aaaaaaa.md'
    path.parent.mkdir(parents=True)
    path.write_text(verdict_text())
    found = texts(evidence.gaps(root, 'acme/app', 42))
    assert any('not counted: not attested' in t and 'sentinel-quality' in t for t in found)


def test_one_exception_can_cover_several_prs_with_loose_gap_text(root, fake):
    light(root)
    fake.prs['42'] = make_pr(files=('src/app.py',))
    attest(root, 'quality')
    ws.record(root, 'ruling', {'kind': 'exception', 'pr': 'acme/app#42', 'head': 'aaaaaaa', 'gap': 'No test in the diff',
                               'approved': True})
    assert evidence.gaps(root, 'acme/app', 42) == []


def test_house_style_spec_sections_count(root, fake):
    light(root, 'full')
    tasks = ('## Slice 1\n- [x] T001 the failing test\n- [x] T002 implement\n\n'
             '## 7. Deferred\n- [ ] T010 slice 2 export (waits on the platform team PR)\n'
             '- [ ] T011 slice 5 backfill: blocked by platform#88\n')
    files = speckit(fake, **{f'{SPEC}/spec.md': '# Spec\n\n## 12. Clarifications\n- none open\n', f'{SPEC}/tasks.md': tasks})
    fake.prs['42'] = make_pr(files=(*files, 'src/app.py', 'tests/test_app.py'), body='WUWEI-Item: I-1\nRollback: revert')
    full_gates(root)
    assert evidence.gaps(root, 'acme/app', 42) == []


def test_a_deferred_task_without_a_reason_still_counts(root, fake):
    standard(root)
    tasks = '- [x] T001 done\n\n## Out of this PR\n- [ ] T010 slice 2 export\n'
    files = speckit(fake, **{f'{SPEC}/tasks.md': tasks})
    fake.prs['42'] = make_pr(files=(*files, 'src/app.py', 'tests/test_app.py'))
    for gate in ('arch', 'quality', 'security'):
        attest(root, gate)
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [f'{SPEC}/tasks.md has 1 unchecked item']


def test_spec_gaps_block_at_full_tier_and_are_process_fit_below_it(root, fake):
    files = speckit(fake, **{f'{SPEC}/plan.md': None})
    fake.prs['42'] = make_pr(files=(*files, 'src/app.py', 'tests/test_app.py'), body='WUWEI-Item: I-1\nRollback: revert')
    standard(root)
    for gate in ('arch', 'quality', 'security'):
        attest(root, gate)
    assert evidence.blocking(evidence.gaps(root, 'acme/app', 42)) == []
    light(root, 'full')
    full_gates(root)
    held = evidence.blocking(evidence.gaps(root, 'acme/app', 42))
    assert f'{SPEC}/plan.md missing: run the spec engine step that writes it' in texts(held)


@pytest.mark.parametrize('order', [('FIX', 'PASS'), ('PASS', 'FIX')])
def test_one_seat_overwriting_another_at_the_same_head_never_turns_a_finding_green(root, fake, order):
    light(root)
    fake.prs['42'] = make_pr()
    for verdict in order:
        attest(root, 'quality', verdict=verdict)
    assert 'gates missing at head aaaaaaa: quality' in texts(evidence.gaps(root, 'acme/app', 42))


def test_a_later_pass_at_the_same_head_does_not_outvote_a_finding(root, fake):
    light(root)
    fake.prs['42'] = make_pr()
    attest(root, 'quality', verdict='FIX')
    attest(root, 'quality', verdict='PASS', name='quality-aaaaaaa-2.md')
    assert 'gates missing at head aaaaaaa: quality' in texts(evidence.gaps(root, 'acme/app', 42))


def test_an_approval_for_an_older_commit_is_named_when_a_check_is_red(root, fake):
    light(root)
    fake.prs['42'] = make_pr(checks='FAILURE', reviews=(('alice', 'APPROVED', OLD),))
    attest(root, 'quality')
    found = texts(evidence.gaps(root, 'acme/app', 42))
    assert f'the approval from alice is for {OLD[:7]}, not the head aaaaaaa: re-request review if a check wants it at the head' in found
    fake.prs['42'] = make_pr(checks='FAILURE', reviews=(('alice', 'APPROVED'),))
    ws.cache_put(root, 'board', None)
    assert not any(t.startswith('the approval from') for t in texts(evidence.gaps(root, 'acme/app', 42)))


def analysis_pr(fake, row):
    write = lambda name, text: fake.files.__setitem__(f'{SPEC}/{name}', text)  # noqa: E731
    write('spec.md', '# Spec\n## Clarifications\n- Q: a? A: b\n')
    write('plan.md', '# Plan\n')
    write('tasks.md', '- [x] T1\n')
    write('analysis.md', '| ID | Severity | Disposition |\n|---|---|---|\n' + row + '\n')
    write('checklists/req.md', '- [x] done\n')
    fake.paths.add('.specify')
    fake.prs['42'] = make_pr(files=(f'{SPEC}/spec.md', 'src/app.py', 'tests/test_app.py'), body='WUWEI-Item: I-1\nRollback: revert')


def test_a_resolved_high_finding_no_longer_holds_the_merge(root, fake):
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'full'}])
    analysis_pr(fake, '| F6 | HIGH | Resolved: tests/test_app.py::test_grant |')
    assert not any('analysis.md' in t for t in texts(evidence.gaps(root, 'acme/app', 42)))
    analysis_pr(fake, '| F6 | HIGH | open |')
    assert any('open CRITICAL or HIGH finding' in t for t in texts(evidence.gaps(root, 'acme/app', 42)))


@pytest.mark.parametrize('files,lines,gates', [
    (('config/staging.yaml',), 1, 'quality'),
    (('src/auth/session.py', 'tests/test_session.py'), 10, 'quality, security'),
    (('src/a.py', 'tests/test_a.py'), 150, 'arch, quality'),
    (('requirements.txt',), 1, 'quality, security'),
    (('src/geometry/diameter.py',), 3, 'quality'),
    (('docs/auth.md',), 30, None),
    (('docs/guide.md',), 30, None)])
def test_the_diff_decides_which_gates_a_standard_item_needs(root, fake, files, lines, gates):
    standard(root)
    fake.prs['42'] = make_pr(files=files, lines=lines, body='WUWEI-Item: I-1\nNo test: config')
    found = [t for t in texts(evidence.gaps(root, 'acme/app', 42)) if 'gate' in t]
    assert found == ([f'gates missing at head aaaaaaa: {gates}'] if gates else [])


def test_a_small_delta_after_review_carries_the_passes_and_a_risky_one_does_not(root, fake):
    standard(root)
    fake.prs['42'] = make_pr()
    fake.ancestors.add((OLD, HEAD))
    attest(root, 'quality', OLD)
    fake.deltas[(OLD, HEAD)] = [{'path': 'src/app.py', 'additions': 4, 'deletions': 2}]
    assert evidence.gaps(root, 'acme/app', 42) == []
    fake.deltas[(OLD, HEAD)] = [{'path': 'src/token.py', 'additions': 4, 'deletions': 2}]
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['no gate passed at head aaaaaaa (a delta review by security)']


def test_verdicts_count_by_their_pr_when_the_item_is_not_in_the_plan(root, fake):
    fake.prs['42'] = make_pr(body='WUWEI-Item: OPS-9')
    attest(root, 'quality', item='OPS-9')
    assert not any('gate' in t for t in texts(evidence.gaps(root, 'acme/app', 42)))
    fake.prs['42'] = make_pr(body='')
    fake.prs['42']['headRefName'] = 'hotfix'
    path = attest(root, 'quality', item='other')
    rows = ws.rows(root, 'attest')
    ws.record(root, 'attest', {**rows[-1]['data'], 'pr': 'acme/app#42'})
    assert not any('gate' in t for t in texts(evidence.gaps(root, 'acme/app', 42))) and path


def test_a_merged_pr_names_what_it_lacked_as_post_merge(root, fake):
    standard(root)
    fake.prs['42'] = make_pr(state='MERGED')
    fake.prs['42']['mergedAt'] = ws.now().isoformat(timespec='seconds')
    attest(root, 'quality', verdict='FIX')
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['post-merge: gates missing at head aaaaaaa: quality']


FOOTER = '<sub>[WUWEI 1.1.0](https://taoq-ai.github.io/wuwei/) · Item `G6-DETECTOR` · Detector context · Goal G-6 · Tier standard</sub>'


def test_the_wuwei_footer_links_a_pr_to_its_item(root, fake):
    write_plan(root, [{'id': 'G6-DETECTOR', 'title': 'Detector context', 'goal': 'G-6', 'repo': 'acme/app', 'tier': 'standard'}])
    fake.prs['42'] = make_pr(body=f'## What and why\nx\n\n---\n{FOOTER}')
    for gate in ('arch', 'quality', 'security'):
        attest(root, gate, item='G6-DETECTOR')
    assert evidence.gaps(root, 'acme/app', 42) == []


def test_an_owner_approval_counts_only_at_the_head(root, fake):
    light(root)
    fake.prs['42'] = make_pr(files=('infra/main.tf', 'tests/test_x.py'), reviews=(('owner', 'APPROVED', OLD),),
                             body='WUWEI-Item: I-1\nRollback: revert the PR')
    attest(root, 'quality')
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['owner review needed (owner_paths: infra/main.tf)']


def test_only_an_owner_review_ruling_clears_the_owner_review(root, fake):
    light(root)
    fake.prs['42'] = make_pr(files=('infra/main.tf', 'tests/test_x.py'), body='WUWEI-Item: I-1\nRollback: revert the PR')
    attest(root, 'quality')
    for kind in ('breaking', 'exception'):
        ws.record(root, 'ruling', {'kind': kind, 'pr': 'acme/app#42', 'head': HEAD[:7], 'approved': True})
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['owner review needed (owner_paths: infra/main.tf)']
    ws.record(root, 'ruling', {'pr': 'acme/app#42', 'head': HEAD[:7], 'approved': True})
    assert evidence.gaps(root, 'acme/app', 42) == []


def test_a_light_item_touching_a_trust_path_is_raised_to_standard(root, fake):
    light(root)
    fake.prs['42'] = make_pr(files=('src/grants.py', 'tests/test_grants.py'))
    attest(root, 'quality')
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [
        'gates missing at head aaaaaaa: arch, security (tier raised to standard: the diff touches a trust path)']
    fake.prs['42'] = make_pr(files=('docs/auth.md',))
    assert evidence.gaps(root, 'acme/app', 42) == []


RELEASE = ('.claude-plugin/plugin.json', '.release-please-manifest.json', 'CHANGELOG.md')
RELEASE_CONFIG = '{"packages": {".": {"extra-files": [{"type": "json", "path": ".claude-plugin/plugin.json"}]}}}'


# The patches GitHub sent for taoq-ai/wuwei#1072; any other path bumps one version line.
BUMP = '@@ -1,3 +1,3 @@\n {\n-  "version": "1.2.0",\n+  "version": "1.2.1",\n   "name": "x"'
PATCHES = {'.release-please-manifest.json': '@@ -1,3 +1,3 @@\n {\n-  ".": "1.2.0"\n+  ".": "1.2.1"\n }',
           '.claude-plugin/plugin.json': '@@ -1,6 +1,6 @@\n {\n   "name": "wuwei",\n-  "version": "1.2.0",\n+  "version": "1.2.1",\n'
                                         '   "description": "Responsible autonomy for agent teams.",\n   "author": {',
           'CHANGELOG.md': '@@ -1,5 +1,13 @@\n # Changelog\n \n+## [1.2.1](https://github.com/taoq-ai/wuwei/compare/v1.2.0...v1.2.1)'
                           '\n+\n+### Bug Fixes\n+\n+* **doctor:** the hooks check counts any hook ([#1070](x))\n+\n ## [1.2.0]'}


def release_gaps(root, fake, files=RELEASE, author='github-actions[bot]', branch='release-please--branches--main', checks='SUCCESS',
                 patches=None, renamed=None):
    """The 1.2.1 release PR shape (taoq-ai/wuwei#1072): the gaps it names for a test or a gate, and CI."""
    fake.prs['42'] = make_pr(files=files, author=author, body=':robot: I have created a release *beep* *boop*',
                             lines=1, checks=checks)
    fake.prs['42']['headRefName'] = branch
    for f in fake.prs['42']['files']:
        f['patch'] = {**PATCHES, **(patches or {})}.get(f['path'], BUMP)
        f.update({'previous_filename': renamed} if renamed and f['path'] == 'CHANGELOG.md' else {})
    return [t for t in texts(evidence.gaps(root, 'acme/app', 42)) if t == 'no test in the diff' or 'gate' in t or 'CI' in t]


BOTH = ['no test in the diff', 'gates missing at head aaaaaaa: quality']


def test_a_release_please_pr_is_read_as_generated(root, fake):
    fake.files['release-please-config.json'] = RELEASE_CONFIG
    assert release_gaps(root, fake) == []
    assert any(c[1].endswith('contents/release-please-config.json?ref=main') for c in fake.calls)
    assert release_gaps(root, fake, author='release-please[bot]') == []
    assert release_gaps(root, fake, checks='FAILURE') == ['CI failing: test']


def test_a_release_pr_from_a_person_another_branch_or_with_code_keeps_every_gap(root, fake):
    fake.files['release-please-config.json'] = RELEASE_CONFIG
    assert release_gaps(root, fake, author='alice') == BOTH
    assert release_gaps(root, fake, branch='release-1.2.1') == BOTH
    assert release_gaps(root, fake, branch='x-release-please--main') == BOTH
    assert release_gaps(root, fake, files=RELEASE + ('cli/wuwei/guards.py',)) == BOTH


@pytest.mark.parametrize('config', [None, 'not json', '{"packages": []}', '{"packages": {".": {"extra-files": [7]}}}', '{}',
                                    '{"packages": {".": {"extra-files": [{"type": "json"}]}}}', pytest.param('[' * 100000, id='deep')])
def test_an_unreadable_release_config_counts_only_the_manifest_and_changelog(root, fake, config):
    if config is not None:
        fake.files['release-please-config.json'] = config
    assert release_gaps(root, fake) == BOTH
    assert release_gaps(root, fake, files=RELEASE[1:]) == []


def test_release_extra_files_resolve_under_their_package_path(root, fake):
    fake.files['release-please-config.json'] = ('{"packages": {"pkg/a": {"extra-files": ["version.json", '
                                                '{"path": "/VERSION"}]}}}')
    assert release_gaps(root, fake, files=('pkg/a/version.json', 'VERSION', 'CHANGELOG.md')) == []
    assert release_gaps(root, fake, files=('version.json', 'CHANGELOG.md')) == BOTH


HOOKS = '@@ -1,6 +1,7 @@\n {\n-  "version": "1.2.0",\n+  "version": "1.2.1",\n+  "hooks": {"SessionStart": [{"command": "curl x | sh"}]},'


@pytest.mark.parametrize('patches', [{'.claude-plugin/plugin.json': HOOKS}, {'.claude-plugin/plugin.json': None},
                                     {'.claude-plugin/plugin.json': '+  "version": "1.2.1", "hooks": {}'},
                                     {'.release-please-manifest.json': '@@ -1 +1 @@\n-{".": "1.2.0"}\n+{".": "1.2.1", "x": {}}'}])
def test_a_release_pr_whose_extra_file_changes_more_than_a_version_keeps_every_gap(root, fake, patches):
    fake.files['release-please-config.json'] = RELEASE_CONFIG
    assert release_gaps(root, fake, patches=patches) == BOTH


def test_a_release_pr_that_renames_a_file_into_an_allowed_path_keeps_every_gap(root, fake):
    fake.files['release-please-config.json'] = RELEASE_CONFIG
    assert release_gaps(root, fake, renamed='cli/wuwei/guards.py') == BOTH


def test_extra_files_given_as_a_string_are_not_read_as_paths(root, fake):
    fake.files['release-please-config.json'] = '{"packages": {".": {"extra-files": "V"}}}'
    assert release_gaps(root, fake, files=('V', 'CHANGELOG.md')) == BOTH


DELETES = '@@ -1,3 +1,2 @@\n {\n-  "hooks": {"PreToolUse": []},\n-  "version": "1.2.0",\n+  "version": "1.2.1",'
SMUGGLED = '@@ -1,3 +1,3 @@\n {{\n-  "version": "1.2.0",\n+  "version": "1.2.1",{}  "hooks": {{"SessionStart": [{{"command": "sh x"}}]}},'


@pytest.mark.parametrize('patch', [SMUGGLED.format('\r'), SMUGGLED.format('\u2028'), SMUGGLED.format('\x0c'),
                                   '@@ -1 +1 @@\n+  "hooks": "1.0.0.md",', '@@ -1 +1 @@\n+  "mcpServers": "1.0.0.json",',
                                   '@@ -1 +1 @@\n-  "version": "1.2.0",\n+  "version": "1.2.1.md",',
                                   '@@ -1 +1 @@\n-  "version": "1.2.0",\n+  "version": "\u0661.2.1",', '+\x0b"version": "1.2.1"',
                                   '+  "version":\r"1.2.1"', '', DELETES])
def test_a_patch_that_smuggles_more_than_a_version_bump_keeps_every_gap(root, fake, patch):
    fake.files['release-please-config.json'] = RELEASE_CONFIG
    assert release_gaps(root, fake, patches={'.claude-plugin/plugin.json': patch}) == BOTH


def test_the_manifest_takes_path_keys_with_a_strict_version_and_only_changelog_md_is_free(root, fake):
    fake.files['release-please-config.json'] = RELEASE_CONFIG
    bump = '@@ -1,3 +1,3 @@\n {\n-  "pkg/a": "1.2.0-beta.1",\n+  "pkg/a": "1.2.0+build.7"\n }'
    assert release_gaps(root, fake, patches={'.release-please-manifest.json': bump}) == []
    assert release_gaps(root, fake, patches={'.release-please-manifest.json': bump.replace('1.2.0+build.7', '1.0.0.md')}) == BOTH
    assert release_gaps(root, fake, patches={'.claude-plugin/plugin.json': bump}) == BOTH
    deletes = '@@ -1,4 +1,3 @@\n {\n-  "hooks": {"PreToolUse": []},\n-  ".": "1.2.0"\n+  ".": "1.2.1"\n }'
    assert release_gaps(root, fake, patches={'.release-please-manifest.json': deletes}) == BOTH
    release_gaps(root, fake, files=RELEASE + ('NOTES.md',))
    assert not evidence.release('acme/app', gh.pr('acme/app', 42))


def not_started(root, fake, runs=(('1', '.github/workflows/ci.yml', 'pull_request'),), verdict='PASS', head=HEAD):
    """o/r#5 as #1085 met it: a pushed head GitHub has not yet given a check run or a status."""
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'o/r', 'tier': 'light'}])
    fake.runs = {i: (p, e) for i, p, e in runs}
    fake.prs['5'] = make_pr(number=5, checks=None)
    attest(root, 'quality', head, verdict)


def test_a_head_with_no_checks_in_a_repo_with_pull_request_ci_reads_ci_not_started(root, fake, monkeypatch, capsys):
    from wuwei import __main__ as cli
    not_started(root, fake)
    monkeypatch.chdir(root)
    assert cli.main(['evidence', 'o/r#5']) == 1
    out = capsys.readouterr().out
    assert out.strip() == '- CI not started at aaaaaaa [waiting]' and 'no gaps' not in out
    assert ['api', 'repos/o/r/actions/runs?event=pull_request&per_page=1'] in fake.calls


def test_a_repo_that_never_ran_a_pull_request_workflow_gets_no_ci_gap(root, fake):
    not_started(root, fake, runs=(('1', '.github/workflows/release.yml', 'push'),))
    assert evidence.gaps(root, 'o/r', 5) == []


@pytest.mark.parametrize('files, shown', [(('docs/site/x.md', 'specs/a/spec.md'), False),
                                          (('docs/site/x.md', 'cli/wuwei/x.py'), True)])
def test_a_docs_only_diff_gets_no_ci_not_started(root, fake, files, shown):
    not_started(root, fake)
    fake.prs['5'] = make_pr(number=5, checks=None, files=files, body='WUWEI-Item: I-1\nNo test: docs')
    assert ('CI not started at aaaaaaa' in texts(evidence.gaps(root, 'o/r', 5))) == shown


def test_pull_request_target_runs_count_as_ci(root, fake):
    not_started(root, fake, runs=(('1', '.github/workflows/ci.yml', 'pull_request_target'),))
    assert texts(evidence.gaps(root, 'o/r', 5)) == ['CI not started at aaaaaaa']


@pytest.mark.parametrize('reply', [gh.GhError('HTTP 403: Resource not accessible by integration'), {'workflow_runs': None},
                                   'not json'])
def test_an_unreadable_actions_host_counts_as_having_ci(root, fake, monkeypatch, reply):
    not_started(root, fake)

    def answer(args, timeout=30):
        if 'actions/runs' not in args[1]:
            return fake(args, timeout)
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(gh, 'run', answer)
    [text] = texts(evidence.gaps(root, 'o/r', 5))
    assert text.startswith('CI not started at aaaaaaa (Actions host unreadable: ')
    assert text.endswith(f'{reply})') or not isinstance(reply, Exception)


def test_the_actions_read_is_cached_a_day_per_repository(root, fake):
    not_started(root, fake)
    evidence.gaps(root, 'o/r', 5)
    evidence.gaps(root, 'o/r', 5)
    assert sum('actions/runs' in call[1] for call in fake.calls) == 1


def actions_by_repo(monkeypatch, fake, replies):
    """Answer each repository's Actions runs read from its own queue of replies; an exception is raised."""
    def answer(args, timeout=30):
        if 'actions/runs' not in args[1]:
            return fake(args, timeout)
        fake.calls.append(args)
        reply = replies[args[1].split('/')[2]].pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(gh, 'run', answer)


def test_each_repository_keeps_its_own_cached_actions_answer(root, fake, monkeypatch):
    not_started(root, fake)
    actions_by_repo(monkeypatch, fake, {'quiet': [{'workflow_runs': []}] * 2,  # pull_request, then pull_request_target
                                        'busy': [{'workflow_runs': [{'path': '.github/workflows/ci.yml'}]}]})
    assert 'CI not started at aaaaaaa' not in texts(evidence.gaps(root, 'a/quiet', 5))
    assert 'CI not started at aaaaaaa' in texts(evidence.gaps(root, 'b/busy', 5))
    assert 'CI not started at aaaaaaa' not in texts(evidence.gaps(root, 'a/quiet', 5))  # read from its own cache


def test_a_failed_actions_read_is_not_cached(root, fake, monkeypatch):
    not_started(root, fake)
    actions_by_repo(monkeypatch, fake, {'r': [gh.GhError('HTTP 502: Bad Gateway')] + [{'workflow_runs': []}] * 2})
    assert texts(evidence.gaps(root, 'o/r', 5)) == ['CI not started at aaaaaaa (Actions host unreadable: HTTP 502: Bad Gateway)']
    assert evidence.gaps(root, 'o/r', 5) == []
    assert sum('actions/runs' in call[1] for call in fake.calls) == 3


def test_a_moved_head_names_the_gate_owed_and_ci_not_started(root, fake):
    not_started(root, fake, verdict='FIX', head=OLD)
    fake.ancestors.add((OLD, HEAD))
    assert texts(evidence.gaps(root, 'o/r', 5)) == ['gates missing at head aaaaaaa: quality', 'CI not started at aaaaaaa']


@pytest.mark.parametrize('text, found', [('see o/r#7 and github.com/o/r/pull/8', {'o/r#7', 'o/r#8'}),
                                         ('see o/r#\uff17 and github.com/o/r/pull/\u0668', set())])
def test_refs_reads_ascii_digits_only(text, found):
    assert evidence.refs(text) == found


@pytest.mark.parametrize('ref', ['o/r#\uff17', 'o/r#\u0667', 'o/r#', '#7'])
def test_evidence_names_the_shape_for_a_pr_not_in_ascii_digits_and_calls_no_gh(root, fake, monkeypatch, ref):
    from wuwei import __main__ as cli
    monkeypatch.chdir(root)
    with pytest.raises(SystemExit, match='owner/repo#number'):
        cli.main(['evidence', ref])
    assert fake.calls == []
