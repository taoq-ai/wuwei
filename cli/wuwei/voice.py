"""Read owner examples and apply mechanical audience rules."""

import json
from pathlib import Path
import re
import sys
from uuid import uuid4

from wuwei import redact, registry, workspace
from wuwei.exits import ADAPTER_DATA, CLEAN, FINDINGS, UNRUN, DAMAGED, SYMLINK


AUDIENCE = re.compile(r'[A-Za-z0-9_-]+\Z')
EMAIL = re.compile(r'(?<![\w.])[-\w.+]+@[-\w.]+\.[A-Za-z]{2,}\b')
PHONE = re.compile(r'(?<!\w)\+?\d[\d ().-]{7,40}\d(?!\w)')
URL = re.compile(r'https?://\S+')
MENTION = re.compile(r'<@[^>]+>|(?<!\w)@[\w.-]+')


def private(text):
    """Remove common personal identifiers before any durable write."""
    text = EMAIL.sub(redact.REDACTED, text)
    text = PHONE.sub(redact.REDACTED, text)
    text = URL.sub(redact.REDACTED, text)
    text = MENTION.sub(redact.REDACTED, text)
    return redact.redact(text)


def parse_profile(text):
    rules = {}
    audience = None
    for line in text.splitlines():
        if line.startswith('## '):
            audience = line[3:].strip()
            if not AUDIENCE.fullmatch(audience):
                raise ValueError(f'invalid voice audience; {DAMAGED}')
            rules.setdefault(audience, {'never': []})
        elif line.startswith('- ') and ':' in line[2:]:
            key, value = (part.strip() for part in line[2:].split(':', 1))
            if key in ('never', 'max_length', 'required_prefix'):
                if audience is None or not value:
                    raise ValueError(f'invalid voice rule; {DAMAGED}')
                if key == 'max_length':
                    if not value.isdecimal() or int(value) < 1:
                        raise ValueError(f'invalid voice max_length; {DAMAGED}')
                    rules[audience][key] = int(value)
                elif key == 'never':
                    rules[audience][key].append(value)
                else:
                    rules[audience][key] = value
    return rules


def audience(channel, config):
    return next((name for name, channels in config['voice']['sources'].items()
                 if channel in channels), 'review' if channel == 'code_host' else channel)


def lint(text, channel, config, root):
    path = Path(root) / '.wuwei/memory/voice.md'
    if path.is_symlink():
        return UNRUN, f'voice: profile is a symlink; {SYMLINK}'
    if not path.exists():
        return CLEAN, ''
    try:
        rules = parse_profile(path.read_text(encoding='utf-8'))
        selected = [rules.get('shared', {}), rules.get(audience(channel, config), {})]
        for rule in selected:
            if len(text) > rule.get('max_length', float('inf')):
                return FINDINGS, 'voice: audience length exceeded; split the message, or trim it to the audience limit in memory/voice.md'
            prefix = rule.get('required_prefix')
            if prefix and not text.startswith(prefix):
                return FINDINGS, 'voice: required prefix missing; add the required prefix from memory/voice.md'
            if any(phrase.casefold() in text.casefold() for phrase in rule.get('never', [])):
                return FINDINGS, 'voice: never phrase; remove the phrase memory/voice.md lists under never'
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        return UNRUN, 'voice: cannot read profile or audience rules; run bin/wuwei doctor, which names the voice file problem'
    return CLEAN, ''


def learn(root=None):
    """Collect before writing, so an unavailable source cannot leave partial proposals."""
    try:
        root = workspace.find_workspace() if root is None else Path(root)
        config = workspace.load_config(root)
        if config['adapters']['chat'] == 'none':
            raise ValueError('chat adapter is none; the owner sets adapters.chat with bin/wuwei config set in a host terminal')
        owners = set(config['owner']['handles'])
        if not owners:
            raise ValueError('owner.handles is empty; the owner sets owner.handles with bin/wuwei config set in a host terminal')
        sources = config['voice']['sources']
        if any(not AUDIENCE.fullmatch(name) for name in sources):
            raise ValueError(f'invalid voice audience; {DAMAGED}')
        examples = {name: [] for name in sources}
        chat = registry.load('chat', config)
        for audience, channels in sources.items():
            for channel in channels:
                result = chat.sent(channel, sorted(owners), root=root)
                if result.exit or not isinstance(result.data, list):
                    raise ValueError(f'chat.sent could not run; {ADAPTER_DATA}')
                for row in result.data:
                    if not isinstance(row, dict) or not isinstance(row.get('sender'), str) or not isinstance(row.get('text'), str):
                        raise ValueError(f'invalid sent message; {DAMAGED}')
                    if row['sender'] in owners and row['text'].strip():
                        examples[audience].append(private(row['text']))
        refs = config['voice']['review_prs']
        if refs:
            host = registry.load('code_host', config)
            examples.setdefault('review', [])
            for ref in refs:
                result = host.threads(ref, root=root)
                if result.exit or not isinstance(result.data, dict):
                    raise ValueError(f'code_host.threads could not run; {ADAPTER_DATA}')
                rows = result.data.get('comments')
                threads = result.data.get('threads')
                if not isinstance(rows, list) or not isinstance(threads, list):
                    raise ValueError(f'invalid PR comments; {DAMAGED}')
                for thread in threads:
                    if not isinstance(thread, dict) or not isinstance(thread.get('comments'), list):
                        raise ValueError(f'invalid PR thread; {DAMAGED}')
                    rows += thread['comments']
                for row in rows:
                    if not isinstance(row, dict) or not isinstance(row.get('author'), str) or not isinstance(row.get('body'), str):
                        raise ValueError(f'invalid PR comment; {DAMAGED}')
                    if row['author'] in owners and not row.get('is_bot') and row['body'].strip():
                        examples['review'].append(private(row['body']))
        day = workspace.day_dir(root)
        proposals = day / 'proposals'
        evidence_dir = day / 'deliverables'
        if any(path.is_symlink() for path in (day, proposals, evidence_dir)):
            raise ValueError(f'voice output path is a symlink; {SYMLINK}')
        for audience, texts in examples.items():
            if not texts:
                continue
            selected = texts[:10]
            profile = (f'## {audience}\n- max_length: {max(map(len, selected))}\n'
                       + '\n'.join(f'> {line.replace(chr(10), chr(10) + "> ")}' for line in selected) + '\n')
            evidence_dir.mkdir(parents=True, exist_ok=True)
            proposals.mkdir(parents=True, exist_ok=True)
            name = f'voice-{audience}-{uuid4().hex}'
            evidence = evidence_dir / f'{name}.md'
            proposal = proposals / f'{name}.json'
            workspace.atomic_write(evidence, profile, replace=False)
            workspace.atomic_write(proposal, json.dumps({
                'target': '.wuwei/memory/voice.md', 'action': 'add', 'text': profile,
                'reason': f'owner {audience} examples',
                'evidence': str(evidence.relative_to(root)),
            }) + '\n', replace=False)
        return CLEAN
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        print(f'voice learn: {exc}', file=sys.stderr)
        return UNRUN
