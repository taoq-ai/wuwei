"""Check or execute the one fresh-head merge policy."""

import json

from wuwei import merge


def register(subparsers):
    parser = subparsers.add_parser('merge', help='Check or merge an eligible PR')
    parser.add_argument('target', help='PR reference, or check')
    parser.add_argument('pr', nargs='?', help='PR reference after check')
    parser.set_defaults(func=run)


def run(args):
    if args.target == 'check':
        if args.pr is None:
            raise ValueError('usage: wuwei merge check <pr>')
        result = merge.check(args.pr)
    else:
        if args.pr is not None:
            raise ValueError('usage: wuwei merge <pr>')
        result = merge.execute(args.target)
    print(result.reason if result.exit else json.dumps(result.data, sort_keys=True))
    if result.exit == 1 and result.data:  # #668: merge check names the next step
        print(f"Next: {result.data['next']}")
    return result.exit
