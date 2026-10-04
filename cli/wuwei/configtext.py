"""The config.toml line model and TOML writer (#494); stdlib only, tomllib reads it back."""

import json
import re
import tomllib


BARE = re.compile(r'[A-Za-z0-9_-]+')
PART = r'\s*(?:[A-Za-z0-9_-]+|"(?:[^"\\\n]|\\.)*"|\'[^\'\n]*\')\s*'
KEYS = rf'{PART}(?:\.{PART})*'
HEADER = re.compile(rf'\s*(?:\[\[({KEYS})\]\]|\[({KEYS})\])\s*(?:#.*)?')
ASSIGN = re.compile(rf'(\s*)({KEYS})=')


def _parts(text):
    """The names of a dotted key, quoted parts decoded."""
    return tuple(tomllib.loads(f'k = {part}')['k'] if part[0] in '"\'' else part
                 for part in (p.strip() for p in re.findall(PART, text)))


def _parses(text):
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return False
    return True


def entries(raw):
    """(lines, items): items are (kind, path, start, end) with kind 'table', 'array' or 'key' and
    lines [start, end); paths carry array-of-tables indexes, so [[repos]] is ('repos', 0)."""
    lines = re.findall(r'[^\n]*\n|[^\n]+', raw)  # Not splitlines: TOML strings may hold U+2028.
    items, table, counts, i = [], (), {}, 0
    while i < len(lines):
        line = lines[i].rstrip('\r\n')
        if header := HEADER.fullmatch(line):
            names = _parts(header[1] or header[2])
            if header[1]:
                counts[names] = counts.get(names, -1) + 1
                for inner in [n for n in counts if len(n) > len(names) and n[:len(names)] == names]:
                    del counts[inner]
            table = []
            for k in range(len(names)):
                table.append(names[k])
                if names[:k + 1] in counts:
                    table.append(counts[names[:k + 1]])
            table = tuple(table)
            items.append(('array' if header[1] else 'table', table, i, i + 1))
            i += 1
            continue
        if assign := ASSIGN.match(line):
            # ponytail: quadratic in a value's line count; config values are short.
            end = next((j for j in range(i + 1, len(lines) + 1) if _parses(''.join(lines[i:j]))), i + 1)
            items.append(('key', (*table, *_parts(assign[2])), i, end))
            i = end
            continue
        i += 1
    return lines, items


def _key(name):
    return name if BARE.fullmatch(name) else json.dumps(name, ensure_ascii=False)


def dumps(value, inline=False):
    """One TOML value: inline tables, scalar lists on one line, other lists one item per line
    unless inline (TOML 1.0 keeps an inline table on one line)."""
    if isinstance(value, str):
        # ensure_ascii=False avoids surrogate pairs; TOML basic strings forbid a raw DEL.
        return json.dumps(value, ensure_ascii=False).replace('\x7f', '\\u007f')
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, dict):
        return '{' + ', '.join(f'{_key(k)} = {dumps(v, True)}' for k, v in value.items()) + '}'
    if isinstance(value, list):
        if inline or all(not isinstance(item, (list, dict)) for item in value):
            return '[' + ', '.join(dumps(item, True) for item in value) + ']'
        return '[\n' + ''.join(f'  {dumps(item, True)},\n' for item in value) + ']'
    raise ValueError(f'{type(value).__name__}: not a TOML value; pass a string, number, boolean, list or table')


def _header(names):
    return '.'.join(_key(n) for n in names if not isinstance(n, int))


def _missing(dotted, index, names):
    return ValueError(f'{dotted}: no entry {index} in {_header(names)}; add it first '
                      '(bin/wuwei config add-repo for a repository)')


def _region(items, n, size):
    """Key items directly under the header at items[n] (n -1 is the root) and the line its
    region ends at."""
    keys = []
    for item in items[n + 1:]:
        if item[0] != 'key':
            return keys, item[2]
        keys.append(item)
    return keys, size


def _set(container, rest, value, dotted):
    """Set rest inside a parsed inline value; an int part indexes a list."""
    for k, part in enumerate(rest[:-1]):
        if isinstance(part, int) and isinstance(container, list) and part < len(container):
            container = container[part]
        elif isinstance(part, int):
            raise _missing(dotted, part, rest[:k])
        elif isinstance(container, dict):
            container = container.setdefault(part, {})
        else:
            return False
    if not isinstance(container, dict):
        return False
    container[rest[-1]] = value
    return True


def place(raw, path, key, value, comment=None):
    """raw with path.key set to value, every other line kept: a present span is replaced, a new
    key goes after its table's last direct key, a missing table is created parents first.
    calibrate.apply verifies the result."""
    target, dotted = (*path, key), '.'.join(map(str, (*path, key)))
    nl = '\r\n' if '\r\n' in raw else '\n'
    lines, items = entries(raw)
    if lines and not lines[-1].endswith('\n'):
        lines[-1] += nl

    def write(at, new, drop=()):
        kept = [i for i in range(len(lines)) if not any(s <= i < e for s, e in drop)]
        return (''.join(lines[i] for i in kept if i < at) + new.replace('\n', nl)
                + ''.join(lines[i] for i in kept if i >= at))

    for kind, found, start, end in items:  # 1: the key's own span; 2: an inline ancestor
        if kind != 'key' or found != target[:len(found)]:
            continue
        lhs = ASSIGN.match(lines[start])
        current = value
        if found != target:
            current = tomllib.loads(''.join(lines[start:end]))
            for part in _parts(lhs[2]):
                current = current[part]
            if not _set(current, target[len(found):], value, dotted):
                continue
        return write(start, f'{lhs[1]}{lhs[2].strip()} = {dumps(current)}\n', [(start, end)])
    headers = {(): -1, **{item[1]: n for n, item in enumerate(items) if item[0] != 'key'}}
    blocks = [n for n, item in enumerate(items) if item[0] == 'array' and item[1][:-1] == target]
    if blocks and isinstance(value, list) and all(isinstance(v, dict) for v in value):  # 3
        spans = [(items[n][2], next((s for k, p, s, _ in items[n + 1:]
                                     if k != 'key' and p[:len(items[n][1])] != items[n][1]), len(lines)))
                 for n in blocks]
        new = ''.join(f'[[{_header(target)}]]\n' + ''.join(f'{_key(k)} = {dumps(v)}\n' for k, v in item.items())
                      for item in value)
        return write(spans[0][0], new, spans)
    entry = (comment or '') + f'{_key(key)} = {dumps(value)}\n'
    if target in headers and items[headers[target]][0] == 'table' and isinstance(value, dict):  # 4
        keys, _ = _region(items, headers[target], len(lines))
        new = ''.join(f'{_key(k)} = {dumps(v)}\n' for k, v in value.items())
        return write(items[headers[target]][3], new, [(s, e) for _, _, s, e in keys])
    if path in headers:  # 5: after the table's last direct key
        keys, _ = _region(items, headers[path], len(lines))
        return write(keys[-1][3] if keys else items[headers[path]][3] if path else 0, entry)
    for k, part in enumerate(path):
        if isinstance(part, int) and path[:k + 1] not in headers:
            raise _missing(dotted, part, path[:k])
    base = next(path[:k] for k in range(len(path) - 1, -1, -1) if path[:k] in headers)
    last = max(n for p, n in headers.items() if p[:len(base)] == base)
    _, at = _region(items, last, len(lines))
    while at > (items[last][3] if last >= 0 else 0) and not lines[at - 1].strip():
        at -= 1
    new = ''.join(f'[{_header(path[:k])}]\n' for k in range(len(base) + 1, len(path) + 1))
    return write(at, '\n' + new + entry)


def declared(path):
    """The workspace.SCHEMA node at path, or None when the schema does not declare it."""
    from wuwei.workspace import SCHEMA
    node = SCHEMA
    for part in path:
        if isinstance(part, int):
            node = node[0] if isinstance(node, list) else None
        else:
            node = node.get(part, node.get('*')) if isinstance(node, dict) else None
        if node is None:
            return None
    return node


KINDS = {str: 'a string', int: 'an integer', float: 'a number', bool: 'true or false'}
SAMPLES = {str: 'text', int: 1, float: 0.5, bool: True}


def _sample(node):
    if isinstance(node, dict):
        names = [n for n in node if n != '*'][:2]
        return {n: _sample(node[n]) for n in names} if names else {'name': _sample(node['*'])}
    if isinstance(node, list):
        return [_sample(node[0])]
    if len(node) > 2 and node[0] is str:
        return node[2][0]
    return node[1] if node[1] not in (None, '') else SAMPLES[node[0]]


def describe(node):
    """(kind, example) of a schema node for a refusal."""
    if isinstance(node, dict):
        kind = 'a table'
    elif isinstance(node, list):
        item = node[0]
        kind = ('a list of tables' if isinstance(item, dict) else
                f"a list of {KINDS[item[0]].split(' ', 1)[1]}s" if item[0] is not bool else 'a list of booleans')
    else:
        kind = KINDS[node[0]]
    return kind, dumps(_sample(node), True)  # One line, for a command-line argument.


def misplaced(raw):
    """Report lines for a key set in a table that declares it and in one that does not."""
    found = {}
    for kind, path, start, _ in entries(raw)[1]:
        if kind == 'key':
            table = declared(path[:-1])
            takes = isinstance(table, dict) and (path[-1] in table or '*' in table)
            found.setdefault(path[-1], []).append((_header(path[:-1]), start + 1, takes))
    return [f'{name} is set in [{good[0]}] (line {good[1]}) and [{bad[0]}] (line {bad[1]}); '
            f'[{bad[0]}] does not take it, remove line {bad[1]}'
            for name, places in found.items() if (good := next((p for p in places if p[2]), None))
            for bad in places if not bad[2]]
