"""Offline seats and port recordings for the scripted day integration tests."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace

from adapters.vcs import git
from fakes.code_host import Fake as CodeHost
from fakes.host import Fake as Host
from fakes.integrity import seed
from fakes.replay import Recorder
from fakes.vcs import Fake as VCS
from wuwei import integrity, registry, state, workspace
from wuwei.__main__ import main
from wuwei.registry import Result


RETRO = 'Blocked: none\nGap: none\nChange: none\n'


class Runtime:
    def __init__(self, day):
        self.day = day
        self.verdict = 'PASS'
        self.builds = 0

    def dispatch(self, role, brief_path, worktree, write, *, root=None):
        day = self.day
        path = Path(brief_path)
        relative = path.relative_to(day.root).as_posix()
        prompt = 'WUWEI brief: ' + relative
        day.hook('PreToolUse', tool_name='Agent', tool_input={
            'subagent_type': role, 'description': 'Scripted seat', 'prompt': prompt})
        if role == 'builder':
            self.builds += 1
            (day.repo / 'memory/demo.py').write_text(f'VALUE = {self.builds}\n')
            result = git.workspace_commit(day.repo, ['memory/demo.py'])
            assert result.exit == 0, result.reason
        elif role.startswith('sentinel-'):
            text = f'Verdict: {self.verdict}\nHead: {day.head}\n'
            if self.verdict == 'FIX':
                text += '- P1 | memory/demo.py:1 | fails when value is one | blocks: yes\n'
            text += 'Probe: not run\nVAL: PASS\n' + RETRO
            # SubagentStop validates all gate files with the stopping seat's role.
            text += 'Simplicity: none\nDesign: none\n'
            target = day.directory / 'decisions' / f'gate-{path.stem}.md'
            target.parent.mkdir(exist_ok=True)
            target.write_text(text)
        else:
            assert role == 'steward'
        transcript = day.root / (path.stem + '.jsonl')
        transcript.write_text(json.dumps({'type': 'user', 'message': {'content': prompt}}) + '\n'
                              + json.dumps({'type': 'assistant', 'message': {'content': RETRO}}) + '\n')
        day.hook('SubagentStop', agent_type=role, agent_id=path.stem,
                 agent_transcript_path=str(transcript), last_assistant_message=RETRO)
        assert day.data['seats'][path.stem]['status'] == 'stopped'
        return Result(0, {'id': path.stem})

    def status(self, job, *, root=None):
        return Result(0, {'status': 'completed'})

    def result(self, job, *, root=None):
        return Result(0, {'usage': {'input_tokens': 2, 'output_tokens': 3, 'model': 'scripted'}})


class Day:
    ref = 'acme/widget#7'

    def __init__(self, root, monkeypatch):
        self.root, self.patch = root, monkeypatch
        root.mkdir()
        monkeypatch.chdir(root)
        monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
        monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
        real_run = subprocess.run

        def local_git(argv, **kwargs):
            assert argv[0] == 'git', f'unexpected external tool: {argv}'
            tree = argv[argv.index('-C') + 1] if '-C' in argv else kwargs.get('cwd', '')
            assert Path(tree).is_relative_to(root), argv
            # The adapter sanitizes Git variables; isolate host config at the process boundary.
            kwargs['env'].update(GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1')
            return real_run(argv, **kwargs)

        def no_network(*args, **kwargs):
            raise AssertionError('network is forbidden in the scripted day')

        monkeypatch.setattr(subprocess, 'run', local_git)
        monkeypatch.setattr(socket.socket, 'connect', no_network)
        base = root / '.wuwei'
        (base / 'memory').mkdir(parents=True)
        (base / 'memory/goals.md').write_text(
            '# Goals\n## G-1\noutcome: Ship a useful result\nmeasure: shipped\n'
            'target: 1\ndate: 2026-10-30\npriority: 1\n')
        (base / 'config.toml').write_text('''
[owner]
name = "Builder"
handles = ["builder"]
[[repos]]
name = "acme/widget"
path = "repo"
default_branch = "main"
fast_checks = ["demo-check"]
[shepherd]
review_channel = "CREVIEW"
lead_login = "lead"
[shepherd.authors]
"reviewer@example.test" = { login = "reviewer", mention = "UREVIEWER" }
"lead@example.test" = { login = "lead", mention = "ULEAD" }
''')
        seed(root)
        self.plugin = root / 'plugin'
        (self.plugin / 'charters').mkdir(parents=True)
        (self.plugin / 'charters/builder.md').write_text('Run tests.\n')
        (self.plugin / 'keys').mkdir()
        (self.plugin / integrity.KEY).write_text('ssh-ed25519 recorded-key\n')
        (base / 'integrity/pinned.pub').write_bytes((self.plugin / integrity.KEY).read_bytes())
        monkeypatch.setattr(integrity, 'PLUGIN', self.plugin)
        self.repo = root / 'repo'
        # ponytail: use a procedure path for demo source so the existing VCS writer can commit it.
        (self.repo / 'memory').mkdir(parents=True)
        (self.repo / 'memory/demo.py').write_text('VALUE = 0\n')
        result = git.workspace_init(self.repo)
        assert result.exit == 0, result.reason
        initial = self.head
        vcs = VCS()
        for name in ('head', 'status', 'diff_stat', 'branches', 'branch', 'pushed_branches',
                     'commit_context'):
            setattr(vcs, name, getattr(git, name))
        identity = {'name': 'Builder', 'email': 'builder@example.test'}
        vcs.results['identity'] = Result(0, {**identity, 'author': identity, 'committer': identity})
        vcs.results['merge_base'] = Result(0, {'sha': initial})
        vcs.results['authorship'] = Result(0, [{'email': 'reviewer@example.test', 'commits': 2}])
        self.host = CodeHost()
        self.host.results['reviews'] = Result(0, [])
        self.host.results['threads'] = Result(0, {'comments': [], 'threads': []})
        self.host.results['request_reviewers'] = Result(0, {'requested': ['reviewer', 'lead']})
        self.host.results['files'] = Result(0, [{'path': 'memory/demo.py'}])
        self.host.results['commits'] = Result(0, [])
        self.host.author_login = lambda repo, email, root=None: Result(0, {'login': email.split('@')[0]})
        self.chat = Recorder({'post': Result(0, {'channel': 'CREVIEW', 'ts': '1.1'}),
                              'sent': Result(0, [])})
        self.chat.post = lambda *args, root=None: self.chat._call('post', args, root)
        self.chat.sent = lambda *args, root=None: self.chat._call('sent', args, root)
        self.runtime = Runtime(self)

        def check(path, command, root=None):
            assert Path(path) == self.repo and command == 'demo-check'
            assert (self.repo / 'memory/demo.py').read_text() == f'VALUE = {self.runtime.builds}\n'
            return Result(0)

        ports = {'vcs': vcs, 'code_host': self.host, 'host': Host(),
                 'runtime': self.runtime, 'checks': SimpleNamespace(run=check), 'chat': self.chat,
                 'integrity': SimpleNamespace(verify=lambda *args: Result(
                     1, reason='recorded unsigned installation'))}
        real_load = registry.load
        monkeypatch.setattr(registry, 'load', lambda kind, config:
                            ports[kind] if kind in ports else real_load(kind, config))
        confirmed = integrity.reconfirm(root, confirm=lambda fingerprint: True)
        assert confirmed.exit == 0, confirmed.reason

    @property
    def directory(self):
        return workspace.day_dir(self.root)

    @property
    def head(self):
        result = git.head(self.repo)
        assert result.exit == 0, result.reason
        return result.data['sha']

    @property
    def data(self):
        return state.read_state(self.root)

    @property
    def events(self):
        return [json.loads(line) for line in (self.directory / 'events.jsonl').read_text().splitlines()]

    def run(self, *args, expected=0, stdin=''):
        out, err = io.StringIO(), io.StringIO()
        with self.patch.context() as patch, redirect_stdout(out), redirect_stderr(err):
            patch.setattr(sys, 'stdin', io.StringIO(stdin))
            code = main(list(map(str, args)))
        assert code == expected, (args, code, out.getvalue(), err.getvalue())
        return out.getvalue() or err.getvalue()

    def hook(self, event, expected=0, **fields):
        payload = {'session_id': 'planner', 'cwd': str(self.root),
                   'transcript_path': str(self.root / 'planner.jsonl'),
                   'hook_event_name': event, 'stop_hook_active': False, **fields}
        return self.run('hook', event, expected=expected, stdin=json.dumps(payload))

    def plan(self, *, agent_surface=False):
        from copy import deepcopy
        candidate = {'id': 'A', 'goal': 'G-1', 'evidence': 'recorded issue A',
            'scope': 'one value', 'overlap': 'none', 'track': 'SLICE',
            'flags': {'trust_surface': False, 'boundary_relevant': False, 'agent_surface': agent_surface},
            'score': {'value': 5, 'time_criticality': 3, 'risk_reduction': 2, 'job_size': 2},
            'evidence_lines': {key: 'recorded issue A' for key in
                               ('value', 'time_criticality', 'risk_reduction', 'job_size')}}
        lower = deepcopy(candidate)
        lower['id'], lower['score']['job_size'] = 'B', 5
        candidates = [lower, candidate]
        source = self.root / 'candidates.json'
        source.write_text(json.dumps(candidates))
        assert [row['id'] for row in json.loads(self.run('rank', source))] == ['A', 'B']
        proposal = {'goals': ['G-1'], 'cap': 1,
            'seat_policy': {'builder': {'runtime': 'claude', 'model': 'scripted'}},
            'envelope': {'start': '09:00', 'end': '17:00', 'net_build_hours': 5},
            'sweep': {'processes': 'measured: none'}, 'candidates': candidates}
        source = self.root / 'proposal.json'
        source.write_text(json.dumps(proposal))
        self.run('plan', 'propose', source)
        assert [row['id'] for row in json.loads((self.directory / 'proposal.json').read_text())['candidates']] == ['A', 'B']

    def approve(self):
        self.run('plan', 'approve', '--items', 'A', '--goals-confirmed')

    def transition(self, phase):
        self.run('state', 'transition', 'A', phase)

    def next(self):
        return json.loads(self.run('dispatch', 'next', 'A'))

    def brief(self, role, name):
        return self.run('brief', role, 'A', name, '--worktree', self.repo, '--file', '-',
                        stdin='Implement or review the demo value.').strip()

    def build(self, name):
        path = self.brief('builder', name)
        action = json.loads(self.run('build', 'next', 'A'))
        assert action['action'] == 'launch'
        self.runtime.dispatch('builder', action['brief'], action['worktree'], True, root=self.root)
        assert json.loads(self.run('build', 'next', 'A'))['action'] == 'check'
        self.run('build', 'check', 'A')
        assert json.loads(self.run('build', 'next', 'A'))['action'] == 'done'

    def gate(self, role, verdict, round_name='initial', expected=0):
        name = f'{role}-{round_name}'
        path = self.brief('sentinel-' + role, name)
        self.runtime.verdict = verdict
        self.run('runtime', 'dispatch', 'sentinel-' + role, self.root / path, self.repo)
        return self.run('dispatch', 'receive', 'A', role, name, '--round', round_name, expected=expected)

    def raise_pr(self, expected=0):
        self.host.results['pr'].data.update(head=self.head, requested_reviewers=['reviewer', 'lead'])
        for row in self.host.results['checks'].data:
            row['sha'] = self.head
        body = self.root / 'pr.md'
        body.write_text('Update the demo value.\n')
        return self.run('pr', 'raise', 'acme/widget', '--base', 'main', '--title',
                        'Update demo', '--body-file', body, '--item', 'A', expected=expected)
