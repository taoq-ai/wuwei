"""Shared outward approval tiers and mechanical text lint."""

import re
from pathlib import Path
import unicodedata

from wuwei.exits import CLEAN, FINDINGS, UNRUN


# ponytail: conservative emoji blocks also reject some text symbols. Use a versioned
# Unicode property table if precise emoji/text presentation distinctions become needed.
EMOJI = re.compile('[\U0001f000-\U0001faff\u2300-\u23ff\u2600-\u27bf'
                   '\u24c2\u25aa-\u25fe'
                   '\u2b00-\u2bff\u203c\u2049'
                   '\u2122\u2139\u20e3\u3030\u303d\u3297\u3299]|[^\n]\ufe0f')
PRONOUNS = ('he him his himself', 'she her hers herself',
            'they them their theirs themself themselves')


# ponytail: cross-script confusables remain distinct; add a Unicode confusable table if needed.
def _normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text)
                   if unicodedata.category(c) not in {'Mn', 'Me', 'Cf'}).casefold()


def lint(text, channel, config):
    """Return a redacted (0|1|2, reason); callers decide how to present findings."""
    if not isinstance(text, str) or not text.strip():
        return UNRUN, 'outward: nonempty text required'
    if not isinstance(channel, str) or not channel.strip():
        return UNRUN, 'outward: channel required'
    try:
        owner = config['owner']
        names = _normalize(owner['name']).split()
        if not names:
            return UNRUN, 'outward: owner name must be configured'
        names.extend(_normalize(handle) for handle in owner.get('handles', []))
        pronouns = set(re.split(r'[/,\s]+', _normalize(owner['pronouns']))) - {''}
        for family in PRONOUNS:
            if pronouns.intersection(family.split()):
                pronouns.update(family.split())
        rules = config['outward']
        patterns = [re.compile(pattern, re.IGNORECASE | re.DOTALL)
                    for pattern in rules['patterns']]
        banned = rules['banned_characters']
        if not isinstance(banned, list) or not all(isinstance(c, str) and c for c in banned):
            raise ValueError('invalid banned characters')
        limits = rules['max_length']
        if not isinstance(limits, dict) or any(type(n) is not int or n < 1 for n in limits.values()):
            raise ValueError('invalid lengths')
    except (KeyError, TypeError, ValueError, AttributeError, re.error):
        return UNRUN, 'outward: invalid lint configuration'
    normalized = _normalize(text)
    views = (normalized, normalized.replace('_', ' '))
    for label, words in (('owner', names), ('pronoun', pronouns)):
        if any(re.search(r'(?<!\w)' + re.escape(word) + r'(?!\w)', view)
               for word in words for view in views):
            return FINDINGS, f'outward: third-person {label} reference'
    if any(pattern.search(view) for pattern in patterns for view in views):
        return FINDINGS, 'outward: internal state pattern'
    if 'emoji' in banned and EMOJI.search(text):
        return FINDINGS, 'outward: emoji is banned'
    if any(c in text or c in normalized for c in banned if c != 'emoji'):
        return FINDINGS, 'outward: banned character'
    if channel in limits and len(text) > limits[channel]:
        return FINDINGS, 'outward: channel length exceeded'
    return CLEAN, ''


TEXT_FIELDS = {'text', 'message', 'body', 'title', 'description'}
METADATA_FIELDS = {'ref', 'channel', 'thread', 'thread_ts', 'item', 'issue', 'issue_id', 'id',
                   'team', 'team_id', 'project', 'project_id', 'state', 'assignee', 'labels',
                   'channel_id', 'issueId', 'teamId', 'stateId', 'assigneeId', 'projectId',
                   'owner', 'repo', 'recipient', 'recipient_org', 'channel_type'}
BOOL_FIELDS = {'is_dm', 'is_external', 'is_shared', 'is_connected', 'is_client'}


def _text(inputs, *, nested=False):
    if not isinstance(inputs, dict):
        raise ValueError('expected input object')
    texts, channels = [], []
    for key, value in sorted(inputs.items()):
        if key in TEXT_FIELDS:
            if not isinstance(value, str):
                raise ValueError('expected plain text')
            texts.append(value)
        elif key == 'draft' and not nested:
            child_texts, child_channels = _text(value, nested=True)
            texts.extend(child_texts)
            channels.extend(child_channels)
        elif key in BOOL_FIELDS:
            if type(value) is not bool:
                raise ValueError('expected boolean audience flag')
        elif key == 'recipients':
            if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
                raise ValueError('expected recipients list')
        elif key in {'issue_number', 'pull_number', 'thread'}:
            if not (key == 'thread' and value is None) and type(value) not in (str, int):
                raise ValueError('invalid issue or pull number')
        elif key in METADATA_FIELDS:
            if not (value is None or isinstance(value, str)
                    or isinstance(value, list) and all(isinstance(item, str) for item in value)):
                raise ValueError('invalid metadata')
            if key in {'channel', 'channel_id'}:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError('invalid channel')
                channels.append(value)
        else:
            raise ValueError('unsupported input field')
    return texts, channels


def _internal(person, rules, namespace, org=None):
    if not isinstance(person, str) or not person.strip():
        return False
    people = {key.casefold(): value for key, value in rules['people'].items()}
    identity = people.get(f'{namespace}:{person}'.casefold(), {})
    email = identity.get('email', person if namespace == 'email' else '')
    identity_org = identity.get('org', '')
    if namespace == 'github' and (not identity_org or
            org is not None and identity_org.casefold() != org.casefold()):
        return False
    evidence = []
    if email:
        match = re.fullmatch(r'[^@\s]+@([^@\s]+)', email)
        evidence.append(bool(match) and match[1].casefold() in
                        {domain.casefold() for domain in rules['company_domains']})
    if identity_org:
        evidence.append(identity_org.casefold() in {name.casefold() for name in rules['code_host_orgs']})
    return bool(evidence) and all(evidence)


def _result(result):
    from wuwei.registry import Result
    if not isinstance(result, Result) or type(result.exit) is not int or result.exit not in (0, 1, 2):
        raise ValueError('invalid port result')
    return result


def _pr_context(context, root, config):
    """Return code and discussion text only for a measured, internal team PR."""
    from wuwei import registry
    rules = config['outbound']
    ref = context.get('ref')
    number = context.get('pull_number', context.get('issue_number'))
    explicit = None
    if number is not None and context.get('owner') and context.get('repo'):
        explicit = f"{context['owner']}/{context['repo']}#{number}"
    ref = ref or explicit
    if not isinstance(ref, str):
        return FINDINGS, ''
    match = re.fullmatch(r'(?:https://github\.com/([^/]+/[^/]+)/pull/|([^#]+)#)([1-9][0-9]*)', ref)
    if not match:
        return FINDINGS, ''
    repo, number = match[1] or match[2], int(match[3])
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        return FINDINGS, ''
    for key, expected in (('owner', repo.split('/')[0]), ('repo', repo.split('/')[1]),
                          ('pull_number', str(number)), ('issue_number', str(number))):
        if key in context and str(context[key]).casefold() != expected.casefold():
            return FINDINGS, ''
    if (repo.casefold() not in {row['name'].casefold() for row in config['repos']}
            or repo.split('/')[0].casefold() not in {org.casefold() for org in rules['code_host_orgs']}):
        return FINDINGS, ''
    host = registry.load('code_host', config)
    result = _result(host.pr(ref, root=root))
    if result.exit:
        return result.exit, ''
    pr = result.data
    if pr['repo'].casefold() != repo.casefold() or type(pr['number']) is not int or pr['number'] != number:
        raise ValueError('PR evidence does not match destination')
    org = repo.split('/')[0]
    if not _internal(pr['author'], rules, 'github', org):
        return FINDINGS, ''
    result = _result(host.reviews(ref, root=root))
    if result.exit:
        return result.exit, ''
    if not isinstance(result.data, list):
        raise ValueError('invalid review evidence')
    if any(not _internal(review['author'], rules, 'github', org) for review in result.data):
        return FINDINGS, ''
    result = _result(host.threads(ref, root=root))
    if result.exit:
        return result.exit, ''
    discussion = result.data
    if not isinstance(discussion['comments'], list) or not isinstance(discussion['threads'], list):
        raise ValueError('invalid discussion evidence')
    comments = list(discussion['comments'])
    for thread in discussion['threads']:
        if not isinstance(thread['comments'], list):
            raise ValueError('invalid thread evidence')
        comments.extend(thread['comments'])
    for comment in comments:
        if not isinstance(comment['body'], str):
            raise ValueError('invalid comment evidence')
        if not _internal(comment['author'], rules, 'github', org):
            return FINDINGS, ''
    target = context.get('thread')
    if target is not None:
        selected = [comment for comment in discussion['comments']
                    if str(comment.get('id')) == str(target)]
        for thread in discussion['threads']:
            if (str(thread.get('id')) == str(target) or any(
                    str(comment.get('id')) == str(target) for comment in thread['comments'])):
                selected.extend(thread['comments'])
        if not selected:
            return FINDINGS, ''
        comments = selected
    return CLEAN, _normalize('\n'.join(comment['body'] for comment in comments))


def classify(text, root, config, context=None, *, kind='chat'):
    """Return (0|1|2, send|draft); missing destination or uncertain meaning drafts."""
    try:
        if not isinstance(text, str) or not text.strip() or not isinstance(kind, str):
            return UNRUN, 'draft'
        context = {} if context is None else context
        _, destinations = _text(context)
        # Some tracker tools wrap fields in draft even though the operation sends.
        nested = context.get('draft', {})
        context = {key: value for key, value in context.items()
                   if key not in TEXT_FIELDS and key != 'draft'}
        for key, value in nested.items():
            if key not in TEXT_FIELDS:
                if key in context and context[key] != value:
                    return FINDINGS, 'draft'
                context[key] = value
        rules = config['outbound']
        normalized = _normalize(text).replace('\u2019', "'")
        # ponytail: explicit deny lists and complete safe forms have limited language
        # coverage. Unknown prose drafts; a semantic classifier is later work.
        patterns = [re.compile(pattern, re.IGNORECASE | re.DOTALL)
                    for key in ('sensitive_patterns', 'commitment_patterns', 'disagreement_patterns')
                    for pattern in rules[key]]
        if (any(re.search(r'(?<!\w)' + re.escape(_normalize(word)) + r'(?!\w)',
                          normalized.replace('_', ' ')) for word in rules['sensitive_keywords'])
                or any(pattern.search(normalized) for pattern in patterns)):
            return FINDINGS, 'draft'
        if (any(context.get(key, False) for key in BOOL_FIELDS)
                or context.get('channel_type', 'channel') != 'channel'
                or any(channel.startswith(('D', 'U')) or channel in rules['external_channels']
                       for channel in destinations)):
            return FINDINGS, 'draft'
        recipients = list(context.get('recipients', []))
        if 'recipient' in context:
            recipients.append(context['recipient'])
        mentions = re.findall(r'(?<![\w@])@([\w.-]+)', normalized)
        recipients.extend(mentions)
        # Email addresses and mentions are audience evidence, never merely message text.
        recipients.extend(re.findall(r'[^\s<>@]+@[^\s<>@]+', normalized))
        namespace = 'github' if kind == 'code_host' else 'slack'
        if any(not _internal(person, rules, 'email' if '@' in person else namespace)
               for person in recipients):
            return FINDINGS, 'draft'
        if ('recipient_org' in context and context['recipient_org'].casefold()
                not in {org.casefold() for org in rules['code_host_orgs']}):
            return FINDINGS, 'draft'
        discussion = ''
        # The chat port cannot prove the thread's participants are internal.
        if kind in ('chat', 'slack') and any(
                context.get(key) is not None for key in ('thread', 'thread_ts')):
            return FINDINGS, 'draft'
        if kind == 'code_host':
            code, discussion = _pr_context(context, root, config)
            if code:
                return code, 'draft'
        elif (kind not in ('chat', 'slack') or not destinations
              or len(set(destinations)) != 1
              or any(channel not in rules['work_channels'] for channel in destinations)):
            return FINDINGS, 'draft'
        plain = re.sub(r'<@[\w.-]+>|(?<![\w@])@[\w.-]+', '', normalized).strip()
        if re.fullmatch(r'(?:ack|acknowledged|thanks|thank you|got it|done|'
                        r'(?:tests?|build|ci) (?:passed|failed|running|is running))[.!]?', plain):
            return CLEAN, 'send'
        technical = re.fullmatch(r'(?:the )?([a-z_][a-z0-9_]*) '
                                 r'(?:is thread safe|uses a lock|returns (?:none|true|false)|'
                                 r'raises (?:valueerror|typeerror))[.]?', plain)
        if technical and kind == 'code_host' and re.search(
                r'(?<!\w)' + re.escape(technical[1]) + r'(?!\w)', discussion):
            return CLEAN, 'send'
        mechanical = re.fullmatch(r'fixed in ([0-9a-f]{7,40})\.?', plain)
        if not mechanical:
            return FINDINGS, 'draft'
        from wuwei import registry
        vcs = registry.load('vcs', config)
        unresolved = FINDINGS
        for repo in config['repos']:
            path = (root / Path(repo['path']).expanduser()).resolve()
            result = _result(vcs.resolve(path, mechanical[1], root=root))
            if result.exit == CLEAN:
                sha = result.data['sha']
                if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', sha) or not sha.startswith(mechanical[1]):
                    raise ValueError('invalid commit evidence')
                return CLEAN, 'send'
            if result.exit == UNRUN:
                unresolved = UNRUN
        return unresolved, 'draft'
    except (OSError, ValueError, TypeError, KeyError, AttributeError, re.error):
        return UNRUN, 'draft'


def check_call(inputs, root, config, channels):
    """Shared lint and send policy for MCP hooks and text-bearing adapter ports."""
    from wuwei.guards import profile_result
    result = check_tier(inputs, root, config, channels)
    if result[0]:
        return result
    try:
        return profile_result(check_lint(inputs, root, config, channels),
                              config['profile'], root, next(iter(channels)))
    except KeyError:
        return UNRUN, 'outward: cannot read profile'


def check_tier(inputs, root, config, channels):
    """Approval tiers are blocking under every profile."""
    try:
        texts, _ = _text(inputs)
        text = '\n'.join(texts)
        if len(channels) != 1:
            return UNRUN, 'outward: ambiguous tool channel configuration'
        code, decision = classify(text, root, config, inputs, kind=next(iter(channels)))
        if code == UNRUN:
            return code, 'outward: cannot classify policy, audience or message evidence; deliver as a draft for the owner to send'
        if decision == 'draft':
            return code, 'outward: deliver as a draft for the owner to send'
        return CLEAN, ''
    except (OSError, ValueError, TypeError, KeyError, AttributeError, re.error):
        return UNRUN, 'outward: cannot read or validate policy or payload'


def check_lint(inputs, root, config, channels):
    """Return raw lint results so the dispatcher can apply the profile."""
    try:
        texts, destinations = _text(inputs)
        text = '\n'.join(texts)
        if len(channels) != 1:
            return UNRUN, 'outward: ambiguous tool channel configuration'
        for channel in sorted(channels.union(destinations)):
            code, reason = lint(text, channel, config)
            if code:
                return code, reason
        return CLEAN, ''
    except (OSError, ValueError, TypeError, KeyError, AttributeError, re.error):
        return UNRUN, 'outward: cannot read or validate policy or payload'
