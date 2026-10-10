"""#530: the safety invariants of design 9.2, checked on the reason corpus and on every case
of the product posture x audience x topic x kind x grant x umbrella x connector mode."""

import ast
import contextlib
import functools
import gc
from importlib import import_module
import io
import itertools
import math
import os
import re
import time

import pytest

from test_card_confirms import answer
from test_commit_push import item_case, workspace_case  # noqa: F401 (fixtures)
from test_decision import CHECKS_RECORD, draft_question
from test_decision_classes import record
from test_grants import run
from test_merge import case  # noqa: F401 (fixture)
from test_posture import fixed
from test_reasons import CLI, ROOT, reasons
from test_workspace import publishes
from wuwei.__main__ import main

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
# Walls a later item removes (design 9.2, I1 notes): (file, substring, note).
LATER = 'follow-up, specs/530-posture-day Deferred'
OWNED = [('guards/commit_push.py', 'config add-repo', LATER),
         ('guards/commit_push.py', 'default_branch', LATER),
         ('guards/commit_push.py', 'empty configured fast check', LATER),
         ('guards/pr.py', 'API repository default branch is unmeasured', LATER),
         ('integrity.py', 'page: plugin integrity', LATER)]
# Refusals that are not walls the workflow puts up (design 9.2, I1 notes).
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


DIMENSIONS = {
    'posture': ('observe', 'guarded', 'strict'),
    'audience': ('owner', 'team', 'company', 'client', 'public'),
    'topic': ('none', 'sensitive', 'commitment', 'disagreement', 'thread'),
    'kind': ('chat', 'tracker', 'docs', 'other'),
    'grant': ('none', 'asked', 'keep', 'once', 'today', 'always'),
    'umbrella': ('send', 'ask'),
    'mode': ('adapter', 'unlisted', 'send', 'draft', 'refuse'),
}
CASES = math.prod(len(values) for values in DIMENSIONS.values())
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
        path, text = self.root / '.wuwei/config.toml', self.base + f'[security]\nposture = "{posture}"\n' + extra
        if path.read_text() != text:  # the same text again is no change for the hook to load
            path.write_text(text)

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
        protect_state on bin/wuwei decide D-1 once and config set cap 2 --from-card D-1 (#529)
        from the planner and from a seat."""
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
            found = []
            for command in ('bin/wuwei decide D-1 once', 'bin/wuwei config set cap 2 --from-card D-1'):
                call = {'cwd': str(self.root), 'session_id': 'planner-1', 'tool_name': 'Bash',
                        'hook_event_name': 'PreToolUse', 'tool_input': {'command': command}}
                found.append((check_bash(call)[0], check_bash({**call, 'agent_id': 'seat-1'})[0]))
            return found, before == state.read_state(self.root).get('grants', {})
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
    config = workspace.load_config('.', raw='')
    return config['grants']['standing'] == [] and config['merge']['default_tier'] == ''  # #530


def i1_outward(case, rules):
    if case[0] != 'strict' and rules.outward(*project(case))[1] == 'block' and case[6] != 'refuse':
        return 'classify blocks with no owner-written row'
    return None


def i1_grant(case, rules):
    posture, grant = case[0], case[4]
    if posture == 'strict':
        return None
    code, reason, *_ = rules.grant(posture, grant)
    if code and not CARD.search(reason) and 'kept it owner-only' not in reason:
        return f'the deploy guard refuses with no card: {reason}'
    expected = 0 if grant in ('once', 'today', 'always') else 1
    if code != expected:
        return f'the deploy guard exits {code} for grant {grant}, expected {expected}: {reason}'
    return None


def i1(case, rules):
    return i1_outward(case, rules) or i1_grant(case, rules)


def i2(case, rules):
    code, decision = rules.outward(*project(case))
    if decision == 'draft' and code != 1:
        return f'a held message exits {code}'
    held, planner, approved, again = rules.card_to_send(case[0])
    if (held, approved, again) != (1, 0, 0) or planner != (case[0] != 'strict'):
        return f'card path: held {held}, planner approves {planner}, approve {approved}, same call {again}'
    return None


def i3(case, rules):
    """#524: a session merge is refused in every posture and names bin/wuwei merge, the one
    journaled path; test_merge_only_at_the_gated_green_head checks what that path merges."""
    from wuwei.guards import MERGE
    squash, admin = rules.merge(case[0])
    for found in (squash, admin):
        if not found or not found[0][1].startswith(MERGE):
            return f'gh pr merge is not refused by the merge policy: {found}'
    if 'bin/wuwei merge' not in squash[0][1]:
        return f'a session merge does not name bin/wuwei merge: {squash[0][1]}'
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
    if not rules.record(case[0], case[4])[1]:
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
    expected = case[4] != 'none' and case[0] != 'strict'
    for name, (planner, seat) in zip(('decide', 'config set'), rules.record(case[0], case[4])[0]):
        if (planner == 0) != expected or seat == 0:
            return f'{name} passes for the planner {planner == 0} (expected {expected}), for a seat {seat == 0}'
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


@functools.cache
def calibration_rule():
    """#559: the Brier states, an uncalibrated class runs at most L1 (too few is not capped), and
    an uncalibrated role only moves a record toward the owner."""
    from wuwei import calibration_scores, cruise, decision
    rule = {'calibration_threshold': 0.15, 'calibration_min': 10}
    found = [calibration_scores.measure(pairs, rule)[1] for pairs in (
        [(0.9, 1)] * 7 + [(0.9, 0)] * 5, [(0.9, 1)] * 10, [(0.9, 1)] * 9)]
    if found != ['uncalibrated', 'calibrated', 'too few']:
        return f'calibration states {found}, expected uncalibrated, calibrated, too few'
    config = {'autonomy': {'mode': 'autonomous'}, 'decisions': {'cruise': {'enabled': True, 'levels': {}}}}
    levels = [cruise.level(config, 'defer', {'levels': {'defer': 3}, 'calibration': calibration})
              for calibration in ({'classes': ['defer'], 'roles': []}, {})]
    if levels != [1, 3]:
        return f'levels {levels} for an uncalibrated and a too-few class, expected 1 and 3'
    routine = {'Class': 'retry', 'Reversibility': 'two-way'}
    consequential = {'Class': 'design', 'Reversibility': 'one-way', 'Blast radius': 'outside', 'Confidence': 'high'}
    moved = [decision.cisr(fields, {}, ambiguous=True) for fields in (routine, consequential)]
    return None if moved == ['Exploratory', 'Strategic'] else f'an uncalibrated role routes as {moved}'


def i12(case, rules):
    return calibration_rule()


@functools.cache
def shadow_rule():
    """#560: a stored shadow never changes the level a class routes at, for any class, shadow
    level and state, cruise on or off, autonomous or supervised."""
    from wuwei import cruise
    for mode, enabled in (('autonomous', True), ('autonomous', False), ('supervised', True)):
        config = {'autonomy': {'mode': mode}, 'decisions': {'cruise': {'enabled': enabled, 'levels': {}}}}
        for name in cruise.CLASSES:
            for level, state in itertools.product((1, 2, 3), cruise.SHADOW):
                run = {'levels': {}, 'changed': {}, 'shadow': {name: {'level': level, 'state': state}}}
                if cruise.level(config, name, run) != cruise.level(config, name, {'levels': {}, 'changed': {}}):
                    return f'a {state} shadow at L{level} moves {name} under {mode}'
    return None


def i13(case, rules):
    return shadow_rule()


def i14(case, rules):
    """#560: a raise card answered raise lands nothing without a passed shadow."""
    def compute():
        from wuwei import cruise, decision, state
        card = {'kind': 'raise', 'class': 'defer', 'level': 1}
        before = decision.running(rules.root)['levels']
        state._write_state(lambda data: data.setdefault('cruise_cards', {}).__setitem__('D-99', card),
                           rules.root, reserved=False)
        cruise.answered(rules.root, 'D-99', 'raise')
        state._write_state(lambda data: data['cruise_cards'].pop('D-99'), rules.root, reserved=False)
        after = decision.running(rules.root)['levels']
        return None if after == before else f'a raise card without a passed shadow landed {after}'
    return rules.memo(('raise card',), compute)


@functools.cache
def pace_rule():
    """#579: no pace lowers a floor: a tier never drops, depth is light only for a light tier or
    fast on a measured, unflagged standard item without guard code, and no pace plans more seats
    than the host fits."""
    from wuwei import dispatch, pace
    # #567: an untiered item runs standard, and a gate reader never takes the builder's prediction.
    if (dispatch.depth({}), dispatch.depth({'depth': 'light'}, gate=True)) != ('standard', 'standard'):
        return 'an untiered item runs below standard'
    for case in itertools.product(pace.PACES, dispatch.TIERS, (None, 'x matches guards/*'), (False, True), (False, True)):
        tier, depth, _ = pace.adjust(*case)
        if dispatch.TIERS.index(tier) < dispatch.TIERS.index(case[1]):
            return f'pace {case[0]} lowers {case[1]} to {tier}'
        if depth == 'light' and tier != 'light' and case != ('fast', 'standard', None, False, True):
            return f'pace {case[0]} runs {case} at light depth'
    for value, load in itertools.product(pace.PACES, (None, 1.0, 34.0)):
        cap = pace.seats(value, {'cap': 4, 'seats': 4, 'bound': 'host', 'cores': 10, 'load': load})[0]
        if cap > 4:
            return f'pace {value} plans {cap} seats on a host that fits 4'
    return None


def i15(case, rules):
    return pace_rule()


def i16(case, rules):
    """#579: no pace changes who decides: the cruise levels and the decision route are the same
    at every pace, and only the planner sets the pace below strict, never a seat."""
    def routes():
        from wuwei import cruise, decision, pace, state, workspace
        config = workspace.load_config(rules.root)
        fields = [{'Reversibility': 'two-way', 'Blast radius': 'own branch'},
                  {'Reversibility': 'one-way', 'Blast radius': 'outside'}]
        seen = set()
        for value in pace.PACES:
            state._write_state(lambda data: data.__setitem__('pace', value), rules.root, reserved=False)
            run = cruise.running(rules.root)
            seen.add((tuple(cruise.level(config, name, run) for name in cruise.CLASSES),
                      tuple(map(decision.route, fields))))
        state._write_state(lambda data: data.pop('pace'), rules.root, reserved=False)
        return None if len(seen) == 1 else f'the pace moves a level or a route: {seen}'

    def setter():
        from wuwei.guards.protect_state import check_bash
        rules.configure(case[0])
        call = rules.bash('bin/wuwei plan set pace=fast')
        return check_bash(call)[0], check_bash({**call, 'agent_id': 'seat-1'})[0]
    found = rules.memo(('pace routes',), routes)
    planner, seat = rules.memo(('pace set', case[0]), setter)
    if (planner == 0) != (case[0] != 'strict') or seat == 0:
        return found or f'plan set pace=fast passes for the planner {planner == 0}, for a seat {seat == 0}'
    return found


@functools.cache
def green_rule():
    """#579: fast merges only at green required checks: the merge policy and the launch guard
    never read the pace, and a pending required check is never green."""
    from wuwei import merge
    for rel in ('merge.py', 'guards/pr.py', 'guards/agent_launch.py'):
        if re.search(r'\bpace\.|import pace|[\'"]pace[\'"]', (CLI / rel).read_text()):
            return f'{rel} reads the pace'
    try:
        merge.green([{'name': 'ci', 'state': 'in_progress', 'conclusion': None}],
                    {'required_checks': [{'name': 'ci', 'app_id': None}]})
    except ValueError:
        return None
    return 'a pending required check is green'


def i17(case, rules):
    return green_rule()


def i18(case, rules):
    """#530: the setup answers never allow a publish target: merge.default_tier = "today" covers
    only a merge on a configured repository below strict, and no allowlist rule matches a deploy,
    release, protected-branch push or force push."""
    def compute(posture):
        from wuwei import grants, workspace
        from wuwei.commands import init
        config = workspace.load_config(rules.root, raw=rules.base + f'[security]\nposture = "{posture}"\n'
                                       '[merge]\ndefault_tier = "today"\n')
        own = config['repos'][0]['name']
        for name in grants.ACTIONS:
            for target in (f'repo:{own}', f'pr:{own}#7', 'repo:other/elsewhere'):
                expected = ('today', grants.DEFAULT) if (
                    name == 'merge' and 'elsewhere' not in target and posture != 'strict') else None
                if grants.active(config, {}, name, target) != expected:
                    return f'merge.default_tier covers {name} on {target}'
        found = publishes(init.allow_rules(config, 'bin/wuwei'))
        return f'an allowlist rule allows a publish target: {found}' if found else None
    return rules.memo(('setup answers', case[0]), lambda: compute(case[0]))


def i19(case, rules):
    """#526: a thread reply follows its recorded participants: a team participant sends under
    both umbrellas, a client or public one is held as a draft, never blocked, below strict."""
    posture, audience, umbrella = case[0], case[1], case[5]
    if posture == 'strict' or audience not in ('team', 'client', 'public'):
        return None

    def compute():
        """The reply under every posture below strict and every umbrella, with one recorded
        participant seeded once for them all."""
        from wuwei import outward, state
        key = 'C0TEAM/1.2'
        state._write_state(lambda data: data.setdefault('outbound_threads', {}).__setitem__(
            key, [f'p-{audience}']), rules.root, reserved=False)
        try:
            return {(p, u): outward.classify('Tests passed.', rules.root, rules.config(p, u, 'adapter'),
                                             {'channel': 'C0TEAM', 'thread_ts': '1.2'}, kind='chat', port=True, why=[])
                    for p in DIMENSIONS['posture'] if p != 'strict' for u in DIMENSIONS['umbrella']}
        finally:
            state._write_state(lambda data: data['outbound_threads'].pop(key), rules.root, reserved=False)
    code, decision = rules.memo(('thread', audience), compute)[posture, umbrella]
    expected = 'send' if audience == 'team' else 'draft'
    if decision != expected or (decision == 'draft') != (code == 1):
        return f'a reply to a {audience} thread participant is {decision} (exit {code}), expected {expected}'
    return None


PROCESS = {'builder': {'runtime': 'codex', 'model': 'm'}}  # #658: seats as processes


def i20(case, rules):
    """#528, #658: CAP comes from the host: the owner's cap when set, else, for seats that are
    separate processes, the seats that fit above the memory floor, one per core, at least one,
    and for Claude subagent seats one per core whatever the free memory; a token budget never
    raises it."""
    def compute():
        from wuwei import calibrate, workspace

        @functools.cache  # calibrate.host only reads the config; parse each of the four once
        def config(cap, budget):
            return workspace.load_config(rules.root, raw=f'cap = {cap}\n' + rules.base + (
                f'[budget]\ntokens_per_day = {budget}\n' if budget else ''))
        floor, seat = config(0, 0)['host']['free_memory_mb'], calibrate.host(rules.root, config(0, 0), free=0, policy=PROCESS)['seat_mib']
        # os.cpu_count set by hand: unittest.mock would import asyncio inside the timed walk.
        real = os.cpu_count
        try:
            for (seats, free), cores, cap, budget in itertools.product(
                    ((1, floor - 1), (1, floor + seat), (8, floor + 8 * seat)), (1, 4), (0, 3), (0, 10**6)):
                os.cpu_count = lambda cores=cores: cores
                for policy, expected in ((PROCESS, cap or min(seats, cores)), ({}, cap or cores)):
                    found = calibrate.host(rules.root, config(cap, budget), free=free, policy=policy)['cap']
                    # Without a budget the plain call is the same call.
                    plain = (calibrate.host(rules.root, config(cap, 0), free=free, policy=policy)['cap']
                             if budget else found)
                    if found != expected or found > plain:
                        return (f'cap {found} (without the budget {plain}) for free {free}, {cores} cores, '
                                f'cap {cap}, budget {budget}, policy {policy}')
        finally:
            os.cpu_count = real
        return None
    return rules.memo(('host cap',), compute)


WORD = ('[outward]\npatterns = ["zz-internal"]\n[[outbound.tiers]]\nchannel = "C0CLIENT"\ntier = "send"\n'
        '[[outbound.tiers]]\nchannel = "C0PUB"\ntier = "send"\n')


def i21(case, rules):
    """#533: an outward.patterns word never refuses or holds a tracker, docs or other write;
    team or company chat is never held and is refused only under strict; a client or public
    chat that an owner row sends is held as a draft naming the word."""
    posture, audience, kind = case[0], case[1], case[3]
    if audience == 'owner':
        return None

    def compute():
        from wuwei import outward, workspace
        config = workspace.load_config(rules.root, raw=rules.base + f'[security]\nposture = "{posture}"\n'
                                       + OUTBOUND.format(umbrella='send') + WORD)
        found = []
        for text in ('Tests passed zz-internal.', 'Tests passed.'):
            why, context = [], {'channel': CHANNEL[audience]} if kind == 'chat' else {}
            if kind != 'chat':
                text += f' @p-{audience}'
            code, decision = outward.classify(text, rules.root, config, context, kind=kind, port=True, why=why)
            with contextlib.redirect_stderr(io.StringIO()):
                lint = outward.check_lint({**context, 'text': text}, rules.root, config, {kind})[0]
            found.append((code, decision, ' '.join(why), lint))
        return found
    (_, decision, why, lint), (_, plain, _, clean) = rules.memo(('word', posture, audience, kind), compute)
    if kind != 'chat' and (decision != plain or lint != clean):
        return f'the word changes a {kind} write: {decision} {lint}, without it {plain} {clean}'
    if kind == 'chat' and audience in ('team', 'company') and (
            decision != plain or lint != (1 if posture == 'strict' else clean)):
        return f'the word in {audience} chat: {decision} {lint}, without it {plain} {clean}'
    # Under strict the owner row itself drafts, so the word is checked below strict.
    if kind == 'chat' and audience in ('client', 'public') and (decision != 'draft' or posture != 'strict' and (
            plain != 'send' or 'zz-internal' not in why)):
        return f'the word to a {audience} reader: {decision} ({why}), without it {plain}'
    return None


def seat_writes(rules, name):
    """protect_state on a seat's Write to .wuwei/<name>: its exit."""
    from wuwei.guards.protect_state import check_file
    return check_file({'hook_event_name': 'PreToolUse', 'session_id': 'planner-1', 'agent_id': 'seat-1',
                       'cwd': str(rules.root), 'tool_name': 'Write',
                       'tool_input': {'file_path': f'.wuwei/{name}', 'content': '{}'}})[0]


def i22(case, rules):
    """#557: a record keeps a two-way door only for a registered undo that ran here; a message
    never does; a seat cannot write the rehearsal ledger."""
    def compute():
        from wuwei import cruise, undo, workspace
        config = workspace.load_config(rules.root, raw=rules.base)
        context = f'repo:{config["repos"][0]["name"]}'
        real = undo.ledger
        try:
            for kinds in ((), tuple(undo.REGISTRY)):
                undo.ledger = lambda root: {kind: {'at': '2026-09-28T12:00:00+00:00', 'by': 'rehearsal'} for kind in kinds}
                for cls in (*cruise.CLASSES, None):
                    kind, reason = undo.measured({'Class': cls, 'Context': context} if cls else {}, rules.root, config)
                    if reason is None and (kind not in undo.REGISTRY or kind not in kinds):
                        return f'{cls} keeps its door with ledger {kinds}'
        finally:
            undo.ledger = real
        return None if seat_writes(rules, undo.NAME) else 'a seat writes the rehearsal ledger'
    return rules.memo(('undo',), compute)


def i23(case, rules):
    """#556: a record naming a target the workspace never touched goes to the owner once and
    names it; a seat cannot write the seen set."""
    def compute():
        from wuwei import novelty, workspace
        rules.configure('guarded', '[autonomy]\nmode = "autonomous"\n')
        (workspace.day_dir(rules.root) / 'decisions/D-60.md').write_text(
            record(cls='retry', radius='item A', wants=(('Context:', 'Context: repo:fixture-org/never-seen'),)))
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            main(['decision', 'route', 'D-60'])
        if not out.getvalue().startswith('owner') or 'repo:fixture-org/never-seen' not in out.getvalue():
            return f'a record naming a new target routes {out.getvalue()!r}'
        return None if seat_writes(rules, novelty.NAME) else 'a seat writes the seen set'
    return rules.memo(('novelty',), compute)


def i24(case, rules):
    """#552: every guard reads the same people, channels and connectors from the register as
    from config.toml: the register's views equal the config's sections."""
    def compute():
        from wuwei import graph
        config = rules.config('guarded', 'send', 'send')
        found = graph.drift(graph.build(config), config)
        return f'the register and config.toml differ on {found}' if found else None
    return rules.memo(('register',), compute)


def i25(case, rules):
    """#605: doctor's identity row and the commit and push guard agree on repos.N.identity: both
    pass a set one, both fail an empty or malformed one with the same reason and fix. The guard
    answers with commit_push.unset_identity on the identity git resolves; its end-to-end path
    stays in tests/test_commit_push.py and tests/test_git_hook.py."""
    def compute():
        from wuwei.commands import doctor
        from wuwei.guards import commit_push
        from wuwei.registry import Result
        found = {'name': 'Builder', 'email': 'builder@example.test'}
        before = rules.fake.results.get('identity')
        rules.fake.results['identity'] = Result(0, found)
        repo = rules.config('guarded', 'send', 'send')['repos'][0]
        try:
            for identity in (found, {'name': '', 'email': ''}, {'name': '<name>', 'email': '<email>'}):
                row = doctor.identity_row({**repo, 'identity': identity}, 0, rules.tree, rules.fake)
                said = None if row['status'] == 'ok' else (row['value'], 'bin/wuwei ' + row['fix'].split(' ', 1)[1])
                guard = commit_push.unset_identity(identity, 0, found)
                if said != guard:
                    return f'identity {identity}: doctor {row}, guard {guard}'
        finally:
            if before is None:
                rules.fake.results.pop('identity', None)
            else:
                rules.fake.results['identity'] = before
        return None
    return rules.memo(('identity',), compute)


def i26(case, rules):
    """#603: every command next returns to start a planned item exits 0 in a multi-repository
    workspace: worktree add names the candidate's --repo, an item with no repository is parked.
    tests/test_dispatch.py runs the park through main; here worktree add runs its command function."""
    def compute():
        import argparse
        import json
        import shlex
        from wuwei import dispatch, workspace
        from wuwei.commands import worktree
        rules.configure('guarded', '[[repos]]\nname = "example/paper"\npath = "paper"\ndefault_branch = "main"\n')
        config = workspace.load_config(rules.root)
        repos = config['repos']
        (workspace.day_dir(rules.root) / 'proposal.json').write_text(json.dumps({'candidates': [
            {'id': 'P-A', 'repo': 'example/paper'}, {'id': 'P-B'}]}))
        if dispatch._start(rules.root, 'P-A', repos[:1])[0] != 'wuwei worktree add P-A':
            return 'one repository changes worktree add'
        if not dispatch._start(rules.root, 'P-B', repos)[0].startswith('wuwei plan park P-B --reason '):
            return 'an item with no repository is not parked'
        add = shlex.split(dispatch._start(rules.root, 'P-A', repos)[0])
        if add[:4] != ['wuwei', 'worktree', 'add', 'P-A'] or len(add) != 6:
            return f'worktree add reads {add}'
        real = workspace.create_worktree
        workspace.create_worktree = lambda repo, *args, **kwargs: {'repo': str(repo)}  # the VCS boundary
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                found = worktree.add(argparse.Namespace(repo=add[5], branch=None), rules.root, config, 'P-A')
        except ValueError as exc:
            return f'{" ".join(add)} refuses: {exc}'
        finally:
            workspace.create_worktree = real
        return None if found['repo'].endswith('paper') else f'{" ".join(add)} picks {found["repo"]}'
    return rules.memo(('start repo',), compute)


def i27(case, rules):
    """#603: a fresh day's gate-confirmed proposed goals approve the plan, and approve never
    writes owner memory."""
    def compute():
        import json
        from wuwei import goals, plan, workspace
        root = rules.root / 'fresh'
        (root / '.wuwei/memory').mkdir(parents=True)
        (root / '.wuwei/config.toml').write_text('')
        memory = (ROOT / 'templates/workspace/memory/goals.md').read_text(encoding='utf-8')
        (root / '.wuwei/memory/goals.md').write_text(memory)
        day = workspace.day_dir(root)
        day.mkdir(parents=True)
        lead = [{'id': f'G-{n}', 'outcome': 'Ship the widget', 'measure': 'widgets shipped', 'target': '1',
                 'date': '2026-10-30', 'priority': n} for n in (1, 2)]
        (day / 'goals.md').write_text(goals.proposed(memory, lead)[0])
        score = {'value': 5, 'time_criticality': 3, 'risk_reduction': 2, 'job_size': 2}
        (day / 'proposal.json').write_text(json.dumps({
            'goals': ['G-1', 'G-2'], 'cap': 2, 'seat_policy': {'builder': {'runtime': 'claude', 'model': 'sonnet'}},
            'envelope': {'start': '09:00', 'end': '17:00', 'net_build_hours': 5},
            'sweep': {'processes': 'measured: none', 'tracker': 'unmeasured: absent'},
            'candidates': [{'id': 'A', 'goal': 'G-1', 'evidence': 'tracker A', 'scope': 'one function',
                            'overlap': 'none', 'track': 'SLICE', 'flags': dict.fromkeys(plan.FLAGS, False),
                            'score': score, 'evidence_lines': dict.fromkeys(score, 'tracker A')}]}))
        (day / 'plan.md').write_text('# Morning plan\n')
        try:
            plan.approve(['A'], root, goals_confirmed=True)
        except (ValueError, OSError) as exc:
            return f'approve refuses the proposed goals: {exc}'
        return None if (root / '.wuwei/memory/goals.md').read_text() == memory else 'approve writes memory'
    return rules.memo(('proposed goals',), compute)


def i28(case, rules):
    """#604: a stored answer never overwrites a present differing key unless config promote
    --keys names it."""
    def compute():
        from wuwei import interview, workspace
        from wuwei.commands import config as command
        rules.configure('guarded', '[autonomy]\nmode = "supervised"\n')
        interview.record(rules.root, workspace.load_config(rules.root), {'autonomy': 'Autonomous'})
        raw = (rules.root / '.wuwei/config.toml').read_text()
        config = workspace.load_config(rules.root)
        text, _, _, summary, _ = command.proposal(rules.root, raw, raw, config, [], keys=())
        if 'mode = "supervised"' not in text or 'Skipped autonomy.mode: kept "supervised"' not in summary:
            return 'promote overwrites a key the owner set'
        text = command.proposal(rules.root, raw, raw, config, [], keys=('autonomy.mode',))[0]
        return None if 'mode = "autonomous"' in text else 'promote --keys autonomy.mode keeps "supervised"'
    return rules.memo(('promote',), compute)


def i31(case, rules):
    """#600: an empty fast-check list never refuses a launch below strict; strict refuses naming
    the fast-checks card until the owner answers it."""
    def compute(posture):
        from wuwei import workspace
        from wuwei.commands import build
        config = workspace.load_config(rules.root, raw=rules.base.replace(
            'fast_checks = ["unit"]', 'fast_checks = []') + f'[security]\nposture = "{posture}"\n')
        try:
            build._repo(rules.root, rules.tree.resolve(), config)
        except ValueError as exc:
            return str(exc)
        return None
    reason = rules.memo(('no checks', case[0]), lambda: compute(case[0]))
    if (reason is None) != (case[0] != 'strict') or reason and 'calibrate --questions' not in reason:
        return f'an empty fast-check list under {case[0]}: {reason}'
    return None


def i32(case, rules):
    """#600: a config card with a list value records without a prompt below strict: the
    planner's config set --from-card writes the answered option's Value row."""
    def compute(posture):
        from wuwei import integrity, workspace
        ident = f'D-{61 + DIMENSIONS["posture"].index(posture)}'
        rules.configure(posture)
        (workspace.day_dir(rules.root) / f'decisions/{ident}.md').write_text(
            CHECKS_RECORD.replace('["make test", "markdownlint ."]', '["make test"]'))
        def prompt(*args, **kwargs):
            raise AssertionError('prompt')
        quiet, confirm, session = io.StringIO(), integrity._host_confirm, os.environ.get('WUWEI_SESSION_ID')
        integrity._host_confirm, os.environ['WUWEI_SESSION_ID'] = prompt, 'planner-1'  # no mock import in the walk
        try:
            with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
                main(['decision', 'route', ident])
                answer(rules.root, ident, f'{ident}: Which fast checks gate every change in repo:acme/paper?',
                       'Detected (Recommended)')
                try:
                    code = main(['config', 'set', '--from-card', ident])
                except AssertionError:
                    code = 'a host prompt'
        finally:
            integrity._host_confirm = confirm
            if session is None:
                os.environ.pop('WUWEI_SESSION_ID', None)
            else:
                os.environ['WUWEI_SESSION_ID'] = session
        written = workspace.load_config(rules.root)['repos'][0]['fast_checks']
        rules.configure(posture)
        return code, written
    code, written = rules.memo(('list card', case[0]), lambda: compute(case[0]))
    expected = (1, ['unit']) if case[0] == 'strict' else (0, ['make test'])
    return None if (code, written) == expected else f'config set --from-card gave {code}, {written}'


def i33(case, rules):
    """#600: a config record that records its previous value is never Strategic on its own: the
    first route stores it two-way and, without a better class, approach."""
    def compute():
        from test_decision import CHECKS_RECORD
        from wuwei import decision, undo, workspace
        n = 70
        for cls, door, confidence in itertools.product(('other', None), ('one-way', 'two-way', 'unsure'),
                                                       ('high', 'low')):
            text = (CHECKS_RECORD.replace('Class: other\n', f'Class: {cls}\n' if cls else '')
                    .replace('Reversibility: one-way', f'Reversibility: {door}')
                    .replace('Confidence: high', f'Confidence: {confidence}'))
            n += 1
            path = workspace.day_dir(rules.root) / f'decisions/D-{n}.md'
            path.write_text(text)
            fields, scores = decision.evaluate(text)
            _, fields, _ = undo.correct(f'D-{n}', path, text, fields, rules.root)
            if decision.cisr(fields, scores) == 'Strategic':
                return f'a config record ({cls}, {door}, {confidence}) is Strategic'
        return None
    return rules.memo(('config record',), compute)


def i34(case, rules):
    """#622: a docs-only diff never lowers review when anything else would raise it: a lead flag,
    a FULL track, a trust, never-auto, FULL-pattern, binary or agent-instruction path, or a full
    floor keeps arch, quality and security; a plain document with nothing raising it gets one.
    #657: documents, notebooks and data alike."""
    def compute():
        from wuwei import dispatch
        config = rules.config('guarded', 'send', 'send')
        config = {**config, 'brief': {**config['brief'], 'full_path_patterns': ['^api/']}}
        doc = {'path': 'docs/guide.md', 'additions': 3, 'deletions': 1}
        raising = [{'path': 'cli/wuwei/guards/pr.py', 'additions': 2, 'deletions': 0},
                   {'path': 'uv.lock', 'additions': 2, 'deletions': 0},
                   {'path': 'api/notes.md', 'additions': 2, 'deletions': 0},
                   {'path': 'docs/logo.txt', 'additions': None, 'deletions': None},
                   {'path': 'AGENTS.md', 'additions': 2, 'deletions': 0}]
        real = dispatch._changes
        try:
            # Each raising factor alone, the plain document, and one case with every factor:
            # the rule is "anything raises", so the product of all factors adds walk time
            # without adding coverage (the walk's budget is 1.0 s on the runner, #626).
            cases = [(None, None, 'SLICE', 'standard')]
            cases += [(extra, None, 'SLICE', 'standard') for extra in raising]
            cases += [(None, flag, 'SLICE', 'standard') for flag in ('trust_surface', 'boundary_relevant', 'agent_surface')]
            cases += [(None, None, 'FULL', 'standard'), (None, None, 'SLICE', 'full'),
                      (raising[0], 'trust_surface', 'FULL', 'full')]
            for extra, flag, track, floor in cases:
                repo = config['repos'][0]
                repo = {**repo, 'gates': {**repo['gates'], 'floor': floor}}
                changes = [doc] + ([extra] if extra else [])
                dispatch._changes = lambda *args: (repo, changes)
                row = {'track': track, 'flags': {flag: True} if flag else {}}
                roles = dispatch.tier(rules.root, config, row)['roles']
                raised = extra or flag or track == 'FULL' or floor == 'full'
                if roles != (list(dispatch.ROLES) if raised else ['goal']):
                    return f'{[c["path"] for c in changes]} flag {flag} track {track} floor {floor} records {roles}'
            changes = [doc, {'path': 'study/results/scores.csv', 'additions': 600, 'deletions': 0}]
            dispatch._changes = lambda *args: (config['repos'][0], changes)
            roles = dispatch.tier(rules.root, config, {'track': 'SLICE', 'flags': {}})['roles']
            if roles != ['goal']:
                return f'a document and a data file record {roles}'
            # A large .json is config by default (devcontainer, tasks): it keeps every gate
            # unless data_paths names it.
            config_json = [{'path': '.devcontainer/devcontainer.json', 'additions': 250, 'deletions': 0}]
            for globs, want in (([], list(dispatch.ROLES)), (['.devcontainer/'], ['goal'])):
                repo = config['repos'][0]
                repo = {**repo, 'gates': {**repo['gates'], 'data_paths': globs}}
                dispatch._changes = lambda *args: (repo, config_json)
                roles = dispatch.tier(rules.root, config, {'track': 'SLICE', 'flags': {}})['roles']
                if roles != want:
                    return f'a config .json with data_paths {globs} records {roles}'
        finally:
            dispatch._changes = real
        return None
    return rules.memo(('docs-only',), compute)
def i42(case, rules):
    """#657: generated and data lines never count toward the tier or the size cap, and both read
    the same count from merge.uncounted; a diff that changes .gitattributes gets no
    linguist-generated exclusion."""
    def compute():
        from wuwei import dispatch, merge
        config = rules.config('guarded', 'send', 'send')
        repo = config['repos'][0]
        repo = {**repo, 'gates': {**repo['gates'], 'floor': 'light'}}
        source = {'path': 'src/app.py', 'additions': 80, 'deletions': 0}
        attributes = rules.root / repo['path'] / '.gitattributes'
        real = dispatch._changes
        try:
            attributes.write_text('dist/* linguist-generated\n')
            for big in ('pilot/manifest.json', 'dist/app.js'):
                large = {'path': big, 'additions': 4800, 'deletions': 0}
                for changes, skipped in (([source, large], [big]),
                                         ([source, {'path': '.gitattributes', 'additions': 1, 'deletions': 0}, large],
                                          [big] if big.endswith('.json') else [])):
                    dispatch._changes = lambda *args: (repo, changes)
                    record = dispatch.tier(rules.root, config, {'track': 'SLICE', 'flags': {}})
                    found = sorted(merge.uncounted(rules.root, repo, changes))
                    paths = [c['path'] for c in changes]
                    if found != skipped:
                        return f'{paths}: merge.uncounted names {found}'
                    if (record['tier'] == 'light') != bool(skipped):
                        return f'{paths}: tier {record["tier"]} with {found} uncounted'
        finally:
            dispatch._changes = real
            attributes.unlink(missing_ok=True)
        return None
    return rules.memo(('uncounted',), compute)


def i35(case, rules):
    """#623: no item opens a fix round past its round cap: dispatch.max_rounds is the tier's
    override when set, else gates.max_rounds, and build.open_fix refuses an item whose build
    already used that many rounds."""
    def compute():
        from wuwei import dispatch, state, workspace
        from wuwei.commands import build
        for cap, tier, override in itertools.product((1, 2, 3), dispatch.TIERS, (0, 1, 3)):
            raw = (rules.base + f'[gates]\nmax_rounds = {cap}\n'
                   f'tier_max_rounds = {{ {tier} = {override} }}\n')
            config = workspace.load_config(rules.root, raw=raw)
            for row_tier in dispatch.TIERS:
                found = dispatch.max_rounds(config, {'gates': {'tier': row_tier}})
                if found != (override if row_tier == tier and override else cap):
                    return f'max_rounds {cap}, {tier} = {override}: a {row_tier} item gets {found}'
        root = rules.root / 'round-cap'  # its own workspace: the walk's items stay untouched
        (root / '.wuwei').mkdir(parents=True, exist_ok=True)
        for cap, override in ((1, 0), (2, 0), (3, 0), (1, 3)):
            (root / '.wuwei/config.toml').write_text(
                f'[gates]\nmax_rounds = {cap}\ntier_max_rounds = {{ light = {override} }}\n')
            limit = override or cap

            def seed(data):
                data['items'].setdefault('R35', {**state.ITEM_DEFAULTS, 'phase': 'planned'})
                data['items']['R35']['gates'] = {'tier': 'light', 'roles': ['quality']}
                data.setdefault('builds', {})['R35'] = {'status': 'done', 'fix_rounds': limit}
            state._write_state(seed, root, reserved=False)
            try:
                build.open_fix('R35', 'Gate quality FIX.', root=root)
            except ValueError as exc:
                if f'round cap {limit} reached' not in str(exc):
                    return f'cap {limit}: open_fix refused with {exc}'
            else:
                return f'cap {limit}: open_fix opened round {limit + 1}'
        return None
    return rules.memo(('round cap',), compute)


def i36(case, rules):
    """#636: an item ticket is attached by the planner below strict or by the owner, never by a
    seat, whose reason names the planner; tracker create --bug stays a seat command."""
    def compute():
        from wuwei.guards.protect_state import check_bash
        rules.configure(case[0])
        for command in ('bin/wuwei tracker create A', 'bin/wuwei plan set A ticket=ENG-1'):
            call = rules.bash(command)
            planner = check_bash(call)[0]
            seat, reason = check_bash({**call, 'agent_id': 'seat-1'})
            if (planner == 0) != (case[0] != 'strict') or seat == 0 or 'planner' not in reason:
                return f'{command}: passes for the planner {planner == 0}, for a seat {seat == 0}'
        call = rules.bash('bin/wuwei tracker create --bug A Broken --evidence cli/x.py:1')
        if check_bash({**call, 'agent_id': 'seat-1'})[0]:
            return 'a seat cannot open a linked bug'
        return None
    return rules.memo(('item tickets', case[0]), compute)


def i37(case, rules):
    """#678: an item with owner_merge set is never merged by WUWEI: merge.owner_hold, the one
    read every merge path reaches through merge.check, holds a set flag, releases a cleared or
    absent one and fails closed on a malformed record."""
    def compute():
        from wuwei import merge
        record = {'value': True, 'by': 'owner', 'at': '2026-09-29T11:00:00+00:00'}
        if merge.owner_hold({'owner_merge': record}) != ('owner', '2026-09-29'):
            return 'a set owner_merge does not hold the merge'
        if merge.owner_hold({'owner_merge': {**record, 'value': False}}) or merge.owner_hold({}):
            return 'a cleared or absent owner_merge holds the merge'
        try:
            merge.owner_hold({'owner_merge': 'yes'})
        except ValueError:
            return None
        return 'a malformed owner_merge record reads as cleared'
    return rules.memo(('owner merge',), compute)
    """#676: an untyped Agent launch in a workspace is never refused below strict and is
    registered as an adhoc seat; under strict it is refused naming seat start --adhoc unless
    that command recorded its prompt."""
    def compute(posture):
        from wuwei import brief, state
        from wuwei.guards import agent_launch
        prompt = f'I38 review under {posture}'
        payload = {'cwd': str(rules.root), 'tool_name': 'Agent', 'tool_input': {
            'subagent_type': 'general-purpose', 'description': 'review', 'prompt': prompt}}
        rules.configure(posture)
        try:
            found = [agent_launch.check(payload)]
            if posture == 'strict':
                with contextlib.redirect_stdout(io.StringIO()):
                    main(['seat', 'start', '--role', 'reviewer', '--adhoc', prompt])
                found.append(agent_launch.check(payload))
            digest = brief.prompt_digest(prompt)
            seats = [seat for seat in state.read_state(rules.root)['seats'].values()
                     if seat.get('prompt_sha256') == digest]
        finally:
            (rules.root / '.wuwei/config.toml').write_text(rules.base)
        return found, [seat['label'] for seat in seats]
    found, labels = rules.memo(('adhoc launch', case[0]), lambda: compute(case[0]))
    if case[0] != 'strict':
        return None if found == [(0, '')] and labels == ['general-purpose'] else f'an untyped launch gave {found}, {labels}'
    (code, reason), after = found
    if code != 1 or 'seat start --role <role> --adhoc' not in reason or after != (0, '') or labels != ['reviewer']:
        return f'an untyped launch under strict gave {found}, {labels}'
    return None


INVARIANTS = {'I1': i1, 'I2': i2, 'I3': i3, 'I4': i4, 'I5': i5, 'I6': i6, 'I7': i7, 'I8': i8,
              'I9': i9, 'I10': i10, 'I11': i11, 'I12': i12, 'I13': i13, 'I14': i14,
              'I15': i15, 'I16': i16, 'I17': i17, 'I18': i18, 'I19': i19, 'I20': i20, 'I21': i21,
              'I22': i22, 'I23': i23, 'I24': i24, 'I25': i25, 'I26': i26, 'I27': i27, 'I28': i28,
              'I31': i31, 'I32': i32, 'I33': i33, 'I34': i34, 'I35': i35,
              'I36': i36, 'I37': i37, 'I42': i42}


def project(case):
    """The outward projection of a case: (posture, audience, topic, kind, umbrella, mode)."""
    posture, audience, topic, kind, _, umbrella, mode = case
    return posture, audience, topic, kind, umbrella, mode


# The case positions each invariant reads (DIMENSIONS order); it runs once per distinct
# projection, and a read of any other position raises (#562).
OUTWARD = (0, 1, 2, 3, 5, 6)
READS = {'I1': None, 'I2': OUTWARD, 'I3': (0,), 'I4': OUTWARD, 'I5': (0, 4),
         'I6': (0,), 'I7': OUTWARD, 'I8': (0, 4), 'I9': (0,), 'I10': (0,), 'I11': (), 'I12': (), 'I13': (), 'I14': (),
         'I15': (), 'I16': (0,), 'I17': (), 'I18': (0,), 'I19': (0, 1, 5), 'I20': (), 'I21': (0, 1, 3),
         'I22': (), 'I23': (), 'I24': (), 'I25': (), 'I26': (), 'I27': (), 'I28': (),
         'I31': (0,), 'I32': (0,), 'I33': (), 'I34': (), 'I35': (), 'I36': (0,), 'I37': (), 'I42': (),
         'I31': (0,), 'I32': (0,), 'I33': (), 'I34': (), 'I35': (), 'I36': (0,), 'I37': (),}
# I1 reads all seven dimensions as one function; its two halves each read fewer (#562).
PARTS = {'I1': ((OUTWARD, i1_outward), ((0, 4), i1_grant))}


class Unread:
    """A dimension the invariant did not declare in READS: any use of it fails the walk."""

    def __init__(self, name):
        self.name = name

    def _read(self, *args):
        raise AssertionError(f'{self.name} reads an undeclared dimension')

    __eq__ = __ne__ = __hash__ = __str__ = __format__ = __bool__ = __iter__ = _read


def walk(world):
    """Every invariant on every case; one line per failure with the full tuple."""
    rules, found, keys = Rules(*world), {}, list(DIMENSIONS)
    checks = [(name, reads, check) for name, invariant in INVARIANTS.items()
              for reads, check in PARTS.get(name, ((READS[name], invariant),))]
    for index, (name, reads, check) in enumerate(checks):
        for values in itertools.product(*(DIMENSIONS[keys[i]] for i in reads)):
            case = [Unread(name)] * len(keys)
            for position, value in zip(reads, values):
                case[position] = value
            found[index, values] = check(tuple(case), rules)
    if not any(found.values()):
        return []
    failures = []
    for case in itertools.product(*DIMENSIONS.values()):
        for index, (name, reads, _) in enumerate(checks):
            if failure := found[index, tuple(case[i] for i in reads)]:
                failures.append(' '.join(f'{key}={value}' for key, value in zip(DIMENSIONS, case))
                                + f': {name} {failure}')
    return failures


def test_invariants_hold(world):
    cases = list(itertools.product(*DIMENSIONS.values()))
    assert len(cases) == CASES and CASES >= 18000
    # The suite's heap is not the walk's cost: a full collection landing inside the walk scans
    # every object the earlier tests left alive, so collect and freeze it before the clock starts.
    gc.collect()
    gc.freeze()
    try:
        start = time.process_time()  # CPU time: a busy host does not fail the walk
        failures = walk(world)
        elapsed = time.process_time() - start
    finally:
        gc.unfreeze()
    assert not failures, '\n'.join(failures[:20])
    assert elapsed < 1.0, f'{len(cases)} cases took {elapsed:.2f} s'


def test_undeclared_read_raises(world, monkeypatch):
    # #562: an invariant reading a dimension READS does not name fails loudly.
    monkeypatch.setitem(READS, 'I4', (0, 1, 2, 5, 6))
    with pytest.raises(AssertionError, match='I4 reads an undeclared dimension'):
        walk(world)


BROKEN = {
    'team block row': lambda monkeypatch: monkeypatch.setattr(
        import_module('wuwei.outward'), 'DEFAULT_TIERS',
        ({'audience': 'team', 'tier': 'block'}, *import_module('wuwei.outward').DEFAULT_TIERS)),
    'grant for every target': lambda monkeypatch: monkeypatch.setattr(
        import_module('wuwei.grants'), 'active', lambda *args: ('today', 'D-1')),
    'host cap of one': lambda monkeypatch: monkeypatch.setattr(
        import_module('wuwei.calibrate'), 'host', lambda *args, **kwargs: {'cap': 1, 'seat_mib': 1024}),
    'the word read on tracker writes': lambda monkeypatch: monkeypatch.setitem(
        import_module('wuwei.outward').OWNER, 'tracker', 'tracker'),
    'a message keeps its door': lambda monkeypatch: monkeypatch.setattr(
        import_module('wuwei.undo'), 'measured', lambda *args: ('message', None)),
    'novelty never seen': lambda monkeypatch: monkeypatch.setattr(
        import_module('wuwei.novelty'), 'novel', lambda *args: []),
    'a view drops a channel': lambda monkeypatch: monkeypatch.setattr(
        import_module('wuwei.graph'), 'views', lambda register, real=import_module('wuwei.graph').views: {
            **real(register), 'outbound.channel_classes': {}}),
    'doctor passes an empty identity': lambda monkeypatch: monkeypatch.setattr(
        import_module('wuwei.commands.doctor'), 'identity_row',
        lambda *args: {'status': 'ok', 'value': 'Builder <builder@example.test>'}),
    'promote overwrites an owner-set key': lambda monkeypatch: monkeypatch.setattr(
        import_module('wuwei.calibrate'), 'kept', lambda raw, settings: (list(settings), [])),
    'an empty fast-check list refuses': lambda monkeypatch: monkeypatch.setattr(
        import_module('wuwei.commands.build'), '_repo', lambda *args: (_ for _ in ()).throw(ValueError('none'))),
    'a list card prompts the host': lambda monkeypatch: monkeypatch.setattr(
        import_module('wuwei.commands.setup'), '_from_card',
        lambda *args: import_module('wuwei.integrity')._host_confirm('digest')),
    'a config record keeps one-way': lambda monkeypatch: monkeypatch.setattr(
        import_module('wuwei.undo'), 'correct', lambda ident, path, text, fields, root: (text, fields, '')),
    'a docs-only diff ignores what raises it': lambda monkeypatch: monkeypatch.setattr(
        import_module('wuwei.dispatch'), 'AGENT_DOCS', ()),
    'a fix round past the cap': lambda monkeypatch: monkeypatch.setattr(
        import_module('wuwei.dispatch'), 'rounds_used', lambda data, item: 0),
    'owner_merge ignored': lambda monkeypatch: monkeypatch.setattr(
        import_module('wuwei.merge'), 'owner_hold', lambda item: None),
    'an untyped launch refused below strict': lambda monkeypatch: monkeypatch.setattr(
        import_module('wuwei.guards.agent_launch'), '_adhoc',
        lambda payload: (_ for _ in ()).throw(import_module('wuwei.brief').Refused('untyped'))),
    'client thread row that sends': lambda monkeypatch: monkeypatch.setattr(
        import_module('wuwei.outward'), 'DEFAULT_TIERS',
        ({'audience': 'client', 'topic': 'thread', 'tier': 'send'}, *import_module('wuwei.outward').DEFAULT_TIERS)),
}


def test_a_pace_that_lowers_a_tier_is_caught(world, monkeypatch):
    # #579: a pace rule that drops a tier fails I15 on every case.
    monkeypatch.setattr(import_module('wuwei.pace'), 'adjust', lambda pace, tier, *args: ('light', 'light', []))
    pace_rule.cache_clear()
    try:
        failures = walk(world)
    finally:
        pace_rule.cache_clear()
    assert failures and 'I15 pace' in failures[0]


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
    # No invariant reads durability; a state write's fsyncs are disk work, not the rules' CPU.
    monkeypatch.setattr(os, 'fsync', lambda fd: None)
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


def test_no_stale_owner_marks():
    # An owner mark names an issue a later item builds; once its spec is on main it is stale.
    design = (ROOT / 'docs/specs/2026-09-24-wuwei-design.md').read_text()
    i1 = re.search(r'^\| I1 \|.*$', design, re.M)[0]
    owned = re.search(r'Owned: ([^.]*)', i1)
    marks = [(note, n) for _, _, note in OWNED for n in re.findall(r'#(\d+)', note)]
    marks += [('design 9.2 I1 Owned', n) for n in re.findall(r'#(\d+)', owned[1] if owned else '')]
    stale = [(note, n) for note, n in marks if list(ROOT.glob(f'specs/{int(n):03d}-*'))]
    assert not stale, stale


@pytest.mark.parametrize('head', ['gated', 'moved', 'red'])
@pytest.mark.parametrize('grant', ['none', 'once', 'today', 'standing'])
@pytest.mark.parametrize('posture', ['observe', 'guarded', 'strict'])
def test_merge_only_at_the_gated_green_head(case, posture, grant, head):
    # I3 (#524): WUWEI merges only at the head the gates checked with green required checks,
    # and only under a matching grant: once or today in every posture, a standing line below strict.
    from test_merge import BASE, REF, SHA, evidence, granted_case, merged_calls, standing_merge
    from wuwei import merge, state, workspace
    from wuwei.watch import records
    root, host = granted_case(case, posture)
    if grant == 'standing':
        standing_merge(root)
    elif grant != 'none':
        state._write_state(lambda d: d.setdefault('grants', {}).update({'D-9': {
            'action': 'merge', 'target': 'repo:example/project', 'rule': 'merge', 'command': None,
            'item': 'item-7', 'seat': None, 'planned': False, 'answered': grant, 'spent': False}}),
            root, reserved=False)
    if head == 'moved':
        for gate in ('arch', 'quality', 'security'):
            (workspace.day_dir(root) / 'decisions' / f'gate-item-7-{gate}.md').write_text(evidence(BASE))
    if head == 'red':
        host.results['checks'].data[0]['conclusion'] = 'failure'
    merge.execute(REF, root)
    expected = head == 'gated' and (grant in ('once', 'today') or grant == 'standing' and posture != 'strict')
    used = [row for row in records(workspace.day_dir(root) / 'events.jsonl') if row['kind'] == 'grant.used']
    assert merged_calls(host) == ([(REF, SHA)] if expected else []), (posture, grant, head)
    assert bool(used) == expected, (posture, grant, head, used)


@pytest.mark.parametrize('grant', ['none', 'today'])
@pytest.mark.parametrize('flag', ['set', 'cleared'])
@pytest.mark.parametrize('path', ['merge check', 'wuwei merge', 'pr act', 'pr guard', 'overnight shepherd'])
def test_owner_merge_holds_on_every_path(case, monkeypatch, capsys, path, flag, grant):
    # I37 (#678): the command paths and the daemon path read one hold; cleared, the normal policy.
    from test_merge import REF, SHA, merged_calls
    from wuwei import merge, plan, pr_actions, shepherd, state, workspace
    from wuwei.guards.pr import check as guard
    from wuwei.registry import Result
    from wuwei.watch import records
    root, host = case
    monkeypatch.delenv('WUWEI_SESSION_ID', raising=False)
    monkeypatch.delenv('WUWEI_SEAT_ROLE', raising=False)
    host.results['label'] = Result(0, {'labels': ['owner-merge']})
    plan.set_owner_merge('item-7', 'true', root)
    if flag == 'cleared':
        host.results['label'].data['labels'] = []
        plan.set_owner_merge('item-7', 'false', root)
    if grant == 'today':
        state._write_state(lambda d: d.setdefault('grants', {}).update({'D-9': {
            'action': 'merge', 'target': 'repo:example/project', 'rule': 'merge', 'command': None,
            'item': 'item-7', 'seat': None, 'planned': False, 'answered': 'today', 'spent': False}}),
            root, reserved=False)
    approved = [{'pr': REF, 'exit': 1, 'state': 'approved', 'parked': False, 'action': 'merge'}]
    monkeypatch.setattr(pr_actions, 'evaluate', lambda root, refs=None: (1, approved))
    monkeypatch.chdir(root / 'repo')
    if path == 'merge check':
        result = merge.check(REF, root)
        code, text = result.exit, result.reason or ''
    elif path == 'wuwei merge':
        code = main(['merge', '7'])
        text = capsys.readouterr().out
    elif path == 'pr act':
        code = pr_actions.act(root, REF)
        text = capsys.readouterr().out
    elif path == 'pr guard':
        code, text = guard({'cwd': str(root / 'repo'), 'tool_input': {'command': 'gh pr merge 7'}})
    else:
        shepherd.overnight(root)
        capsys.readouterr()
        [event] = [row['payload'] for row in records(workspace.day_dir(root) / 'events.jsonl')
                   if row['kind'] == 'shepherd.overnight']
        code, text = (1 if event['outcome'] == 'queued' else 0), event['reason']
    held = 'owner merges: owner_merge set by owner on 2026-09-29' in text
    if flag == 'set':
        assert code == 1 and held and merged_calls(host) == [], (path, grant, code, text)
        return
    assert not held and 'owner_merge' not in text, (path, grant, text)
    merges = [(REF, SHA)] if path in ('wuwei merge', 'pr act') else []
    assert merged_calls(host) == merges, (path, grant, text)
    if path == 'overnight shepherd':
        assert text.startswith('merge cleared by policy; '), text
    elif path == 'merge check':
        assert code == 0, text
