"""Markdown lines to (kind, text) for the remote docs adapters."""

import re


# ponytail: headings, list items and paragraphs only; no inline formatting, tables or links
# as rich text. Add a real Markdown parser when pages need them.
def parse(body):
    rows = []
    for line in body.splitlines():
        heading = re.fullmatch(r'(#{1,3}) +(.*)', line.strip())
        if heading:
            rows.append((f'h{len(heading[1])}', heading[2]))
        elif line.startswith('- '):
            rows.append(('li', line[2:].strip()))
        elif line.strip():
            rows.append(('p', line.strip()))
    return rows
