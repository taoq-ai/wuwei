"""A gate's verdict file: its shape, parsed and linted in one place."""

import re

GATES = ('arch', 'quality', 'security', 'goal')
VERDICTS = ('PASS', 'FIX', 'ESCALATE')
FINDING = re.compile(r'^- \[(critical|high|medium|low)\] (\S+:\d+) blocks: (yes|no)\. Failure: (\S.*)$')
FORMAT = '''Verdict: PASS | FIX | ESCALATE
Gate: arch | quality | security | goal
Item: <plan item id>
PR: <owner/repo>#<number>
Head: <the 40-character sha you reviewed>

## Findings
- [critical|high|medium|low] <file>:<line> blocks: yes|no. Failure: <the concrete scenario that goes wrong>
(or the single word none)'''


def _field(text, name):
    match = re.search(rf'^{name}:[ \t]*(.*)$', text, re.M)
    return match[1].strip() if match else ''


def parse(text):
    errors = []
    result = {'verdict': _field(text, 'Verdict').upper(), 'gate': _field(text, 'Gate').lower(),
              'item': _field(text, 'Item'), 'head': _field(text, 'Head').lower(),
              'repo': '', 'pr': None, 'findings': [], 'errors': errors}
    if result['verdict'] not in VERDICTS:
        errors.append('Verdict: must be PASS, FIX or ESCALATE')
    if result['gate'] not in GATES:
        errors.append(f'Gate: must be one of {", ".join(GATES)}')
    if not re.fullmatch(r'[0-9a-f]{40}', result['head']):
        errors.append('Head: must be the full 40-character sha you reviewed')
    match = re.fullmatch(r'([\w.-]+/[\w.-]+)#(\d+)', _field(text, 'PR'))
    if match:
        result['repo'], result['pr'] = match[1], int(match[2])
    else:
        errors.append('PR: must be <owner/repo>#<number>')
    section = re.search(r'^## Findings[ \t]*$(.*?)(?=^## |\Z)', text, re.M | re.S)
    if section is None:
        errors.append('Findings: the verdict needs a "## Findings" section (a finding per line, or none)')
    else:
        lines = [line.strip() for line in section[1].splitlines() if line.strip()]
        if lines != ['none']:
            for line in lines:
                found = FINDING.match(line)
                if found is None:
                    errors.append(f'finding not in the shape "- [severity] file:line blocks: yes|no. '
                                  f'Failure: <scenario>": {line[:80]}')
                    continue
                result['findings'].append({'severity': found[1], 'where': found[2],
                                           'blocks': found[3] == 'yes', 'failure': found[4]})
    if result['verdict'] == 'PASS' and any(f['blocks'] for f in result['findings']):
        errors.append('PASS with a blocking finding: make it FIX, or mark the finding blocks: no')
    return result
