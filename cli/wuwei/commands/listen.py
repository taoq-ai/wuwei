"""Run or install the workspace listener."""

from wuwei import listen, workspace
from wuwei.commands import watch as service


def register(subparsers):
    service.add(subparsers, 'listen', 'Poll the inbound source into the workspace inbox'
                ).set_defaults(func=run)


def run(args):
    if (args.listen_action != 'uninstall' and
            workspace.load_config(workspace.find_workspace())['adapters']['inbound'] == 'none'):
        raise ValueError('listen could not run: adapters.inbound is "none"; configure an inbound source')
    return service.service(args, 'listen', listen.run)
