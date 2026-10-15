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
    pr = make_pr(files=('infra/main.tf', 'tests/test_x.py'), body='WUWEI-Item: I-1\nRollback: revert the PR')
    pr['statusCheckRollup'] = [{'name': 'test', 'conclusion': '', 'status': 'IN_PROGRESS'}]
    fake.prs['42'] = pr
    attest(root, 'quality')
    gaps = evidence.gaps(root, 'acme/app', 42)
    assert texts(gaps) == ['CI running', 'owner review needed (owner_paths: infra/main.tf)']
    assert not any(gap['actionable'] for gap in gaps)
    assert gaps[1]['owner']


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
    assert kinds == {'not linked to a plan item (add WUWEI-Item: <id> to the PR body)': 'process',
                     'no test in the diff': 'safety', '500 changed lines: split it, or add a Size: <reason> line': 'process',
                     'gates missing at head aaaaaaa: arch, quality, security': 'safety', 'no reviewer requested': 'process'}


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
