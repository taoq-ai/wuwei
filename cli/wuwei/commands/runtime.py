"""Invoke the configured runtime port from the CLI."""

import json
import sys

from wuwei import dispatch, registry, workspace
from wuwei.exits import ADAPTER_DATA


def register(subparsers):
    parser = subparsers.add_parser('runtime', help='Dispatch and inspect runtime jobs')
    actions = parser.add_subparsers(dest='action', required=True)
    launch = actions.add_parser('dispatch')
    launch.add_argument('role')
    launch.add_argument('brief')
    launch.add_argument('worktree')
    launch.add_argument('--write', action='store_true')
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
        config = workspace.load_config(root)
        if args.action == 'dispatch':
            role = 'sentinel-' + args.role if args.role in dispatch.ROLES else args.role
            selected = registry.runtime_config(role, config, root)
            adapter = registry.load('runtime', selected)
            response = adapter.dispatch(role, args.brief, args.worktree, args.write, root=root)
        else:
            job = json.loads(args.job)
            selected_name = job.get('runtime') if isinstance(job, dict) else None
            if selected_name is not None:
                registry.validate('runtime', selected_name)
                config = {**config, 'adapters': {**config['adapters'], 'runtime': selected_name}}
            adapter = registry.load('runtime', config)
            if args.action == 'status':
                response = adapter.status(job, root=root)
            elif args.action == 'result':
                response = adapter.result(job, root=root)
            else:
                response = adapter.continue_job(job, args.feedback, root=root)
        if not isinstance(response, registry.Result) or type(response.exit) is not int or response.exit not in (0, 1, 2):
            raise ValueError(f'invalid runtime result; {ADAPTER_DATA}')
        if response.exit:
            print(response.reason or 'runtime operation did not complete; retry; if it repeats, run bin/wuwei doctor', file=sys.stderr)
        else:
            data = response.data
            if args.action == 'dispatch' and selected['adapters']['runtime'] != config['adapters']['runtime']:
                if not isinstance(data, dict):
                    raise ValueError(f'invalid runtime job; {ADAPTER_DATA}')
                data = {**data, 'runtime': selected['adapters']['runtime']}
            print(json.dumps(data, allow_nan=False))
        return response.exit
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f'runtime: {exc}', file=sys.stderr)
        return 2
