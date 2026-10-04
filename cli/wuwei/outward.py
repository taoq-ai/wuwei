"""Shared outward approval tiers and mechanical text lint."""

import os
import re
from pathlib import Path
import sys
import unicodedata

from wuwei.exits import CLEAN, FINDINGS, UNRUN, DAMAGED


# ponytail: conservative emoji blocks also reject some text symbols. Use a versioned
# Unicode property table if precise emoji/text presentation distinctions become needed.
# Pattern strings, compiled on first use by re's cache: most hooks lint no text.
EMOJI = ('[\U0001f000-\U0001faff\u2300-\u23ff\u2600-\u27bf'
         '\u24c2\u25aa-\u25fe'
         '\u2b00-\u2bff\u203c\u2049'
         '\u2122\u2139\u20e3\u3030\u303d\u3297\u3299]|[^\n]\ufe0f')
PRONOUNS = ('he him his himself', 'she her hers herself',
            'they them their theirs themself themselves')
REVIEW_REQUEST = (
    r'PR #([1-9][0-9]*) ready for review: '
    r'<https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/\1\|#\1> '
    r'((?:<@[A-Z0-9]+>(?: |$))+)')


# Structural tells from the humanizer skill (MIT, 3.1.0). A hit is a style finding;
# outward.humanize_strict turns it into a refusal for outward text (humanize_lint).
TELLS = (  # pattern strings, compiled on first use by re's cache
    ('not-x-but-y', r"\bnot (?:just|only|merely) [^.\n]{1,80}?\bbut\b|\bit['\u2019]?s not [^.\n]{1,60}?[,;] it['\u2019]?s\b"),
    ('closer', r"\b(?:that is the real win|that distinction matters|read that again|let that sink in|the message was clear)\b"),
    ('run-up', r"\b(?:let['\u2019]?s dive in|let['\u2019]?s break (?:this|it) down|here['\u2019]?s what you need to know|here['\u2019]?s the thing|without further ado)\b"),
    ('saying', r"\b(?:at its core|the real question is|what really matters|the heart of the matter)\b"),
    ('dash', r"[\u2013\u2014]| -- "),
    ('inflation', r"\b(?:plays? an? (?:key|crucial|vital) role|evolving landscape|setting the stage for|lasting legacy|the future looks bright)\b"),
    ('sales', r"\b(?:groundbreaking|breathtaking|nestled|renowned|must-visit|stunning|diverse array)\b"),
    ('stock-word', r"\b(?:delv(?:e|es|ed|ing)|tapestry|testament|showcas(?:e|es|ed|ing)|pivotal|meticulous(?:ly)?|intricate|intricacies|vibrant|garner(?:s|ed)?|bolstered|interplay)\b"),
    ('bold-label', r"(?m)^\s*(?:[-*]|\d+\.)\s+\*\*[^*\n]+\*\*"),
    ('chat-leftover', r"\b(?:i hope this helps|great question|you['\u2019]?re absolutely right|let me know if|would you like me to)\b|\b(?:certainly|of course)!"),
)


def tells(text):
    """Names of the tells in text, each kind once, in table order; inline code is not prose."""
    text = re.sub(r'`[^`\n]*`', '', text)
    return [name for name, pattern in TELLS if re.search(pattern, text, re.IGNORECASE)]


# Humanize kinds by port or tool channel; a DM is 'dm' whatever the channel.
KINDS = {'chat': 'review', 'slack': 'review', 'tracker': 'tracker', 'code_host': 'pr', 'docs': 'docs'}
HUMANIZE = ('rewrite it with the humanizer skill in embedded mode, '
            'or the checklist in charters/_common-authoring.md')


def humanize_lint(inputs, root, config, channels, *, draft=False):
    """The humanizer pass on outward text: (0, '') off or clean, (1, reason) strict,
    else warn, record outward.ai_tells and return (0, reason)."""
    try:
        texts, _ = _text(inputs)
        if len(channels) != 1:
            return UNRUN, 'outward: ambiguous tool channel configuration; pass one channel per call'
        kind = 'dm' if inputs.get('is_dm') is True else KINDS.get(next(iter(channels)))
        rules = config['outward']
        if not rules['humanize'] or kind not in rules['humanize_kinds']:
            return CLEAN, ''
        found = tells('\n'.join(texts))
        if not found:
            return CLEAN, ''
        reason = f"outward: ai tells {', '.join(found)}; {HUMANIZE}"
        if rules['humanize_strict']:
            return FINDINGS, reason
        from wuwei import state
        state.append_event('outward.ai_tells', {'kind': kind, 'tells': found, 'draft': draft}, root)
        print(f'warning: {reason}', file=sys.stderr)
        return CLEAN, reason
    except (OSError, ValueError, TypeError, KeyError, AttributeError, re.error):
        return UNRUN, 'outward: cannot read or validate policy or payload; run bin/wuwei config check; if the config is clean, save this as a draft for the owner to send'


# ponytail: cross-script confusables remain distinct; add a Unicode confusable table if needed.
def _normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text)
                   if unicodedata.category(c) not in {'Mn', 'Me', 'Cf'}).casefold()


OWNER_UNSET = ('owner.name: not set; the outward lint refuses every outward message '
               'except replies in the owner DM')


def lint(text, channel, config, *, root=None, to_owner=False):
    """Return a redacted (0|1|2, reason); callers decide how to present findings.

    to_owner: the text is addressed to the owner, so the third-person rules do not apply.
    """
    if not isinstance(text, str) or not text.strip():
        return UNRUN, 'outward: nonempty text required; pass the message text'
    if not isinstance(channel, str) or not channel.strip():
        return UNRUN, 'outward: channel required; pass the channel the message goes to'
    try:
        owner = config['owner']
        names = _normalize(owner['name']).split()
        if not names and not to_owner:
            return UNRUN, 'outward: owner name must be configured; the owner sets owner.name with bin/wuwei config set in a host terminal'
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
            raise ValueError(f'invalid banned characters; {DAMAGED}')
        limits = rules['max_length']
        if not isinstance(limits, dict) or any(type(n) is not int or n < 1 for n in limits.values()):
            raise ValueError(f'invalid lengths; {DAMAGED}')
    except (KeyError, TypeError, ValueError, AttributeError, re.error):
        return UNRUN, 'outward: invalid lint configuration; run bin/wuwei config check, which names the outward key to fix'
    normalized = _normalize(text)
    views = (normalized, normalized.replace('_', ' '))
    for label, words in () if to_owner else (('owner', names), ('pronoun', pronouns)):
        if any(re.search(r'(?<!\w)' + re.escape(word) + r'(?!\w)', view)
               for word in words for view in views):
            return FINDINGS, f'outward: third-person {label} reference; write it in the first person, or address the owner directly'
    if any(pattern.search(view) for pattern in patterns for view in views):
        return FINDINGS, 'outward: internal state pattern; remove the internal state words (item ids, phases, file paths) from the message'
    if 'emoji' in banned and re.search(EMOJI, text):
        return FINDINGS, 'outward: emoji is banned; remove the emoji and send again'
    if any(c in text or c in normalized for c in banned if c != 'emoji'):
        return FINDINGS, 'outward: banned character; remove the banned character (outward.banned_characters lists them) and send again'
    if channel in limits and len(text) > limits[channel]:
        return FINDINGS, 'outward: channel length exceeded; split the message or shorten it to the channel limit (outward.max_length)'
    if root is not None:
        from wuwei.voice import lint as voice_lint
        code, reason = voice_lint(text, channel, config, root)
        if code:
            return code, reason
    return CLEAN, ''


TEXT_FIELDS = {'text', 'message', 'body', 'title', 'description'}
APPROVAL_REQUIRED = 'outward: deliver as a draft for the owner to send'
METADATA_FIELDS = {'ref', 'channel', 'thread', 'thread_ts', 'item', 'issue', 'issue_id', 'id',
                   'team', 'team_id', 'project', 'project_id', 'state', 'assignee', 'labels',
                   'channel_id', 'issueId', 'teamId', 'stateId', 'assigneeId', 'projectId',
                   'owner', 'repo', 'recipient', 'recipient_org', 'channel_type', 'kind',
                   'category', 'parent'}
BOOL_FIELDS = {'is_dm', 'is_external', 'is_shared', 'is_connected', 'is_client'}


# #501: destination keys, in the order a draft's destination is picked from them.
DESTINATIONS = ('channel', 'channel_id', 'recipient', 'recipients', 'to', 'issue_key',
                'issue_id', 'page_id', 'database_id', 'repo', 'pull_number', 'cc', 'bcc')
NOT_TEXT = METADATA_FIELDS | BOOL_FIELDS | {'issue_number', 'status', 'type', 'object'}


def _strings(value, key, texts, found, text=True, destination=None):
    """#501: walk one payload value; a string is text unless a key on its path is an id,
    flag, structural or destination key; destination values go to found."""
    name = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', key).lower()
    if name in DESTINATIONS:
        destination = name
    if (destination or key in NOT_TEXT or name in NOT_TEXT or name == 'id'
            or name.endswith(('_id', '_ids'))):
        text = False
    if isinstance(value, dict):
        for child, item in sorted(value.items()):
            _strings(item, child, texts, found, text, destination)
    elif isinstance(value, list):
        for item in value:
            _strings(item, key, texts, found, text, destination)
    elif destination and (isinstance(value, str) or type(value) is int):
        found.append((DESTINATIONS.index(destination), str(value)))
    elif text and isinstance(value, str):
        texts.append(value)


def _text(inputs):
    """(texts, destinations) of a payload; known policy keys keep their type checks (#501)."""
    if not isinstance(inputs, dict):
        raise ValueError('expected input object; pass the outward input as a JSON object of fields such as text and channel')
    nested = inputs.get('draft', {})
    if not isinstance(nested, dict) or 'draft' in nested:
        raise ValueError('unsupported input field; remove the unknown field, or ask the owner if it is needed')
    for key, value in [*inputs.items(), *nested.items()]:
        if key in BOOL_FIELDS:
            if type(value) is not bool:
                raise ValueError('expected boolean audience flag; set is_dm, is_external, is_shared, is_connected and is_client to true or false')
        elif key == 'recipients':
            if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
                raise ValueError('expected recipients list; pass recipients as a list of non-empty strings, or remove the field')
        elif key in {'issue_number', 'pull_number', 'thread'}:
            if not (key == 'thread' and value is None) and type(value) not in (str, int):
                raise ValueError(f'invalid issue or pull number; {DAMAGED}')
        elif key in METADATA_FIELDS:
            if not (value is None or isinstance(value, str)
                    or isinstance(value, list) and all(isinstance(item, str) for item in value)):
                raise ValueError(f'invalid metadata; {DAMAGED}')
            if key in {'channel', 'channel_id'}:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f'invalid channel; {DAMAGED}')
    texts, found = [], []
    _strings(inputs, '', texts, found)
    return texts, [value for _, value in sorted(found, key=lambda pair: pair[0])]


OWNER = {'chat': 'slack', 'slack': 'slack', 'mail': 'mail'}  # #495: kinds with a private audience.
SLACK_SHAPE = {'user': '[UW][A-Z0-9]+', 'dm': 'D[A-Z0-9]+'}  # A channel id is never the owner.


def owner_only(context, config, kind):
    """#495: True when the owner alone is addressed: every destination and recipient is the
    owner's identity in outbound.owner for this kind. A nested draft wrapper never is."""
    if not isinstance(context, dict) or 'draft' in context:
        return False
    found = config['outbound']['owner'].get(OWNER.get(kind), '')
    mine = ({value.casefold() for key, value in found.items() if re.fullmatch(SLACK_SHAPE.get(key, ''), value)}
            if isinstance(found, dict) else {found.casefold()} - {''})
    texts, destinations = _text(context)
    targets = [*destinations, *context.get('recipients', []), *filter(None, [context.get('recipient')])]
    if kind == 'mail':  # #501: any address in the payload (a Graph ccRecipients shape) is a reader.
        targets += [address for text in texts for address in re.findall(r'[^\s<>@]+@[^\s<>@]+', text)]
    return bool(mine and targets) and all(target.casefold() in mine for target in targets)


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
        raise ValueError(f'invalid port result; {DAMAGED}')
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
        raise ValueError('PR evidence does not match destination; retry with the exact owner/repo#n; if it repeats, run bin/wuwei doctor')
    org = repo.split('/')[0]
    if not _internal(pr['author'], rules, 'github', org):
        return FINDINGS, ''
    result = _result(host.reviews(ref, root=root))
    if result.exit:
        return result.exit, ''
    if not isinstance(result.data, list):
        raise ValueError(f'invalid review evidence; {DAMAGED}')
    if any(not _internal(review['author'], rules, 'github', org) for review in result.data):
        return FINDINGS, ''
    result = _result(host.threads(ref, root=root))
    if result.exit:
        return result.exit, ''
    discussion = result.data
    if not isinstance(discussion['comments'], list) or not isinstance(discussion['threads'], list):
        raise ValueError(f'invalid discussion evidence; {DAMAGED}')
    comments = list(discussion['comments'])
    for thread in discussion['threads']:
        if not isinstance(thread['comments'], list):
            raise ValueError(f'invalid thread evidence; {DAMAGED}')
        comments.extend(thread['comments'])
    for comment in comments:
        if not isinstance(comment['body'], str):
            raise ValueError(f'invalid comment evidence; {DAMAGED}')
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


def _external_tracker(config):
    """A GitHub project or board owned outside outbound.code_host_orgs is external."""
    if config['adapters']['tracker'] != 'github':
        return False
    orgs = {org.casefold() for org in config['outbound']['code_host_orgs']}
    tracker = config['tracker']
    project = tracker['project'] or next((repo['name'] for repo in config['repos']), '')
    return any(name.split('/')[0].casefold() not in orgs
               for name in (project, tracker['board']) if name)


MENTION = r'(?<![\w@])@([\w.-]+)'


def _flagged(normalized, rules):
    """(tier, config key) of the first sensitive keyword or sensitive, commitment or
    disagreement pattern that matches; None when none does."""
    # ponytail: explicit deny lists and complete safe forms have limited language
    # coverage. Unknown prose drafts; a semantic classifier is later work.
    if any(re.search(r'(?<!\w)' + re.escape(_normalize(word)) + r'(?!\w)',
                     normalized.replace('_', ' ')) for word in rules['sensitive_keywords']):
        return 'sensitive', 'outbound.sensitive_keywords'
    for key in ('sensitive_patterns', 'commitment_patterns', 'disagreement_patterns'):
        if any(re.search(pattern, normalized, re.IGNORECASE | re.DOTALL) for pattern in rules[key]):
            return key.split('_')[0], f'outbound.{key}'
    return None


def check_send(inputs, root, config, channels):
    """#492 connector mode send: the outbound security check and the patterns of classify,
    without its audience rules; a write without text has nothing to hold back."""
    try:
        from wuwei import security
        code, reason = security.outbound(inputs, root)
        if code:
            return code, reason
        texts, _ = _text(inputs)
        # The rule is a fragment: the guard's drafts.hold adds the draft id and the owner's next step (#493).
        rule = ''
        if os.environ.get('WUWEI_SEAT_ROLE') == 'shepherd':
            rule = 'headless seat: a headless shepherd seat posts drafts only'
        elif flag := texts and _flagged(_normalize('\n'.join(texts)).replace('’', "'"), config['outbound']):
            rule = f'approval tier {flag[0]} for {next(iter(channels))}: {flag[1]}'
        if rule:
            return FINDINGS, f'{APPROVAL_REQUIRED}: {rule}'
        return CLEAN, ''
    except (OSError, ValueError, TypeError, KeyError, AttributeError, re.error):
        return UNRUN, 'outward: cannot read or validate policy or payload; run bin/wuwei config check; if the config is clean, save this as a draft for the owner to send'


def classify(text, root, config, context=None, *, kind='chat', port=False, why=None):
    """Return (0|1|2, send|draft); missing destination or uncertain meaning drafts.
    A list in why gets '<rule>: <evidence>' for the draft (#493); evidence has no '; '."""
    def held(rule):
        if isinstance(why, list):
            why.append(rule)
        return FINDINGS, 'draft'

    def tier(name, evidence):
        from wuwei import voice
        return held(f'approval tier {name} for '
                    f'{voice.audience(destinations[0] if destinations else kind, config)}: {evidence}')

    try:
        if os.environ.get('WUWEI_SEAT_ROLE') == 'shepherd':
            return held('headless seat: a headless shepherd seat posts drafts only')
        if not isinstance(text, str) or not isinstance(kind, str):
            return UNRUN, 'draft'
        context = {} if context is None else context
        _text(context)
        # #501: the chat rules read channel ids only; a recipient, issue or repo is no channel.
        destinations = [part[key] for part in (context, context.get('draft', {}))
                        for key in ('channel', 'channel_id') if key in part]
        if owner_only(context, config, kind):
            return CLEAN, 'send'  # #495: only the owner reads it; security and the lint still run.
        # Some tracker tools wrap fields in draft even though the operation sends.
        nested = context.get('draft', {})
        context = {key: value for key, value in context.items()
                   if key not in TEXT_FIELDS and key != 'draft'}
        for key, value in nested.items():
            if key not in TEXT_FIELDS:
                if key in context and context[key] != value:
                    return tier('unclassified', 'nested draft fields disagree')
                context[key] = value
        rules = config['outbound']
        normalized = _normalize(text).replace('\u2019', "'")
        if flag := _flagged(normalized, rules):
            return tier(*flag)
        if (any(context.get(key, False) for key in BOOL_FIELDS)
                or context.get('channel_type', 'channel') != 'channel'
                or any(channel.startswith(('D', 'U')) or channel in rules['external_channels']
                       for channel in destinations)):
            if (context.get('is_dm') or context.get('channel_type') in ('im', 'mpim')
                    or any(channel.startswith(('D', 'U')) for channel in destinations)):
                who = next(iter(destinations), None) or context.get('recipient')
                if who:
                    return held(f"unknown DM recipient {who}: not the owner's DM or user id in outbound.owner.slack")
                return tier('direct message', 'every direct message drafts')
            return tier('external', 'shared, connected, client or outbound.external_channels')
        recipients = list(context.get('recipients', []))
        if 'recipient' in context:
            recipients.append(context['recipient'])
        review_match = (re.fullmatch(REVIEW_REQUEST, text) if kind in ('chat', 'slack')
                        and destinations == [config['shepherd']['review_channel']] else None)
        mention_text = re.sub(r'<@[\w.-]+>', '', normalized) if review_match else normalized
        mentions = re.findall(MENTION, mention_text)
        recipients.extend(mentions)
        # Email addresses and mentions are audience evidence, never merely message text.
        recipients.extend(re.findall(r'[^\s<>@]+@[^\s<>@]+', normalized))
        namespace = 'github' if kind == 'code_host' else 'slack'
        unknown = [person for person in recipients
                   if not _internal(person, rules, 'email' if '@' in person else namespace)]
        if unknown:
            person = unknown[0]
            return held(f"unknown mention {person if '@' in person else '@' + person}: "
                        'not an internal person in outbound.people')
        if ('recipient_org' in context and context['recipient_org'].casefold()
                not in {org.casefold() for org in rules['code_host_orgs']}):
            return tier('external', 'recipient_org not in outbound.code_host_orgs')
        if kind == 'docs':  # #419: a docs write sends only when its kind is in docs.auto.
            return ((CLEAN, 'send') if context.get('kind') in config['docs']['auto']
                    else tier('docs', 'kind not in docs.auto'))
        if kind == 'tracker':
            # 5.11: record-derived tracker writes in tracker.auto send; the rest draft.
            # Only the CLI port sets category; a seat's MCP payload cannot claim it.
            return ((CLEAN, 'send') if port and context.get('category') in config['tracker']['auto']
                    and not _external_tracker(config) else tier(
                        'tracker', 'category not in tracker.auto, or the board is outside outbound.code_host_orgs'))
        discussion = ''
        # The chat port cannot prove the thread's participants are internal.
        if kind in ('chat', 'slack') and any(
                context.get(key) is not None for key in ('thread', 'thread_ts')):
            return tier('thread', 'chat threads draft until their participants are known')
        if kind == 'code_host':
            code, discussion = _pr_context(context, root, config)
            if code == FINDINGS:
                return tier('external', 'not a measured team pull request')
            if code:
                return code, 'draft'
        elif (kind not in ('chat', 'slack') or not destinations
              or len(set(destinations)) != 1
              or any(channel not in rules['work_channels'] for channel in destinations)):
            if kind in ('chat', 'slack'):
                missing = next((channel for channel in destinations
                                if channel not in rules['work_channels']), 'none')
                return held(f'unknown destination {missing}: not in outbound.work_channels')
            return tier('unclassified', f'no auto-send rule for channel {kind}')
        plain = re.sub(r'<@[\w.-]+>|(?<![\w@])@[\w.-]+', '', normalized).strip()
        if review_match:
            from wuwei import shepherd, state
            ref = f'{review_match[2]}#{review_match[1]}'
            expected = state.read_state(root).get('pr_reviewers', {}).get(ref)
            mapped = {row['login']: row['mention'] for row in config['shepherd']['authors'].values()}
            mentions = re.findall(r'<@([A-Z0-9]+)>', review_match[3])
            if (expected and set(mentions) == {mapped.get(login) for login in expected}
                    and len(mentions) == len(expected)):
                gate = shepherd.ping_gate(root, ref)
                if gate.exit == FINDINGS:
                    return tier('review gate', (gate.reason or 'refused').split('; ')[0])
                return (CLEAN, 'send') if gate.exit == 0 else (gate.exit, 'draft')
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
            if review_match:
                return tier('review ping', 'the mentions are not the requested reviewers')
            if kind in ('chat', 'slack') and 'review' in plain:
                return held('review ping without a code-host link: the review request form '
                            'with the PR link goes to shepherd.review_channel')
            return tier('unclassified', 'not an acknowledgement, status, technical or mechanical reply')
        from wuwei import registry
        vcs = registry.load('vcs', config)
        unresolved = FINDINGS
        for repo in config['repos']:
            path = (root / Path(repo['path']).expanduser()).resolve()
            result = _result(vcs.resolve(path, mechanical[1], root=root))
            if result.exit == CLEAN:
                sha = result.data['sha']
                if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', sha) or not sha.startswith(mechanical[1]):
                    raise ValueError('invalid commit evidence; retry; if it repeats, run bin/wuwei doctor, which tests the code host adapter')
                return CLEAN, 'send'
            if result.exit == UNRUN:
                unresolved = UNRUN
        if unresolved == FINDINGS:
            return tier('unresolved commit', f'{mechanical[1]} is in no configured repository')
        return unresolved, 'draft'
    except (OSError, ValueError, TypeError, KeyError, AttributeError, re.error):
        return UNRUN, 'draft'


def check_call(inputs, root, config, channels, *, port=False):
    """Shared lint and send policy for MCP hooks and text-bearing adapter ports."""
    from wuwei.guards import profile_result
    result = check_tier(inputs, root, config, channels, port=port)
    draft = result[0] == FINDINGS and result[1].startswith(APPROVAL_REQUIRED)
    if result[0] and not draft:
        return result
    try:
        # A draft gets the humanize pass only; the outward lint runs again at approval.
        lint = (CLEAN, '') if draft else check_lint(inputs, root, config, channels)
        if not lint[0]:
            lint = humanize_lint(inputs, root, config, channels, draft=draft)
        lint = profile_result(lint, config['profile'], root, next(iter(channels)))
    except KeyError:
        return UNRUN, 'outward: cannot read profile; run bin/wuwei config check, which names the profile key to fix'
    return lint if lint[0] else (result if draft else (CLEAN, ''))


def check_tier(inputs, root, config, channels, *, port=False):
    """Approval tiers are blocking under every profile."""
    try:
        from wuwei import security
        code, reason = security.outbound(inputs, root)
        if code:
            return code, reason
        texts, _ = _text(inputs)
        text = '\n'.join(texts)
        if len(channels) != 1:
            return UNRUN, 'outward: ambiguous tool channel configuration; pass one channel per call'
        if texts and not text.strip():
            return UNRUN, 'outward: nonempty text required; pass the message text'
        why, kind = [], next(iter(channels))
        code, decision = classify(text, root, config, inputs, kind=kind, port=port, why=why)
        if code == UNRUN:
            return code, 'outward: cannot classify policy, audience or message evidence; deliver as a draft for the owner to send'
        if decision == 'draft':
            return code, f'{APPROVAL_REQUIRED}: {why[0]}' if why else APPROVAL_REQUIRED
        if owner_only(inputs, config, kind):
            # ponytail: logged before check_lint, so a self-DM the lint refuses still counts; move it to the lint's clean result if the count must be exact.
            from wuwei import state  # Only a message to the owner pays for the event (#495).
            state.append_event('outward.to_owner', {'channel': kind}, root)
        return CLEAN, ''
    except (OSError, ValueError, TypeError, KeyError, AttributeError, re.error):
        return UNRUN, 'outward: cannot read or validate policy or payload; run bin/wuwei config check; if the config is clean, save this as a draft for the owner to send'


def check_lint(inputs, root, config, channels, *, to_owner=False):
    """Return raw lint results so the dispatcher can apply the profile."""
    try:
        texts, destinations = _text(inputs)
        text = '\n'.join(texts)
        if len(channels) != 1:
            return UNRUN, 'outward: ambiguous tool channel configuration; pass one channel per call'
        if not texts:
            return CLEAN, ''  # #501: a write without text has nothing to lint.
        to_owner = to_owner or owner_only(inputs, config, next(iter(channels)))
        for channel in sorted(channels.union(destinations)):
            code, reason = lint(text, channel, config, root=root, to_owner=to_owner)
            if code:
                return code, reason
        return CLEAN, ''
    except (OSError, ValueError, TypeError, KeyError, AttributeError, re.error):
        return UNRUN, 'outward: cannot read or validate policy or payload; run bin/wuwei config check; if the config is clean, save this as a draft for the owner to send'
