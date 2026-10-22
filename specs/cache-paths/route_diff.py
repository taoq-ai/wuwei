"""The main-versus-head route differential for cache-paths (AGENTS.md "Testing the guards").

hook.py changes in _confirm, which every planner PreToolUse runs before the doors judge. So each route in the corpus
goes through hook.handle as a planner's Bash call, with a pending answer entry answer-s1--x.json kept for the session:
- plain: the entry lies in the workspace's own .wuwei/cache;
- linked: .wuwei/cache is a link to an outside folder that holds the entry.
Each case records the decision, its reason, and the files left in the cache and outside. Case folders are made and
removed under <base>; both trees read the fake host from one tests folder, so only the runtime moves.

    python3 -I route_diff.py <tree> <tests folder> <base> > <out>.json
    python3 -I route_diff.py compare <main>.json <head>.json
"""
import collections
import hashlib
import json
import shutil
import sys
from pathlib import Path

LAYOUTS = ('plain', 'linked')
if sys.argv[1] == 'compare':
    main, head = (json.loads(Path(name).read_text(encoding='utf-8')) for name in sys.argv[2:4])
    moved = sorted(key for key in main['cases'] if main['cases'][key] != head['cases'].get(key))
    print(f"corpus sha256 {main['corpus_sha256']} (main) {head['corpus_sha256']} (head); {main['routes']} routes; "
          f"{len(main['cases'])} cases; {len(moved)} moved")
    for layout in LAYOUTS:
        print(f"{layout}: {sum(1 for k in main['cases'] if k.startswith(layout + ' '))} cases, "
              f"{sum(1 for k in moved if k.startswith(layout + ' '))} moved")
    door = lambda case: (case['decision'], case['reason'].split('\n\nWUWEI: the answer')[0])  # noqa: E731  the door's own words
    turned = [key for key in moved if door(main['cases'][key]) != door(head['cases'][key])]
    print(f"decision or door reason moved: {len(turned)}")
    for key in turned:
        print(f"- {key}:\n  main {json.dumps(main['cases'][key], sort_keys=True)}\n  head {json.dumps(head['cases'][key], sort_keys=True)}")
    for name, side in (('main', main), ('head', head)):
        left = collections.Counter(', '.join(side['cases'][k]['outside']) or 'nothing' for k in side['cases'] if k.startswith('linked '))
        print(f"linked, files in the outside folder after the call at {name}: " + '; '.join(f'{n} x [{f}]' for f, n in left.most_common()))
    sys.exit(0)
tree, tests, base = (Path(arg).resolve() for arg in sys.argv[1:4])
sys.path[:0] = [str(tree / 'cli'), str(tests)]

from wuwei import gh, guards, hook, ws  # noqa: E402  (before conftest, which puts its own tree's cli first on the path)
from conftest import FakeGh, make_pr  # noqa: E402

assert Path(hook.__file__).is_relative_to(tree), hook.__file__
guards.origin = lambda cwd: 'o/r'
guards.current_branch = lambda cwd: 'i-1-change'
ws.PROJECTS = base / 'projects'


def run(layout, command):
    case = base / 'case'
    shutil.rmtree(case, ignore_errors=True)
    root, outside = case / 'ws', case / 'outside'
    (root / ws.DIR).mkdir(parents=True)
    outside.mkdir()
    ws.write_config(root, {**ws.DEFAULTS, 'repos': ['acme/app'], 'owner_paths': ['infra/**']})
    ws.atomic_write(root / ws.DIR / 'plan.json', json.dumps({'items': [
        {'id': 'I-1', 'title': 'change', 'goal': 'G-1', 'repo': 'o/r', 'tier': 'standard'}]}))
    if layout == 'linked':
        (root / ws.DIR / 'cache').symlink_to(outside, target_is_directory=True)
    (root / ws.DIR / 'cache').mkdir(exist_ok=True)
    (root / ws.DIR / 'cache' / 'answer-s1--x.json').write_text(json.dumps({'id': 'x', 'path': None, 'questions': ['q']}))
    fake = FakeGh()
    gh.run = fake
    fake.prs['5'] = make_pr(number=5, files=('src/app.py', 'tests/test_app.py'))
    try:
        out = hook.handle(root, 'PreToolUse', {'session_id': 's1', 'cwd': str(root), 'tool_name': 'Bash',
                                               'tool_input': {'command': command}})
        spec = (out or {}).get('hookSpecificOutput', {})
        decision = {'decision': spec.get('permissionDecision'), 'reason': str(spec.get('permissionDecisionReason') or '')}
    except Exception as exc:
        decision = {'decision': 'raised', 'reason': f'{type(exc).__name__}: {exc}'}
    decision['reason'] = decision['reason'].replace(str(root), '<root>').replace(str(outside), '<outside>').replace(str(base), '<base>')
    decision['outside'] = sorted(p.name for p in outside.iterdir())
    decision['answer kept'] = (root / ws.DIR / 'cache' / 'answer-s1--x.json').is_file() if layout == 'plain' else None
    shutil.rmtree(case)
    return decision


corpus = tests / 'fixtures' / 'routes.json'
routes = json.loads(corpus.read_text(encoding='utf-8'))['routes']
cases = {f'{layout} {route["command"]}': run(layout, route['command']) for layout in LAYOUTS for route in routes}
shutil.rmtree(base / 'projects', ignore_errors=True)
print(json.dumps({'corpus_sha256': hashlib.sha256(corpus.read_bytes()).hexdigest(), 'routes': len(routes), 'cases': cases},
                 sort_keys=True, indent=1))
