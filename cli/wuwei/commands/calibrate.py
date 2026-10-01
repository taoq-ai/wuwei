"""Profile the configured repositories and propose the workspace configuration."""

import json
import re
import sys

from wuwei import calibrate, workspace
from wuwei.exits import CLEAN, FINDINGS, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('calibrate', help='profile repositories and propose config')
    parser.add_argument('--repo', help='calibrate only this configured repository')
    parser.set_defaults(func=run)


def run(args):
    try:
        root = workspace.find_workspace()
        config = workspace.load_config(root)
        raw = (root / '.wuwei/config.toml').read_text(encoding='utf-8')
        selected = [(i, repo) for i, repo in enumerate(config['repos'])
                    if args.repo in (None, repo['name'])]
        if not config['repos']:
            raise ValueError(calibrate.NO_REPOS)
        if not selected:
            raise ValueError(f'unknown repository {args.repo!r}; use a configured repos.name')
        results = calibrate.survey(root, config, selected)
    except (OSError, ValueError) as exc:
        print(f'wuwei calibrate: {exc}', file=sys.stderr)
        return UNRUN
    error = None
    try:
        _, diff, edits = calibrate.propose(raw, results)
    except ValueError as exc:
        diff, edits, error = '', [], str(exc)
    day = workspace.day_dir(root)
    (day / 'proposals').mkdir(parents=True, exist_ok=True)
    evidence = f'.wuwei/days/{day.name}/calibration.md'
    written = []
    for result in results:
        name = result['repo']['name']
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        for role, text in calibrate.charter_proposals(result['repo'], result['facts'],
                                                      result['style']).items():
            path = day / 'proposals' / f'calibration-{slug}-{role}.json'
            workspace.atomic_write(path, json.dumps({
                'target': f'.wuwei/charters/{role}.md', 'action': 'add', 'text': text,
                'reason': f'calibration of {name}: repository conventions',
                'evidence': evidence}, indent=2) + '\n')
            written.append(f'.wuwei/days/{day.name}/proposals/{path.name}')
    workspace.atomic_write(day / 'calibration.md', calibrate.report(results, diff, edits, written, error))
    print(f'Wrote {evidence}')
    print(diff or ('Could not place the proposal: ' + error if error else 'No config.toml changes'))
    for key, current, detected in edits:
        print(f'Config differs; edit by hand: {key}')
    print('Next: review the report, run bin/wuwei config promote in a host terminal, '
          'then bin/wuwei promote for the charter proposals.')
    if error or any(r['style'] is None or r['baseline'] is None for r in results):
        print('wuwei calibrate: ' + (error or 'commit style or PR baseline unmeasured'), file=sys.stderr)
        return UNRUN
    flagged = any(f['kind'] in ('instruction_like', 'unsafe') for r in results for f in r['findings'])
    return FINDINGS if flagged else CLEAN
