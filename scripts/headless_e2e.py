"""Opt-in real Claude day. The normal test suite exercises this runner offline."""

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import secrets
import shutil
import sys
import tempfile
import time
import tomllib

import headless_adapter as adapter

ROOT = Path(__file__).resolve().parents[1]
DAY = '2026-09-29'
ERRORS = (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError)
# ponytail: initial bounds (turns, USD, seconds) per rehearsal session; the owner
# tunes them after measured runs.
REHEARSAL = {'first': (150, 15, 1800), 'second': (40, 5, 600)}
PLANNED = 'decision outcome D-1 (planned, host terminal)'


def check_result(result):
    try:
        data = json.loads(result.stdout)
    except ValueError:
        data = None
    if (result.returncode or not isinstance(data, dict) or data.get('type') != 'result'
            or data.get('is_error') is not False or data.get('subtype') != 'success'):
        # Inspect diagnostic text only after structured runtime failure. Successful
        # assistant prose is never an authentication or completion signal.
        diagnostic = (result.stdout + result.stderr).lower()
        if 'oauth' in diagnostic and 'expired' in diagnostic:
            raise RuntimeError('unmeasured: expired OAuth session; run claude auth login and retry')
        subtype = data.get('subtype', 'runtime error') if isinstance(data, dict) else 'invalid JSON result'
        if 'invalid api key' in diagnostic or 'not logged in' in diagnostic:
            subtype = 'authentication failed; run claude auth login or set ANTHROPIC_API_KEY'
        raise RuntimeError(f'unmeasured: Claude {subtype}')
    return data


def validate(data, events, hooks):
    """Return measured findings. Assistant prose cannot satisfy any assertion."""
    findings = []
    def require(condition, message):
        if not condition:
            findings.append(message)
    require(data.get('gate_approved') is True and data.get('approved_items') == ['A'],
            'morning gate was not recorded')
    require(data.get('builds', {}).get('A', {}).get('status') == 'done', 'build did not finish')
    seats = data.get('seats', {})
    require(bool(seats) and all(s.get('status') == 'stopped' for s in seats.values()),
            'seats are missing or still running')
    require(any(s.get('role') == 'builder' and s.get('item') == 'A' for s in seats.values()),
            'builder seat missing')
    require(data.get('close_requested') is True, 'close was not requested')
    require(data.get('items', {}).get('A', {}).get('phase') == 'parked', 'fixture item was not parked')
    kinds = [row['kind'] for row in events]
    for kind in ('plan.approved', 'seat launched', 'seat stopped', 'seat.usage',
                 'build.checked', 'retro.captured', 'day.close_requested'):
        require(kind in kinds, f'missing event: {kind}')
    if all(k in kinds for k in ('plan.approved', 'seat launched', 'gate.received', 'day.close_requested')):
        require(kinds.index('plan.approved') < kinds.index('seat launched') <
                kinds.index('gate.received') < kinds.index('day.close_requested'), 'events out of order')
    for role in ('arch', 'quality', 'security'):
        require(any(e['kind'] == 'gate.received' and e['payload'].get('item') == 'A'
                    and e['payload'].get('role') == role and e['payload'].get('round') == 'initial'
                    and e['payload'].get('verdict') == 'PASS' for e in events), f'{role} gate missing')
    for event, code in [('SessionStart', 0), ('PreToolUse', 0), ('PostToolUse', 0),
                        ('SubagentStop', 0), ('Stop', 2), ('Stop', 0)]:
        require(any(h['event'] == event and h['exit'] == code for h in hooks),
                f'missing hook exit: {event}={code}')
    require(any(h['event'] == 'PreToolUse' and h['exit'] == 2 and h.get('tool') == 'Agent'
                and h.get('input', {}).get('description') == 'headless refusal probe' for h in hooks),
            'unbriefed Agent was not refused')
    require(any(h['event'] == 'PostToolUse' and h['exit'] == 0 and h.get('tool') == 'Skill'
                and h.get('input', {}).get('skill') == 'wuwei:wuwei-plan' for h in hooks),
            'plan skill was not invoked')
    actions = [(i, h['result']) for i, h in enumerate(hooks)
               if h.get('args') == ['build', 'next', 'A'] and h['exit'] == 0
               and isinstance(h.get('result'), dict) and h['result'].get('action') == 'launch']
    require(any(h['event'] == 'PreToolUse' and h['exit'] == 0 and h.get('tool') == 'Agent'
                and h.get('input', {}).get('prompt') == action.get('prompt')
                and h.get('input', {}).get('subagent_type') == action.get('agent_type')
                for index, action in actions for h in hooks[index + 1:]),
            'Agent did not receive the build next launch contract unchanged')
    for role in ('builder', 'sentinel-arch', 'sentinel-quality', 'sentinel-security', 'steward'):
        require(any(s.get('role') == role for s in seats.values()), f'{role} seat missing')
        require(any(h['event'] == 'PreToolUse' and h['exit'] == 0 and h.get('tool') == 'Agent'
                    and h.get('input', {}).get('subagent_type') == 'wuwei:' + role for h in hooks),
                f'{role} launch hook missing')
        require(any(h['event'] == 'SubagentStop' and h['exit'] == 0
                    and h.get('agent_type') == 'wuwei:' + role for h in hooks), f'{role} stop hook missing')
    planner = data.get('planner_session_id')
    stops = [(i, h['exit']) for i, h in enumerate(hooks)
             if h['event'] == 'Stop' and h.get('session') == planner]
    closes = [i for i, h in enumerate(hooks) if h.get('args') == ['close'] and h['exit'] == 0]
    require(bool(planner) and bool(stops) and stops[-1][1] == 0 and
            any(block < close < stops[-1][0] for block, code in stops if code == 2 for close in closes),
            'planner must block, close successfully, then stop cleanly')
    return findings


def checked(argv, *, cwd, env, input=None):
    result = adapter.run(argv, cwd=cwd, env=env, input=input)
    if result.returncode:
        raise RuntimeError(f'unmeasured: fixture command {Path(str(argv[0])).name} '
                           f'failed ({result.returncode}): {result.stderr.strip() or result.stdout.strip()}')
    return result.stdout


def prepare(scratch, *, local_login=False, repo=None, url=None):
    home, root = scratch / 'home', scratch / 'workspace'
    home.mkdir(mode=0o700)
    root.mkdir()
    # Keep only tool lookup and credentials; inherited workspace, Git and Claude
    # settings must never pull the owner's projects into the fixture.
    env = {key: os.environ[key] for key in ('PATH', 'ANTHROPIC_API_KEY', 'GH_TOKEN')
           if key in os.environ and (repo or key != 'GH_TOKEN')}
    env.update(HOME=str(home), WUWEI_WORKSPACE=str(root), WUWEI_NOW=DAY + 'T12:00:00Z',
               GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    if repo:
        # The merge soak and code host timestamps need the real clock. Pushes and
        # the code host authenticate through gh with GH_TOKEN only.
        del env['WUWEI_NOW']
        env['GIT_CONFIG_GLOBAL'] = str(home / '.gitconfig')
        Path(env['GIT_CONFIG_GLOBAL']).write_text(
            '[credential "https://github.com"]\n\thelper =\n\thelper = !gh auth git-credential\n'
            '[user]\n\tname = WUWEI Rehearsal\n\temail = rehearsal@example.invalid\n')
    (home / '.claude').mkdir(mode=0o700)
    (home / '.claude.json').write_text(json.dumps({'hasCompletedOnboarding': True}))
    if local_login and not env.get('ANTHROPIC_API_KEY'):
        original = Path(os.environ.get('CLAUDE_CONFIG_DIR', str(Path.home() / '.claude')))
        credentials = original / '.credentials.json'
        if credentials.is_file():
            target = home / '.claude/.credentials.json'
            shutil.copyfile(credentials, target)
            target.chmod(0o600)
    source = scratch / 'source'
    source.mkdir()
    for name in ('.claude-plugin', 'cli', 'adapters', 'bin', 'hooks', 'charters',
                 'skills', 'agents', 'templates', 'keys'):
        shutil.copytree(ROOT / name, source / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('README.md', 'LICENSE', 'pyproject.toml', 'docs/integrity.md', 'scripts/build-release.py'):
        target = source / name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    key = scratch / 'signing-key'
    checked(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', key], cwd=scratch, env=env)
    shutil.copyfile(key.with_suffix('.pub'), source / 'keys/manifest-signing-key.pub')
    checked([sys.executable, source / 'scripts/build-release.py', '--key', key,
             '--output', home / 'plugin'], cwd=source,
            env={**env, 'PYTHONPATH': os.pathsep.join(map(str, [source / 'cli', source]))})
    plugin = home / 'plugin/wuwei'
    shim = scratch / 'observer'
    shim.mkdir()
    log = root / 'headless-hooks.jsonl'
    command = [sys.executable, str(ROOT / 'scripts/headless_adapter.py'), sys.executable, str(log)]
    (shim / 'python3').write_text('#!/bin/sh\nexec ' + shlex.join(command) + ' "$@"\n')
    (shim / 'python3').chmod(0o700)
    env['PATH'] = str(shim) + os.pathsep + env.get('PATH', os.defpath)
    cli = plugin / 'bin/wuwei'
    checked([cli, 'init', root], cwd=root, env=env)
    if repo:
        return rehearsal_fixture(root, plugin, env, repo, url or f'https://github.com/{repo}.git')
    # A local clone gives real HEAD/status evidence without creating a commit or
    # using a network service. No remote remains available to the model.
    checked(['git', 'clone', '--quiet', '--local', '--no-hardlinks', ROOT, root / 'repo'], cwd=root, env=env)
    checked(['git', '-C', root / 'repo', 'remote', 'remove', 'origin'], cwd=root, env=env)
    checked(['git', '-C', root / 'repo', 'branch', 'headless-base', 'HEAD'], cwd=root, env=env)
    (root / '.wuwei/config.toml').write_text('''[host]
free_memory_mb = 0
[[repos]]
name = "fixture/demo"
path = "repo"
default_branch = "headless-base"
fast_checks = ["test -s README.md"]
[brief]
remote = "refs/heads"
[adapters]
code_host = "none"
''')
    fixture_plan(root, 'repo/README.md', 'Verify README exists; no tracked edits')
    decision = checked([cli, 'decision', 'template'], cwd=root, env=env)
    (root / 'park.md').write_text(decision.replace('Outcome: pending', 'Outcome: parked A'))
    return root, plugin, env


def fixture_plan(root, evidence, scope):
    (root / '.wuwei/memory/goals.md').write_text('''# Goals
## G-1
outcome: Verify the headless fixture
measure: verified item
target: 1
date: 2026-10-30
priority: 1
''')
    proposal = {'goals': ['G-1'], 'cap': 1,
                'seat_policy': {'builder': {'runtime': 'claude', 'model': 'sonnet'}},
                'envelope': {'start': '09:00', 'end': '17:00', 'net_build_hours': 1},
                'sweep': {'tracker': 'unmeasured: no remote fixture', 'processes': 'fixture only'},
                'candidates': [{'id': 'A', 'goal': 'G-1', 'evidence': evidence,
                    'scope': scope, 'overlap': 'none', 'track': 'SLICE',
                    'flags': {'trust_surface': False, 'boundary_relevant': False, 'agent_surface': False},
                    'score': {'value': 1, 'time_criticality': 1, 'risk_reduction': 1, 'job_size': 1},
                    'evidence_lines': {k: 'headless fixture' for k in
                                       ('value', 'time_criticality', 'risk_reduction', 'job_size')}}]}
    (root / 'proposal.json').write_text(json.dumps(proposal))


def rehearsal_fixture(root, plugin, env, repo, url):
    login = checked(['gh', 'api', 'user', '--jq', '.login'], cwd=root, env=env).strip()
    checked(['git', 'clone', '--quiet', url, root / 'repo'], cwd=root, env=env)
    base = checked(['git', '-C', root / 'repo', 'symbolic-ref', '--short', 'refs/remotes/origin/HEAD'],
                   cwd=root, env=env).strip().removeprefix('origin/')
    # The builder brief never names this per-run line, so the first check fails
    # and only the loop's continue feedback can carry it to the builder.
    line = 'checked: ' + secrets.token_hex(4)
    check = (f"grep -qx '{line}' REHEARSAL.md 2>/dev/null || "
             f"{{ echo 'REHEARSAL.md must contain the line: {line}'; exit 1; }}")
    (root / '.wuwei/config.toml').write_text(f'''[owner]
handles = [{json.dumps(login)}]
[host]
free_memory_mb = 0
[[repos]]
name = {json.dumps(repo)}
path = "repo"
default_branch = {json.dumps(base)}
merge_deploys = false
fast_checks = [{json.dumps(check)}]
[repos.merge]
auto = true
soak_minutes = 0
[shepherd]
min_reviewers = 0
[adapters]
code_host = "github"
chat = "none"
''')
    fixture_plan(root, repo, 'Add REHEARSAL.md through one PR')
    return root, plugin, env


def prompt(root, plugin):
    cli = shlex.quote(str(plugin / 'bin/wuwei'))
    return f'''Run this scripted WUWEI integration day. Invoke Skill wuwei:wuwei-plan first.
The fixture owner explicitly approves proposal.json, goals G-1, queue A, CAP 1,
seat policy and envelope as supplied. Reuse this supplied lead proposal; do not
launch discovery or ask interactive questions. All work is inside this scratch
workspace. Use {cli} for every wuwei command, always from the workspace root.
No network, commits, pushes, PRs, tracker or chat calls. Do not alter config,
plugin files, state, events or telemetry directly. Follow these steps exactly:
1. Register your actual planner session as instructed by the skill. Run mcp check,
plan propose proposal.json and plan approve --items A --goals-confirmed.
2. Probe the launch guard ONCE: call Agent with subagent_type wuwei:builder,
description "headless refusal probe", prompt "Deliberate test: no brief".
This must be denied. The fixture authorizes this one negative probe; resolve it
by logging the proper brief next, never bypassing the guard.
3. Write brief builder A builder --worktree repo --body "Verify README.md
exists and run the configured fast checks. This is a verification-only fixture;
no tracked edits are needed. Do not commit. Report Blocked: none, Gap: none,
Change: none on separate lines if verified. Keep the worktree clean."
Run build next A; pass its prompt UNCHANGED to Agent and agent_type as
subagent_type, with a description. After the real Agent returns call build next A,
execute any returned check command, then build next A until done; done moves A
to gate. Never imitate Agent with Bash, synthesize a transcript, or run a hook
in place of Agent.
4. Run dispatch next A. For each of arch, quality, security write brief
sentinel-ROLE A ROLE --gate --worktree repo --body TEXT, where TEXT describes this
verification-only item, no remote CI and no tracked changes. Ask for a narrow
review of README presence and measured fast checks, a verdict at the brief's
path with Head, Probe, residual risk, VAL, CLASS, Simplicity and Design rows as
applicable, and the three-line retro with Change: none if no charter change is
needed. Use runtime dispatch sentinel-ROLE BRIEF repo, then Agent with the exact
returned prompt and agent_type. These three reviews may run in parallel.
After each seat stops, dispatch receive A ROLE ROLE. dispatch next A must say raise.
5. This fixture deliberately publishes nothing. Copy park.md to today's
.wuwei/days/{DAY}/decisions/D-1.md, run decision route D-1, then
state transition A parked. Run close now, BEFORE retro: it must refuse. Its
steward_launch is an instruction: launch that steward via Agent with the returned
prompt unchanged; its scope is to observe only, propose no changes for this
fixture, and return a three-line retro. End your turn once now, so the real Stop
hook blocks for the missing day retro. After the Stop refusal, run retro, then
close --check retro, then close. Finish only after close succeeds.
Do not treat unmeasured adapter output as clean. If any unexpected refusal or
error occurs, report it and stop. No prose response is used as proof of success.
'''


def exercise(*, local_login=False):
    with tempfile.TemporaryDirectory(prefix='wuwei-headless-') as temporary:
        root, plugin, env = prepare(Path(temporary), local_login=local_login)
        print('Headless e2e: running Claude (48 turns, USD 3, 300 seconds)', flush=True)
        result = adapter.run(adapter.claude_command(plugin), cwd=root, env=env,
                             input=prompt(root, plugin), timeout=300)
        check_result(result)
        day = root / '.wuwei/days' / DAY
        data = json.loads((day / 'state.json').read_text())
        events = [json.loads(line) for line in (day / 'events.jsonl').read_text().splitlines()]
        hooks = [json.loads(line) for line in (root / 'headless-hooks.jsonl').read_text().splitlines()]
        findings = validate(data, events, hooks)
        for finding in findings:
            print('headless e2e finding: ' + finding)
        if not findings:
            print('Headless e2e passed: plan, builder, gates, blocked Stop and clean close measured')
        return int(bool(findings))


def rehearsal_prompt(plugin, stage, *, repo=None, base=None, pr=None):
    cli = shlex.quote(str(plugin / 'bin/wuwei'))
    if stage == 'second':
        return f"""The owner has answered D-1 on the host terminal. Continue the same day.
Use {cli} for every wuwei command, from the workspace root. Run merge {pr}. Then
run pr state until it reports {pr} as merged, polling at most once a minute. Then
run report, retro, close --check retro and close. Finish only after close
succeeds. Never run state transition, state set or state recover, and never edit
files under .wuwei directly. If a command refuses or fails, report it and stop.
"""
    return f"""Run this WUWEI release rehearsal day. Invoke Skill wuwei:wuwei-plan first.
The fixture owner explicitly approves proposal.json, goals G-1, queue A, CAP 1,
seat policy and envelope as supplied. Reuse the supplied proposal; do not launch
discovery or ask interactive questions. Use {cli} for every wuwei command, always
from the workspace root. Never run state transition, state set or state recover,
and never edit files under .wuwei directly: the product moves every phase. If a
command refuses unexpectedly, report it and stop. Follow these steps:
1. Register your planner session as the skill says. Run mcp check, plan propose
proposal.json and plan approve --items A --goals-confirmed.
2. Run worktree add A. Write brief builder A builder --worktree <that worktree>
--body "Add REHEARSAL.md with the line status: draft and commit it on the item
branch. Follow any fast check feedback exactly and commit again."
3. Run the build next A step loop exactly as the skill says until done: pass each
launch prompt unchanged to Agent with its agent_type, execute each returned
check, and continue the builder when build next says continue.
4. Run dispatch next A and dispatch the three gates as the skill says, through
runtime dispatch and Agent. The sentinel-quality brief body must carry this
rehearsal rule: return FIX with one finding marked blocks: yes when REHEARSAL.md
lacks the line reviewed: quality, else PASS. Receive each verdict with dispatch
receive. Follow action fix and the delta round exactly as the skill says.
5. When dispatch next A says raise, push the item branch to origin with git, write
a short PR body file and run pr raise {repo} --base {base} --title "WUWEI
rehearsal" --body-file <file> --item A.
6. Write today's decisions/D-1.md from decision template: Question "Merge the
rehearsal PR today or defer?", option A merge today, option B defer, Recommendation
A, Reversibility: one-way, Decided-by: owner. Run decision route D-1. Then end your
turn; if the Stop hook blocks for the pending decision, end your turn again.
"""


def session(plugin, root, env, stage, text, resume=None):
    turns, budget, seconds = REHEARSAL[stage]
    print(f'Rehearsal: Claude session {stage} ({turns} turns, USD {budget}, {seconds} seconds)', flush=True)
    return check_result(adapter.run(adapter.claude_command(plugin, turns=turns, budget=budget, resume=resume),
                                    cwd=root, env=env, input=text, timeout=seconds))


def day_evidence(root):
    day = max((root / '.wuwei/days').iterdir())
    data = json.loads((day / 'state.json').read_text())
    events = [json.loads(line) for line in (day / 'events.jsonl').read_text().splitlines()]
    hooks = [json.loads(line) for line in (root / 'headless-hooks.jsonl').read_text().splitlines()]
    return data, events, hooks


def owner_decision(root, plugin, env, planned):
    """The owner answers D-1 through the product's host terminal digest; no bypass."""
    path = max((root / '.wuwei/days').iterdir()) / 'decisions/D-1.md'
    if not path.is_file():
        return 'decision D-1 was not written'
    option = re.search(r'^Recommendation:\s*(\S+)', path.read_text(), re.M)
    if not option:
        return 'decision D-1 has no recommendation'
    print(f'Rehearsal: confirm decision D-1 option {option[1]} on this terminal', flush=True)
    planned.append(PLANNED)
    # own_group=False keeps the controlling terminal that _host_confirm opens. PATH drops the
    # observer shim: its 30s bound would kill the digest prompt; decision.decided records the answer.
    result = adapter.run([plugin / 'bin/wuwei', 'decision', 'outcome', 'D-1', option[1]],
                         cwd=root, env={**env, 'PATH': env['PATH'].split(os.pathsep, 1)[1]},
                         timeout=600, own_group=False)
    if result.returncode:
        return f'decision outcome D-1 exited {result.returncode}: {result.stderr.strip()}'
    return None


def manual_repairs(hooks):
    return ['manual repair: ' + ' '.join(map(str, h['args'])) for h in hooks
            if h['event'] == 'cli' and h.get('args', [])[:2] in (
                ['state', 'transition'], ['state', 'set'], ['state', 'recover'])]


def rehearsal_findings(data, events, hooks):
    """One finding per journey step the product did not record."""
    findings = []
    def require(condition, message):
        if not condition:
            findings.append(message)
    require(any(h.get('args') == ['build', 'next', 'A'] and h['exit'] == 0
                and (h.get('result') or {}).get('action') == 'continue' for h in hooks),
            'failing check did not continue the builder')
    gates = [(e['payload'].get('role'), e['payload'].get('round'), e['payload'].get('verdict'))
             for e in events if e['kind'] == 'gate.received' and e['payload'].get('item') == 'A']
    fixed = {role for role, round_name, result in gates if round_name == 'initial' and result == 'FIX'}
    require(bool(fixed), 'no initial gate FIX')
    require(any(role in fixed and round_name == 'delta' and result == 'PASS'
                for role, round_name, result in gates), 'no delta PASS for the FIX gate')
    kinds = [e['kind'] for e in events]
    require('pr.raised' in kinds and len(data.get('raised_prs', [])) == 1, 'pr was not raised once')
    require(any(e['kind'] == 'decision.decided' and e['payload'].get('id') == 'D-1' for e in events),
            'owner decision D-1 was not recorded')
    require('merge.auto' in kinds, 'merge policy did not merge')
    require(data.get('items', {}).get('A', {}).get('phase') == 'merged', 'item A is not merged')
    phases = [e['payload']['phase_changes']['A'] for e in events
              if 'A' in e['payload'].get('phase_changes', {})]
    require(phases == ['implement', 'gate', 'fix', 'delta', 'raised', 'merged'],
            f'phase sequence was {phases}')
    require(data.get('close_requested') is True, 'close was not requested')
    seats = data.get('seats', {})
    require(bool(seats) and all(s.get('status') == 'stopped' for s in seats.values()),
            'seats are missing or still running')
    return findings + manual_repairs(hooks)


def measure(events, hooks, results, planned):
    costs = [result.get('total_cost_usd') for result in results]
    return {'interventions': [*planned, *manual_repairs(hooks)],
            'refusals': [e['payload'].get('reason', '') for e in events if e['kind'] == 'hook.refusal']
            + [f"wuwei {' '.join(map(str, h['args'][:2]))}: exit 2" for h in hooks
               if h['event'] == 'cli' and h['exit'] == 2],
            'cost_usd': None if not costs or None in costs else round(sum(costs), 4)}


def host_terminal():
    try:
        with open('/dev/tty'):
            return True
    except OSError:
        return False


def preconditions(local_login):
    """Return the first missing input as a reason, before any external call."""
    if not os.environ.get('ANTHROPIC_API_KEY') and not local_login:
        return 'ANTHROPIC_API_KEY is not set (or pass --local-login)'
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', os.environ.get('WUWEI_REHEARSAL_REPO', '')):
        return 'WUWEI_REHEARSAL_REPO must name the test repository as owner/name'
    if not os.environ.get('GH_TOKEN'):
        return 'GH_TOKEN is not set'
    if not host_terminal():
        return 'no host terminal for the owner decision'
    return None


def report(verdict, fields, reason=None):
    """Print the verdict line, findings and a last-line JSON result; return the exit code."""
    cost = fields['cost_usd']
    if reason:
        fields['findings'] = [*fields['findings'], reason]
    print(f"rehearsal {verdict}: " + (reason + '; ' if reason else '') + f"interventions {len(fields['interventions'])}, "
          f"elapsed {fields['elapsed_seconds']}s, "
          + ('cost unmeasured' if cost is None else f'cost USD {cost}')
          + f", refusals {len(fields['refusals'])}")
    for finding in fields['findings']:
        print('rehearsal finding: ' + finding)
    print(json.dumps({**fields, 'verdict': verdict}, sort_keys=True))
    return {'pass': 0, 'fail': 1}.get(verdict, 2)


def rehearse(*, local_login=False):
    started = time.monotonic()
    fields = {'interventions': [], 'cost_usd': None, 'refusals': [], 'findings': [], 'pr': None}
    reason = preconditions(local_login)
    if reason:
        fields['elapsed_seconds'] = round(time.monotonic() - started)
        return report('unmeasured', fields, reason)
    repo = os.environ['WUWEI_REHEARSAL_REPO']
    results, planned, findings = [], [], []
    try:
        with tempfile.TemporaryDirectory(prefix='wuwei-rehearsal-') as temporary:
            root, plugin, env = prepare(Path(temporary), local_login=local_login, repo=repo)
            config = tomllib.loads((root / '.wuwei/config.toml').read_text())
            text = rehearsal_prompt(plugin, 'first', repo=repo, base=config['repos'][0]['default_branch'])
            results.append(session(plugin, root, env, 'first', text))
            failure = owner_decision(root, plugin, env, planned)
            pr = (day_evidence(root)[0].get('raised_prs') or [None])[0]
            if failure:
                findings.append(failure)
            elif pr:
                results.append(session(plugin, root, env, 'second', rehearsal_prompt(plugin, 'second', pr=pr),
                                       resume=results[0]['session_id']))
            data, events, hooks = day_evidence(root)
            fields.update(measure(events, hooks, results, planned), pr=pr,
                          findings=findings + rehearsal_findings(data, events, hooks))
    except ERRORS as exc:
        fields.update(interventions=planned, findings=findings,
                      elapsed_seconds=round(time.monotonic() - started))
        return report('unmeasured', fields, str(exc).removeprefix('unmeasured: '))
    fields['elapsed_seconds'] = round(time.monotonic() - started)
    return report('fail' if fields['findings'] else 'pass', fields)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-login', action='store_true', help='Use local Claude login without an API key')
    parser.add_argument('--rehearsal', action='store_true',
                        help='Bounded live release rehearsal against WUWEI_REHEARSAL_REPO')
    args = parser.parse_args(argv)
    if args.rehearsal:
        return rehearse(local_login=args.local_login)
    if not os.environ.get('ANTHROPIC_API_KEY') and not args.local_login:
        print('headless e2e unmeasured: ANTHROPIC_API_KEY is not set')
        return 2
    try:
        return exercise(local_login=args.local_login)
    except ERRORS as exc:
        print('headless e2e unmeasured: ' + str(exc).removeprefix('unmeasured: '))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
