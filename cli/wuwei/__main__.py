"""wuwei: the process auditor's command line. It reads and records; it never stands in for git or gh."""

import argparse
import json
from pathlib import Path
import sys

from wuwei import agents, board, evidence, hook, plan, report, setup, ws

PLUGIN = Path(__file__).resolve().parents[2]


def _root():
    root = ws.find()
    if root is None:
        raise SystemExit('wuwei: no .wuwei/ here or above; run wuwei init')
    return root


def _ref(text):
    repo, _, number = text.rpartition('#')
    if not repo or not number.isdigit():
        raise SystemExit('wuwei: name the PR as owner/repo#number')
    return repo, int(number)


def cmd_plan(args):
    root = _root()
    if args.action == 'add' and args.source:
        for item in plan.add_from(root, args.source):
            print(f'{item["id"]} added with score {item["score"]}')
    elif args.action == 'add':
        fields = ('value', 'time', 'risk', 'size') if ws.config(root)['prioritisation'] == 'wsjf' else (
            'reach', 'impact', 'confidence', 'effort')
        scores = {name: getattr(args, name) for name in fields}
        scores = {k: int(v) if float(v).is_integer() and k not in ('impact', 'confidence') else float(v)
                  for k, v in scores.items() if v is not None}
        item = plan.add(root, args.id, args.title, args.goal, args.repo, args.tier, scores, args.why or '',
                        args.promise or '', args.accept or ())
        print(f'{item["id"]} added with score {item["score"]}')
    elif args.action in ('park', 'drop', 'done'):
        status = {'park': 'parked', 'drop': 'dropped', 'done': 'done'}[args.action]
        plan.mark(root, args.id, status, args.reason or '')
        print(f'{args.id} {status}')
    elif args.action == 'view':
        from wuwei import view
        path, summary, line = view.write(root)
        if args.html:
            print(view.render(root)[0])
            return 0
        print(f'{summary}\n\nPage: {path}\nAsk: plan: approve this plan? {line}')
    elif args.action == 'run':  # an operations item: done by its run evidence, not a pull request (#1049)
        print(f'{plan.mark(root, args.id, "open", args.reason or "", kind="run")["id"]} run evidence recorded')
    elif args.action == 'restore':
        print(f'{plan.restore(root, args.id)["id"]} open again')
    elif args.action == 'show' and args.id:
        item = plan.find(root, args.id)
        if item is None:
            raise ValueError(f'{args.id} is not in the plan')
        print(json.dumps(item, indent=1))
    elif args.action == 'pass':
        ws.record(root, 'plan.pass', {'note': args.reason or ''})
        print('plan pass recorded; the day is open')
    else:
        rows = plan.items(root)
        if args.json:
            print(json.dumps(rows, indent=1))
            return 0
        for item in rows:
            print(f'{item["score"]:>7}  {item["id"]:<10} {item.get("status", "open"):<8} {item.get("tier", ""):<9} '
                  f'{item.get("goal", ""):<5} {item.get("repo", "")}  {item["title"]}')
        if not rows:
            print('the plan is empty: run /wuwei-plan')
    return 0


def cmd_status(args):
    root = _root()
    rows = board.compute(root, everything=args.all)
    print(json.dumps(rows, indent=1) if args.json else board.text(rows, root))
    return 0


def cmd_owe(args):
    item = plan.owe(_root(), args.where, args.what, args.who, within=args.within, due=args.due)
    print(f'{item["id"]} reply owed to {item["who"]} in {item["where"]}, due {item["due"]}')
    return 0


def cmd_watch(args):
    root = _root()
    if args.record:
        ws.record(root, 'watch.pass', {'summary': args.record})
    passes = ws.rows(root, 'watch.pass')
    open_replies = [r for r in board.replies(root)]
    print(f'last pass: {passes[-1]["ts"] if passes else "never"}; replies owed: {len(open_replies)} '
          f'({sum(1 for r in open_replies if "overdue" in r["gaps"][0]["text"])} overdue)')
    return 0


def cmd_andon(args):
    root = _root()
    if not args.clear and not args.reason:
        raise SystemExit('wuwei: say why: wuwei andon owner/repo --reason "<what is broken for everyone>"')
    board.andon(root, args.repo, args.reason or '', clear=args.clear)
    print(f'andon {"cleared" if args.clear else "raised"} on {args.repo}')
    return 0


def cmd_evidence(args):
    if args.record:
        from wuwei import replay
        gaps = replay.record(_root(), *_ref(args.pr), args.record)
        print(f'recorded {args.pr} in {args.record}/case.json; copy it under tests/replay/ to hold future versions to it')
        return 1 if gaps else 0
    gaps = evidence.blocking(evidence.gaps(_root(), *_ref(args.pr)))
    print(json.dumps(gaps, indent=1) if args.json else '\n'.join(
        f'- {g["text"]}' + ('' if g['actionable'] else ' [waiting]') for g in gaps) or 'no gaps: ready to merge')
    return 1 if gaps else 0


def cmd_sent(args):
    root = _root()
    ws.record(root, 'sent', {'tool': 'outside the session', 'refs': [args.pr.lower()], 'link': args.link})
    ws.cache_put(root, 'board', None)
    print(f'recorded: {args.pr} was posted at {args.link}')
    return 0


def cmd_report(args):
    root = _root()
    print(json.dumps(report.dora(root, args.window), indent=1) if args.dora else report.day(root, args.day))
    return 0


def cmd_close(args):
    path = report.close(_root())
    print(f'checkpoint written: {path}\nlaunch the steward for the retro; plan again any time to reopen the day')
    return 0


def cmd_init(args):
    for line in setup.init(args.directory, cloud=args.cloud, codex=args.codex):
        print(line)
    return 0


def cmd_sync(args):
    from wuwei import sync
    root = _root()
    try:
        print(sync.pull(root))
        print(sync.push(root))
    except RuntimeError as exc:
        print(f'wuwei sync: {exc}', file=sys.stderr)
        return 1
    return 0


def cmd_doctor(args):
    rows = setup.doctor(ws.find())
    for name, status, detail in rows:
        print(f'{status:<5} {name}: {detail}')
    return 2 if any(s == 'fail' for _, s, _ in rows) else 1 if any(s == 'warn' for _, s, _ in rows) else 0


def cmd_config(args):
    root = _root()
    data = ws.set_config(root, args.key, args.value) if args.key else ws.config(root)
    print('\n'.join(f'{k} = {json.dumps(v)}' for k, v in data.items()))
    return 0


def cmd_verify(args):
    broken = ws.verify(_root())
    print('ledger intact' if not broken else f'ledger broken at {", ".join(broken)}')
    return 1 if broken else 0


def cmd_agents(args):
    if args.action == 'build':
        agents.build(PLUGIN)
    stale = agents.stale(PLUGIN)
    print('agents match the charters' if not stale else 'stale: ' + ', '.join(stale))
    return 1 if stale else 0


def version():
    return json.loads((PLUGIN / '.claude-plugin' / 'plugin.json').read_text(encoding='utf-8'))['version']


def main(argv=None):
    if (sys.argv[1:] if argv is None else argv)[:1] == ['--version']:
        print(version())
        return 0
    parser = argparse.ArgumentParser(prog='wuwei', description=f'WUWEI {version()}')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('plan', help='show [id], add, park, drop, done, run, restore, pass or view')
    p.add_argument('action', nargs='?', default='show',
                   choices=('show', 'add', 'park', 'drop', 'done', 'run', 'restore', 'pass', 'view'))
    for name in ('id', 'title'):
        p.add_argument(name, nargs='?')
    for name in ('goal', 'repo', 'why', 'reason', 'promise'):
        p.add_argument(f'--{name}')
    p.add_argument('--accept', action='append', help='an acceptance scenario; repeat for each')
    p.add_argument('--from', dest='source', help="with add: the lead's candidates file")
    p.add_argument('--tier', default='standard')
    for name in ('value', 'time', 'risk', 'size', 'reach', 'impact', 'confidence', 'effort'):
        p.add_argument(f'--{name}', type=float)
    for name in ('--json', '--html'):  # --html with view: print the page for a widget
        p.add_argument(name, action='store_true')
    p.set_defaults(func=cmd_plan)
    p = sub.add_parser('status', help='the board: what each open item still lacks')
    p.add_argument('--json', action='store_true')
    p.add_argument('--all', action='store_true', help='include process gaps (for the watch)')
    p.set_defaults(func=cmd_status)
    p = sub.add_parser('evidence', help='the gaps of one PR, owner/repo#number')
    p.add_argument('pr')
    p.add_argument('--record', metavar='DIR', help='save the case for a replay test')
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=cmd_evidence)
    p = sub.add_parser('report', help='the day report, or --dora')
    p.add_argument('--day')
    p.add_argument('--dora', action='store_true')
    p.add_argument('--window', type=int, default=28)
    p.set_defaults(func=cmd_report)
    sub.add_parser('close', help='checkpoint the day: write the report').set_defaults(func=cmd_close)
    p = sub.add_parser('init', help='create the workspace and merge the harness rules')
    p.add_argument('directory', nargs='?', default='.')
    p.add_argument('--cloud', action='store_true', help='also copy the plugin into .claude/ for cloud sessions')
    p.add_argument('--codex', action='store_true', help='also write the role agents and door rules into .codex/')
    p.set_defaults(func=cmd_init)
    sub.add_parser('sync', help='pull, then push .wuwei/ on the wuwei/state branch').set_defaults(func=cmd_sync)
    sub.add_parser('doctor', help='install, workspace and the strength of each door').set_defaults(func=cmd_doctor)
    p = sub.add_parser('config', help='show, or set one of the five keys')
    for name in ('key', 'value'):
        p.add_argument(name, nargs='?')
    p.set_defaults(func=cmd_config)
    sub.add_parser('verify', help='check the ledger hash chain').set_defaults(func=cmd_verify)
    p = sub.add_parser('sent', help='record a review request posted outside the session, with its link')
    p.add_argument('pr', help='owner/repo#number')
    p.add_argument('link')
    p.set_defaults(func=cmd_sent)
    p = sub.add_parser('owe', help='record a reply someone is waiting for')
    p.add_argument('where', help='the thread link or id')
    p.add_argument('what')
    p.add_argument('--who', required=True)
    p.add_argument('--within', default='4h', help='30m, 4h, 1d')
    p.add_argument('--due', help='an ISO time instead of --within')
    p.set_defaults(func=cmd_owe)
    p = sub.add_parser('watch', help='the last watch pass and replies owed; --record notes a pass')
    p.add_argument('--record', metavar='SUMMARY')
    p.set_defaults(func=cmd_watch)
    p = sub.add_parser('andon', help='pull the cord on one repository: no new builds there until cleared')
    p.add_argument('repo')
    p.add_argument('--reason')
    p.add_argument('--clear', action='store_true')
    p.set_defaults(func=cmd_andon)
    p = sub.add_parser('agents', help='check or build the role agents from the charters')
    p.add_argument('action', nargs='?', default='check', choices=('check', 'build'))
    p.set_defaults(func=cmd_agents)
    p = sub.add_parser('hook', help='called by the harness only')
    p.add_argument('event')
    p.set_defaults(func=lambda args: hook.main(args.event))
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        print(f'wuwei: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
