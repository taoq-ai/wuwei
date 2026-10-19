"""Count the rows of the announcement test whose verdict moves from main to the head:

    python3 -I specs/announcement-url/rows.py tests/test_evidence.py
"""
import ast
import re
import sys

src = open(sys.argv[1]).read()
block = re.search(r"@pytest.mark.parametrize\('line, found', \[(.*?)\n\]\)\ndef test_an_announcement", src, re.S)[1]
rows = [ast.literal_eval(m[1]) for m in re.finditer(r"^\s*\(('(?:[^'\\]|\\.)*'), (?:CONFIRM|ANNOUNCE)\)", block, re.M)]
old = re.compile(r'^Announcement:[ \t]*\S', re.M)
new = re.compile(r'^Announcement:[ \t]*https?://[^\s/?#]\S*[ \t\r]*$', re.M)
body = lambda r: 'WUWEI-Item: I-1\n' + r
print(len(rows), 'rows;', sum(bool(new.search(body(r))) for r in rows), 'count at head;',
      sum(bool(old.search(body(r))) and not new.search(body(r)) for r in rows), 'counted on main and refused at head;',
      sum(not old.search(body(r)) and not new.search(body(r)) for r in rows), 'refused on both')
