"""Run or install workspace watch supervision."""

import hashlib
import os
from pathlib import Path
import sys
from xml.sax.saxutils import escape

from wuwei import registry, watch, workspace


def service_platform():
    return sys.platform


def register(subparsers):
    parser = subparsers.add_parser('watch', help='Supervise workspace activity and owned PRs')
    parser.add_argument('--once', action='store_true', help='Run due work once and return 0/1/2')
    actions = parser.add_subparsers(dest='watch_action')
    actions.add_parser('install', help='Install and start the user watch service')
    actions.add_parser('uninstall', help='Stop and remove the user watch service')
    parser.set_defaults(func=run)


def run(args):
    if args.watch_action is None:
        return watch.run(once=args.once)
    watch_service = registry.watch_service()
    if args.once:
        raise ValueError('--once cannot be combined with install or uninstall')
    root = workspace.find_workspace()
    platform = service_platform()
    if platform not in ('darwin', 'linux'):
        raise ValueError('watch service installation supports macOS and Linux')
    token = hashlib.sha256(str(root).encode()).hexdigest()[:12]
    label = f'wuwei-{token}'
    home = Path.home()
    path = (home / 'Library/LaunchAgents' / f'{label}.plist' if platform == 'darwin' else
            Path(os.environ.get('XDG_CONFIG_HOME', home / '.config')) / 'systemd/user' / f'{label}.service')
    if args.watch_action == 'uninstall':
        if not path.exists():
            return 0
        if platform == 'darwin':
            watch_service.call(['launchctl', 'bootout', f'gui/{os.getuid()}', str(path)])
        else:
            watch_service.call(['systemctl', '--user', 'disable', '--now', path.name])
        path.unlink()
        if platform == 'linux':
            watch_service.call(['systemctl', '--user', 'daemon-reload'])
        print(f'watch uninstalled: {label}')
        return 0
    if path.exists():
        raise ValueError('watch already installed; run watch uninstall first')
    plugin = Path(__file__).resolve().parents[3]
    command = plugin / 'bin/wuwei'
    if not command.is_file():
        raise OSError(f'watch executable missing: {command}')
    values = {'@LABEL@': label, '@WORKSPACE@': str(root), '@PLUGIN_ROOT@': str(command.parent.parent),
              '@PATH@': os.environ.get('PATH', ''), '@STDOUT_LOG@': str(root / '.wuwei/watch.stdout.log'),
              '@STDERR_LOG@': str(root / '.wuwei/watch.stderr.log')}
    template = plugin / ('templates/wuwei-watch.plist' if platform == 'darwin' else 'templates/wuwei-watch.service')
    rendered = template.read_text()
    for key, value in values.items():
        if '\n' in value or '\r' in value:
            raise ValueError(f'invalid watch service value: {key}')
        if platform == 'darwin':
            value = escape(value, {'"': '&quot;'})
        else:
            value = value.replace('\\', '\\\\').replace('"', '\\"')
        rendered = rendered.replace(key, value)
    path.parent.mkdir(parents=True, exist_ok=True)
    workspace.atomic_write(path, rendered)
    if platform == 'darwin':
        watch_service.call(['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(path)])
    else:
        watch_service.call(['systemctl', '--user', 'daemon-reload'])
        watch_service.call(['systemctl', '--user', 'enable', '--now', path.name])
    print(f'watch installed: {label}')
    return 0
