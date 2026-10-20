"""Main-versus-head route differential for verdict-shape-examples (AGENTS.md "Mutants" and "Testing the guards"):

    python specs/verdict-shape-examples/route_diff.py <tree> <scratch dir>

It loads the runtime from <tree>/cli and this branch's tests/ helpers, then prints JSON: the sha256 of
tests/fixtures/routes.json and each route's verdict and reason read through guards.bash under four workspaces.
PR o/r#5 changes code and a test, so its only gate gap is quality; an approved exception waives that gap at its
head, so the door reads the uncounted lines that follow it:
  none        no verdict files
  arch-bad    a refused arch verdict (a gate the PR does not need)
  quality-bad an unattested quality verdict (the gate the gap names)
  both        the two together
Run it once with the main tree and once with the head tree, and diff the two outputs."""

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(Path(sys.argv[1]).resolve() / 'cli'), str(HERE / 'tests')]

import pytest  # noqa: E402

import wuwei  # noqa: E402
from wuwei import gh, guards, ws  # noqa: E402
from conftest import HEAD, FakeGh, make_pr, verdict_text, write_plan  # noqa: E402
import test_guards  # noqa: E402

BAD = verdict_text(gate='arch', head=HEAD, pr='o/r#5').replace('Confidence: high', 'Confidence: sure')
GOOD = verdict_text(gate='quality', head=HEAD, pr='o/r#5')
CASES = {'none': {}, 'arch-bad': {'arch': BAD}, 'quality-bad': {'quality': GOOD}, 'both': {'arch': BAD, 'quality': GOOD}}


def workspace(scratch, files):
    path = Path(tempfile.mkdtemp(dir=scratch))
    (path / ws.DIR).mkdir()
    ws.write_config(path, {**ws.DEFAULTS, 'repos': ['o/r'], 'owner_paths': ['infra/**']})
    write_plan(path, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'o/r', 'tier': 'standard'}])
    ws.record(path, 'ruling', {'kind': 'exception', 'pr': 'o/r#5', 'head': HEAD[:7],
                               'gap': f'gates missing at head {HEAD[:7]}: quality', 'approved': True})
    for gate, body in files.items():
        target = path / ws.DIR / 'verdicts' / 'I-1' / f'{gate}-{HEAD[:7]}.md'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
    return path


def routes(scratch, files):
    patch, out = pytest.MonkeyPatch(), []
    fake = FakeGh()
    patch.setattr(gh, 'run', fake)
    patch.setattr(guards, 'origin', lambda cwd: 'o/r')
    patch.setattr(guards, 'current_branch', lambda cwd: 'i-1-change')
    fake.prs['5'] = make_pr(number=5)
    fake.prs['7'] = {**make_pr(number=7), 'isDraft': True}
    test_guards.branch(fake)
    for route in test_guards.ROUTES:
        found = guards.bash(workspace(scratch, files), route['command'], '/repo', 's1')
        out.append({'command': route['command'], 'verdict': test_guards.door_reached(found), 'reason': found and found['reason']})
    patch.undo()
    return out


def main():
    scratch = Path(sys.argv[2]).resolve()
    corpus = HERE / 'tests' / 'fixtures' / 'routes.json'
    print(json.dumps({'runtime': wuwei.__file__, 'routes_sha256': hashlib.sha256(corpus.read_bytes()).hexdigest(),
                      'cases': {name: routes(scratch, files) for name, files in CASES.items()}}, indent=1))


if __name__ == '__main__':
    main()
