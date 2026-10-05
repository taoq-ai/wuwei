"""Profile the configured repositories and propose the workspace configuration."""

import json
from pathlib import Path
import re
import sys

from wuwei import calibrate, workspace
from wuwei.exits import CLEAN, FINDINGS, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('calibrate', help='profile repositories and propose config')
    parser.add_argument('action', nargs='?', choices=('export', 'import'),
                        help='export a shareable profile, or import one as a proposal')
    parser.add_argument('target', nargs='?', metavar='NAME|SOURCE',
                        help='profile name to export; starter name, https URL or file to import')
    parser.add_argument('--repo', help='calibrate only this configured repository')
    parser.add_argument('--measure', action='store_true',
                        help='time each test runner once through the checks port (runs repository commands)')
    parser.add_argument('--skip', action='append', default=[], metavar='KEY',
                        help='leave this profile key or charters.<role> out of the import')
    interview = parser.add_mutually_exclusive_group()
    interview.add_argument('--interview', nargs='*', metavar='QUESTION',
                           help='ask the owner interview on this host terminal (all questions, or these)')
    interview.add_argument('--questions', action='store_true',
                           help='print the interview as AskUserQuestion widgets')
    interview.add_argument('--answer', action='append', metavar='ID=VALUE',
                           help='record an interview answer relayed from the widgets')
    parser.set_defaults(func=run)


def run(args):
    if args.action:
        return _profile(args)
    if args.interview is not None or args.questions or args.answer:
        return _interview(args)
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
        results = calibrate.survey(root, config, selected, measure=args.measure)
        host = calibrate.host(root, config)
    except (OSError, ValueError) as exc:
        print(f'wuwei calibrate: {exc}', file=sys.stderr)
        return UNRUN
    error = None
    try:
        _, diff, edits = calibrate.propose(raw, results)
    except ValueError as exc:
        diff, edits, error = '', [], str(exc)
    evidence, _ = record(root, results, diff, edits, error, host, config)
    print(f'Wrote {evidence}')
    print(diff or ('Could not place the proposal: ' + error if error else 'No config.toml changes'))
    for key, current, detected in edits:
        print(f'Config differs; edit by hand: {key}')
    for name, command, note in calibrate.ci_only(results):
        print(f'CI only, not proposed as a fast check: {name}: {command} ({note})')
    print(f"Next: review the report, run bin/wuwei config promote{' --measure' if args.measure else ''} "
          'in a host terminal, then bin/wuwei promote for the charter proposals.')
    if 'unmeasured' in host:
        print(f"wuwei calibrate: host unmeasured: {host['unmeasured']}; run bin/wuwei doctor, then retry", file=sys.stderr)
        return UNRUN
    if error or any(r['style'] is None or r['baseline'] is None for r in results):
        print('wuwei calibrate: ' + (error or 'commit style or PR baseline unmeasured') + '; run bin/wuwei doctor, then retry', file=sys.stderr)
        return UNRUN
    flagged = any(f['kind'] in ('instruction_like', 'unsafe') for r in results for f in r['findings'])
    return FINDINGS if flagged else CLEAN


def record(root, results, diff, edits, error, host=None, config=None):
    """Write today's charter proposals and calibration.md; (evidence path, proposal paths)."""
    day = workspace.day_dir(root)
    (day / 'proposals').mkdir(parents=True, exist_ok=True)
    evidence = f'.wuwei/days/{day.name}/calibration.md'
    written = []
    for result in results:
        name = result['repo']['name']
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        for role, text in calibrate.charter_proposals(result['repo'], calibrate.proposed(result),
                                                      result['style']).items():
            path = day / 'proposals' / f'calibration-{slug}-{role}.json'
            workspace.atomic_write(path, json.dumps({
                'target': f'.wuwei/charters/{role}.md', 'action': 'add', 'text': text,
                'reason': f'calibration of {name}: repository conventions',
                'evidence': evidence}, indent=2) + '\n')
            written.append(f'.wuwei/days/{day.name}/proposals/{path.name}')
    workspace.atomic_write(day / 'calibration.md', calibrate.report(results, diff, edits, written, error, host, config))
    return evidence, written


def _interview(args):
    from wuwei import integrity, interview

    try:
        root = workspace.find_workspace()
        config = workspace.load_config(root)
        repos = [repo['name'] for repo in config['repos'] if args.repo in (None, repo['name'])]
        if args.repo and not repos:
            raise ValueError(f'unknown repository {args.repo!r}; use a configured repos.name')
        if args.questions:
            print(json.dumps(interview.widgets(root, repos), indent=2))
            return CLEAN
        if args.answer:
            picked = interview.parse(args.answer, repos)
        else:
            ids = [interview.question(qid)['id'] for qid in args.interview]
            if not sys.stdin.isatty():
                raise OSError(integrity.HOST_TERMINAL)
            picked = interview.ask(ids, repos)
        answers = interview.record(root, config, picked)
    except EOFError:
        print('wuwei calibrate: interview interrupted; nothing written; run bin/wuwei calibrate again to start over', file=sys.stderr)
        return UNRUN
    except (OSError, ValueError) as exc:
        print(f'wuwei calibrate: {exc}', file=sys.stderr)
        return UNRUN
    print('\n'.join(interview.describe(answers, config)))
    print('Next: run bin/wuwei config promote in a host terminal for the config keys, '
          'then bin/wuwei promote for the charter and voice proposals.')
    return CLEAN


def _profile(args):
    from wuwei import profiles

    try:
        if not args.target:
            raise ValueError(f'calibrate {args.action} needs a NAME or SOURCE; pass a profile NAME or SOURCE')
        if args.interview is not None or args.questions or args.answer or (args.skip and args.action == 'export'):
            raise ValueError(f'calibrate {args.action} takes only --repo' + (' and --skip' if args.action == 'import' else '') + '; remove the other options')
        root = workspace.find_workspace()
        config = workspace.load_config(root)
        names = [repo['name'] for repo in config['repos'] if args.repo in (None, repo['name'])]
        if args.repo and not names:
            raise ValueError(f'unknown repository {args.repo!r}; use a configured repos.name')
        if args.action == 'export':
            profile = profiles.export(root, config, args.target, args.repo)
            workspace.atomic_write(Path(f'{args.target}.json'),
                                   json.dumps(profile, indent=2, sort_keys=True) + '\n', replace=False)
            print(f'Wrote {args.target}.json')
            for drop in profile['dropped']:
                print(f"Dropped {drop['where']}: {drop['why']}")
            return CLEAN
        profile = profiles.read(args.target)
        accepted, refused, flagged = profiles.review(profile, config, names)
        if refused:
            for key, why in refused:
                print(f'wuwei calibrate: refused: {key} ({why}); nothing written; run it again with a value bin/wuwei config check accepts', file=sys.stderr)
            return FINDINGS
        accepted = profiles.skip(profile, accepted, args.skip)
        raw = (root / '.wuwei/config.toml').read_text(encoding='utf-8')
        _, diff, edits = calibrate.propose(raw, [], profiles.settings(accepted, config, names))
        written = profiles.record(root, accepted, names)
    except (OSError, ValueError) as exc:
        print(f'wuwei calibrate: {exc}', file=sys.stderr)
        return UNRUN
    print(diff or 'No config.toml changes')
    for key, _, _ in edits:
        print(f'Config differs; edit by hand: {key}')
    for path in written:
        print(f'Proposed {path}')
    for where, rule in flagged:
        print(f'Flagged {where} ({rule}), not proposed')
    print('Next: run bin/wuwei config promote in a host terminal for the config keys, '
          'then bin/wuwei promote for the charter proposals.')
    return FINDINGS if flagged else CLEAN
