"""Run or install workspace watch supervision."""

import os
from pathlib import Path
import sys
from xml.sax.saxutils import escape

from wuwei import registry, watch, workspace


def service_platform():
    return sys.platform


def add(subparsers, name, help):
    parser = subparsers.add_parser(name, help=help)
    parser.add_argument('--once', action='store_true', help='Run due work once and return 0/1/2')
    actions = parser.add_subparsers(dest=f'{name}_action')
    install = actions.add_parser('install', help=f'Install and start the user {name} service')
    install.add_argument('--dry-run', action='store_true',
                         help='Print the unit path, unit and service commands without changing anything')
    actions.add_parser('uninstall', help=f'Stop and remove the user {name} service')
    return parser


def register(subparsers):
    add(subparsers, 'watch', 'Supervise workspace activity and owned PRs').set_defaults(func=run)


def run(args):
    return service(args, 'watch', watch.run)


def service(args, name, loop):
    action = getattr(args, f'{name}_action')
    if action is None:
        return loop(once=args.once)
    watch_service = registry.watch_service()
    if args.once:
        raise ValueError('--once cannot be combined with install or uninstall; run bin/wuwei watch --once on its own')
    root = workspace.find_workspace()
    platform = service_platform()
    if platform not in ('darwin', 'linux'):
        raise ValueError(f'{name} service installation supports macOS and Linux; run the service by hand on this platform')
    label, path = workspace.watch_unit(root, platform, name=name)
    if action == 'uninstall':
        if not path.exists():
            return 0
        _remove(path, platform, watch_service, name)
        print(f'{name} uninstalled: {label}')
        return 0
    if path.exists():
        raise ValueError(f'{name} already installed; run {name} uninstall first')
    plugin = Path(__file__).resolve().parents[3]
    command = plugin / 'bin/wuwei'
    if not command.is_file():
        raise OSError(f'{name} executable missing: {command}')
    values = {'@LABEL@': label, '@WORKSPACE@': str(root), '@PLUGIN_ROOT@': str(command.parent.parent),
              '@PATH@': os.environ.get('PATH', ''), '@STDOUT_LOG@': str(root / f'.wuwei/{name}.stdout.log'),
              '@STDERR_LOG@': str(root / f'.wuwei/{name}.stderr.log'), '@COMMAND@': name}
    template = plugin / ('templates/wuwei-watch.plist' if platform == 'darwin' else 'templates/wuwei-watch.service')
    rendered = template.read_text()
    for key, value in values.items():
        if '\n' in value or '\r' in value:
            raise ValueError(f'invalid {name} service value: {key}')
        if platform == 'darwin':
            value = escape(value, {'"': '&quot;'})
        else:
            value = value.replace('\\', '\\\\').replace('"', '\\"')
        rendered = rendered.replace(key, value)
    commands = ([['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(path)]] if platform == 'darwin' else
                [['systemctl', '--user', 'daemon-reload'], ['systemctl', '--user', 'enable', '--now', path.name]])
    if args.dry_run:
        print(f'unit: {path}')
        print(rendered)
        for argv in commands:
            print('$ ' + ' '.join(argv))
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    workspace.atomic_write(path, rendered)
    try:
        for argv in commands:
            watch_service.call(argv)
    except (OSError, ValueError):
        _remove(path, platform, watch_service, name)
        raise
    print(f'{name} installed: {label}')
    return 0


def _remove(path, platform, watch_service, name):
    """Stop the service and delete its unit; service failures are warnings."""
    def call(argv):
        try:
            watch_service.call(argv)
        except (OSError, ValueError) as exc:
            print(f'wuwei {name}: warning: {exc}; run bin/wuwei doctor', file=sys.stderr)
    if platform == 'darwin':
        call(['launchctl', 'bootout', f'gui/{os.getuid()}', str(path)])
    else:
        call(['systemctl', '--user', 'disable', '--now', path.name])
    path.unlink(missing_ok=True)
    if platform == 'linux':
        call(['systemctl', '--user', 'daemon-reload'])
