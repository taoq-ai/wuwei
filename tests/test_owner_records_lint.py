"""No owner-facing text asks the owner to type or paste a workflow record (#357)."""

import ast
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MARKS = ('. ', '? ', '! ', '.\n', '?\n', '!\n', '\n\n')
PATTERN = re.compile(r"\bpaste\b|\bedit the file\b|\b(?:set|sets|record|records)\s+`?"
                     r"(?:Outcome|Decided-by)\b|Decided-by: owner`? in\b|\badd\b[^.\n]*\bgoals\.md|"
                     r"\bopen\s+`?\.wuwei/|replace this guide", re.I)
ALLOWED = {
    # Credentials are the owner's own secret file; no workflow step can answer for them.
    'Edit the file as the owner; the existing state guard refuses agent writes to it.',
    # A warning against pasting secrets, not an instruction to type a record.
    'Never paste the secret or the URI into a website.',
    # config.toml tables and values that span lines are the documented exception to `config set`;
    # the owner may still edit the file afterwards, never as a required step.
    'In a host terminal, change one value with `bin/wuwei config set <key> <value>` and add a '
    'repository with `bin/wuwei config add-repo` (see [calibration](#calibration)); edit the file '
    'by hand only for what they refuse, a table or a value that spans lines.',
    'Edit the file yourself only for a table or a value that spans lines.',
}
# removed by #354 (decide command); delete this set when it lands
PENDING_354 = {
    'An owner reviews every linked report, sets `Decided-by: owner` and `Outcome: proceed` in '
    'the queued decision and runs `bin/wuwei mcp decide` from a host terminal, typing the '
    'displayed digest.',
    'The owner reviews the reports, records `Decided-by: owner` and `Outcome: proceed` in the '
    'decision, then runs `wuwei mcp decide` from the host terminal.',
    'review the decision named, set Outcome: proceed, then wuwei mcp decide',
}


def sentences(text):
    """(line, sentence) for every pattern hit, whitespace collapsed."""
    found = []
    for match in PATTERN.finditer(text):
        start = max(text.rfind(mark, 0, match.start()) for mark in MARKS)
        start = 0 if start < 0 else start + 2
        ends = [index for index in (text.find(mark, match.end()) for mark in MARKS) if index >= 0]
        end = min(ends) + 1 if ends else len(text)
        sentence = ' '.join(text[start:end].split())
        found.append((text.count('\n', 0, match.start()) + 1, sentence))
    return found


def hits(path, text, line=0):
    rel = path.relative_to(ROOT).as_posix()
    return [f'{rel}:{line + number}: {sentence}' for number, sentence in sentences(text)
            if sentence not in ALLOWED | PENDING_354]


def collect():
    found = []
    files = [*ROOT.glob('skills/**/SKILL.md'), *ROOT.glob('docs/site/**/*.md'),
             *ROOT.glob('templates/**/*.md'), *ROOT.glob('templates/**/*.toml')]
    for path in sorted(files):
        found += hits(path, path.read_text(encoding='utf-8'))
    for path in sorted(ROOT.glob('cli/wuwei/**/*.py')):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                found += hits(path, node.value, node.lineno - 1)
    return found


def test_lint_catches_planted_instruction():
    planted = ROOT / 'docs/site/planted.md'
    assert hits(planted, 'Paste these blocks into .wuwei/memory/goals.md.')
    assert not hits(planted, 'Never paste the secret or the URI into a website.')


def test_no_owner_hand_edit_instructions():
    found = collect()
    assert not found, '\n'.join(found)
