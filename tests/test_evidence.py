import pytest
import hashlib
import shutil
import time

from conftest import HEAD, OLD, footer, make_pr, verdict_text, write_plan
from wuwei import evidence, gh, ws


def attest(root, gate, head=HEAD, verdict='PASS', item='I-1', name=None, breaking='no', pr='acme/app#42', extra=''):
    path = root / ws.DIR / 'verdicts' / item / (name or f'{gate}-{head[:7]}.md')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(extra + verdict_text(gate=gate, verdict=verdict, head=head, item=item, pr=pr, breaking=breaking))
    ws.record(root, 'attest', {'path': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                               'gate': gate, 'item': item, 'head': head, 'verdict': verdict, 'role': f'sentinel-{gate}', 'agent': 'x'})
    return path


def forget(root):
    """A test that changes what the host holds at one sha drops what the cache kept for it, as GitHub never does."""
    shutil.rmtree(root / ws.DIR / 'cache', ignore_errors=True)


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


OLD_LINE = 'PR names its item by the old WUWEI-Item line: end the body with the WUWEI footer'


def test_the_old_item_line_alone_is_process_fit_that_names_the_footer(root, fake):
    standard(root)
    for gate in ('arch', 'quality', 'security'):
        attest(root, gate)
    fake.prs['42'] = make_pr(body='WUWEI-Item: I-1')
    found = evidence.gaps(root, 'acme/app', 42)
    assert [(g['text'], g['kind']) for g in found] == [(OLD_LINE, 'process')]
    assert evidence.visible(found) == evidence.blocking(found) == []
    for body in (footer(), 'WUWEI-Item: I-1\n\n' + footer(), footer() + '\nWUWEI-Item: I-1'):
        fake.prs['42'] = make_pr(body=body)
        assert OLD_LINE not in texts(evidence.gaps(root, 'acme/app', 42))


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
    pr = make_pr(files=('infra/main.tf', 'tests/test_x.py'), body=footer() + '\nRollback: revert the PR')
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
                             body=footer() + '\nRollback: revert the PR')
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
    fake.prs['42'] = make_pr(lines=300, body=footer() + '\nSize: one generated migration')
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
    fake.prs['42'] = make_pr(body=footer() + '\nRollback: revert the PR; the column is additive')
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
    fake.prs['42'] = make_pr(body=footer() + '\n## Summary\nx\n## Testing\ny')
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


SECURITY, OWNER = 'gates missing at head aaaaaaa: security', 'owner review needed (owner_paths: infra/main.tf)'


def owned_pr(root, fake):
    standard(root)
    fake.prs['42'] = make_pr(files=('infra/main.tf', 'tests/test_x.py'), body=footer() + '\nRollback: revert the PR')
    attest(root, 'quality')


def except_gap(root, text, head=HEAD[:7]):
    ws.record(root, 'ruling', {'kind': 'exception', 'pr': 'acme/app#42', 'head': head, 'gap': text, 'approved': True})


def test_a_short_or_partial_exception_waives_nothing(root, fake):
    owned_pr(root, fake)
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [SECURITY, OWNER]
    for text in ('e', 'E', ' e ', 'securit', 'security gate', 'owner review', 'owner review needed', 'gates missing',
                 'gates missing at head aaaaaaa', 'gates missing at head aaaaaaa: security, quality', SECURITY + ' and arch',
                 OWNER[:-1], 'owner_paths: infra/main.tf', 'infra/main.tf', 'a', '.', '?', '', None, 7, ['e']):
        except_gap(root, text)
    except_gap(root, 'quality')  # quality is not missing, so its name waives nothing either
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [SECURITY, OWNER]


def test_an_exception_naming_the_printed_gap_waives_that_gap_alone(root, fake):
    from wuwei import report
    owned_pr(root, fake)
    except_gap(root, 'Gates  missing at head aaaaaaa:\tsecurity. ', head=OLD[:7])  # another head waives nothing
    ws.record(root, 'ruling', {'kind': 'exception', 'pr': 'acme/app#41', 'head': HEAD[:7], 'gap': SECURITY, 'approved': True})
    ws.record(root, 'ruling', {'kind': 'exception', 'pr': 'acme/app#42', 'head': HEAD[:7], 'gap': OWNER, 'approved': False})
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [SECURITY, OWNER]
    except_gap(root, 'Gates  missing at head aaaaaaa:\tsecurity. ')
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [OWNER]
    except_gap(root, OWNER + ' [waiting]')  # as wuwei evidence prints a waiting gap
    assert evidence.gaps(root, 'acme/app', 42) == []
    assert f'- exception: acme/app#42 at aaaaaaa: {OWNER} [waiting]' in report.day(root)


def test_a_ruling_without_a_head_or_of_another_kind_waives_nothing_and_marks_after_waiting_fold(root, fake):
    owned_pr(root, fake)
    ws.record(root, 'ruling', {'kind': 'exception', 'pr': 'acme/app#42', 'gap': SECURITY, 'approved': True})
    ws.record(root, 'ruling', {'kind': 'breaking', 'pr': 'acme/app#42', 'head': HEAD[:7], 'gap': SECURITY, 'approved': True})
    except_gap(root, 'gates missing at head aaaaaaa: [waiting]security')
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [SECURITY, OWNER]
    except_gap(root, OWNER + ' [waiting]!')
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [SECURITY]


def test_an_exception_naming_its_gate_list_exactly_waives_that_gate_gap(root, fake):
    standard(root)
    fake.prs['42'] = make_pr(files=('infra/main.tf', 'src/app.py', 'tests/test_x.py'), body=footer() + '\nRollback: x')
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['gates missing at head aaaaaaa: quality, security', OWNER]
    for text in ('security', 'quality', 'arch', 'security, quality', 'quality, security, arch', 'quality security'):
        except_gap(root, text)
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['gates missing at head aaaaaaa: quality, security', OWNER]
    except_gap(root, 'Quality,  Security.')
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [OWNER]


def test_no_generated_accepted_gap_waives_a_gap_it_does_not_name(monkeypatch):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('probe', Path(__file__).parents[1] / 'specs' / 'excepted-exact' / 'probe.py')
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    gaps, accepted = probe.pairs()
    found, wrong = [evidence.gap(g) for g in gaps], []
    for a in accepted:
        monkeypatch.setattr(ws, 'rows', lambda root, kind, a=a: [{'data': {'kind': 'exception', 'pr': 'acme/app#42',
                                                                          'head': HEAD[:7], 'gap': a, 'approved': True}}])
        left = {g['text'] for g in evidence.excepted('.', 'acme/app#42', HEAD, found)}
        wrong += [(a, g) for g in gaps if (g not in left) != probe.names(a, g)]
    assert len(accepted) > 9000 and wrong == []


def test_a_delta_review_exception_names_its_gate(root, fake):
    standard(root)
    fake.prs['42'] = make_pr()
    fake.ancestors.add((OLD, HEAD))
    for gate in ('arch', 'quality', 'security'):
        attest(root, gate, OLD)
    except_gap(root, 'security')
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['no gate passed at head aaaaaaa (a delta review by quality)']
    except_gap(root, 'quality')
    assert evidence.gaps(root, 'acme/app', 42) == []


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
    fake.prs['42'] = make_pr(files=(*files, 'src/app.py', 'tests/test_app.py'), body=footer() + '\nRollback: revert')
    full_gates(root)
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [
        f'{SPEC}/spec.md has no ## Clarifications section: run clarify',
        f'{SPEC}/analysis.md has an open CRITICAL or HIGH finding: | A1 | HIGH | FR-2 has no task |',
        f'{SPEC}/checklists/requirements.md has 1 unchecked item']


def test_a_clean_full_tier_speckit_feature_passes(root, fake):
    light(root, 'full')
    fake.prs['42'] = make_pr(files=(*speckit(fake), 'src/app.py', 'tests/test_app.py'), body=footer() + '\nRollback: revert')
    full_gates(root)
    assert evidence.gaps(root, 'acme/app', 42) == []


def test_a_retarget_at_the_same_head_reads_the_spec_of_the_new_file_list(root, fake):
    """A stacked PR moved onto main keeps its head, but its diff now carries its parent's feature (#1161)."""
    from wuwei import guards
    light(root, 'full')
    fake.prs['42'] = make_pr(files=(*speckit(fake), 'src/app.py', 'tests/test_app.py'), body=footer() + '\nRollback: revert')
    full_gates(root)
    assert guards.merge_door(root, 'acme/app', 42) is None
    fake.files.update({'specs/8-stacked/spec.md': '# Spec\n', 'specs/8-stacked/plan.md': '# Plan\n', 'specs/8-stacked/tasks.md': '- [ ] T1\n'})
    fake.prs['42']['files'] += [{'path': 'specs/8-stacked/spec.md', 'additions': 5, 'deletions': 0}]
    found = guards.merge_door(root, 'acme/app', 42)
    assert found is not None and 'specs/8-stacked/tasks.md has 1 unchecked item' in found['reason'], found


def test_a_path_holding_a_newline_does_not_share_a_spec_key_with_two_paths(root, fake):
    """A git path may hold a newline, so the file-list digest must not join paths on one."""
    from wuwei import guards
    light(root, 'full')
    files = speckit(fake)
    fake.files.update({'specs/8-stacked/spec.md': '# Spec\n', 'specs/8-stacked/plan.md': '# Plan\n', 'specs/8-stacked/tasks.md': '- [ ] T1\n'})
    fake.prs['42'] = make_pr(files=(*files, 'specs/8-stacked/spec.md\nsrc/app.py', 'tests/test_app.py'), body=footer() + '\nRollback: revert')
    full_gates(root)
    assert guards.merge_door(root, 'acme/app', 42) is None
    fake.prs['42'] = make_pr(files=(*files, 'specs/8-stacked/spec.md', 'src/app.py', 'tests/test_app.py'), body=footer() + '\nRollback: revert')
    found = guards.merge_door(root, 'acme/app', 42)
    assert found is not None and 'specs/8-stacked/tasks.md has 1 unchecked item' in found['reason'], found


def test_a_wuwei_upgrade_reads_the_spec_again(root, fake, monkeypatch):
    """A new version may add or tighten a spec rule, so a result an older version cached is not reused."""
    from wuwei import guards
    light(root, 'full')
    fake.prs['42'] = make_pr(files=(*speckit(fake), 'src/app.py', 'tests/test_app.py'), body=footer() + '\nRollback: revert')
    full_gates(root)
    assert guards.merge_door(root, 'acme/app', 42) is None
    fake.files['specs/7-rate-limits/tasks.md'] = '- [ ] T1\n'
    monkeypatch.setattr(ws, 'version', lambda: '999.0.0')
    found = guards.merge_door(root, 'acme/app', 42)
    assert found is not None and 'tasks.md has 1 unchecked item' in found['reason'], found


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
    forget(root)
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [f'{change}/proposal.md missing: run the spec engine step that writes it']


def test_an_old_feature_the_pr_only_amends_is_not_held_to_the_full_spec_set(root, fake):
    light(root, 'full')
    files = speckit(fake)
    old = 'specs/2-identity'
    fake.files[f'{old}/contracts/api.yaml'] = 'openapi: 3.1.0\n'
    fake.prs['42'] = make_pr(files=(*files, f'{old}/contracts/api.yaml', 'src/app.py', 'tests/test_app.py'),
                             body=footer() + '\nRollback: revert')
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
    fake.prs['42'] = make_pr(files=(*files, 'src/app.py', 'tests/test_app.py'), body=footer() + '\nRollback: revert')
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
    fake.prs['42'] = make_pr(files=(*files, 'src/app.py', 'tests/test_app.py'), body=footer() + '\nRollback: revert')
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


def test_a_pass_at_the_same_head_that_names_the_fix_it_closes_clears_it(root, fake):
    """A finding closed outside the diff (the PR body) no longer needs a no-op commit to move the head (#1162)."""
    light(root)
    fake.prs['42'] = make_pr()
    fix = attest(root, 'quality', verdict='FIX')
    attest(root, 'quality', verdict='PASS', name='quality-aaaaaaa-2.md', extra='Supersedes: some-other.md\n')
    assert 'gates missing at head aaaaaaa: quality' in texts(evidence.gaps(root, 'acme/app', 42))
    attest(root, 'quality', verdict='PASS', name='quality-aaaaaaa-3.md', extra=f'Supersedes: {fix.relative_to(root)}\n')
    assert not any(t.startswith('gates missing') for t in texts(evidence.gaps(root, 'acme/app', 42)))


def test_a_pass_never_supersedes_an_escalate_an_older_fix_or_another_items_fix(root, fake):
    light(root)
    fake.prs['42'] = make_pr()
    gaps = lambda: texts(evidence.gaps(root, 'acme/app', 42))  # noqa: E731
    attest(root, 'quality', verdict='FIX')
    newest = attest(root, 'quality', verdict='FIX', name='quality-aaaaaaa-2.md')
    attest(root, 'quality', verdict='PASS', name='quality-aaaaaaa-3.md', extra='Supersedes: I-1/quality-aaaaaaa.md\n')
    attest(root, 'quality', verdict='PASS', name='quality-aaaaaaa-4.md', item='I-2', extra='Supersedes: I-2/quality-aaaaaaa-2.md\n')
    assert 'gates missing at head aaaaaaa: quality' in gaps()  # only the newest FIX of this item, by item and file
    attest(root, 'quality', verdict='PASS', name='quality-aaaaaaa-5.md', extra=f'Supersedes: {newest}\n')
    assert not any(t.startswith('gates missing') for t in gaps())
    escalated = attest(root, 'quality', verdict='ESCALATE', name='quality-aaaaaaa-6.md')
    attest(root, 'quality', verdict='PASS', name='quality-aaaaaaa-7.md', extra=f'Supersedes: {escalated.relative_to(root)}\n')
    assert 'gates missing at head aaaaaaa: quality' in gaps()  # an ESCALATE is the owner's


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
    fake.prs['42'] = make_pr(files=(f'{SPEC}/spec.md', 'src/app.py', 'tests/test_app.py'), body=footer() + '\nRollback: revert')


def test_a_resolved_high_finding_no_longer_holds_the_merge(root, fake):
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'full'}])
    analysis_pr(fake, '| F6 | HIGH | Resolved: tests/test_app.py::test_grant |')
    assert not any('analysis.md' in t for t in texts(evidence.gaps(root, 'acme/app', 42)))
    analysis_pr(fake, '| F6 | HIGH | open |')
    forget(root)
    assert any('open CRITICAL or HIGH finding' in t for t in texts(evidence.gaps(root, 'acme/app', 42)))


@pytest.mark.parametrize('files,lines,gates', [
    (('config/staging.yaml',), 1, 'quality'),
    (('src/auth/session.py', 'tests/test_session.py'), 10, 'quality, security'),
    (('src/a.py', 'tests/test_a.py'), 150, 'arch, quality'),
    (('requirements.txt',), 1, 'quality, security'),
    (('src/geometry/diameter.py',), 3, 'quality'),
    (('docs/auth.md',), 30, None),
    (('docs/guide.md',), 30, None),
    (('README.md', 'docs/site/index.md'), 150, None),
    (('specs/004-voice/spec.md', 'specs/004-voice/plan.md'), 890, 'arch')])
def test_the_diff_decides_which_gates_a_standard_item_needs(root, fake, files, lines, gates):
    standard(root)
    fake.prs['42'] = make_pr(files=files, lines=lines, body=footer() + '\nNo test: config')
    found = [t for t in texts(evidence.gaps(root, 'acme/app', 42)) if 'gate' in t]
    assert found == ([f'gates missing at head aaaaaaa: {gates}'] if gates else [])


@pytest.mark.parametrize('tier,files,gates', [
    ('standard', {'specs/004-voice/spec.md': 900, 'specs/004-voice/plan.md': 879, 'specs/001-x/spec.md': 1}, ('arch',)),
    ('standard', {'README.md': 100, 'docs/site/index.md': 100, 'docs/site/concepts/evidence.md': 100}, ()),
    ('standard', {'README.md': 5000, 'LICENSE': 300, 'docs/guide.md': 900}, ()),
    ('standard', {'specs/004-voice/spec.md': 200}, ()),
    ('standard', {'openspec/changes/x/proposal.md': 201}, ('arch',)),
    ('standard', {'src/a.py': 150, 'specs/004-voice/spec.md': 51}, ('arch', 'quality')),
    ('standard', {'src/a.py': 150, 'specs/004-voice/spec.md': 50}, ('quality',)),
    ('standard', {'src/a.py': 150, 'README.md': 300, 'LICENSE': 300}, ('quality',)),
    ('light', {'specs/001-x/contracts/api.yaml': 3}, ('arch',)),
    ('light', {'openspec/changes/x/specs/contracts/events.md': 3}, ('arch',)),
    ('standard', {'specs/contracts/api.yaml': 3}, ('arch',)),
    ('full', {'specs/001-x/contracts/api.yaml': 3}, ('arch',)),
    ('light', {'specs/001-x/spec.md': 3, 'docs/contracts/api.md': 3, 'specs/contracts.md': 3}, ()),
    ('standard', {'docs/conf.py': 300}, ('arch',)),
    ('standard', {'src/docs/x.py': 300}, ('arch',)),
    ('standard', {'NOTICE_handler.py': 300}, ('arch', 'quality')),
    ('standard', {'requirements/prod.txt': 300}, ('arch',)),
    ('standard', {'CMakeLists.txt': 300}, ('arch',)),
    ('standard', {'charters/x.md': 300}, ('arch',)),
    ('standard', {'AGENTS.md': 300}, ('arch',)),
    ('light', {'Specs/001-x/contracts/api.md': 3}, ('arch',)),
    ('standard', {'docs/requirements.txt': 300}, ('arch', 'quality', 'security')),
    ('light', {'docs/openapi.yaml': 3}, ('arch',)),
    ('light', {'specs/001-x/api.proto': 3}, ('arch',)),
    ('light', {'specs/001-x/Contracts/api.yaml': 3}, ('arch',)),
    ('light', {'contracts/Token.sol': 3, 'src/specs/contracts/h.py': 3}, ('quality',)),
])
def test_the_wide_trigger_counts_code_and_spec_lines_and_a_spec_contract_takes_arch(root, tier, files, gates):
    files = [{'path': path, 'additions': n, 'deletions': 0} for path, n in files.items()]
    assert evidence.needed(root, tier, files) == gates


def test_a_long_docs_delta_carries_the_passes_and_a_long_spec_delta_is_read_by_arch(root, fake):
    standard(root)
    fake.prs['42'] = make_pr()
    fake.ancestors.add((OLD, HEAD))
    for gate in ('arch', 'quality'):
        attest(root, gate, OLD)
    fake.deltas[(OLD, HEAD)] = [{'path': 'README.md', 'additions': 300, 'deletions': 0}]
    assert evidence.gaps(root, 'acme/app', 42) == []
    fake.deltas[(OLD, HEAD)] = [{'path': 'specs/004-voice/spec.md', 'additions': 200, 'deletions': 0}]
    forget(root)
    assert evidence.gaps(root, 'acme/app', 42) == []
    for path, n in (('specs/004-voice/spec.md', 201), ('specs/004-voice/contracts/api.yaml', 2)):
        fake.deltas[(OLD, HEAD)] = [{'path': path, 'additions': n, 'deletions': 0}]
        forget(root)
        assert texts(evidence.gaps(root, 'acme/app', 42)) == ['no gate passed at head aaaaaaa (a delta review by arch)']


def test_a_small_delta_after_review_carries_the_passes_and_a_risky_one_does_not(root, fake):
    standard(root)
    fake.prs['42'] = make_pr()
    fake.ancestors.add((OLD, HEAD))
    attest(root, 'quality', OLD)
    fake.deltas[(OLD, HEAD)] = [{'path': 'src/app.py', 'additions': 4, 'deletions': 2}]
    assert evidence.gaps(root, 'acme/app', 42) == []
    fake.deltas[(OLD, HEAD)] = [{'path': 'src/token.py', 'additions': 4, 'deletions': 2}]
    forget(root)
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['no gate passed at head aaaaaaa (a delta review by security)']


def test_verdicts_count_by_their_pr_when_the_item_is_not_in_the_plan(root, fake):
    fake.prs['42'] = make_pr(body=footer('OPS-9'))
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
                             body=footer() + '\nRollback: revert the PR')
    attest(root, 'quality')
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['owner review needed (owner_paths: infra/main.tf)']


def test_only_an_owner_review_ruling_clears_the_owner_review(root, fake):
    light(root)
    fake.prs['42'] = make_pr(files=('infra/main.tf', 'tests/test_x.py'), body=footer() + '\nRollback: revert the PR')
    attest(root, 'quality')
    for kind in ('breaking', 'exception', None, '', 0, False, []):
        ws.record(root, 'ruling', {'kind': kind, 'pr': 'acme/app#42', 'head': HEAD[:7], 'approved': True})
    ws.record(root, 'ruling', {'pr': 'acme/app#42', 'head': '', 'approved': True})  # a blank head matches no head
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
    attest(root, 'quality', head, verdict, pr='o/r#5')


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


@pytest.mark.parametrize('files, shown', [
    (('docs/site/x.md', 'specs/a/spec.md'), False), (('specs/a/plan.json',), False), (('LICENSE', 'README.rst'), False),
    (('docs/site/x.md', 'cli/wuwei/x.py'), True), (('requirements.txt',), True), (('CMakeLists.txt',), True),
    (('docs/exploit.py',), True), (('src/docs/x.py',), True), (('LICENSE.py',), True), ((), True),
    (('charters/builder.md',), True), (('agents/builder.md',), True), (('.claude/skills/x/SKILL.md',), True),
    (('AGENTS.md',), True), (('.claude/wuwei/charters/_gate.md',), True)])
def test_only_a_docs_or_specs_diff_skips_ci_not_started(root, fake, files, shown):
    not_started(root, fake)
    fake.prs['5'] = make_pr(number=5, checks=None, files=files, body=footer() + '\nNo test: docs')
    assert ('CI not started at aaaaaaa' in texts(evidence.gaps(root, 'o/r', 5))) == shown
    assert any('actions/runs' in call[1] for call in fake.calls) == shown  # a docs-only diff makes no Actions read


def test_a_file_renamed_out_of_code_keeps_ci_not_started(root, fake):
    not_started(root, fake)
    fake.prs['5'] = make_pr(number=5, checks=None, files=('docs/x.md',), body=footer() + '\nNo test: docs')
    fake.prs['5']['files'][0]['previous_filename'] = 'cli/wuwei/x.py'
    assert 'CI not started at aaaaaaa' in texts(evidence.gaps(root, 'o/r', 5))


def test_pull_request_target_runs_count_as_ci(root, fake):
    not_started(root, fake, runs=(('1', '.github/workflows/ci.yml', 'pull_request_target'),))
    assert texts(evidence.gaps(root, 'o/r', 5)) == ['CI not started at aaaaaaa']


@pytest.mark.parametrize('reply, error', [
    (gh.GhError('HTTP 403: Resource not accessible by integration'), 'HTTP 403: Resource not accessible by integration'),
    ({'workflow_runs': None}, "'NoneType' object is not iterable"), ('not json', "'str' object has no attribute 'get'")])
def test_an_unreadable_actions_host_counts_as_having_ci(root, fake, monkeypatch, reply, error):
    not_started(root, fake)

    def answer(args, timeout=30):
        if 'actions/runs' not in args[1]:
            return fake(args, timeout)
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(gh, 'run', answer)
    assert texts(evidence.gaps(root, 'o/r', 5)) == [f'CI not started at aaaaaaa (Actions host unreadable: {error})']


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


def breaking(root, fake, *said, title='feat: change 42'):
    """Breaking gaps once arch verdicts are attested in the order given, as (head, Breaking, verdict[, PR]) rows."""
    standard(root)
    fake.prs['42'] = {**make_pr(), 'title': title}
    fake.ancestors.add((OLD, HEAD))
    for n, (head, says, verdict, *pr) in enumerate(said):
        attest(root, 'arch', head, verdict, name=f'arch-{n}.md', breaking=says, pr=(pr or ['acme/app#42'])[0])
    attest(root, 'quality')
    attest(root, 'security')
    return [t for t in texts(evidence.gaps(root, 'acme/app', 42)) if t.startswith('breaking change')]


OTHER = 'c' * 40  # a head that is no ancestor of the PR head
ANNOUNCE = ['breaking change without an announcement: add "Announcement: <http(s) URL of the published client '
            'communication, release note or migration guide>", the URL alone on its line, without brackets']
CONFIRM = ['breaking change needs the owner\'s confirmation: ask "breaking: acme/app#42 at aaaaaaa: <what breaks>. '
           'Announced at <link>. Proceed?"']


@pytest.mark.parametrize('line, found', [
    ('Announcement: https://github.com/o/r/issues/1#issuecomment-1', CONFIRM),
    ('Announcement: http://status.acme.test/2026-10-15-export-v1', CONFIRM),
    ('Announcement:https://acme.test/n', CONFIRM),
    ('Announcement: \t https://acme.test/n \t', CONFIRM),
    ('Announcement: https://acme.test/n\r\nmore', CONFIRM),  # a CRLF body
    ('Announcement: CHANGELOG.md\nAnnouncement: https://acme.test/n', CONFIRM),  # a URL line among others
    ('Announcement: CHANGELOG.md (placeholder)', ANNOUNCE),
    ('Announcement: CHANGELOG.md', ANNOUNCE),  # a bare path
    ('Announcement: docs/migration.md', ANNOUNCE),
    ('Announcement: see CHANGELOG', ANNOUNCE),
    ('Announcement: TBD at release', ANNOUNCE),
    ('Announcement: see https://acme.test/n', ANNOUNCE),  # a URL inside prose
    ('Announcement: https://acme.test/n (written at release)', ANNOUNCE),
    ('Announcement: https://acme.test/a https://acme.test/b', ANNOUNCE),
    ('Announcement: [the note](https://acme.test/n)', ANNOUNCE),
    ('Announcement: <https://acme.test/n>', ANNOUNCE),
    ('Announcement: ftp://files.acme.test/notes.txt', ANNOUNCE),  # a non-http scheme
    ('Announcement: file:///home/x/notes.md', ANNOUNCE),
    ('Announcement: javascript:alert(1)', ANNOUNCE),
    ('Announcement: HTTPS://acme.test/n', ANNOUNCE),
    ('Announcement: www.acme.test/n', ANNOUNCE),
    ('Announcement: https://', ANNOUNCE),
    ('Announcement: https:// acme.test/n', ANNOUNCE),
    ('Announcement: https:///n', ANNOUNCE),
    ('Announcement:', ANNOUNCE),  # whitespace and blanks
    ('Announcement: \t ', ANNOUNCE),
    ('Announcement:\nhttps://acme.test/n', ANNOUNCE),
    ('Announcement: https://acme.test/n', ANNOUNCE),
    ('Announcement: https://acme.test/n ', ANNOUNCE),
    ('  Announcement: https://acme.test/n', ANNOUNCE),
    ('> Announcement: https://acme.test/n', ANNOUNCE),
    ('announcement: https://acme.test/n', ANNOUNCE),
])
def test_an_announcement_counts_only_as_one_http_url_alone_on_its_line(root, fake, line, found):
    standard(root)
    fake.prs['42'] = {**make_pr(body=f'{footer()}\n{line}'), 'title': 'feat!: drop the v1 export'}
    for gate in ('arch', 'quality', 'security'):
        attest(root, gate)
    assert texts(evidence.gaps(root, 'acme/app', 42)) == found


def test_a_body_at_the_github_limit_is_read_in_linear_time(root, fake):
    head = footer() + '\nAnnouncement: https://'
    body = head + 'a' * (65536 - len(head) - 2) + ' x'  # a host run that never reaches the end of the line
    standard(root)
    fake.prs['42'] = {**make_pr(body=body), 'title': 'feat!: drop the v1 export'}
    for gate in ('arch', 'quality', 'security'):
        attest(root, gate)
    started = time.perf_counter()
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ANNOUNCE
    assert time.perf_counter() - started < 1


@pytest.mark.parametrize('said, found', [
    ([(OLD, 'yes: drops --format', 'FIX'), (HEAD, 'no', 'PASS')], []),  # a later re-read clears it
    ([(OLD, 'no', 'PASS'), (HEAD, 'yes: drops --format', 'FIX')], ANNOUNCE),  # a later re-read finds it
    ([(HEAD, 'yes: drops --format', 'PASS'), (HEAD, 'no', 'PASS')], ANNOUNCE),  # relaunching at one head clears nothing
    ([(HEAD, 'no', 'PASS'), (HEAD, 'yes: drops --format', 'PASS')], ANNOUNCE),
    ([(HEAD, 'no', 'PASS'), (OLD, 'yes: drops --format', 'PASS')], ANNOUNCE),  # a yes holds at any head
    ([(HEAD, 'yes: drops --format', 'PASS'), (OLD, 'no', 'PASS')], ANNOUNCE),  # F1: a stale seat at an ancestor
    ([(HEAD, 'yes: drops --format', 'PASS'), (OTHER, 'no', 'PASS')], ANNOUNCE),  # F2: a head off this PR's line
    ([(HEAD, 'yes: drops --format', 'PASS'), (OTHER, 'no', 'PASS', 'acme/app#7')], ANNOUNCE),  # F3: another PR
    ([(HEAD, 'yes: drops --format', 'PASS'), (OTHER, 'no', 'PASS', 'acme/other#1')], ANNOUNCE),  # F3: another repo
    ([(OLD, 'yes: drops --format', 'FIX'), (HEAD, 'no', 'PASS', 'acme/app#7')], ANNOUNCE),  # another PR, on the line
    ([(OLD, 'yes: drops --format', 'FIX'), (HEAD, 'no', 'PASS', 'acme/app')], []),  # before the draft PR existed
    ([(OLD, 'yes: drops --format', 'FIX'), (HEAD, 'no', 'PASS', 'Acme/App#42')], []),
    ([(OLD, 'no', 'PASS'), (OLD, 'yes: x', 'FIX'), (HEAD, 'no', 'PASS')], []),  # a descendant re-read still clears
    ([(HEAD, 'yes: drops --format', 'PASS', 'acme/app#7')], ANNOUNCE),  # a yes from another PR of the item holds
])
def test_breaking_is_read_from_the_latest_arch_verdict(root, fake, said, found):
    assert breaking(root, fake, *said) == found


@pytest.mark.parametrize('title', ['fix(x)!: drop the v1 export', 'feat!: drop the v1 export'])
def test_a_declared_break_holds_though_every_arch_verdict_says_no(root, fake, title):
    assert breaking(root, fake, (OLD, 'yes: x', 'FIX'), (HEAD, 'no', 'PASS'), title=title) == ANNOUNCE


def test_ledger_order_decides_not_file_names(root, fake):
    standard(root)
    fake.prs['42'] = make_pr()
    fake.ancestors.add((OLD, HEAD))
    attest(root, 'arch', OLD, name='arch-z.md', breaking='yes: drops --format')  # sorts last, attested first
    attest(root, 'arch', name='arch-a.md', breaking='no')
    attest(root, 'quality')
    attest(root, 'security')
    assert evidence.gaps(root, 'acme/app', 42) == []


def test_an_edited_arch_verdict_that_kept_no_breaking_field_leaves_the_last_one_that_did(root, fake):
    standard(root)
    fake.prs['42'] = make_pr()
    fake.ancestors.add((OLD, HEAD))
    attest(root, 'arch', OLD, name='arch-0.md', breaking='yes: drops --format')
    edited = attest(root, 'arch', HEAD, 'FIX', name='arch-1.md')
    edited.write_text(edited.read_text() + '\nedited\n')  # the FIX holds as recorded, without its Breaking line
    assert ANNOUNCE[0] in texts(evidence.gaps(root, 'acme/app', 42))


def test_a_no_on_a_dropped_descendant_of_the_yes_clears_nothing(root, fake):
    fake.ancestors.add((OLD, OTHER))  # OTHER grew from OLD but was force-pushed away: not under the PR head
    assert breaking(root, fake, (OLD, 'yes: drops --format', 'FIX'), (OTHER, 'no', 'PASS')) == ANNOUNCE


def gated(root, fake, *said):
    """Gate gaps once quality verdicts are attested in the order given, as (head, verdict[, PR]) rows; the change
    needs quality alone."""
    standard(root)
    fake.prs['42'] = make_pr()
    fake.ancestors.update({(OLD, HEAD), (OLD, OTHER)})  # OTHER grew from OLD off this PR's line
    for n, (head, verdict, *pr) in enumerate(said):
        attest(root, 'quality', head, verdict, name=f'quality-{n}.md', pr=(pr or ['acme/app#42'])[0])
    return [t for t in texts(evidence.gaps(root, 'acme/app', 42)) if t.startswith(('gates missing', 'no gate passed'))]


OWED = ['gates missing at head aaaaaaa: quality']


@pytest.mark.parametrize('said, found', [
    ([(HEAD, 'FIX'), (OLD, 'PASS')], OWED),  # an older ancestor's pass attested after a finding at the head
    ([(OTHER, 'PASS')], OWED),  # a head off this PR's line
    ([(HEAD, 'PASS', 'acme/app#7')], OWED),  # another PR of the item
    ([(HEAD, 'PASS', 'acme/other#42')], OWED),  # another repository
    ([(HEAD, 'FIX'), (HEAD, 'PASS')], OWED),  # a relaunch at one head clears nothing
    ([(HEAD, 'FIX'), (OLD, 'FIX'), (HEAD, 'PASS')], OWED),  # an older finding does not move the newer one back
    ([(HEAD, 'FIX'), (OLD, 'PASS', 'acme/app#7'), (HEAD, 'PASS', 'acme/app#7')], OWED),
    ([(OLD, 'FIX'), (HEAD, 'PASS')], []),  # a pass at a descendant clears it
    ([(OLD, 'FIX'), (HEAD, 'PASS', 'acme/app')], []),  # written before the draft PR existed
    ([(OLD, 'FIX'), (HEAD, 'PASS', 'Acme/App#42')], []),
    ([(HEAD, 'PASS'), (OLD, 'PASS')], []),  # an older pass attested later leaves the newer one
    ([(HEAD, 'PASS'), (HEAD, 'FIX')], OWED),  # a finding replaces a pass at one head
    ([(HEAD, 'PASS'), (OLD, 'FIX')], OWED),  # and at an older head, so the gate reads again
    ([(HEAD, 'PASS'), (OLD, 'FIX', 'acme/app#7')], OWED),  # a finding on the PR's line holds from another PR
    ([(OLD, 'FIX', 'acme/app#7'), (HEAD, 'PASS')], []),  # and a pass here at a descendant clears it
])
def test_a_gate_is_read_from_its_verdict_at_the_newest_head_on_this_pr(root, fake, said, found):
    assert gated(root, fake, *said) == found


@pytest.mark.parametrize('edited', [False, True])
def test_a_finding_for_another_pr_of_the_item_still_holds(root, fake, edited):
    standard(root)
    attest(root, 'quality')
    path = root / ws.DIR / 'verdicts' / 'I-1' / 'quality-fix.md'
    path.write_text(verdict_text(verdict='FIX', pr='acme/app#7'))
    ws.record(root, 'attest', {'path': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                               'gate': 'quality', 'item': 'I-1', 'head': HEAD, 'pr': 'acme/app#7', 'verdict': 'FIX'})
    if edited:
        path.write_text(path.read_text() + '\nedited\n')  # the FIX holds as recorded
    found = texts(evidence.gate_gaps(root, 'acme/app', 'I-1', ('quality',), HEAD, ref='acme/app#42'))
    assert [t for t in found if t.startswith('gates missing')] == OWED


@pytest.mark.parametrize('pr, found', [('acme/app#42', []), ('acme/app', []), ('acme/other#42', OWED)])
def test_before_its_pr_is_read_a_verdict_counts_on_its_repository(root, fake, pr, found):
    standard(root)
    attest(root, 'quality', pr=pr)
    assert texts(evidence.gate_gaps(root, 'acme/app', 'I-1', ('quality',), HEAD)) == found


def imported(root, verdict, head):
    """A 0.34 verdict as wuwei upgrade attests it: no PR in the row, the head as 0.34 wrote it."""
    path = root / ws.DIR / 'verdicts' / 'I-1' / f'quality-imported-{verdict}.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(verdict_text(gate='quality', verdict=verdict, head=HEAD, pr=''))
    ws.record(root, 'attest', {'path': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                               'gate': 'quality', 'item': 'I-1', 'head': head, 'verdict': verdict, 'imported': True})


@pytest.mark.parametrize('ref', ['acme/app#42', 'acme/app#7', ''])
def test_an_imported_pass_counts_for_every_pr_of_its_item(root, fake, ref):
    standard(root)
    imported(root, 'PASS', HEAD)
    assert texts(evidence.gate_gaps(root, 'acme/app', 'I-1', ('quality',), HEAD, ref=ref)) == []


def test_an_imported_finding_at_a_short_head_holds_against_a_pass_at_that_commit(root, fake):
    standard(root)
    fake.ancestors.add((HEAD[:7], HEAD))
    imported(root, 'FIX', HEAD[:7])
    attest(root, 'quality', HEAD, 'PASS', name='quality-relaunch.md')
    assert [t for t in texts(evidence.gate_gaps(root, 'acme/app', 'I-1', ('quality',), HEAD, ref='acme/app#42'))
            if t.startswith('gates missing')] == OWED


def test_the_walk_asks_the_code_host_about_each_pair_of_heads_once(root, fake):
    standard(root)
    mid = 'd' * 40
    fake.ancestors.update({(OLD, mid), (mid, HEAD), (OLD, HEAD)})
    attest(root, 'quality', OLD, 'PASS', name='quality-0.md')
    attest(root, 'quality', mid, 'FIX', name='quality-1.md')
    found = texts(evidence.gate_gaps(root, 'acme/app', 'I-1', ('quality',), HEAD, ref='acme/app#42'))
    asked = [c[1].split('/compare/')[1] for c in fake.calls if c[0] == 'api' and '/compare/' in c[1]]
    assert found[:1] == OWED and sorted(asked) == sorted([f'{OLD}...{HEAD}', f'{mid}...{HEAD}', f'{OLD}...{mid}'])


@pytest.mark.parametrize('head, supersedes, pr, found', [
    (HEAD, 'I-1/quality-fix.md', 'acme/app#42', []),  # a pass at the finding's head that names it clears it (#1162)
    (HEAD, 'I-1/quality-fix.md', 'acme/app', []),  # written before the draft PR existed
    (HEAD, '', 'acme/app#42', OWED),  # the same pass without Supersedes clears nothing
    (HEAD, 'I-2/quality-fix.md', 'acme/app#42', OWED),  # nor one naming another item's file of that name
    (HEAD, 'XI-1/quality-fix.md', 'acme/app#42', OWED),  # nor one whose item only ends in this item's id
    (OLD, 'I-1/quality-fix.md', 'acme/app#42', OWED),  # a pass at an older head never clears, named or not
    (HEAD, 'I-1/quality-fix.md', 'acme/app#7', OWED),  # nor a pass for another PR of the item
])
def test_a_pass_clears_a_finding_at_its_head_only_by_naming_it(root, fake, head, supersedes, pr, found):
    standard(root)
    fake.prs['42'] = make_pr()
    fake.ancestors.add((OLD, HEAD))
    attest(root, 'quality', HEAD, 'FIX', name='quality-fix.md')
    attest(root, 'quality', head, 'PASS', name='quality-pass.md', pr=pr, extra=f'Supersedes: {supersedes}\n' if supersedes else '')
    assert [t for t in texts(evidence.gaps(root, 'acme/app', 42)) if t.startswith(('gates missing', 'no gate'))] == found


def test_a_later_fix_at_its_head_does_not_replace_a_held_escalate(root, fake):
    standard(root)
    fake.prs['42'] = make_pr()
    attest(root, 'quality', HEAD, 'ESCALATE', name='quality-esc.md')
    attest(root, 'quality', HEAD, 'FIX', name='quality-fix.md')
    attest(root, 'quality', HEAD, 'PASS', name='quality-pass.md', extra='Supersedes: I-1/quality-fix.md\n')
    assert [t for t in texts(evidence.gaps(root, 'acme/app', 42)) if t.startswith(('gates missing', 'no gate'))] == OWED


# The checks the base branch requires (required-checks): #1156 and #1157 merged with none of them run on their heads.
REQUIRED_1157 = ['test (3.11)', 'test (3.12)', 'ziran-audit']
BRANCH = 'repos/acme/app/branches/'  # the branch read, never the rules read under rules/branches/
BLOCKED = 'GitHub reports the merge blocked for a reason WUWEI cannot name: read the merge box on the PR'


def complete(root, fake, checks=('CodeQL',)):
    """acme/app#42 with every gate passed at its head and each named check run green: no gap on main."""
    standard(root)
    fake.prs['42'] = make_pr()
    fake.prs['42']['statusCheckRollup'] = [{'name': name, 'conclusion': 'SUCCESS', 'status': 'COMPLETED'} for name in checks]
    for gate in ('arch', 'quality', 'security'):
        attest(root, gate)


def denied(root, auto=False):
    from wuwei import guards
    return (guards.merge_door(root, 'acme/app', 42, auto=auto) or {}).get('reason', '')


def test_a_required_check_with_no_run_on_the_head_holds_the_merge(root, fake):
    complete(root, fake)
    fake.protection['main'] = ['test (3.11)']
    found = evidence.gaps(root, 'acme/app', 42)
    assert [(g['text'], g['kind'], g['actionable']) for g in found] == [
        ('required check not run at aaaaaaa: test (3.11)', 'safety', True)]
    assert '- required check not run at aaaaaaa: test (3.11)' in denied(root)
    assert '- required check not run at aaaaaaa: test (3.11)' in denied(root, auto=True)  # it never starts by waiting


def test_the_merged_release_pr_shows_its_required_checks_post_merge(root, fake):
    complete(root, fake)
    fake.protection['main'] = REQUIRED_1157
    fake.prs['42'].update(state='MERGED', mergedAt='2026-10-19T08:00:00Z')
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [
        'post-merge: required checks not run at aaaaaaa: test (3.11), test (3.12), ziran-audit']


@pytest.mark.parametrize('protection, rulesets, shown', [
    (REQUIRED_1157, [], 'required checks not run at aaaaaaa: test (3.11), test (3.12), ziran-audit'),
    ([], ['ziran-audit'], 'required check not run at aaaaaaa: ziran-audit'),
    (None, ['ziran-audit'], 'required check not run at aaaaaaa: ziran-audit'),
    (['test (3.11)'], ['test (3.11)', 'ziran-audit'], 'required checks not run at aaaaaaa: test (3.11), ziran-audit')])
def test_protection_and_rulesets_each_require_checks_and_each_is_named_once(root, fake, protection, rulesets, shown):
    complete(root, fake)
    fake.protection['main'], fake.rulesets['main'] = protection, rulesets
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [shown]
    assert ['api', 'repos/acme/app/branches/main'] in fake.calls
    assert ['api', 'repos/acme/app/rules/branches/main?per_page=100&page=1'] in fake.calls


def test_every_required_check_green_reads_as_on_main(root, fake):
    complete(root, fake, checks=('CodeQL', 'test (3.11)', 'test (3.12)'))
    fake.prs['42']['statusCheckRollup'].append({'context': 'ziran-audit', 'state': 'SUCCESS', 'url': None})
    fake.prs['42']['mergeableState'] = 'clean'
    main = evidence.gaps(root, 'acme/app', 42)
    forget(root)
    fake.protection['main'], fake.rulesets['main'] = ['test (3.11)', 'test (3.12)'], ['ziran-audit']
    assert evidence.gaps(root, 'acme/app', 42) == main == []
    assert denied(root) == ''


@pytest.mark.parametrize('run, shown', [
    ({'conclusion': 'FAILURE', 'status': 'COMPLETED'}, 'CI failing: test (3.11)'),
    ({'conclusion': '', 'status': 'IN_PROGRESS'}, 'CI running')])
def test_a_required_check_that_ran_reads_as_ci(root, fake, run, shown):
    complete(root, fake)
    fake.prs['42']['statusCheckRollup'].append({'name': 'test (3.11)', **run})
    fake.protection['main'] = ['test (3.11)']
    assert texts(evidence.gaps(root, 'acme/app', 42)) == [shown]


@pytest.mark.parametrize('reply', [None, []])
def test_a_branch_that_requires_no_check_is_not_a_gap(root, fake, reply):
    complete(root, fake)
    fake.protection['main'] = reply  # unprotected, or protected with no required check
    assert evidence.gaps(root, 'acme/app', 42) == []


def answering(monkeypatch, fake, route, reply):
    def answer(args, timeout=30):
        if route not in args[1]:
            return fake(args, timeout)
        fake.calls.append(args)
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(gh, 'run', answer)


@pytest.mark.parametrize('route, reply, error', [
    (BRANCH, gh.GhError('gh: Not Found (HTTP 404)'), 'gh: Not Found (HTTP 404)'),
    (BRANCH, gh.GhError('gh: Branch not found (HTTP 404)'), 'gh: Branch not found (HTTP 404)'),
    (BRANCH, gh.GhError('gh: Resource not accessible by integration (HTTP 403)'), 'gh: Resource not accessible by integration (HTTP 403)'),
    (BRANCH, {'name': 'main', 'protected': True}, "'protection'"),
    (BRANCH, {'protection': {'enabled': True}}, "'required_status_checks'"),
    (BRANCH, {'protection': {'required_status_checks': {'checks': [{'context': 'test (3.11)'}]}}}, "'contexts'"),
    (BRANCH, {'protection': {'required_status_checks': {'contexts': None}}}, "unsupported operand type(s) for +: 'NoneType' and 'list'"),
    (BRANCH, 'not json', 'string indices must be integers, not \'str\''),
    ('/rules/branches/', gh.GhError('gh: HTTP 502: Bad Gateway (HTTP 502)'), 'gh: HTTP 502: Bad Gateway (HTTP 502)'),
    ('/rules/branches/', [{'type': 'required_status_checks'}], "'parameters'")])
def test_an_unreadable_required_read_fails_closed(root, fake, monkeypatch, route, reply, error):
    complete(root, fake)
    answering(monkeypatch, fake, route, reply)
    found = evidence.gaps(root, 'acme/app', 42)
    assert [(g['text'], g['kind'], g['actionable']) for g in found] == [
        (f'required checks unreadable on main: {error}', 'safety', False)]
    assert f'- required checks unreadable on main: {error}' in denied(root)


def test_a_failed_required_read_is_read_again(root, fake):
    complete(root, fake)
    fake.protection['main'] = gh.GhError('gh: HTTP 502: Bad Gateway (HTTP 502)')
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['required checks unreadable on main: gh: HTTP 502: Bad Gateway (HTTP 502)']
    fake.protection['main'] = ['test (3.11)']
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['required check not run at aaaaaaa: test (3.11)']


def test_the_required_read_is_kept_per_repository_and_base_branch(root, fake):
    import os
    complete(root, fake)
    fake.protection.update({'main': ['test (3.11)'], 'a__b': ['ziran-audit']})
    reads = lambda: sum(args[1].startswith(('repos/acme/app/branches/', 'repos/acme/other/branches/')) for args in fake.calls)  # noqa: E731
    assert texts(evidence.gaps(root, 'acme/app', 42)) == texts(evidence.gaps(root, 'acme/app', 42)) == [
        'required check not run at aaaaaaa: test (3.11)']
    assert reads() == 1 and sum('/rules/branches/' in args[1] for args in fake.calls) == 1
    fake.protection['main'] = []  # kept for its window: the next read still names it
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['required check not run at aaaaaaa: test (3.11)'] and reads() == 1
    fake.prs['42']['baseRefName'] = 'a/b'
    assert evidence.gaps(root, 'acme/app', 42) == [] and reads() == 2
    fake.prs['42']['baseRefName'] = 'a__b'  # never the entry of a/b
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['required check not run at aaaaaaa: ziran-audit'] and reads() == 3
    evidence.gaps(root, 'acme/other', 42)
    assert reads() == 4
    fake.prs['42']['baseRefName'] = 'main'
    for entry in (root / ws.DIR / 'cache').glob('required-acme__app-*.json'):
        old = entry.stat().st_mtime - evidence.PR_TTL - 1
        os.utime(entry, (old, old))
    assert evidence.gaps(root, 'acme/app', 42) == [] and reads() == 5


@pytest.mark.parametrize('state, other, shown', [
    ('blocked', None, True), ('blocked', 'process', True), ('blocked', 'safety', False), ('clean', None, False),
    ('unknown', None, False), ('unstable', None, False), ('behind', None, False), ('has_hooks', None, False), (None, None, False)])
def test_github_blocked_with_no_gap_wuwei_can_name_is_a_gap(root, fake, state, other, shown):
    complete(root, fake)
    fake.prs['42']['mergeableState'] = state
    if other == 'process':
        fake.prs['42']['reviewRequests'] = []
    if other == 'safety':
        fake.prs['42']['statusCheckRollup'][0]['conclusion'] = 'FAILURE'
    found = evidence.gaps(root, 'acme/app', 42)
    assert (evidence.gap(BLOCKED, actionable=False) in found) == shown  # a review hold is not the team's to act on
    assert (f'- {BLOCKED}' in denied(root)) == shown
    assert len(evidence.blocking(found)) == (1 if shown or other == 'safety' else 0)
    assert (denied(root, auto=True) == '') == (other != 'safety')  # GitHub's auto-merge waits on its own hold


def test_the_pr_read_carries_github_mergeable_state(root, fake):
    fake.prs['42'] = {**make_pr(), 'mergeableState': 'blocked'}
    assert gh.pr('acme/app', 42)['mergeableState'] == 'blocked'


@pytest.mark.parametrize('running', [{'name': 'build', 'conclusion': '', 'status': 'IN_PROGRESS'},
                                     {'context': 'ci/external', 'state': 'PENDING', 'url': None}])
def test_a_required_check_not_yet_created_while_ci_runs_waits_and_lets_auto_merge_arm(root, fake, running):
    complete(root, fake)  # a needs: job: GitHub creates its check run only once the job is queued
    fake.prs['42']['statusCheckRollup'].append(running)
    fake.protection['main'] = ['test (3.11)']
    found = evidence.gaps(root, 'acme/app', 42)
    assert [(g['text'], g['kind'], g['actionable']) for g in found] == [
        ('CI running', 'safety', False), ('required check not run yet at aaaaaaa: test (3.11)', 'safety', False)]
    assert denied(root, auto=True) == ''
    assert denied(root).endswith('- CI running\n- required check not run yet at aaaaaaa: test (3.11)')


def test_a_required_check_on_the_second_page_of_rules_is_read(root, fake, monkeypatch):
    complete(root, fake)
    rule = {'type': 'required_status_checks', 'parameters': {'required_status_checks': [{'context': 'ziran-audit'}]}}
    monkeypatch.setattr(gh, 'run', lambda args, timeout=30, run=gh.run: (
        [{'type': 'deletion'}] * 100 if args[1].endswith('page=1') else [rule]) if '/rules/branches/' in args[1] else run(args, timeout))
    assert texts(evidence.gaps(root, 'acme/app', 42)) == ['required check not run at aaaaaaa: ziran-audit']


@pytest.mark.parametrize('status, shown', [
    ('COMPLETED', 'required check not run at aaaaaaa: ziran-audit (release-please pushed with the workflow token, which starts no '
                  'workflow: close and reopen the PR, or give release-please a token)'),
    ('IN_PROGRESS', 'required check not run yet at aaaaaaa: ziran-audit')])  # while CI runs the check may still come
def test_a_release_pr_with_no_required_run_names_the_way_through(root, fake, status, shown):
    fake.files['release-please-config.json'] = RELEASE_CONFIG
    fake.protection['main'] = ['ziran-audit']
    release_gaps(root, fake)
    fake.prs['42']['statusCheckRollup'][0]['status'] = status
    forget(root)
    assert [t for t in texts(evidence.gaps(root, 'acme/app', 42)) if t.startswith('required')] == [shown]


@pytest.mark.parametrize('base, path', [('a#b', 'a%23b'), ('a/b', 'a/b'), ('a%b', 'a%25b')])
def test_the_base_branch_name_is_encoded_in_the_required_reads(root, fake, base, path):
    complete(root, fake)
    fake.prs['42']['baseRefName'] = base
    evidence.gaps(root, 'acme/app', 42)
    assert ['api', f'repos/acme/app/branches/{path}'] in fake.calls
    assert ['api', f'repos/acme/app/rules/branches/{path}?per_page=100&page=1'] in fake.calls
