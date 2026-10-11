"""Outward text lint and the owner's own surfaces (#838)."""

import functools
import re
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
UNREADABLE = ('outward: cannot read or validate policy or payload; run bin/wuwei config check, '
              'which names the key to fix')
HUMANIZE = ('rewrite it with the humanizer skill in embedded mode, '
            'or the checklist in charters/_common-authoring.md')


def humanize_lint(inputs, root, config, channels):
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
        state.append_event('outward.ai_tells', {'kind': kind, 'tells': found}, root)
        print(f'warning: {reason}', file=sys.stderr)
        return CLEAN, reason
    except (OSError, ValueError, TypeError, KeyError, AttributeError, re.error):
        return UNRUN, UNREADABLE


# ponytail: cross-script confusables remain distinct; add a Unicode confusable table if needed.
def _normalize(text):
    if text.isascii():  # #626: NFKD keeps ASCII, and no ASCII character is Mn, Me or Cf.
        return text.casefold()
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
            return UNRUN, 'outward: owner name must be configured; the owner sets owner.name with bin/wuwei config set'
        names.extend(_normalize(handle) for handle in owner.get('handles', []))
        pronouns = set(re.split(r'[/,\s]+', _normalize(owner['pronouns']))) - {''}
        for family in PRONOUNS:
            if pronouns.intersection(family.split()):
                pronouns.update(family.split())
        rules = config['outward']
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
    if 'emoji' in banned and re.search(EMOJI, text):
        return FINDINGS, 'outward: emoji is banned; remove the emoji and send again'
    if any(c in text or c in normalized for c in banned if c != 'emoji'):
        return FINDINGS, 'outward: banned character; remove the banned character (outward.banned_characters lists them) and send again'
    if channel in limits and len(text) > limits[channel]:
        return FINDINGS, 'outward: channel length exceeded; split the message or shorten it to the channel limit (outward.max_length)'
    return CLEAN, ''


TEXT_FIELDS = {'text', 'message', 'body', 'title', 'description'}
METADATA_FIELDS = {'ref', 'channel', 'thread', 'thread_ts', 'item', 'issue', 'issue_id', 'id',
                   'team', 'team_id', 'project', 'project_id', 'state', 'assignee', 'labels',
                   'channel_id', 'issueId', 'teamId', 'stateId', 'assigneeId', 'projectId',
                   'owner', 'repo', 'recipient', 'recipient_org', 'channel_type', 'kind',
                   'category', 'parent'}
BOOL_FIELDS = {'is_dm', 'is_external', 'is_shared', 'is_connected', 'is_client'}


# #501: destination keys; #838: canvas_id names a Slack canvas.
DESTINATIONS = ('channel', 'channel_id', 'recipient', 'recipients', 'to', 'issue_key',
                'issue_id', 'page_id', 'database_id', 'canvas_id', 'repo', 'pull_number', 'cc', 'bcc')
NOT_TEXT = METADATA_FIELDS | BOOL_FIELDS | {'issue_number', 'status', 'type', 'object'}


@functools.lru_cache(maxsize=256)
def _snake(key):
    """issueId -> issue_id, once per key name (#626)."""
    return re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', key).lower()


def _strings(value, key, texts, found, text=True, destination=None):
    """#501: walk one payload value; a string is text unless a key on its path is an id,
    flag, structural or destination key; destination values go to found."""
    name = _snake(key)
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
            if key == 'parent' and isinstance(value, dict):
                continue  # #838: a Notion parent; its page_id is a destination
            if not (value is None or isinstance(value, str)
                    or isinstance(value, list) and all(isinstance(item, str) for item in value)):
                raise ValueError(f'invalid metadata; {DAMAGED}')
            if key in {'channel', 'channel_id'}:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f'invalid channel; {DAMAGED}')
    texts, found = [], []
    _strings(inputs, '', texts, found)
    return texts, [value for _, value in sorted(found, key=lambda pair: pair[0])]


# #495, #838: kinds with a private audience; Slack canvases and docs pages by outbound.owner.pages.
OWNER = {'chat': 'slack', 'slack': 'slack', 'mail': 'mail', 'docs': 'pages'}
SLACK_SHAPE = {'user': '[UW][A-Z0-9]+', 'dm': 'D[A-Z0-9]+'}  # A channel id is never the owner.


def owner_only(context, config, kind, read=None):
    """#495: True when the owner alone is addressed: every destination and recipient is the
    owner's identity in outbound.owner for this kind. A nested draft wrapper never is. read is
    the caller's _text(context), when it has one (#626)."""
    if not isinstance(context, dict) or 'draft' in context or _readers(context, kind):
        return False
    mine = _owner_ids(config, kind)
    texts, destinations = read or _text(context)
    targets = [*destinations, *context.get('recipients', []), *filter(None, [context.get('recipient')])]
    if kind == 'mail':  # #501: any address in the payload (a Graph ccRecipients shape) is a reader.
        targets += [address for text in texts for address in re.findall(r'[^\s<>@]+@[^\s<>@]+', text)]
    return bool(mine and targets) and all(target.casefold() in mine for target in targets)


# #838 review: keys that name readers outside DESTINATIONS; any of them means others read it.
READERS = {'users', 'user_ids', 'emails', 'participants', 'members'}


def _readers(value, kind):
    """True when a payload names readers DESTINATIONS does not hold (at any depth), or is a
    mail draft or reply-all, whose recipients the payload does not show."""
    if isinstance(value, list):
        return any(_readers(item, kind) for item in value)
    if not isinstance(value, dict):
        return False
    for key, item in value.items():
        name = _snake(key)
        if name not in DESTINATIONS and (name in READERS or name.endswith(('_ids', '_emails'))):
            return True
        if kind == 'mail' and (name == 'draft_id' or name == 'reply_all' and item is True):
            return True
        if _readers(item, kind):
            return True
    return False


def _owner_ids(config, kind):
    """#495: the owner's casefolded identities in outbound.owner for this kind; #838: Slack and
    docs kinds add the owner's own canvas and page ids."""
    owner = config['outbound']['owner']
    found = owner.get(OWNER.get(kind), '')
    if isinstance(found, dict):
        ids = {value.casefold() for key, value in found.items() if re.fullmatch(SLACK_SHAPE.get(key, ''), value)}
    elif isinstance(found, list):
        ids = set()
    else:
        ids = {found.casefold()} - {''}
    return ids | {page.casefold() for page in owner['pages']} if OWNER.get(kind) in ('slack', 'pages') else ids


def _external_tracker(config):
    """A GitHub project or board owned outside outbound.code_host_orgs is external."""
    if config['adapters']['tracker'] != 'github':
        return False
    orgs = {org.casefold() for org in config['outbound']['code_host_orgs']}
    tracker = config['tracker']
    project = tracker['project'] or next((repo['name'] for repo in config['repos']), '')
    return any(name.split('/')[0].casefold() not in orgs
               for name in (project, tracker['board']) if name)


# Owner disposition markers (#362): only the owner posts them; a seat or port never does.
MARKERS = ('WUWEI parked ', 'WUWEI carried ')
OWNER_MARKERS = 'owner disposition markers must be posted by the owner'


def check_call(inputs, root, config, channels):
    """The port policy (#838): the canary floor and the owner's markers, then the outward-text
    lint and the humanize pass."""
    import json
    from wuwei import security
    from wuwei.guards import profile_result
    try:
        code, reason = security.outbound(inputs, root)
        if code:
            return code, reason
        if any(marker in json.dumps(inputs) for marker in MARKERS):
            return FINDINGS, OWNER_MARKERS
        lint = check_lint(inputs, root, config, channels)
        if not lint[0]:
            lint = humanize_lint(inputs, root, config, channels)
        lint = profile_result(lint, config['profile'], root, next(iter(channels)))
        if lint[0]:
            return lint
        to_owner(inputs, root, config, next(iter(channels)))
        return CLEAN, ''
    except KeyError:
        return UNRUN, 'outward: cannot read profile; run bin/wuwei config check, which names the profile key to fix'
    except (OSError, ValueError, TypeError, AttributeError, re.error):
        return UNRUN, UNREADABLE


def to_owner(inputs, root, config, kind):
    """True, recording outward.to_owner, when only the owner reads the call (#495)."""
    if not owner_only(inputs, config, kind):
        return False
    from wuwei import state  # Only a message to the owner pays for the event.
    state.append_event('outward.to_owner', {'channel': kind}, root)
    return True


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
        return UNRUN, UNREADABLE
