"""A derived SQLite graph over the .wuwei records (spike #444). Throwaway PoC code.

The records stay the store; this index can be deleted and rebuilt with no loss.
"""

import hashlib
import json
from pathlib import Path
import re
import sqlite3

REF = r'example/app#\d+'


def fts_available():
    try:
        sqlite3.connect(':memory:').execute('create virtual table t using fts5(x)')
        return True
    except sqlite3.OperationalError:
        return False


def build(root, db, fts):
    """Build the graph at db from root/.wuwei and return the open connection."""
    db = Path(db)
    db.unlink(missing_ok=True)
    conn = sqlite3.connect(db)
    conn.executescript('''create table meta(search text);
        create table nodes(id text primary key, type text, title text, path text, line integer, excerpt text);
        create table edges(src text, dst text, type text, path text, line integer);''')
    conn.execute('insert into meta values (?)', ('fts5' if fts else 'like',))
    root = Path(root)

    def node(ident, kind, title, path, line, text):
        conn.execute('insert or ignore into nodes values (?, ?, ?, ?, ?, ?)',
                     (ident, kind, title, path, line, text[:200]))

    def edge(src, dst, kind, path, line):
        conn.execute('insert into edges values (?, ?, ?, ?, ?)', (src, dst, kind, path, line))

    for file in sorted((p for p in (root / '.wuwei').rglob('*') if p.is_file()),
                       key=lambda p: str(p.relative_to(root))):
        path = str(file.relative_to(root))
        lines = file.read_text(encoding='utf-8').splitlines()
        parts = file.relative_to(root / '.wuwei').parts
        for number, text in enumerate(lines, 1):
            if parts[0] == 'charters' and text.startswith('- '):
                lesson = 'lesson:' + re.search(r'\((L-\d+)\)$', text)[1]
                node(lesson, 'lesson', text[2:], path, number, text)
                for ref in re.findall(REF + r'|INC-\d+', text):
                    edge(lesson, ('incident:' if ref.startswith('INC') else 'pr:') + ref,
                         'learned_from', path, number)
            elif parts[0] == 'memory' and file.name == 'ledger.jsonl':
                record = json.loads(text)
                edge('lesson:' + record['lesson'], 'retro:' + record['evidence'], 'learned_from',
                     path, number)
            elif parts[0] != 'days':
                continue
            elif parts[2] == 'decisions' and text.startswith('Question: '):
                ident = f'decision:{parts[1]}/{file.stem}'
                node(ident, 'decision', text[10:], path, number, text)
                edge(ident, 'item:' + text[10:].split(':')[0], 'decided_in', path, number)
            elif parts[2] == 'decisions' and text.startswith('Context: '):
                for day, name in re.findall(r'Reverses (\S+) (D-\d+)', text):
                    edge(f'decision:{parts[1]}/{file.stem}', f'decision:{day}/{name}',
                         'supersedes', path, number)
            elif parts[2] == 'incidents' and text.startswith('Title: '):
                node('incident:' + file.stem, 'incident', text[7:], path, number, text)
            elif parts[2] == 'incidents' and text.startswith('Caused by: '):
                edge('pr:' + text[11:], 'incident:' + file.stem, 'caused', path, number)
            elif parts[2] == 'retro':
                change = json.loads(text)['fields']['Change']
                node('retro:' + path, 'retro', change, path, number, change)
            elif parts[2] == 'proposal.json':
                for candidate in json.loads(text)['candidates']:
                    item, ticket = 'item:' + candidate['id'], candidate['evidence'].split()[0]
                    node(item, 'item', f'{candidate["id"]} {candidate["scope"]}', path, number, text)
                    node('ticket:' + ticket, 'ticket', candidate['evidence'], path, number, text)
                    edge('ticket:' + ticket, item, 'mentions', path, number)
            elif parts[2] == 'events.jsonl':
                record = json.loads(text)
                kind, payload = record['kind'], record['payload']
                if kind == 'pr.raised':
                    pr = 'pr:' + payload['pr']
                    node(pr, 'pr', f'{payload["pr"]} for {payload["item"]}', path, number, text)
                    edge('item:' + payload['item'], pr, 'closed_by', path, number)
                    for name in payload.get('files', []):
                        node('file:' + name, 'file', name, path, number, text)
                        edge(pr, 'file:' + name, 'touches', path, number)
                elif kind == 'pr.reverted':
                    pr = 'pr:' + payload['pr']
                    node(pr, 'pr', f'{payload["pr"]} reverts {payload["reverts"]}: {payload["reason"]}',
                         path, number, text)
                    edge(pr, 'pr:' + payload['reverts'], 'reverted', path, number)
    if fts:
        conn.execute('create virtual table search using fts5(id unindexed, text)')
        conn.execute("insert into search select id, title || ' ' || excerpt from nodes order by id")
    conn.commit()
    return conn


def ask(conn, words, limit=5):
    """Full text over node titles and excerpts: rows (id, type, title, path, line, excerpt)."""
    columns = 'n.id, n.type, n.title, n.path, n.line, n.excerpt'
    if conn.execute('select search from meta').fetchone()[0] == 'fts5':
        query = ' OR '.join('"' + w.replace('"', '""') + '"' for w in words)
        return conn.execute(f'select {columns} from search join nodes n on n.id = search.id '
                            'where search match ? order by bm25(search), n.id limit ?',
                            (query, limit)).fetchall()
    score = ' + '.join(["(instr(lower(n.title || ' ' || n.excerpt), lower(?)) > 0)"] * len(words))
    return conn.execute(f'select {columns} from (select n.*, {score} as score from nodes n) n '
                        'where score > 0 order by score desc, n.id limit ?',
                        (*words, limit)).fetchall()


def around(conn, node, hops=2, types=None):
    """Nodes within `hops` edges of node in either direction, ordered by (hop, type, id)."""
    seen, frontier, reached = {node}, [node], {}
    filter_ = f' and type in ({",".join("?" * len(types))})' if types else ''
    for hop in range(1, hops + 1):
        found = []
        for current in frontier:
            for src, dst in conn.execute(f'select src, dst from edges where (src = ? or dst = ?){filter_}',
                                         (current, current, *(types or ()))):
                other = dst if src == current else src
                if other not in seen:
                    seen.add(other)
                    found.append(other)
                    reached[other] = hop
        frontier = found
    rows = [conn.execute('select id, type, title, path, line, excerpt from nodes where id = ?',
                         (ident,)).fetchone() for ident in reached]
    return sorted((row for row in rows if row), key=lambda row: (reached[row[0]], row[1], row[0]))


def dump_hash(conn):
    return hashlib.sha256('\n'.join(conn.iterdump()).encode()).hexdigest()
