"""Reusable mechanical outward-text policy, independent of hooks and profiles."""

import re
import sys
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
                   'channel_id', 'issueId', 'owner', 'repo'}


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
        elif key in {'issue_number', 'pull_number'}:
            if type(value) not in (str, int):
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


def classify(text, root, config):
    """Return (0|1|2, send|draft) for adapters and the future outbound tiers (#95)."""
    try:
        if not isinstance(text, str) or not text.strip():
            return UNRUN, 'draft'
        # ponytail: only this complete mechanical form auto-sends; widen through #95.
        mechanical = re.fullmatch(r'fixed in ([0-9a-f]{7,40})\.?', text.strip(), re.IGNORECASE)
        if not mechanical:
            return FINDINGS, 'draft'
        from wuwei import registry
        vcs = registry.load('vcs', config)
        unresolved = FINDINGS
        for repo in config['repos']:
            path = (root / Path(repo['path']).expanduser()).resolve()
            result = vcs.resolve(path, mechanical[1].lower(), root=root)
            if result.exit == CLEAN:
                return CLEAN, 'send'
            if result.exit == UNRUN:
                unresolved = UNRUN
        return unresolved, 'draft'
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return UNRUN, 'draft'


def check_call(inputs, root, config, channels):
    """Shared lint and send policy for MCP hooks and text-bearing adapter ports."""
    try:
        texts, destinations = _text(inputs)
        text = '\n'.join(texts)
        for channel in sorted(channels.union(destinations)):
            code, reason = lint(text, channel, config)
            if code == FINDINGS and config['profile'] == 'standard':
                print(f'warning: {reason}', file=sys.stderr)
            elif code:
                if code == FINDINGS:
                    reason += '; deliver as a draft for the owner to send'
                return code, reason
        code, decision = classify(text, root, config)
        if code == UNRUN:
            return code, 'outward: commit could not be resolved'
        if decision == 'draft':
            return code, 'outward: deliver as a draft for the owner to send'
        return CLEAN, ''
    except (OSError, ValueError, TypeError, KeyError, AttributeError, re.error):
        return UNRUN, 'outward: cannot read or validate policy or payload'
