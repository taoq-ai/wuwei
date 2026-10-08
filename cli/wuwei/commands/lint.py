"""Measure prose against the plain tone rule in charters/_common-authoring.md."""

from pathlib import Path
import re
import sys

AVERAGE, LONGEST = 20, 35
# ponytail: a suffix heuristic with false hits ("comment", "decision"); compare rates over
# time, and move to a word list if the rate misleads.
NOMINAL = re.compile(r'\b(?=[a-z]{7})[a-z]*(?:tion|sion|ment|ance|ence|ness|ity)s?\b', re.I)
_DROP = re.compile(r'\A---\n.*?\n---\n|```.*?```|<!--.*?-->', re.S)
_ITEM = re.compile(r'\s*(?:[-*]|\d+\.)\s')


def _blocks(text):
    """The prose of one text as blocks; a sentence never crosses a block."""
    text = _DROP.sub('\n', text)
    text = re.sub(r'`[^`\n]*`', 'code', text)
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
    blocks, current = [], []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or (set(stripped) <= set('|:- ') and '-' in stripped):
            blocks.append(current)
            current = []
        elif stripped.startswith('|'):
            blocks.append(current)
            blocks.extend([cell] for cell in stripped.split('|'))
            current = []
        elif _ITEM.match(line):
            blocks.append(current)
            current = [line[_ITEM.match(line).end():]]
        else:
            current.append(line)
    blocks.append(current)
    return [' '.join(' '.join(block).split()) for block in blocks if block]


def _lengths(block):
    for piece in re.split(r'(?<=[.!?])\s+', block):
        words = sum(1 for token in piece.split() if re.search(r'[\w{]', token))
        if words:
            yield words


def sentences(text):
    """The length in words of each sentence of one text. A semicolon is not a boundary."""
    return [n for block in _blocks(text) for n in _lengths(block)]


def measure(*texts):
    lengths = [n for text in texts for n in sentences(text)]
    words = sum(lengths)
    return {'sentences': len(lengths), 'words': words,
            'average': words / len(lengths) if lengths else 0.0,
            'longest': max(lengths, default=0), 'over': sum(n > LONGEST for n in lengths),
            'nominalisations': sum(len(NOMINAL.findall(block)) for text in texts for block in _blocks(text))}


def at_rule(m):
    return m['average'] < AVERAGE and m['over'] == 0


def line(name, m):
    rate = 100 * m['nominalisations'] / m['words'] if m['words'] else 0.0
    return (f"{name}: average {m['average']:.1f} words, longest {m['longest']}, {m['over']} over {LONGEST}, "
            f"{m['sentences']} sentences, {m['nominalisations']} nominalisations ({rate:.1f} per 100 words), "
            f"{'at' if at_rule(m) else 'over'} the rule")


def register(subparsers):
    parser = subparsers.add_parser('lint', help='Measure prose against a writing rule')
    actions = parser.add_subparsers(dest='lint_action', required=True)
    tone = actions.add_parser('tone', help='Report sentence length and nominalisations per file against the '
                                           'plain tone rule')
    tone.add_argument('paths', nargs='+')
    tone.set_defaults(func=run_tone)


def run_tone(args):
    files = []
    for name in args.paths:
        path = Path(name)
        found = sorted(path.rglob('*.md')) if path.is_dir() else [path] if path.is_file() else []
        if not found:
            print(f'wuwei lint tone: {name} is not a file or a directory with markdown files; '
                  'pass a markdown file or a directory of them', file=sys.stderr)
            return 2
        files += found
    texts = []
    for path in files:
        try:
            texts.append(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeDecodeError) as exc:
            print(f'wuwei lint tone: cannot read {path} ({exc}); pass a readable UTF-8 file', file=sys.stderr)
            return 2
    measured = [measure(text) for text in texts]
    for path, m in zip(files, measured):
        print(line(str(path), m))
    if len(files) > 1:
        print(line('total', measure(*texts)))
    return 0 if all(map(at_rule, measured)) else 1
