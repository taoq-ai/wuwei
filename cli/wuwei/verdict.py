"""Shared gate verdict lint, ported from the production verdict-lint script."""

from pathlib import Path
import re

from wuwei.exits import CLEAN, FINDINGS, UNRUN


RETRO_KEYS = ('Blocked', 'Gap', 'Change')
VERDICTS = ('PASS', 'FIX', 'PARK', 'ESCALATE')
VERDICT_ROW = r'^(?:## |- )?Verdict:? *(' + '|'.join(VERDICTS) + r')\b'
CITATION = r'[A-Za-z0-9_./-]+\.[a-z]+:[0-9]+|\bL[0-9]+\b'
BLOCKS = r'blocks?:? *(yes|no)\b|\| *(yes|no) *\|'
BLOCKS_YES = r'blocks?:? *yes\b|\| *yes *\|'
SCENARIO = r'scenario|reproduc|fails? when|would |impact|consequence|breaks? '
CLASS_NAMES = ('AUTH', 'VAL', 'DOC', 'TEST', 'INF', 'RET', 'ERR', 'STATE', 'CON', 'BUD',
               'DATA', 'PROOF')
CLASSES = '(' + '|'.join(CLASS_NAMES) + r'): *(PASS|N\.A\.|FINDING)'
SEVERITY = r'(?:P[0-3]|critical|high|medium|low|info)\b'
FINDING_ID = r'\[?(?:[FQSAGN]\d+|Finding\s+\d+)\]?(?:[\s(:.]|$)'  # #677: any role's ids
FIELDS = r'(?:File|Location|Scenario|Severity|blocks?|Probe|Mutation):'
HEADING = r'^\s*(?:#{1,6}\s+(.+?)|([A-Za-z][\w ()/-]*):)\s*$'  # #665: a section heading
FORMAT = {  # #665: the one verdict format; agents build renders section() into the sentinel agents
    'Verdict': ('`Verdict: PASS|FIX|PARK|ESCALATE`, once', 'Verdict: FIX'),
    'Head': ('`Head: <7 to 40 hex>`, the sha you reviewed, once', 'Head: 3f1c2ab'),
    'Finding': ('`F<n> <severity> <file:line> <failure scenario> blocks: yes|no`; a numbered '
                'line is a finding only under a `Findings` heading',
                'F1 medium src/calc.py:19 fails when the input is empty. blocks: yes'),
    'Probe': ('`Probe: <what ran and what it showed>`, or `Probe: not run`', 'Probe: not run'),
    'Class': ('`<CLASS>: PASS|N.A.|FINDING <id>`, one line per class you check, CLASS one of '
              + ', '.join(CLASS_NAMES) + ' (arch, quality and security)', 'VAL: FINDING F1'),
    'Simplicity': ('`Simplicity: <what to delete and what replaces it, or none and why>` (quality)',
                   'Simplicity: none, one guard and one division'),
    'Design': ('`Design: <what makes this change harder to test or change, or none and why>` (quality)',
               'Design: none, a single pure function'),
    'Blocked': ('`Blocked: <evidence or none>`', 'Blocked: none'),
    'Gap': ('`Gap: <evidence or none>`', 'Gap: none'),
    'Change': ('`Change: <evidence or none>`', 'Change: none'),
}



def section():
    """The sentinel agents' verdict section, rendered from FORMAT (#665)."""
    rows = ''.join(f'- {key}: {form}\n' for key, (form, _) in FORMAT.items())
    example = ''.join(line + '\n' for _, line in FORMAT.values())
    return ('## Verdict format\n\nWrite these lines; the verdict lint checks them.\n\n' + rows
            + '\nAn example the lint accepts:\n\n```text\n' + example + '```\n')


def _fix(key, line=None):
    return (f" in '{line.strip()[:80]}'" if line else '') + f'; write: {FORMAT[key][0]}'


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
    blocks, current, findings = [], [], False
    for line in text.splitlines():
        start = re.match(r'^\s*(?:#{1,6}\s+|[-*+]\s+|\|\s*)?\[?'
                         + SEVERITY, line, re.I)
        explicit = re.match(r'^\s*(?:Severity:\s*' + SEVERITY + r'|(?:[-*+]\s+)?Assumption:)', line, re.I)
        # #665: a numbered line is a finding under a Findings heading, or when a severity or
        # an id leads it or it carries blocks:; a numbered list elsewhere is prose.
        lead = '' if findings else (r'(?=\[?' + SEVERITY + r'|Severity:|' + FINDING_ID
                                    + r'|.*?(?:' + BLOCKS + '))')
        numbered = re.match(r'^\s*(?:\d+[.)]\s+' + lead + '|' + FINDING_ID + ')', line, re.I)
        heading = (not (start or numbered) and re.match(HEADING, line)
                   and not re.match(r'^\s*' + FIELDS, line, re.I))
        if heading:
            findings = bool(re.search(r'findings?\b', line, re.I))
        # Table rows can put a finding ID before the severity. Evidence-bearing
        # bullets also start a finding when their severity was accidentally omitted.
        row = (re.match(r'^\s*(?:[-*+]\s+|\|)', line)
               and re.search(CITATION + '|' + BLOCKS + '|' + SEVERITY, line, re.I))
        if current and re.match(r'^\s*[-*+]\s+(?:File|Location|Scenario|blocks?|Probe|Mutation):',
                                line, re.I):
            row = False
        heading_only = len(current) == 1 and re.match(
            r'^\s*(?:#|\d+[.)]\s+|' + FINDING_ID + ')', current[0], re.I)
        if start or row or numbered or explicit and not heading_only:
            if current:
                blocks.append('\n'.join(current))
            current = [line]
        elif current:
            # #665: a bare label (Fix:, Failure scenario:) stays inside the finding; only a
            # markdown heading or a verdict section label closes it.
            if re.match(r'^(?:#|Blocked:|Gap:|Change:|Simplicity:|Design:)', line) or heading and re.match(
                    r'^\s*(?:Findings?|Evidence|Probes?|Residual risks?|Assumptions?)\s*:\s*$', line, re.I):
                blocks.append('\n'.join(current))
                current = []
            else:
                current.append(line)
    if current:
        blocks.append('\n'.join(current))
    return blocks


# #667: a finding that calls the item's docs value missing; the words must touch the value,
# so a finding about the page's content ("docs path docs/x.md is missing a flag") never matches.
DOCS_MISSING = re.compile(
    r'\bdocs? (?:value|path):? (?:is |was )?(?:still )?(?:missing|not set|not recorded|unset|absent)\b'
    r'|\b(?:missing|no|unset) docs? (?:value|path)\b|\bdoc\b[^\n]{0,40}\bvalue missing\b', re.I)


def lint(text, *, quality=False, class_sweep=False, light=False, docs=None):
    """light (#567, a light item's gate): Verdict:, Head: and findings; no probe row, class
    line, Simplicity or Design row, and no retro note unless one of its lines is written.
    docs (#667): (item, recorded value) refuses a finding that calls that value missing."""
    text = active_text(text)
    failures = []
    verdicts = re.findall(VERDICT_ROW, text, re.M)
    verdict = verdicts[0] if verdicts else None
    if not verdict:
        failures.append("missing a 'Verdict: PASS|FIX|PARK|ESCALATE' line at the start of a line")
    elif len(lines := re.findall(r'^(?:## |- )?Verdict(?:[: \t]|$).*$', text, re.M)) != 1:
        failures.append('expected exactly one Verdict: line' + _fix('Verdict', '; '.join(lines[1:])))

    # Keep the production refusals in their original order before added checks.
    if verdict and verdict != 'PASS':
        for pattern, message in (
            (CITATION, f'{verdict} verdict names no file:line (or Lnn for docs)'),
            (BLOCKS + '|blocking', 'no per-finding blocks yes/no'),
            (SCENARIO, 'no failure scenario stated'),
        ):
            if not re.search(pattern, text, re.I):
                failures.append(message)
    if not light and not re.search(r'^(?:Probes?|Mutation):[ \t]*\S[^\n]*$', text, re.M | re.I):
        failures.append("no mutation/probe line (say 'not run' if the seat could not run them)")
    if not light and (class_sweep or quality) and not re.search(CLASSES, text):
        near = re.search(r'^\s*[A-Z]+: *(?:PASS|N\.A\.|FINDING)\b.*$', text, re.M)
        failures.append('no class-sweep line' + _fix('Class', near and near[0]))
    _, missing, invalid = retro_fields(text)
    if light and len(missing) == len(RETRO_KEYS):
        missing = []
    for key in RETRO_KEYS:
        if key in missing:
            failures.append(f"retro note missing '{key}:' line")
        elif key in invalid:
            failures.append(f"retro note has duplicate '{key}:' lines")

    blocks = finding_blocks(text)
    blocking = [block for block in blocks if re.search(BLOCKS_YES, block, re.I)]
    if verdict == 'PASS' and blocking:
        failures.append('PASS verdict carries a blocking finding'
                        + _fix('Verdict', blocking[0].splitlines()[0]) + ', or blocks: no')
    if verdict == 'FIX' and not blocking:
        lines = [line.strip() for line in text.splitlines() if re.search(BLOCKS_YES, line, re.I)]
        failures.append('FIX verdict but no blocking finding parsed; the lines that look like '
                        f'findings are: {"; ".join(lines) or "none"} (start each finding with its '
                        'severity or an id such as F1, Q1 or Finding 1, or list it under a Findings '
                        'heading; write Verdict: PASS when none blocks)')
    if verdict and verdict != 'PASS' and not blocks:
        failures.append('no finding with severity (P0-P3, critical, high, medium, low or info)'
                        + _fix('Finding'))
    for number, block in enumerate(blocks, 1):
        if docs and DOCS_MISSING.search(block):
            failures.append(f'finding {number}: says the docs value is missing, but {docs[0]} records docs '
                            f'{docs[1]} (bin/wuwei why {docs[0]} --json); drop or correct the finding')
        missing = [field for pattern, field in ((r'\b' + SEVERITY, 'severity'),
                                                (CITATION, 'file:line'), (BLOCKS, 'blocks yes/no'),
                                                (SCENARIO, 'failure scenario'))
                   if not re.search(pattern, block, re.I)]
        if missing:
            failures.append(f'finding {number}: missing {", ".join(missing)}'
                            + _fix('Finding', block.splitlines()[0]))
    if quality and not light:
        for key in ('Simplicity', 'Design'):
            values = rows(text, key)
            if len(values) != 1 or not values[0].strip():
                failures.append(f'quality verdict requires exactly one nonempty {key}: row')
    heads = rows(text, 'Head')
    if len(heads) != 1 or not re.fullmatch(r'[0-9a-fA-F]{7,40}', heads[0].strip()):
        failures.append('expected exactly one Head: <7 to 40 hex> row'
                        + _fix('Head', heads and 'Head: ' + heads[-1]))
    if failures:
        return FINDINGS, '\n'.join([*failures, 'REJECT: send back to the seat'])
    return CLEAN, f'OK: {verdict}'


def is_quality(path):
    return 'quality' in re.split(r'[-_.]', Path(path).name.lower())


def record_rejection(path, code, message, *, root=None):
    """Record file/guard rejections when a WUWEI workspace is available."""
    if not code:
        return code, message
    import hashlib
    from wuwei import state, workspace

    try:
        if root is None:
            try:
                root = workspace.find_workspace(Path(path).parent)
            except FileNotFoundError:
                return code, message
        try:
            digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        except OSError:
            digest = None
        state.append_event('verdict.rejected', {'file': str(path), 'sha256': digest,
                           'reasons': message.splitlines()}, root=root)
    except (OSError, ValueError, RuntimeError) as exc:
        return UNRUN, f'{message}\nverdict lint: could not record rejection: {exc}; run bin/wuwei doctor'
    return code, message


def light(path, data):
    """#567: whether a gate file belongs to a seat whose item dispatch tiered light; False
    whenever the seat or item cannot be resolved (today's full shape)."""
    from wuwei import brief, dispatch
    try:
        seat = brief.seats(data).get(Path(path).stem[len('gate-'):]) if data else None
        return seat is not None and dispatch.depth(data['items'][seat['item']], gate=True) == 'light'
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def recorded_docs(path, data, root=None):
    """#667: (item, docs value) when the gate file's seat item records one at lint time; None
    when the value is missing, not required or the seat, item or config cannot be resolved."""
    from wuwei import brief, docs, workspace
    try:
        seat = brief.seats(data).get(Path(path).stem[len('gate-'):]) if data else None
        if seat is None:
            return None
        config = workspace.load_config(root or workspace.find_workspace(Path(path).parent))
        value = docs.shown(config, data['items'][seat['item']])
        return None if value in ('missing', 'n/a') else (seat['item'], value)
    except (KeyError, TypeError, ValueError, AttributeError, OSError):
        return None


def day_state(path):
    """The day state beside a decisions/gate-*.md file, else None."""
    from wuwei import state
    day = Path(path).parent.parent
    try:
        return state.read_state(directory=day) if (day / 'state.json').is_file() else None
    except (OSError, ValueError):
        return None


def lint_file(path, *, role='', root=None):
    try:
        path = Path(path)
        role = role.rsplit(':', 1)[-1]
        data = day_state(path)
        code, message = lint(path.read_text(encoding='utf-8'), light=light(path, data),
                    docs=recorded_docs(path, data, root),
                    quality=role == 'sentinel-quality' or is_quality(path) or is_quality(path.resolve()),
                    class_sweep=role in ('sentinel-arch', 'sentinel-quality', 'sentinel-security') or any(
                        {'arch', 'quality', 'security'} & set(re.split(r'[-_.]', p.name.lower()))
                        for p in (path, path.resolve())))
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
        code, message = UNRUN, f'verdict lint: could not read {path}: {exc}'
    return record_rejection(path, code, message, root=root)
