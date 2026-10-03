"""Reply and visibility obligations from fresh code-host evidence."""

from datetime import datetime
import hashlib
import json
import re
from urllib.parse import urlsplit

from wuwei import registry, state, verdict, workspace
from wuwei.commands.event import FREE_KINDS
from wuwei.references import pull_request
from wuwei.verdict import VERDICTS
from wuwei.exits import DAMAGED, ADAPTER_DATA

SOLO = 'reviewers: none (solo)'


def _read(operation, *args, root):
    result = operation(*args, root=root)
    if type(result.exit) is not int or result.exit != 0:
        raise ValueError(result.reason or 'code-host read unavailable; retry; if it repeats, run bin/wuwei doctor, which tests the code host adapter')
    return result.data


def _list(value):
    if not isinstance(value, list):
        raise ValueError(f'expected complete evidence list; {DAMAGED}')
    return value


def _time(value):
    if not isinstance(value, str):
        raise ValueError(f'missing evidence timestamp; {DAMAGED}')
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f'evidence timestamp needs timezone; {DAMAGED}')
    return parsed


def _records(records, *, reviews=False):
    for row in _list(records):
        if (not isinstance(row, dict) or type(row.get('id')) is not int or row['id'] <= 0
                or not isinstance(row.get('author'), str) or not row['author'].strip()
                or type(row.get('is_bot')) is not bool or not isinstance(row.get('body'), str)):
            raise ValueError(f'incomplete comment evidence; {DAMAGED}')
        _time(row['submitted_at'] if reviews else row['created_at'])
        if 'updated_at' in row:
            _time(row['updated_at'])
        if reviews and row['state'] not in ('approved', 'commented', 'changes_requested', 'dismissed'):
            raise ValueError(f'unknown review state; {ADAPTER_DATA}')
    return records


def _evidence(host, ref, root):
    reviews = _records(_read(host.reviews, ref, root=root), reviews=True)
    discussion = _read(host.threads, ref, root=root)
    _records(discussion['comments'])
    for thread in _list(discussion['threads']):
        if (not isinstance(thread.get('id'), str) or not thread['id']
                or type(thread.get('resolved')) is not bool
                or type(thread.get('outdated')) is not bool):
            raise ValueError(f'incomplete thread evidence; {DAMAGED}')
        if not _records(thread['comments']):
            raise ValueError(f'empty thread evidence; {DAMAGED}')
    return reviews, discussion


def _fingerprint(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _ledger(data):
    ledger = data.get('reply_acks', {})
    if not isinstance(ledger, dict):
        raise ValueError(f'invalid acknowledgement ledger; {DAMAGED}')
    for ref, entries in ledger.items():
        pull_request(ref)
        if not isinstance(entries, dict):
            raise ValueError(f'invalid acknowledgement entries; {DAMAGED}')
        for key, entry in entries.items():
            if (not re.fullmatch(r'(comment|review):[1-9][0-9]*', key)
                    or not isinstance(entry, dict)
                    or not isinstance(entry.get('fingerprint'), str)
                    or not re.fullmatch('[0-9a-f]{64}', entry['fingerprint'])
                    or not isinstance(entry.get('reply_fingerprint'), str)
                    or not re.fullmatch('[0-9a-f]{64}', entry['reply_fingerprint'])
                    or type(entry.get('reply_id')) is not int or entry['reply_id'] <= 0
                    or not isinstance(entry.get('me'), str) or not entry['me'].strip()):
                raise ValueError(f'invalid acknowledgement record; {DAMAGED}')
    return ledger


def _replies(reviews, discussion, me, acks):
    owed = []
    for surface, records in (('comment', discussion['comments']), ('review', reviews)):
        for row in records:
            key = f'{surface}:{row["id"]}'
            ack = acks.get(key, {})
            if (ack.get('fingerprint') == _fingerprint(row) and ack.get('me') == me
                    and any(reply['id'] == ack['reply_id'] and reply['author'] == me
                            and not reply['is_bot'] and _fingerprint(reply) == ack['reply_fingerprint']
                            for reply in discussion['comments'])):
                continue
            if (row['author'] != me and not row['is_bot'] and row['body'].strip()
                    and not (surface == 'review' and row['state'] == 'approved')):
                owed.append(key)
    for thread in discussion['threads']:
        if thread['resolved']:
            continue
        comments = sorted(thread['comments'], key=lambda row: (_time(row['created_at']), row['id']))
        humans = any(not row['is_bot'] for row in comments)
        if humans and not answered(thread, me):
            owed.append(f'thread:{thread["id"]}')
        elif (not humans and not thread['outdated'] and
              re.search(r'badges/p1\.svg|\*\*P1\*\*', comments[0]['body'])):
            owed.append(f'bot-p1:{thread["id"]}')
    return owed


def answered(thread, me):
    """True when the latest human comment of the thread is by the owner login."""
    comments = sorted(thread.get('comments') or [], key=lambda row: (_time(row['created_at']), row['id']))
    humans = [row for row in comments if not row['is_bot']]
    return bool(humans) and humans[-1]['author'] == me


def _gate_recorded(directory, head):
    if not isinstance(head, str) or not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', head):
        raise ValueError(f'invalid PR head; {DAMAGED}')
    for path in sorted((directory / 'decisions').glob('gate-*.md')):
        text = path.read_text(encoding='utf-8')
        code, _ = verdict.lint(text,
            quality=verdict.is_quality(path) or verdict.is_quality(path.resolve()), class_sweep=any(
            {'arch', 'quality', 'security'} & set(re.split(r'[-_.]', p.name.lower()))
            for p in (path, path.resolve())))
        if code:
            continue
        active = verdict.active_text(text)
        values = re.findall(verdict.VERDICT_ROW, active, re.M)
        recorded_head, = verdict.rows(active, 'Head')
        if values[0] in VERDICTS and head.lower().startswith(recorded_head.strip().lower()):
            return True
    return False


def _not_applicable(config, recorded=None):
    """Visibility findings the owner's config, or a PR recorded with no reviewer, makes
    impossible to owe."""
    if config['shepherd']['min_reviewers'] == 0:
        return {'reviewer': 'shepherd.min_reviewers = 0', 'channel-post': 'shepherd.min_reviewers = 0'}
    if recorded == []:
        return {'reviewer': SOLO, 'channel-post': SOLO}
    if config['adapters']['chat'] == 'none':
        return {'channel-post': 'adapters.chat = "none"'}
    return {}


def _visibility(ref, pr, reviews, data, me, directory, config):
    skip = _not_applicable(config, data.get('pr_reviewers', {}).get(ref))
    reviewers = []
    for field in ('requested_reviewers', 'requested_teams'):
        for name in _list(pr[field]):
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f'invalid requested reviewer; {DAMAGED}')
            if name != me:
                reviewers.append(name)
    if not reviewers:
        reviewers = [row['author'] for row in reviews if not row['is_bot'] and row['author'] != me]
    owed = [] if reviewers or 'reviewer' in skip else ['reviewer']
    posts = _list(data.get('channel_posts', []))
    posted = False
    for post in posts:
        if not isinstance(post, dict) or post.get('pr') != ref or post.get('status') != 'posted':
            continue
        url = urlsplit(post.get('url', ''))
        mentions = post.get('reviewers', [])
        if (url.scheme == 'https' and url.hostname and url.path not in ('', '/')
                and isinstance(mentions, list) and mentions
                and all(isinstance(name, str) and name.strip() for name in mentions)
                and (not reviewers or set(reviewers).issubset(mentions))):
            posted = True
    if not posted and 'channel-post' not in skip:
        owed.append('channel-post')
    if not _gate_recorded(directory, pr['head']):
        owed.append('verdict')
    return owed


def _check_empty_day(directory):
    written = (directory / 'state.json').exists()
    path = directory / 'events.jsonl'
    if not (written or path.exists()):
        return
    recorded_state = False
    for line in path.read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        if (not isinstance(row, dict) or not isinstance(row.get('kind'), str)
                or not isinstance(row.get('payload'), dict)):
            raise ValueError(f'invalid event record; {DAMAGED}')
        kind, payload = row['kind'], row['payload']
        recorded_state |= kind not in FREE_KINDS and type(payload.get('prs_seen')) is bool
        if kind.startswith('state.'):
            seen = payload.get('prs_seen') or (kind == 'state.set'
                   and payload.get('path') in ('raised_prs', 'claimed_prs') and payload.get('value'))
        else:
            seen = (kind == 'watch: sweep' and payload.get('sweep') == 'obligations'
                    and payload.get('prs')) or kind == 'reply: acknowledged'
        if seen or payload.get('prs_seen'):
            raise ValueError(f"empty PR set contradicts today's events; {DAMAGED}")
    if written and not recorded_state:
        raise ValueError('no recorded PR state for today; run bin/wuwei pr state first')


def _owner_login(config):
    handles = [handle for handle in config['owner']['handles']
               if not re.fullmatch(r'[UW][A-Z0-9]+', handle)]
    if len(handles) != 1 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', handles[0]):
        raise ValueError('owner.handles needs one unambiguous code-host login (excluding chat IDs); the owner sets owner.handles to one code-host login with bin/wuwei config set in a host terminal')
    return handles[0]


def evaluate(root=None):
    """Calculate today's obligations without writing a summary event."""
    root = workspace.find_workspace(root)
    directory = workspace.day_dir(root)
    counts = dict(sweep='obligations', prs=0, reply_owed=0, visibility_owed=0, unreadable=0)
    try:
        data = state.read_state(directory=directory)
        ledger = _ledger(data)
        refs = []
        for ref in data['raised_prs'] + data['claimed_prs']:
            try:
                if pull_request(ref) not in refs:
                    refs.append(ref)
            except ValueError as exc:
                counts['unreadable'] += 1
                print(f'day PR reference UNREADABLE: {exc}')
        counts['prs'] = len(refs)
        if not refs:
            _check_empty_day(directory)
        if refs:
            config = workspace.load_config(root)
            me = _owner_login(config)
            host = registry.load('code_host', config)
        for ref in refs:
            try:
                pr = _read(host.pr, ref, root=root)
                if pr['state'] == 'closed':
                    continue
                if pr['state'] != 'open':
                    raise ValueError(f'unknown PR state; {ADAPTER_DATA}')
                reviews, discussion = _evidence(host, ref, root)
                replies = _replies(reviews, discussion, me, ledger.get(ref, {}))
                visibility = _visibility(ref, pr, reviews, data, me, directory, config)
                counts['reply_owed'] += len(replies)
                counts['visibility_owed'] += len(visibility)
                for finding in replies + visibility:
                    print(f'{ref} OWED {finding}')
                for finding, reason in _not_applicable(config, data.get('pr_reviewers', {}).get(ref)).items():
                    print(f'{ref} NOT APPLICABLE {finding}: {reason}')
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                counts['unreadable'] += 1
                print(f'{ref} UNREADABLE: {exc}')
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        counts['unreadable'] += 1
        print(f'obligations UNREADABLE: {exc}')
    counts['owed'] = counts['reply_owed'] + counts['visibility_owed'] + counts['unreadable']
    counts['exit'] = 2 if counts['unreadable'] else int(counts['owed'] > 0)
    return counts


def sweep(root=None):
    """Sweep today's union once, retaining failures and recording one summary."""
    root = workspace.find_workspace(root)
    from wuwei import integrity
    measured = integrity.check(root)
    if measured.reason:
        print(measured.reason)
    directory = workspace.day_dir(root)
    counts = evaluate(root)
    counts['integrity_owed'] = int(measured.exit == 1)
    counts['unreadable'] += int(measured.exit == 2)
    counts['exit'] = max(counts['exit'], measured.exit)
    state.append_event('watch: sweep', counts, directory=directory)
    print(f'obligations: {counts["reply_owed"]} replies, {counts["visibility_owed"]} visibility, '
          f'{counts["unreadable"]} unreadable')
    return counts['exit']


def reply(ref, surface, target_id, text, root=None):
    """Reply using fresh API evidence; only unthreaded surfaces need an ack."""
    root = workspace.find_workspace(root)
    directory = workspace.day_dir(root)
    ref = pull_request(ref)
    if (surface not in ('comment', 'review', 'thread') or type(target_id) is not int or target_id <= 0
            or not isinstance(text, str) or not text.strip()):
        raise ValueError('reply needs a surface, positive ID and nonempty body; pass the surface, a positive ID and the reply text')
    if not (directory / 'state.json').is_file():
        raise ValueError('day state missing; start the day with /wuwei:wuwei-plan')
    data = state.read_state(directory=directory)
    _ledger(data)
    if ref not in data['raised_prs'] + data['claimed_prs']:
        raise ValueError('PR is not raised or claimed today; claim it with bin/wuwei pr claim first')
    config = workspace.load_config(root)
    me = _owner_login(config)
    host = registry.load('code_host', config)
    if _read(host.pr, ref, root=root)['state'] != 'open':
        raise ValueError('PR is not open; run bin/wuwei pr state for its current state')
    if surface == 'thread':
        return _thread_reply(host, ref, target_id, text, me, root)
    reviews, discussion = _evidence(host, ref, root)
    rows = discussion['comments'] if surface == 'comment' else reviews
    target = next((row for row in rows if row['id'] == target_id), None)
    if target is None or target['author'] == me or target['is_bot'] or not target['body'].strip():
        raise ValueError('no human obligation with that surface and ID; run bin/wuwei nudges for the open obligations and their ids')
    fingerprint = _fingerprint(target)
    prior_replies = {row['id'] for row in discussion['comments']}
    result = host.comment(ref, text, None, root=root)
    if type(result.exit) is not int or result.exit not in (0, 1, 2):
        raise ValueError(f'invalid reply result; {DAMAGED}')
    if result.exit:
        print(result.reason or 'reply was not posted')
        return result.exit
    reply_id = result.data['id']
    if type(reply_id) is not int or reply_id <= 0 or reply_id in prior_replies:
        raise ValueError(f'invalid posted reply ID; {DAMAGED}')
    reviews, discussion = _evidence(host, ref, root)
    rows = discussion['comments'] if surface == 'comment' else reviews
    if not any(row['id'] == target_id and _fingerprint(row) == fingerprint for row in rows):
        raise ValueError('target changed while replying; acknowledgement not recorded; read the thread again and rerun the reply')
    posted = next((row for row in discussion['comments'] if row['id'] == reply_id
                   and row['author'] == me and not row['is_bot'] and row['body'] == text), None)
    if posted is None:
        raise ValueError('posted reply could not be verified; acknowledgement not recorded; check the PR by hand; rerun the reply if it is missing')
    key = f'{surface}:{target_id}'

    def acknowledge(fresh):
        _ledger(fresh)
        fresh.setdefault('reply_acks', {}).setdefault(ref, {})[key] = {
            'fingerprint': fingerprint, 'reply_id': reply_id,
            'reply_fingerprint': _fingerprint(posted), 'me': me}

    state._write_state(acknowledge, reserved=False, directory=directory,
                       kind='reply: acknowledged', payload={'pr': ref, 'surface': surface,
                       'id': target_id, 'reply_id': reply_id})
    return 0


def _thread_reply(host, ref, target_id, text, me, root):
    def target():
        discussion = _read(host.threads, ref, root=root)
        for thread in _list(discussion['threads']):
            comments = sorted(_records(thread['comments']),
                              key=lambda row: (_time(row['created_at']), row['id']))
            if comments and comments[0]['id'] == target_id:
                if thread['resolved'] or thread['outdated']:
                    return None
                return comments[-1]
        return None

    first = target()
    if first is None or first['author'] == me:
        raise ValueError('thread is resolved, missing or already answered; run bin/wuwei nudges for the threads still waiting')
    latest = target()
    if latest is None or latest['id'] != first['id'] or _fingerprint(latest) != _fingerprint(first):
        print('thread last word changed; reread before replying')
        return 1
    result = host.comment(ref, text, target_id, root=root)
    if result.exit:
        print(result.reason or 'thread reply was not posted')
        return result.exit
    reply_id = result.data['id']
    posted = target()
    if (posted is None or posted['id'] != reply_id or posted['author'] != me
            or posted['body'] != text or posted['is_bot']):
        raise ValueError('posted thread reply could not be verified; check the PR by hand; rerun the reply if it is missing')
    state.append_event('reply: thread_posted', {'pr': ref, 'root_id': target_id,
                                                'reply_id': reply_id}, root=root)
    return 0
