"""Main-versus-head evidence for goal-met, run with pytest's interpreter:

    python specs/goal-met/differential.py <tree> <scratch dir>

It loads the runtime from <tree>/cli and this branch's tests/ helpers, then prints JSON: the sha256 of
tests/fixtures/routes.json, each route's verdict and reason read through guards.bash and through the
PreToolUse hook, and the counts of the goal: probe (tests/test_hook.py goal_met_probe)."""

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(Path(sys.argv[1]).resolve() / 'cli'), str(HERE / 'tests')]

import pytest  # noqa: E402

import wuwei  # noqa: E402
from wuwei import gh, guards, hook, ws  # noqa: E402
from conftest import FakeGh, make_pr  # noqa: E402
import test_guards  # noqa: E402
from test_hook import goal_met_probe  # noqa: E402


def root(scratch):
    path = Path(tempfile.mkdtemp(dir=scratch))
    (path / ws.DIR).mkdir()
    ws.write_config(path, {**ws.DEFAULTS, 'repos': ['acme/app'], 'owner_paths': ['infra/**']})
    return path


def routes(scratch):
    patch, out = pytest.MonkeyPatch(), []
    fake = FakeGh()
    patch.setattr(gh, 'run', fake)
    patch.setattr(guards, 'origin', lambda cwd: 'o/r')
    patch.setattr(guards, 'current_branch', lambda cwd: 'i-1-change')
    fake.prs['5'] = make_pr(number=5, files=('src/app.py',))
    fake.prs['7'] = {**make_pr(number=7, files=('src/app.py',)), 'isDraft': True}
    test_guards.branch(fake, ('src/app.py',))
    for route in test_guards.ROUTES:
        found = guards.bash(root(scratch), route['command'], '/repo', 's1')
        hooked = hook.handle(root(scratch), 'PreToolUse', {'session_id': 's1', 'tool_name': 'Bash', 'cwd': '/repo',
                                                           'tool_input': {'command': route['command']}})
        out.append({'command': route['command'], 'recorded': route['verdict'], 'verdict': test_guards.door_reached(found),
                    'reason': found and found['reason'], 'hook': json.dumps(hooked, sort_keys=True)})
    patch.undo()
    return out


def main():
    scratch = Path(sys.argv[2]).resolve()
    patch = pytest.MonkeyPatch()
    generated, recorded, holes = goal_met_probe(root(scratch), patch)
    patch.undo()
    corpus = HERE / 'tests' / 'fixtures' / 'routes.json'
    print(json.dumps({'runtime': wuwei.__file__, 'routes_sha256': hashlib.sha256(corpus.read_bytes()).hexdigest(),
                      'routes': routes(scratch), 'probe': {'generated': generated, 'recorded': recorded,
                                                           'holes': len(holes), 'first_holes': holes[:5]}}, indent=1))


if __name__ == '__main__':
    main()
