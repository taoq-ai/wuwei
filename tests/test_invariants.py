"""#530: the safety invariants of design 9.2, checked on the reason corpus and on every case
of the product posture x audience x topic x kind x grant x umbrella x connector mode."""

import ast
import contextlib
import functools
from importlib import import_module
import io
import itertools
import re
import time

import pytest

from test_commit_push import item_case, workspace_case  # noqa: F401 (fixtures)
from test_posture import fixed
from test_reasons import CLI, ROOT, reasons

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
          ('integrity.py', ('measure',), ('integrity.check',))]
# Walls a later item of #530 removes (design 9.2, I1 notes): (file, substring, issue).
OWNED = [('guards/pr.py', 'merge policy', '#524'), ('guards/pr.py', 'admin merge', '#524'),
         ('guards/pr.py', 'PR approval', '#524'), ('guards/pr.py', 'branch protection', '#524'),
         ('guards/pr.py', 'a shepherd seat never merges', '#524'),
         ('guards/commit_push.py', 'config add-repo', '#529'),
         ('guards/commit_push.py', 'default_branch', '#529'),
         ('guards/commit_push.py', 'empty configured fast check', '#529'),
         ('guards/pr.py', 'API repository default branch is unmeasured', '#529'),
         ('integrity.py', 'page: plugin integrity', '#529')]
# Refusals that are not walls the workflow puts up (design 9.2, I1 notes).
EXEMPT = [('grants.py', '{} {}; ask the owner to run it in a host terminal', 'heartbeat probe'),
          ('grants.py', 'permissions deny it', 'permissions.deny, deferred'),
          ('grants.py', 'kept it owner-only', "the owner's own Keep answer"),
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


DIMENSIONS = {
    'posture': ('observe', 'guarded', 'strict'),
    'audience': ('owner', 'team', 'company', 'client', 'public'),
    'topic': ('none', 'sensitive', 'commitment', 'disagreement', 'thread'),
    'kind': ('chat', 'tracker', 'docs', 'other'),
    'grant': ('none', 'asked', 'keep', 'once', 'today', 'always'),
    'umbrella': ('send', 'ask'),
    'mode': ('adapter', 'unlisted', 'send', 'draft', 'refuse'),
}
CHANNEL = {'owner': 'D0OWNER', 'team': 'C0TEAM', 'company': 'C0CO', 'client': 'C0CLIENT',
           'public': 'C0PUB'}
TEXT = {'none': 'Tests passed.', 'sensitive': 'Tests passed for the salary review.',
        'commitment': 'We will ship it tomorrow.', 'disagreement': 'I disagree with this.',
        'thread': 'Tests passed.'}
OUTBOUND = """[owner]
name = "Pat Example"
[outbound]
default_tier = "{umbrella}"
channel_classes = {{C0TEAM = "team", C0CO = "company", C0CLIENT = "client", C0PUB = "public"}}
[outbound.owner]
slack = {{user = "U0OWNER", dm = "D0OWNER"}}
[outbound.people]
"slack:p-team" = {{class = "team"}}
"slack:p-company" = {{class = "company"}}
"slack:p-client" = {{class = "client"}}
"slack:p-public" = {{class = "public"}}
[docs]
auto = ["report"]
"""
DEPLOY = 'gh workflow run deploy-production.yml -R example/project'
STANDING = ('[grants]\nstanding = [{action = "deploy", target = "repo:example/project", '
            'scope = "always", decision = "D-9", date = "2026-09-28"}]\n')
RELEASE = STANDING.replace('"deploy"', '"release"')
OPAQUE = ('bash loop.sh', 'gh pr view $(git rev-parse --abbrev-ref HEAD)',
          '''python3 -c "import subprocess; print(subprocess.run(['gh','pr','view','7']).stdout)"''')


class Rules:
    """The real rules, each called once per projection of a case (the dimensions it reads)."""

    def __init__(self, root, tree, base, fake):
        self.root, self.tree, self.base, self.fake, self.cache = root, tree, base, fake, {}

    def memo(self, key, compute):
        if key not in self.cache:
            self.cache[key] = compute()
        return self.cache[key]

    def configure(self, posture, extra=''):
        (self.root / '.wuwei/config.toml').write_text(
            self.base + f'[security]\nposture = "{posture}"\n' + extra)

    def config(self, posture, umbrella, mode):
        from wuwei import workspace
        modes = f'[outward.modes]\nfixture = "{mode}"\n' if mode in ('send', 'draft', 'refuse') else ''
        return self.memo(('config', posture, umbrella, mode), lambda: workspace.load_config(
            self.root, raw=self.base + f'[security]\nposture = "{posture}"\n'
            + OUTBOUND.format(umbrella=umbrella) + modes))

    def outward(self, posture, audience, topic, kind, umbrella, mode, docs='page', category=None):
        """(exit, send|draft|block) of outward.classify, which runs outward.decide."""
        def compute():
            from wuwei import outward
            text, context = TEXT[topic], {}
            if kind == 'chat':
                context['channel'] = CHANNEL[audience]
                if topic == 'thread':
                    context['thread_ts'] = '1.2'
            elif audience != 'owner':  # no owner identity and no thread outside chat
                text += f' @p-{audience}'
            if kind == 'docs':
                context['kind'] = docs
            if category:
                context['category'] = category
            tool = {'adapter': None, 'unlisted': 'mcp__other__post_message'}.get(
                mode, 'mcp__fixture__post_message')
            return outward.classify(text, self.root, self.config(posture, umbrella, mode), context,
                                    kind=kind, port=mode == 'adapter', why=[], tool=tool)
        return self.memo(('outward', posture, audience, topic, kind, umbrella, mode, docs, category),
                         compute)

    def grant(self, posture, grant):
        """The deploy guard (grants.gate) on a seeded grant state: (exit, reason, rows before,
        rows after, standing before, standing after)."""
        def compute():
            from test_grants import run
            from wuwei import state, workspace
            self.configure(posture, '[deploy]\nworkflows = ["deploy-production.yml"]\n'
                           + (STANDING if grant == 'always' else ''))
            rows = {} if grant in ('none', 'always') else {'D-1': {
                'action': 'deploy', 'target': 'repo:example/project', 'rule': 'deploy.workflows',
                'command': DEPLOY, 'item': None, 'seat': 'wuwei:builder', 'planned': False,
                'answered': None if grant == 'asked' else grant, 'spent': False}}
            state._write_state(lambda data: data.__setitem__('grants', rows), self.root, reserved=False)
            standing = workspace.load_config(self.root)['grants']['standing']
            code, reason = run(self.root, DEPLOY)
            return (code, reason, rows, state.read_state(self.root).get('grants', {}), standing,
                    workspace.load_config(self.root)['grants']['standing'])
        return self.memo(('grant', posture, grant), compute)

    def record(self, posture, grant):
        """decision.record_gate on the planner's card question (when one was asked), then
        protect_state on bin/wuwei decide D-1 once from the planner and from a seat."""
        def compute():
            from wuwei import state
            from wuwei.guards.decision import record_gate
            from wuwei.guards.protect_state import check_bash
            self.configure(posture)
            state._write_state(lambda data: data['sessions']['planner-1'].__setitem__('gate_asked', []),
                               self.root, reserved=False)
            before = state.read_state(self.root).get('grants', {})
            if grant != 'none':
                record_gate({'cwd': str(self.root), 'session_id': 'planner-1',
                             'tool_name': 'AskUserQuestion', 'tool_input': {'questions': [
                                 {'question': 'Allow deploy on example/project? (D-1)', 'header': 'D-1'}]}})
            call = {'cwd': str(self.root), 'session_id': 'planner-1', 'tool_name': 'Bash',
                    'hook_event_name': 'PreToolUse', 'tool_input': {'command': 'bin/wuwei decide D-1 once'}}
            return (check_bash(call)[0], check_bash({**call, 'agent_id': 'seat-1'})[0],
                    before == state.read_state(self.root).get('grants', {}))
        return self.memo(('record', posture, grant), compute)

    def enforced(self, posture, check, payload):
        """The guard's own result levelled by the real hook.posture: [(guard, reason, line, exit)]."""
        from wuwei.commands import hook
        code, reason = check(payload)
        self.configure(posture)
        return hook.posture(payload, [(check, reason, code)], self.root) if code else []

    def merge(self, posture):
        def compute():
            from wuwei.guards import pr
            return [self.enforced(posture, pr.check, self.bash(f'gh pr merge 7 -R example/project {flag}'))
                    for flag in ('--squash', '--admin')]
        return self.memo(('merge', posture), compute)

    def marker(self, posture):
        def compute():
            from wuwei.guards import outward, pr
            mcp = {'cwd': str(self.root), 'session_id': 'seat-1', 'hook_event_name': 'PreToolUse',
                   'tool_name': 'mcp__slack__post_message',
                   'tool_input': {'channel': 'C0TEAM', 'text': 'WUWEI parked DIV-1'}}
            return [self.enforced(posture, outward.check_tier, mcp),
                    self.enforced(posture, pr.check, self.bash(
                        "gh pr comment 7 -R example/project --body 'WUWEI parked DIV-1'"))]
        return self.memo(('marker', posture), compute)

    def bash(self, command, cwd=None, **extra):
        return {'hook_event_name': 'PreToolUse', 'session_id': 'planner-1', 'cwd': str(cwd or self.root),
                'transcript_path': str(self.root / 'transcript.jsonl'), 'tool_name': 'Bash',
                'tool_input': {'command': command}, **extra}

    def hook(self, posture, payload, extra=''):
        """The whole PreToolUse hook in process: its exit."""
        import json
        import sys
        from types import SimpleNamespace
        from wuwei.commands import hook
        self.configure(posture, extra)
        stdin, sys.stdin = sys.stdin, io.StringIO(json.dumps(payload))
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                return hook.run(SimpleNamespace(event='PreToolUse'))
        finally:
            sys.stdin = stdin

    def evidence(self, posture):
        """A branch push and a PR raise with recorded evidence, from the planner and a builder."""
        builder = {'agent_id': 'seat-1', 'agent_type': 'wuwei:builder'}
        return self.memo(('evidence', posture), lambda: [self.hook(posture, payload) for payload in (
            self.bash('git push origin HEAD:refs/heads/div-1', self.tree),
            self.bash('git push origin HEAD:refs/heads/div-1', self.tree, **builder),
            self.bash('gh pr create -R example/project --head div-1 -r alice'),
            self.bash('gh pr create -R example/project --head div-1 -r alice', **builder))])

    def tag(self, posture):
        """A release tag push from the item worktree with a standing release grant, then with
        the release card answered Allow once and no standing grant: their exits."""
        def compute():
            from wuwei import state
            update = self.fake.results['push_context'].data['updates'][0]
            branch, update['destination'] = update['destination'], 'refs/tags/v1'
            push = self.bash('git push origin refs/tags/v1', self.tree)
            once = {'action': 'release', 'target': 'repo:example/project', 'rule': 'tag push',
                    'command': 'git push origin refs/tags/v1', 'item': None, 'seat': 'main session',
                    'planned': False, 'answered': 'once', 'spent': False}
            try:
                standing = self.hook(posture, push, RELEASE)
                state._write_state(lambda data: data.setdefault('grants', {}).__setitem__('D-8', once),
                                   self.root, reserved=False)
                return [standing, self.hook(posture, push)]
            finally:
                update['destination'] = branch
                state._write_state(lambda data: data.get('grants', {}).pop('D-8', None),
                                   self.root, reserved=False)
        return self.memo(('tag', posture), compute)

    def opaque(self, posture):
        return self.memo(('opaque', posture),
                         lambda: [self.hook(posture, self.bash(command)) for command in OPAQUE])

    def card_to_send(self, posture):
        """A held chat message, the planner's Draft card answered Send now, the approval, and the
        same call again: (planner may approve, exit of the same call after approval)."""
        def compute():
            from test_decision import draft_question
            from wuwei.__main__ import main
            from wuwei.guards.decision import record_gate
            from wuwei.guards.outward import check_tier
            from wuwei.guards.protect_state import check_bash
            self.configure(posture, OUTBOUND.format(umbrella='send'))
            call = {'cwd': str(self.root), 'session_id': 'seat-1', 'hook_event_name': 'PreToolUse',
                    'tool_name': 'mcp__slack__post_message',
                    'tool_input': {'channel': 'C0CLIENT', 'text': f'Tests passed under {posture}.'}}
            code, reason = check_tier(call)
            draft = re.search(r'draft-[0-9a-f]{32}', reason)[0]
            record_gate(draft_question(self.root, draft, answer='Send now'))
            approve = f'bin/wuwei drafts approve {draft}'
            planner = check_bash(self.bash(approve))[0] == 0
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                approved = main(['drafts', 'approve', draft])
            return code, planner, approved, check_tier(call)[0]
        return self.memo(('card', posture), compute)


def default_has_no_grant():
    from wuwei import workspace
    return workspace.load_config('.', raw='')['grants']['standing'] == []


def i1(case, rules):
    posture, grant, mode = case[0], case[4], case[6]
    if posture == 'strict':
        return None
    if rules.outward(*project(case))[1] == 'block' and mode != 'refuse':
        return 'classify blocks with no owner-written row'
    code, reason, *_ = rules.grant(posture, grant)
    if code and not CARD.search(reason) and 'kept it owner-only' not in reason:
        return f'the deploy guard refuses with no card: {reason}'
    expected = 0 if grant in ('once', 'today', 'always') else 1
    if code != expected:
        return f'the deploy guard exits {code} for grant {grant}, expected {expected}: {reason}'
    return None


def i2(case, rules):
    code, decision = rules.outward(*project(case))
    if decision == 'draft' and code != 1:
        return f'a held message exits {code}'
    held, planner, approved, again = rules.card_to_send(case[0])
    if (held, approved, again) != (1, 0, 0) or planner != (case[0] != 'strict'):
        return f'card path: held {held}, planner approves {planner}, approve {approved}, same call {again}'
    return None


def i3(case, rules):
    from wuwei.guards import MERGE
    for found in rules.merge(case[0]):
        if not found or not found[0][1].startswith(MERGE):
            return f'gh pr merge is not refused by the merge policy: {found}'
    return None


def i4(case, rules):
    if case[3] == 'chat' and case[1] == 'owner' and rules.outward(*project(case))[1] != 'send':
        return 'a message to the owner DM does not send'
    return None


def i5(case, rules):
    code, reason, before, after, standing, standing_after = rules.grant(case[0], case[4])
    for key, row in after.items():
        old = before.get(key, {'answered': None, 'spent': False})
        if row['answered'] != old['answered'] or row['spent'] != old['spent'] and old['answered'] != 'once':
            return f'grant {key} changed from {old} to {row}'
    if standing != standing_after or not rules.memo('default', default_has_no_grant):
        return 'a standing grant changed or ships by default'
    if not rules.record(case[0], case[4])[2]:
        return 'the record gate changed a grant row'
    return None


def i6(case, rules):
    from wuwei.guards import RECORDS_FLOOR
    for found in rules.marker(case[0]):
        if not found or not found[0][1].startswith(RECORDS_FLOOR):
            return f'an owner disposition marker is not refused: {found}'
    return None


def i7(case, rules):
    posture, audience, topic, kind, _, umbrella, mode = case
    if kind not in ('docs', 'tracker') or audience != 'team' or topic != 'none':
        return None
    if mode == 'adapter':
        auto = ('report', None) if kind == 'docs' else ('page', 'progress')
        outside = ('page', None) if kind == 'docs' else ('page', 'bugs')
        sent = rules.outward(*project(case), *auto)[1]
        held = rules.outward(*project(case), *outside)[1]
        if (sent, held) != ('send', 'draft'):
            return f'adapter write in auto {sent}, outside auto {held}'
    if mode == 'unlisted' and umbrella == 'send' and rules.outward(*project(case))[1] != 'send':
        return 'a connector write under the send umbrella does not send'
    return None


def i8(case, rules):
    planner, seat, _ = rules.record(case[0], case[4])
    expected = case[4] != 'none' and case[0] != 'strict'
    if (planner == 0) != expected or seat == 0:
        return f'decide passes for the planner {planner == 0} (expected {expected}), for a seat {seat == 0}'
    return None


def i9(case, rules):
    if case[0] != 'strict' and any(rules.evidence(case[0])):
        return f'a push or PR raise with recorded evidence is refused: {rules.evidence(case[0])}'
    if case[0] != 'strict' and any(rules.tag(case[0])):
        return f'a tag push with a release grant or an Allow once card is refused: {rules.tag(case[0])}'
    return None


def i10(case, rules):
    if case[0] != 'strict' and any(rules.opaque(case[0])):
        return f'an opaque read is refused: {rules.opaque(case[0])}'
    return None


@functools.cache
def budget_rule():
    """#558: a class runs lower only on a spent error budget: more events than the allowance
    and at least two, never on one event, and no single-trigger lowering left in cruise."""
    from wuwei import budget_classes, cruise
    rule = {'budget_share': 0.1, 'budget_window_days': 14, 'burn_warn': 2.0}
    found = [budget_classes.measure(*counts, rule)[2] for counts in ((20, 3, 0), (20, 2, 2), (20, 0, 0), (5, 1, 0))]
    if found != ['spent', 'warn', 'ok', 'ok']:
        return f'budget states {found}, expected spent, warn, ok, ok'
    left = [name for name in ('lower', 'streak', 'escaped') if hasattr(cruise, name)]
    return f'single-trigger lowering left in cruise: {left}' if left else None


def i11(case, rules):
    return budget_rule()


INVARIANTS = {'I1': i1, 'I2': i2, 'I3': i3, 'I4': i4, 'I5': i5, 'I6': i6, 'I7': i7, 'I8': i8,
              'I9': i9, 'I10': i10, 'I11': i11}


def project(case):
    """The outward projection of a case: (posture, audience, topic, kind, umbrella, mode)."""
    posture, audience, topic, kind, _, umbrella, mode = case
    return posture, audience, topic, kind, umbrella, mode


def walk(world):
    """Every invariant on every case; one line per failure with the full tuple."""
    rules, failures = Rules(*world), []
    for case in itertools.product(*DIMENSIONS.values()):
        for name, invariant in INVARIANTS.items():
            found = invariant(case, rules)
            if found:
                failures.append(' '.join(f'{key}={value}' for key, value in zip(DIMENSIONS, case))
                                + f': {name} {found}')
    return failures


def test_invariants_hold(world):
    cases = list(itertools.product(*DIMENSIONS.values()))
    assert len(cases) >= 2000
    start = time.process_time()  # CPU time: a busy host does not fail the walk
    failures = walk(world)
    elapsed = time.process_time() - start
    assert not failures, '\n'.join(failures[:20])
    # ponytail: one wall-clock sample; a slower host raises it in the latency benchmarks, not here.
    assert elapsed < 1.0, f'{len(cases)} cases took {elapsed:.2f} s'


BROKEN = {
    'team block row': lambda monkeypatch: monkeypatch.setattr(
        import_module('wuwei.outward'), 'DEFAULT_TIERS',
        ({'audience': 'team', 'tier': 'block'}, *import_module('wuwei.outward').DEFAULT_TIERS)),
    'grant for every target': lambda monkeypatch: monkeypatch.setattr(
        import_module('wuwei.grants'), 'active', lambda *args: ('today', 'D-1')),
}


@pytest.mark.parametrize('broken', BROKEN)
def test_broken_rule_is_caught(world, monkeypatch, broken):
    BROKEN[broken](monkeypatch)
    failures = walk(world)
    assert failures and 'posture=' in failures[0] and 'mode=' in failures[0]


@pytest.fixture
def world(item_case, monkeypatch):
    """One workspace for every rule: the item worktree of test_commit_push with its fake ports,
    the PR gate verdicts of test_pr_guards, a registered planner and one deploy card D-1."""
    from test_commit_push import SHA
    from test_pr_guards import evidence
    from wuwei import plan, state, workspace
    from wuwei.registry import Result
    from wuwei import integrity
    monkeypatch.setattr(integrity, '_host_confirm', lambda *args, **kwargs: True)  # the owner at the host
    root, fake, tree = item_case
    (tree / '.git').write_text('gitdir: elsewhere\n')
    (root / 'loop.sh').write_text('gh pr view 7\n')
    fake.results.update(branch=Result(0, {'name': 'div-1'}), resolve=Result(0, {'sha': SHA}))
    base = (root / '.wuwei/config.toml').read_text().replace('path = "repo"', 'path = "worktrees/DIV-1"')
    state._write_state(lambda data: data['items'].update({'DIV-1': {'worktree': 'worktrees/DIV-1'}}),
                       root, reserved=False)
    decisions = workspace.day_dir(root) / 'decisions'
    decisions.mkdir(parents=True, exist_ok=True)
    for gate in ('arch', 'quality', 'security'):
        (decisions / f'gate-DIV-1-{gate}.md').write_text(evidence(SHA))
    (workspace.day_dir(root) / 'plan.md').write_text('# Morning plan\n')
    plan.session('planner-1', root)
    rules = Rules(root, tree, base, fake)
    rules.grant('guarded', 'none')  # writes D-1, the card the record gate cites
    return root, tree, base, fake


def test_table_matches_the_checks():
    design = (ROOT / 'docs/specs/2026-09-24-wuwei-design.md').read_text()
    table = design[design.index('### 9.2 '):design.index('## 10. ')]
    assert re.findall(r'^\| (I\d+) \|', table, re.M) == list(INVARIANTS)
    for path in (ROOT / 'docs/specs/2026-09-24-wuwei-design.md', ROOT / 'docs/site/security.md'):
        assert 'Owner-only actions always block' not in path.read_text(), path
