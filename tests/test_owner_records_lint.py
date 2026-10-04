"""No owner-facing text asks the owner to type or paste a workflow record or a digest (#357, #354)."""

import ast
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MARKS = ('. ', '? ', '! ', '.\n', '?\n', '!\n', '\n\n')
PATTERN = re.compile(r"\bpaste\b|\bedit the file\b|\b(?:set|sets|record|records)\s+`?"
                     r"(?:Outcome|Decided-by)\b|Decided-by: owner`? in\b|\badd\b[^.\n]*\bgoals\.md|"
                     r"\bopen\s+`?\.wuwei/|replace this guide|\bowner fixes memory/|"
                     r"\btyp(?:e|es|ing) the (?:displayed )?digest\b|To confirm, type", re.I)
ALLOWED = {
    # Credentials are the owner's own secret file; no workflow step can answer for them.
    'Edit the file yourself; the existing state guard refuses agent writes to it.',
    # A warning against pasting secrets, not an instruction to type a record.
    'Never paste the secret or the URI into a website.',
    # config.toml tables and values that span lines are the documented exception to `config set`;
    # the owner may still edit the file afterwards, never as a required step.
    'In a host terminal, change one value with `bin/wuwei config set <key> <value>` and add a '
    'repository with `bin/wuwei config add-repo` (see [calibration](#calibration)); edit the file '
    'by hand only for what they refuse, a table or a value that spans lines.',
    'Edit the file yourself only for a table or a value that spans lines.',
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
            if sentence not in ALLOWED]


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
    assert hits(planted, 'Run it and type the displayed digest.')
    assert hits(planted, 'goals line 1: no goals; the owner fixes memory/goals.md with bin/wuwei goals edit in a host terminal')
    assert not hits(planted, 'Never paste the secret or the URI into a website.')


def test_no_owner_hand_edit_instructions():
    found = collect()
    assert not found, '\n'.join(found)
