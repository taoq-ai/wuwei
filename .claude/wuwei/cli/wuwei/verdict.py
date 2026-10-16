"""A gate's verdict file: its shape, parsed and linted in one place."""

import re

GATES = ('arch', 'quality', 'security', 'goal')
VERDICTS = ('PASS', 'FIX', 'ESCALATE')
FINDING = re.compile(r'^- \[(critical|high|medium|low)\] (?:(\S+:\d+(?:-\d+)?) )?blocks: (yes|no)\.?[ \t]*(.*)$', re.I)
FORMAT = '''Verdict: PASS | FIX | ESCALATE
Gate: arch | quality | security | goal
Item: <plan item id>
PR: <owner/repo>#<number>   (or <owner/repo> alone: gates run on the branch before its PR opens)
Head: <the 40-character sha you reviewed>
Confidence: medium   (exactly one word: low, medium or high; give the reason under Probes)
Breaking: no   (arch gate only; or "yes: <what breaks for which clients>")

## Findings
- [critical|high|medium|low] <file>:<line> blocks: yes. Failure: <the concrete scenario that goes wrong>
- [low] <file>:<line> blocks: no. <a note>   (the <file>:<line> is optional on a note)
(or the single word none)'''


def _field(text, name):
    match = re.search(rf'^{name}:[ \t]*(.*)$', text, re.M)
    return match[1].strip() if match else ''


def parse(text, strict=False):
    """strict (at attestation) also asks the arch gate for its Breaking: line."""
    errors = []
    result = {'verdict': _field(text, 'Verdict').upper(), 'gate': _field(text, 'Gate').lower(),
              'item': _field(text, 'Item'), 'head': _field(text, 'Head').lower(),
              'confidence': _field(text, 'Confidence').lower(),
              'repo': '', 'pr': None, 'findings': [], 'errors': errors}
    if result['verdict'] not in VERDICTS:
        errors.append('Verdict: must be PASS, FIX or ESCALATE')
    if result['gate'] not in GATES:
        errors.append(f'Gate: must be one of {", ".join(GATES)}')
    if not re.fullmatch(r'[0-9a-f]{40}', result['head']):
        errors.append('Head: must be the full 40-character sha you reviewed')
    confident = re.match(r'(low|medium|high)\b', result['confidence'])
    result['confidence'] = confident[1] if confident else result['confidence']
    if not confident:
        errors.append('Confidence: must start with low, medium or high')
    match = re.fullmatch(r'([\w.-]+/[\w.-]+)(?:#(\d+))?', _field(text, 'PR'))
    if match:
        result['repo'], result['pr'] = match[1], int(match[2]) if match[2] else None
    else:
        errors.append('PR: must be <owner/repo>#<number>, or <owner/repo> before the PR opens')
    section = re.search(r'^## Findings[ \t]*$(.*?)(?=^## |\Z)', text, re.M | re.S)
    if section is None:
        errors.append('Findings: the verdict needs a "## Findings" section (a finding per line, or none)')
    else:
        lines = [line.strip() for line in section[1].splitlines() if line.strip()]
        if lines != ['none']:
            for line in lines:
                found = FINDING.match(line)
                if found is None:
                    errors.append(f'finding not in the shape "- [severity] <file>:<line> blocks: yes|no. ...": {line[:80]}')
                    continue
                blocks, rest = found[3].lower() == 'yes', found[4]
                failure = re.search(r'Failure:\s*(\S.*)', rest)
                if blocks and not (found[2] and failure):
                    errors.append(f'a blocking finding needs "<file>:<line>" and "Failure: <the scenario>": {line[:80]}')
                    continue
                result['findings'].append({'severity': found[1].lower(), 'where': found[2], 'blocks': blocks,
                                           'failure': failure[1] if failure else rest})
    said = re.match(r'(no|yes)\b[ \t:]*(.*)', _field(text, 'Breaking'), re.I)
    result['breaking'] = (said[2].strip() or 'yes') if said and said[1].lower() == 'yes' else ''
    if strict and result['gate'] == 'arch' and not said:
        errors.append('Breaking: an arch verdict says "Breaking: no" or "Breaking: yes: <what breaks for which clients>"')
    if result['verdict'] == 'PASS' and any(f['blocks'] for f in result['findings']):
        errors.append('PASS with a blocking finding: make it FIX, or mark the finding blocks: no')
    return result
