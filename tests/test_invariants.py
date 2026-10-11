"""#530: the refusal-string lint: every guard reason, levelled by the posture, is never a wall
under observe or guarded."""

import ast
from importlib import import_module
import re

from test_posture import fixed
from test_reasons import CLI, reasons

# A wall: the only way out is the owner acting outside the session, and no card is named.
WALL = re.compile(r'no setting lowers it|host terminal|ask the owner to|only the owner|by hand'
                  r'|leave \w+ to the owner')
CARD = re.compile(r'bin/wuwei (?:decision show D-|drafts show draft-)')


def wall(reason, line):
    return not CARD.search(reason) and bool(WALL.search(reason + '\n' + line))


# Reasons the guards return from helpers outside guards/: (file, functions, guard checks).
CALLED = [('grants.py', ('gate', 'evidence'), ('deploy.check', 'commit_push.check', 'pr.check')),
          ('security.py', ('outbound', 'gh_outbound'), ('outward.check_tier', 'pr.check')),
          ('drafts.py', ('reason',), ('outward.check_tier',)),
          ('outward.py', ('check_tier', 'blocked'), ('outward.check_tier',)),
          ('integrity.py', ('measure',), ('integrity.check',)),
          ('shell.py', ('_text', '_cwd', '_cd_target'), ('protect_state.check_bash',))]
# Walls a later item removes; the note on each row is its rationale: (file, substring, note).
LATER = 'follow-up, specs/530-posture-day Deferred'
OWNED = [('guards/commit_push.py', 'config add-repo', LATER),
         ('guards/commit_push.py', 'default_branch', LATER),
         ('guards/commit_push.py', 'empty configured fast check', LATER),
         ('guards/pr.py', 'API repository default branch is unmeasured', LATER),
         ('integrity.py', 'page: plugin integrity', LATER)]
# Refusals that are not walls the workflow puts up; the note on each row is its rationale.
MERGES = "merge family: bin/wuwei merge is the path (#524); approval and override stay the owner's"
EXEMPT = [('grants.py', '{} {}; ask the owner to run it in a host terminal', 'heartbeat probe'),
          ('grants.py', 'permissions deny it', 'permissions.deny, deferred'),
          ('grants.py', 'kept it owner-only', "the owner's own Keep answer"),
          *[('guards/pr.py', part, MERGES) for part in (
              'merge policy', 'admin merge', 'PR approval', 'branch protection', 'a shepherd seat never merges')],
          ('guards/stop.py', 'day state missing for registered planner', 'records: state recovery'),
          ('guards/deploy.py', 'if it publishes, run it as a plain literal command',
           'unknown git: the hook levels it to a warning below strict')]


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
    assert len(rows) > 200
    stale = [row for row in OWNED + EXEMPT if not any(r[0] == row[0] and row[1] in r[3] for r in rows)]
    assert not stale, stale
    for posture in ('observe', 'guarded'):
        (tmp_path / '.wuwei/config.toml').write_text(f'[security]\nposture = "{posture}"\n')
        for rel, line, (module, name), reason in rows:
            check = fixed(module, 1, reason)
            check.__name__ = name
            for guard, shown, posture_line, _ in hook.posture(payload, [(check, reason, 1)], tmp_path):
                if (not wall(shown, posture_line) or 'posture: records = ' in posture_line
                        or shown.startswith(RECORDS_FLOOR) or listed(OWNED + EXEMPT, rel, shown)):
                    continue
                walls.append(f'{posture} {rel}:{line} {module}.{name}: {shown} | {posture_line}')
    assert not walls, '\n'.join(sorted(set(walls)))
