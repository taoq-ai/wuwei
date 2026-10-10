"""#362: every reason string names a next step, in the voice of its reader."""

import ast
import functools
from pathlib import Path
import re

from wuwei import exits


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'cli/wuwei'
# A command (case-sensitive, so prose "WUWEI <word>" is not one) or a verb in imperative
# position: at the start, after ';', ':', ',' or '(', or after 'then', 'or', 'and' or 'so'.
NEXT_STEP = re.compile(
    r'(?-i:\bwuwei (?:[a-z][\w-]*\b|\{\}))(?!:)|/wuwei:wuwei-|\bconfig set\b|'
    r'(?:^|[;:,(]\s*|\b(?:then|or|and|so)\s+)(?:do not\s+)?(?:run|rerun|use|set|add|pass|retry|remove|'
    r'replace|restore|create|write|answer|install|fetch|start|split|ask|wait|configure|read|review|'
    r'stop|have)\b', re.I)
LABEL = re.compile(r'[\w ./{}-]+: ')
PRONOUN = re.compile(r'\b(?:you|your)\b', re.I)
OWNER = re.compile(r'\bthe owner\b', re.I)
# Caught and replaced before anyone reads it (research.md KEEP row).
KEEP = {('workspace.py', 'time component required')}
# Person-facing scope (spec Assumptions): whole modules, or named top-level functions.
PERSON_MODULES = ('commands/doctor.py', 'commands/setup.py', 'commands/nudges.py')
PERSON_PARTS = {'commands/next.py': {'step'},
                'control_plane.py': {'HELP', 'render', 'escalate', 'notify'}}


def _text(node):
    """[(text, family)] for a reason literal, [] for anything else (a variable, str(exc))."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [(node.value, False)]
    if isinstance(node, ast.JoinedStr):
        parts, family = [], False
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(value.value)
            else:
                inner = value.value
                name = inner.id if isinstance(inner, ast.Name) else getattr(inner, 'attr', None)
                family = family or name in exits.FAMILIES
                parts.append('{}')
        return [(''.join(parts), family)]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _text(node.left), _text(node.right)
        if isinstance(node.right, (ast.Name, ast.Attribute)):
            name = getattr(node.right, 'id', None) or node.right.attr
            right = [('{}', name in exits.FAMILIES)]
        if not left or not right:
            return left or right
        return [(a + b, fa or fb) for a, fa in left for b, fb in right]
    if isinstance(node, ast.IfExp):
        return _text(node.body) + _text(node.orelse)
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):  # x or 'fallback' (#456)
        return [] if _passthrough(node.values[-1]) else _text(node.values[-1])
    return []


def _passthrough(node):
    """f'{exc}' or f'label: {exc}': the wrapped reason is checked where it is made."""
    if not isinstance(node, ast.JoinedStr) or not isinstance(node.values[-1], ast.FormattedValue):
        return False
    head = ''.join(v.value if isinstance(v, ast.Constant) else '{}' for v in node.values[:-1])
    return head == '' or LABEL.fullmatch(head) is not None


def _code(node):
    return (isinstance(node, ast.Constant) and type(node.value) is int and node.value in (1, 2)
            or isinstance(node, ast.Name) and node.id in ('FINDINGS', 'UNRUN'))


def reasons(source, name='module.py'):
    """[(line, text, family)] for every reason site in source."""
    found = []

    def add(node):
        if node is None or _passthrough(node):
            return
        for text, family in _text(node):
            if ' ' in text.strip():  # One word is a token such as outward's 'draft' tier.
                found.append((node.lineno, text, family))

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and node.exc.args
                and getattr(node.exc.func, 'id', '') != 'AttributeError'):  # module __getattr__
            add(node.exc.args[0])
        elif isinstance(node, ast.Call):
            func = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, 'attr', '')
            if (func == 'print' and node.args and any(
                    k.arg == 'file' and ast.unparse(k.value) == 'sys.stderr' for k in node.keywords)):
                add(node.args[0])
            elif func == 'Result' and node.args and _code(node.args[0]):
                add(node.args[2] if len(node.args) > 2 else next(
                    (k.value for k in node.keywords if k.arg == 'reason'), None))
        elif (isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple)
              and len(node.value.elts) == 2 and _code(node.value.elts[0])):
            add(node.value.elts[1])
        elif (isinstance(node, ast.Assign) and name.endswith('protect_state.py')
              and any(getattr(t, 'id', '') == '_OWNER_ACTIONS' for t in node.targets)):
            for value in node.value.values:
                add(value)
    return found


def _sources():
    for path in sorted(CLI.rglob('*.py')):
        yield path.relative_to(CLI).as_posix(), path.read_text()


def _person_ranges(rel, tree):
    """Line ranges of the person-facing scope in one module."""
    if rel in PERSON_MODULES:
        return [(1, 10 ** 9)]
    names = PERSON_PARTS.get(rel, ())
    ranges = [(n.lineno, n.end_lineno) for n in tree.body
              if getattr(n, 'name', None) in names
              or isinstance(n, ast.Assign) and any(getattr(t, 'id', '') in names for t in n.targets)]
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and getattr(node.func, 'attr', getattr(node.func, 'id', None)) == 'widget'
                and node.args):
            ranges.append((node.args[0].lineno, node.args[0].end_lineno))
            if len(node.args) > 2:
                ranges.append((node.args[2].lineno, node.args[2].end_lineno))
    return ranges


def _docstrings(tree):
    return {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))
            and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}


def person_facing():
    """[(where, text)] for every non-docstring string constant in the person-facing scope."""
    found = []
    for rel, source in _sources():
        tree = ast.parse(source)
        ranges = _person_ranges(rel, tree)
        if not ranges:
            continue
        skip = _docstrings(tree)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip
                    and any(a <= node.lineno <= b for a, b in ranges)):
                found.append((f'{rel}:{node.lineno}', node.value))
    return found


@functools.cache
def all_reasons():
    """Every reason as (rel, line, text, family, seat); read once per run (#685)."""
    found = []
    for rel, source in _sources():
        tree = ast.parse(source)
        ranges = _person_ranges(rel, tree)
        for line, text, family in reasons(source, rel):
            seat = not any(a <= line <= b for a, b in ranges)
            found.append((rel, line, text, family, seat))
    return tuple(found)


def test_collector_finds_a_new_bare_wall():
    assert [text for _, text, _ in reasons("raise ValueError('invalid thing')")] == ['invalid thing']
    assert all(family for *_, family in reasons(
        "from wuwei.exits import DAMAGED\nraise ValueError(f'invalid thing; {DAMAGED}')"))
    assert reasons("import sys\nprint(f'wuwei x: {exc}', file=sys.stderr)") == []
    # Incidental verbs and prose WUWEI are not a next step (F1).
    for text in ('state file must not use symlinks', 'invalid recorded gate set', 'WUWEI record is broken',
                 'guard could not run'):
        assert not NEXT_STEP.search(text), text
    assert NEXT_STEP.search('state file is a symlink; run bin/wuwei doctor')


def test_collector_finds_an_or_fallback_wall():
    def texts(source):
        return [text for _, text, _ in reasons(source)]
    assert texts("raise ValueError(result.reason or 'branch protection unmeasured')") == [
        'branch protection unmeasured']
    assert texts("import sys\nprint(result.reason or f'{name}: unreadable scopes', file=sys.stderr)") == [
        '{}: unreadable scopes']
    assert texts("Result(2, None, a or b or 'poll failed now')") == ['poll failed now']
    assert reasons("raise ValueError(result.reason or f'{exc}')") == []
    assert reasons("raise ValueError(result.reason or f'build: {exc}')") == []


def test_record_id_hint_matches_its_prefix(tmp_path):
    from wuwei.decision import today_path
    for prefix, clarification in (('D', False), ('C', True)):
        with pytest.raises(ValueError, match=f'such as {prefix}-1$'):
            today_path('../x', tmp_path, clarification=clarification)


def test_family_texts_name_a_next_step_without_a_pronoun():
    for name in exits.FAMILIES:
        text = getattr(exits, name)
        assert NEXT_STEP.search(text) and not PRONOUN.search(text), name


def test_every_reason_names_a_next_step():
    walls = [f'{rel}:{line}: {text}' for rel, line, text, family, _ in all_reasons()
             if not family and not NEXT_STEP.search(text) and (Path(rel).name, text) not in KEEP]
    assert not walls, f'{len(walls)} walls:\n' + '\n'.join(walls)


def test_seat_facing_reasons_have_no_pronoun():
    found = [f'{rel}:{line}: {text}' for rel, line, text, _, seat in all_reasons()
             if seat and PRONOUN.search(text)]
    assert not found, '\n'.join(found)


def test_person_facing_text_never_says_the_owner():
    found = [f'{where}: {text}' for where, text in person_facing() if OWNER.search(text)]
    assert not found, '\n'.join(found)


def test_keep_rows_unchanged():
    for name, text in KEEP:
        assert any(text in found for _, found, _ in reasons((CLI / name).read_text()))


# Spec US4: commands run before a plan answer with the state and the next command.

import pytest  # noqa: E402

from wuwei.__main__ import main  # noqa: E402


@pytest.fixture
def fresh(tmp_path, monkeypatch):
    from wuwei.commands import init
    for name in ('WUWEI_WORKSPACE', 'CDPATH'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('WUWEI_NOW', '2026-10-03T09:00:00+00:00')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init, '_register_mcp', lambda root: 0)
    from fakes.integrity import measured
    measured(monkeypatch)
    assert main(['init', str(tmp_path)]) == 0
    return tmp_path


def run(capsys, *args):
    capsys.readouterr()
    code = main(list(args))
    out = capsys.readouterr()
    return code, out.out + out.err


def test_before_plan_close(fresh, capsys):
    assert run(capsys, 'close') == (
        0, 'Nothing to close today: no day has started. Start one with /wuwei:wuwei-plan.\n')
    assert not (fresh / '.wuwei/days').exists() or not list((fresh / '.wuwei/days').rglob('*.json*'))


def test_before_plan_report(fresh, capsys):
    assert run(capsys, 'report') == (
        0, 'No report today: no day has started. Start one with /wuwei:wuwei-plan.\n')


def test_before_plan_decision_show(fresh, capsys):
    code, text = run(capsys, 'decision', 'show', 'D-1')
    assert (code, text) == (0, 'No D-1 today; bin/wuwei nudges --all lists open decisions.\n')
    assert 'Errno' not in text and str(fresh) not in text


def test_before_plan_goals(fresh, capsys):
    code, text = run(capsys, 'goals')
    assert (code, text) == (0, 'No goals yet: run /wuwei:wuwei-plan and approve the proposed goals, '
                               'or bin/wuwei goals edit.\n')
    (fresh / '.wuwei/memory/goals.md').write_text(
        '# Goals\n## G-1\noutcome: Ship\nmeasure: shipped\ntarget: 1\ndate: 2026-10-30\npriority: 1\n'
        '## G-2\noutcome: Learn\nmeasure: notes\ntarget: 3\ndate: 2026-11-30\npriority: 2\n')
    code, text = run(capsys, 'goals')
    assert code == 0 and text.splitlines() == [
        'G-1 (priority 1): Ship; measure: shipped; target: 1 by 2026-10-30',
        'G-2 (priority 2): Learn; measure: notes; target: 3 by 2026-11-30']
    with pytest.raises(SystemExit) as exc:
        main(['goals', 'edit', '--help'])
    assert exc.value.code == 0


def test_before_plan_template(fresh, capsys):
    assert run(capsys, 'plan', 'template')[0] == 0


def test_before_plan_build_check(fresh, capsys):
    code, text = run(capsys, 'build', 'check', 'DIV-1')
    assert code == 2 and 'DIV-1' in text and 'bin/wuwei build next DIV-1' in text
    assert 'not waiting for checks' in text


def test_before_plan_build_check_names_the_status(fresh, monkeypatch):
    from wuwei import state
    from wuwei.commands import build
    state._write_state(lambda data: data.setdefault('builds', {}).update(
        {'DIV-1': {'status': 'ready'}}), fresh, reserved=False)
    with pytest.raises(ValueError, match=r'DIV-1 is not waiting for checks \(build ready\)'):
        build.check('DIV-1', root=fresh)


def test_before_plan_dispatch_next(fresh, capsys):
    from wuwei import dispatch, state
    code, text = run(capsys, 'dispatch', 'next', 'DIV-1')
    assert code == 1 and '/wuwei:wuwei-plan' in text and 'DIV-1' in text
    state._write_state(lambda data: data.update(
        gate_approved=True, approved_items=['DIV-1'],
        items={'DIV-1': {'phase': 'implement', 'status': 'running'}}), fresh, reserved=False)
    with pytest.raises(dispatch.Refused, match='implement') as exc:
        dispatch.next_step('DIV-1', fresh)
    assert 'bin/wuwei build next DIV-1' in str(exc.value)


def test_before_plan_approve(fresh, capsys):
    code, text = run(capsys, 'plan', 'approve', '--items', 'DIV-1', '--goals-confirmed')
    assert code == 1 and '/wuwei:wuwei-plan' in text


def test_bool_tuple_is_not_an_exit_reason():
    assert reasons("def f():\n    return True, 'a b'\n") == []
