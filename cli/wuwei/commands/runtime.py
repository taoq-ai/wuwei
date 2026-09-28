"""Invoke the configured runtime port from the CLI."""

import json
import sys

from wuwei import registry, workspace


def register(subparsers):
    parser = subparsers.add_parser('runtime', help='Dispatch and inspect runtime jobs')
    actions = parser.add_subparsers(dest='action', required=True)
    dispatch = actions.add_parser('dispatch')
    dispatch.add_argument('role')
    dispatch.add_argument('brief')
    dispatch.add_argument('worktree')
    dispatch.add_argument('--write', action='store_true')
    for name in ('status', 'result'):
        command = actions.add_parser(name)
        command.add_argument('job', help='JSON job handle from dispatch')
    resume = actions.add_parser('continue')
    resume.add_argument('job', help='JSON job handle from dispatch')
    resume.add_argument('feedback')
    parser.set_defaults(func=run)


def run(args, *, root=None):
    try:
        root = workspace.find_workspace(root)
        adapter = registry.load('runtime', workspace.load_config(root))
        if args.action == 'dispatch':
            response = adapter.dispatch(args.role, args.brief, args.worktree, args.write, root=root)
        else:
            job = json.loads(args.job)
            if args.action == 'status':
                response = adapter.status(job, root=root)
            elif args.action == 'result':
                response = adapter.result(job, root=root)
            else:
                response = adapter.continue_job(job, args.feedback, root=root)
        if not isinstance(response, registry.Result) or type(response.exit) is not int or response.exit not in (0, 1, 2):
            raise ValueError('invalid runtime result')
        if response.exit:
            print(response.reason or 'runtime operation did not complete', file=sys.stderr)
        else:
            print(json.dumps(response.data, allow_nan=False))
        return response.exit
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f'runtime: {exc}', file=sys.stderr)
        return 2
