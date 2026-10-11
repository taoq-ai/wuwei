"""#530: the refusal-string lint: every guard reason, levelled by the posture, is never a wall
under observe or guarded."""

import ast
from importlib import import_module
import re

from test_enforce import fixed
from test_reasons import CLI, reasons

# A wall: the only way out is the owner acting outside the session, and no card is named.
WALL = re.compile(r'no setting lowers it|host terminal|ask the owner to|only the owner|by hand'
                  r'|leave \w+ to the owner')


def wall(reason, line):
    return bool(WALL.search(reason + '\n' + line))


# Reasons the guards return from helpers outside guards/: (file, functions, guard checks).
CALLED = [('security.py', ('outbound', 'gh_outbound'), ('edges.check_send', 'edges.check_bash')),
          ('outward.py', ('check_lint', 'humanize_lint', 'lint'), ('outward.check_lint',)),
          ('shell.py', ('_text', '_cwd', '_cd_target'), ('protect_state.check_bash',))]
# Walls a later item removes; the note on each row is its rationale: (file, substring, note).
OWNED = []  # #831: the config and integrity commands ask their own Owner step card
# Refusals that are not walls the workflow puts up; the note on each row is its rationale.
MERGES = "merge family: bin/wuwei merge is the path (#524); approval and override stay the owner's"
EXEMPT = [*[('guards/edges.py', part, MERGES) for part in (
              'merge policy', 'admin merge', 'PR approval', 'branch protection')],
          ('guards/stop.py', 'day state missing for registered planner', 'records: state recovery')]


def _functions(tree):
    return [(node.name, node.lineno, node.end_lineno) for node in tree.body
            if isinstance(node, ast.FunctionDef)]


def corpus():
    """[(file, line, check, reason)]: every guard reason with each guard check that returns it."""
    found = []
    for path in sorted((CLI / 'guards').glob('*.py')):
        if path.name == '__init__.py':
            continue
        name, source = path.stem, path.read_text()
        checks = [guard.check for guard in import_module(f'wuwei.guards.{name}').GUARDS]
        functions = _functions(ast.parse(source))
        lines = source.splitlines()
        body = {f: '\n'.join(lines[start - 1:end]) for f, start, end in functions}
        for line, text, _ in reasons(source, path.name):
            inside = next((f for f, start, end in functions if start <= line <= end), None)
            # The check itself, else the checks that call the helper, else every check.
            own = ([c for c in checks if c.__name__ == inside]
                   or [c for c in checks if f'{inside}(' in body.get(c.__name__, '')] or checks)
            found += [(f'guards/{path.name}', line, (name, c.__name__), text) for c in own]
    for rel, names, keys in CALLED:
        source = (CLI / rel).read_text()
        ranges = [(start, end) for f, start, end in _functions(ast.parse(source)) if f in names]
        for line, text, _ in reasons(source, rel):
            if any(start <= line <= end for start, end in ranges):
                found += [(rel, line, tuple(key.split('.')), text) for key in keys]
    return found


def listed(rows, rel, reason):
    return next((note for file, part, note in rows if file == rel and part in reason), None)


def test_reason_corpus_has_no_wall(tmp_path, monkeypatch):
    from wuwei import state
    from wuwei.commands import hook
    from wuwei.guards import RECORDS_FLOOR
    monkeypatch.setattr(state, 'append_event', lambda *args, **kwargs: None)
    (tmp_path / '.wuwei').mkdir()
    payload = {'hook_event_name': 'PreToolUse', 'session_id': 'fixture', 'tool_name': 'Read',
               'tool_input': {}}
    rows, walls = corpus(), []
    # #839 (part 17): the parser guards' reasons went with their code; the floor is the count measured after.
    # Batch 7: the floor was re-measured at 153; the drop came from an earlier part in this batch.
    assert len(rows) >= 153
    stale = [row for row in OWNED + EXEMPT if not any(r[0] == row[0] and row[1] in r[3] for r in rows)]
    assert not stale, stale
    for enforce in ('true', 'false'):
        (tmp_path / '.wuwei/config.toml').write_text(f'[guards]\nenforce = {enforce}\n')
        for rel, line, (module, name), reason in rows:
            check = fixed(module, 1, reason, name)
            for guard, shown, _ in hook.enforce(payload, [(check, reason, 1)], tmp_path):
                if (not wall(shown, '') or shown.startswith(RECORDS_FLOOR)
                        or listed(OWNED + EXEMPT, rel, shown)):
                    continue
                walls.append(f'enforce={enforce} {rel}:{line} {module}.{name}: {shown}')
    assert not walls, '\n'.join(sorted(set(walls)))
