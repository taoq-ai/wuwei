"""Shared gate verdict lint, ported from the production verdict-lint script."""

from pathlib import Path
import re

from wuwei.exits import CLEAN, FINDINGS, UNRUN


RETRO_KEYS = ('Blocked', 'Gap', 'Change')
CITATION = r'[A-Za-z0-9_./-]+\.[a-z]+:[0-9]+|\bL[0-9]+\b'
BLOCKS = r'blocks?:? *(yes|no)\b|\| *(yes|no) *\|'
SCENARIO = r'scenario|reproduc|fails? when|would |impact|consequence|breaks? '
CLASSES = r'(AUTH|VAL|DOC|TEST|INF|RET|ERR|STATE|CON|BUD|DATA|PROOF): *(PASS|N\.A\.|FINDING)'
SEVERITY = r'(?:P[0-3]|critical|high|medium|low|info)\b'


def active_text(text, *, unformat=True):
    """Ignore examples and comments, and normalize inline Markdown emphasis."""
    lines, fence = [], None
    for line in re.sub(r'<!--.*?(?:-->|\Z)', '', text, flags=re.S).splitlines():
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is None and not line.lstrip().startswith('>'):
            lines.append(line.replace('**', '').replace('`', '') if unformat else line)
    return '\n'.join(lines)


def rows(text, key):
    return re.findall(r'^\*{0,2}' + re.escape(key)
                      + r'\*{0,2}:\*{0,2}[ \t]*(.*)$', text, re.M)


def retro_fields(text):
    fields, missing, invalid = {}, [], []
    text = active_text(text, unformat=False)
    for key in RETRO_KEYS:
        values = rows(text, key)
        if not values or not any(value.strip() for value in values):
            missing.append(key)
        elif len(values) != 1:
            invalid.append(key)
        else:
            fields[key] = values[0].strip()
    return fields, missing, invalid


def finding_blocks(text):
    blocks, current = [], []
    for line in text.splitlines():
        start = re.match(r'^\s*(?:#{1,6}\s+|[-*+]\s+|\|\s*)?\[?'
                         + SEVERITY, line, re.I)
        explicit = re.match(r'^\s*Severity:\s*' + SEVERITY, line, re.I)
        numbered = re.match(r'^\s*(?:\d+[.)]\s+|\[?F\d+\]?(?:[\s(:.]|$))', line, re.I)
        # Table rows can put a finding ID before the severity. Evidence-bearing
        # bullets also start a finding when their severity was accidentally omitted.
        row = (re.match(r'^\s*(?:[-*+]\s+|\|)', line)
               and re.search(CITATION + '|' + BLOCKS + '|' + SEVERITY, line, re.I))
        if current and re.match(r'^\s*[-*+]\s+(?:File|Location|Scenario|blocks?|Probe|Mutation):',
                                line, re.I):
            row = False
        heading_only = len(current) == 1 and re.match(
            r'^\s*(?:#|\d+[.)]\s+|\[?F\d+\]?(?:[\s(:.]|$))', current[0], re.I)
        if start or row or numbered or explicit and not heading_only:
            if current:
                blocks.append('\n'.join(current))
            current = [line]
        elif current:
            if re.match(r'^(?:#|Blocked:|Gap:|Change:|Simplicity:|Design:)', line):
                blocks.append('\n'.join(current))
                current = []
            else:
                current.append(line)
    if current:
        blocks.append('\n'.join(current))
    return blocks


def lint(text, *, quality=False, class_sweep=False):
    text = active_text(text)
    failures = []
    verdicts = re.findall(r'^(?:## |- )?Verdict:? *(PASS|FIX|PARK|ESCALATE)\b', text, re.M)
    verdict = verdicts[0] if verdicts else None
    if not verdict:
        failures.append("missing a 'Verdict: PASS|FIX|PARK|ESCALATE' line at the start of a line")
    elif len(re.findall(r'^(?:## |- )?Verdict(?:[: \t]|$)', text, re.M)) != 1:
        failures.append('expected exactly one Verdict: line')

    # Keep the production refusals in their original order before added checks.
    if verdict and verdict != 'PASS':
        for pattern, message in (
            (CITATION, f'{verdict} verdict names no file:line (or Lnn for docs)'),
            (BLOCKS + '|blocking', 'no per-finding blocks yes/no'),
            (SCENARIO, 'no failure scenario stated'),
        ):
            if not re.search(pattern, text, re.I):
                failures.append(message)
    if not re.search(r'^(?:Probes?|Mutation):[ \t]*\S[^\n]*$', text, re.M | re.I):
        failures.append("no mutation/probe line (say 'not run' if the seat could not run them)")
    if (class_sweep or quality) and not re.search(CLASSES, text):
        failures.append('no class-sweep line (CLASS: PASS|N.A.|FINDING <id>)')
    _, missing, invalid = retro_fields(text)
    for key in RETRO_KEYS:
        if key in missing:
            failures.append(f"retro note missing '{key}:' line")
        elif key in invalid:
            failures.append(f"retro note has duplicate '{key}:' lines")

    blocks = finding_blocks(text)
    if verdict == 'PASS' and any(re.search(r'blocks?:? *yes\b|\| *yes *\|', block, re.I)
                                 for block in blocks):
        failures.append('PASS verdict carries a blocking finding')
    if verdict and verdict != 'PASS' and not blocks:
        failures.append('no finding with severity (P0-P3, critical, high, medium, low or info)')
    for number, block in enumerate(blocks, 1):
        for pattern, field in ((r'\b' + SEVERITY, 'severity'),
                               (CITATION, 'file:line'), (BLOCKS, 'blocks yes/no'),
                               (SCENARIO, 'failure scenario')):
            if not re.search(pattern, block, re.I):
                failures.append(f'finding {number}: missing {field}')
    if quality:
        for key in ('Simplicity', 'Design'):
            values = rows(text, key)
            if len(values) != 1 or not values[0].strip():
                failures.append(f'quality verdict requires exactly one nonempty {key}: row')
    heads = rows(text, 'Head')
    if len(heads) != 1 or not re.fullmatch(r'[0-9a-fA-F]{7,40}', heads[0].strip()):
        failures.append('expected exactly one Head: <7 to 40 hex> row')
    if failures:
        return FINDINGS, '\n'.join([*failures, 'REJECT: send back to the seat'])
    return CLEAN, f'OK: {verdict}'


def is_quality(path):
    return 'quality' in re.split(r'[-_.]', Path(path).name.lower())


def record_rejection(path, code, message, *, root=None):
    """Record file/guard rejections when a WUWEI workspace is available."""
    if not code:
        return code, message
    from wuwei import state, workspace

    try:
        if root is None:
            try:
                root = workspace.find_workspace(Path(path).parent)
            except FileNotFoundError:
                return code, message
        state.append_event('verdict.rejected', {'file': str(path),
                           'reasons': message.splitlines()}, root=root)
    except (OSError, ValueError, RuntimeError) as exc:
        return UNRUN, f'{message}\nverdict lint: could not record rejection: {exc}'
    return code, message


def lint_file(path, *, role='', root=None):
    try:
        path = Path(path)
        role = role.rsplit(':', 1)[-1]
        code, message = lint(path.read_text(encoding='utf-8'),
                    quality=role == 'sentinel-quality' or is_quality(path) or is_quality(path.resolve()),
                    class_sweep=role in ('sentinel-arch', 'sentinel-quality', 'sentinel-security') or any(
                        {'arch', 'quality', 'security'} & set(re.split(r'[-_.]', p.name.lower()))
                        for p in (path, path.resolve())))
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
        code, message = UNRUN, f'verdict lint: could not read {path}: {exc}'
    return record_rejection(path, code, message, root=root)
