"""Stop's minimal PR action reader and externally verified disposition producer."""

from wuwei import decision, obligations, registry, state, watch, workspace
from wuwei.references import pull_request


def _verify(root, host, ref, record, config):
    kind, identifier, comment_id = record['kind'], record['decision'], record['comment_id']
    day = workspace.day_dir(root).name
    if (kind not in ('parked', 'carried') or record['day'] != day
            or type(comment_id) is not int or comment_id <= 0):
        raise ValueError('invalid PR disposition')
    text = decision.today_path(identifier, root).read_text(encoding='utf-8')
    fields, _ = decision.evaluate(text)
    if (decision.route(fields) != 'owner' or fields['Decided-by'] != 'owner'
            or identifier in state.read_state(root).get('decision_outcomes', {})):
        raise ValueError('disposition needs an owner-routed decision without a seat outcome')
    if obligations._fingerprint(text) != record['decision_fingerprint']:
        raise ValueError('disposition decision changed; verify again')
    discussion = obligations._read(host.threads, ref, root=root)
    comments = obligations._records(discussion['comments'])
    expected = f'WUWEI {kind} {ref} {identifier} {day} {record["decision_fingerprint"]}'
    owner = obligations._owner_login(config)
    if not any(row['id'] == comment_id and row['author'] == owner and not row['is_bot']
               and row['body'].strip() == expected for row in comments):
        raise ValueError('disposition needs a fresh owner-authored comment: ' + expected)
    return kind


def record_disposition(root, ref, kind, identifier, comment_id):
    ref = pull_request(ref)
    config = workspace.load_config(root)
    host, refs = watch.owned(root, config)
    if ref not in refs:
        raise ValueError('PR must be raised or claimed today')
    text = decision.today_path(identifier, root).read_text(encoding='utf-8')
    record = {'kind': kind, 'decision': identifier, 'comment_id': comment_id,
              'day': workspace.day_dir(root).name,
              'decision_fingerprint': obligations._fingerprint(text)}
    _verify(root, host, ref, record, config)
    def update(data):
        data.setdefault('pr_dispositions', {})[ref] = record
    state._write_state(update, root, reserved=False, kind='pr.disposition',
                       payload={'pr': ref, **record})
    return 0


def check(root, *, closing=False):
    findings, code = [], 0
    try:
        data = state.read_state(root)
        if not (workspace.day_dir(root) / 'state.json').is_file():
            raise ValueError('day state missing')
        config = workspace.load_config(root)
        host, refs = watch.owned(root, config)
        if not refs:
            obligations._check_empty_day(workspace.day_dir(root))
        actions = watch.saved(root).get('actions', {})
        dispositions = data.get('pr_dispositions', {})
        if not isinstance(actions, dict) or not isinstance(dispositions, dict):
            raise ValueError('invalid PR action or disposition ledger')
        for ref in refs:
            try:
                pr = obligations._read(host.pr, ref, root=root)
                if (pr['state'] not in ('open', 'closed') or type(pr['merged']) is not bool
                        or f'{pr["repo"]}#{pr["number"]}' != ref
                        or (pr['merged'] and pr['state'] != 'closed')):
                    raise ValueError('invalid PR state evidence')
                if pr['merged']:
                    continue
                disposition = (_verify(root, host, ref, dispositions[ref], config)
                               if ref in dispositions else None)
                if disposition == 'parked' or closing and disposition == 'carried':
                    continue
                if ref in actions:
                    action = actions[ref]
                    deadline = obligations._time(action['deadline'])
                    created = obligations._time(action['created_at'])
                    if (created > workspace.now() or deadline <= created
                            or not isinstance(action['action'], str) or not action['action'].strip()
                            or action['state'] not in ('open', 'closed')):
                        raise ValueError('invalid action record')
                    if workspace.now() > deadline:
                        code = max(code, 1)
                        findings.append(f'{ref} {pr["state"]}: overdue action: {action["action"]}')
                if closing:
                    code = max(code, 1)
                    findings.append(f'{ref} {pr["state"]}: must be merged, parked or carried to tomorrow')
            except watch.ERRORS as exc:
                code = 2
                findings.append(f'{ref} action unmeasured: {exc}')
    except watch.ERRORS as exc:
        code = 2
        findings.append(f'PR actions unmeasured: {exc}')
    return code, '\n'.join(findings)
