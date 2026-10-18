"""Probe for the Announcement: shape (item announcement-url). Run from a copy of the tree, never a worktree:

    python3 -I specs/announcement-url/probe.py <tree> [<main tree>]

Part 1 generates Announcement: lines (prefix x value x suffix x line end x position in the body), reads
each through breaking_gaps at <tree> (and at <main tree> when given), and compares with an oracle built on
urllib.parse: the line counts when its text after the colon, less spaces and tabs around it, is one
http:// or https:// URL with a host and no whitespace. Part 2 applies mutants to the regex in <tree> and
runs the focused test, which must kill each one."""

import itertools
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

PREFIXES = ['Announcement:', 'Announcement: ', 'Announcement:\t', 'Announcement:  \t ', '  Announcement: ',
            '> Announcement: ', 'announcement: ', 'Announcement: ', '- Announcement: ']
VALUES = ['https://acme.test/n', 'http://acme.test/n', 'https://github.com/o/r/issues/1#issuecomment-1',
          'https://acme.test', 'https://acme.test:8080/a?b=c', 'HTTPS://acme.test/n', 'ftp://acme.test/n',
          'file:///x', 'javascript:alert(1)', 'www.acme.test/n', 'CHANGELOG.md', 'CHANGELOG.md (placeholder)',
          'see CHANGELOG', 'see https://acme.test/n', 'https://acme.test/n (later)', '<https://acme.test/n>',
          '[n](https://acme.test/n)', 'https://', 'https:// acme.test', 'https:///n', 'https://acme.test/a b',
          '', 'TBD', 'https://acme.test/ ']
SUFFIXES = ['', ' ', '\t', ' \t ', ' ', ' x']
ENDS = ['', '\n', '\r\n', '\nmore', '\r\nmore']
PLACES = ['last', 'first']


def oracle(line):
    if not line.startswith('Announcement:'):
        return False
    value = line[len('Announcement:'):].strip(' \t')
    return (value.startswith(('http://', 'https://')) and not any(c.isspace() for c in value)
            and bool(urlsplit(value).netloc))


def reader(tree):
    source = (Path(tree) / 'cli' / 'wuwei' / 'evidence.py').read_text()
    pattern = re.search(r"if not re\.search\(r'(\^Announcement:[^']*)', body, re\.M\)", source)[1]
    return lambda body: bool(re.search(pattern, body, re.M))


def part1(tree, main):
    head, old = reader(tree), main and reader(main)
    ran = holes = moved = opened = 0
    for prefix, value, suffix, end, place in itertools.product(PREFIXES, VALUES, SUFFIXES, ENDS, PLACES):
        line = prefix + value + suffix
        body = f'WUWEI-Item: I-1\n{line}{end}' if place == 'last' else f'{line}{end}\nWUWEI-Item: I-1'
        ran += 1
        want, got = oracle(line), head(body)
        if want != got:
            holes += 1
            print('HOLE', repr(body), 'head', got, 'oracle', want)
        if old and old(body) != got:
            moved += 1
            opened += got  # main refused, the head counts it
    print(f'part 1: {ran} bodies, {holes} holes against the oracle, {moved} verdicts moved from main, '
          f'{opened} of them to counted')
    return holes


MUTANTS = [(r'https?://', r'\w+://'), (r'https?://', r'https?:'), (r'[^\s/?#]+', r'[^\s/?#]*'),
           (r'[ \t\r]*$', r'[ \t\r]*'), (r'[ \t\r]*$', r'[ \t]*$'), (r'\S*[ \t\r]*$', r'.*$'),
           (r'^Announcement:', r'Announcement:'), (r':[ \t]*h', r':\s*h')]


def part2(tree):
    path = Path(tree) / 'cli' / 'wuwei' / 'evidence.py'
    source, survived = path.read_text(), 0
    test = 'tests/test_evidence.py::test_an_announcement_counts_only_as_one_http_url_alone_on_its_line'
    for old, new in MUTANTS:
        line = re.search(r".*if not re\.search\(r'\^Announcement:.*", source)[0]
        assert old in line, old
        path.write_text(source.replace(line, line.replace(old, new, 1)))
        run = subprocess.run([shutil.which('pytest') or 'pytest', '-q', '-x', '-p', 'no:cacheprovider', test],
                             cwd=tree, capture_output=True, text=True)
        killed = run.returncode != 0
        survived += not killed
        print('killed' if killed else 'SURVIVED', repr(old), '->', repr(new))
    path.write_text(source)
    print(f'part 2: {len(MUTANTS)} mutants, {survived} survived')
    return survived


if __name__ == '__main__':
    tree, main = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None
    sys.exit(1 if part1(tree, main) + part2(tree) else 0)
