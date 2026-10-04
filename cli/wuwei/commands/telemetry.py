"""Design 5.13: preview what leaves, turn sharing off, send an attributed week, present proposals."""

from argparse import Namespace
from hashlib import sha256
import json
import sys

from wuwei import state, telemetry, workspace
from wuwei.exits import CLEAN, FINDINGS, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('telemetry', help='weekly usage counts: preview, off, send, proposals')
    actions = parser.add_subparsers(dest='action', required=True)
    for name, text in (('preview', 'print exactly what each sharing mode would send'),
                       ('send', 'open the attributed issue for a final week (owner, host terminal)')):
        action = actions.add_parser(name, help=text)
        action.add_argument('week', nargs='?')
    actions.add_parser('off', help='stop sharing: set telemetry.share to "off"')
    proposals = actions.add_parser('proposals', help="the latest final week's proposals")
    proposals.add_argument('--widget', action='store_true', help='one yes-or-no question per proposal, once')
    parser.set_defaults(func=run)


def run(args):
    try:
        root = workspace.find_workspace()
        config = workspace.load_config(root)
        action = {'preview': _preview, 'off': _off, 'send': _send, 'proposals': _proposals}[args.action]
        return action(root, config, args)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'wuwei telemetry {args.action}: {exc}', file=sys.stderr)
        return UNRUN


def _final(root, week):
    found = telemetry.load_week(root, week) if week else telemetry.latest_final(root)
    if not found or not found.get('final'):
        raise LookupError('no final week yet; wait for the watch to record a finished week')
    return found


def _preview(root, config, args):
    try:
        found = _final(root, args.week)
        anonymous = telemetry.validate(telemetry.payload(found, token=telemetry.token(root)))
    except LookupError as exc:
        print(f'wuwei telemetry preview: {exc.args[0]}', file=sys.stderr)
        return FINDINGS
    except ValueError as exc:
        print(f'wuwei telemetry preview: the payload breaks a rule: {exc}', file=sys.stderr)
        return FINDINGS
    tele = config['telemetry']
    title, body = telemetry.issue(anonymous)
    endpoint = tele['endpoint'] if tele['endpoint'].startswith('https://') else ''
    print(f"mode in force: {tele['share'] or 'not asked (off)'}", '',
          f"anonymous: {f'posts to {endpoint}' if endpoint else 'nothing is sent: no endpoint'}",
          json.dumps(anonymous, indent=2, sort_keys=True), '',
          f"attributed: issue on {tele['repository']} from your gh account (shows your login)",
          title, body, 'off: nothing leaves this machine', sep='\n')
    return CLEAN


def _off(root, config, args):
    from wuwei.commands import setup
    if config['telemetry']['share'] == 'off':
        print('telemetry.share is already "off"')
        return CLEAN
    code = setup.set_value(Namespace(key='telemetry.share', value='"off"'), confirm=lambda *_, **__: True)
    if code == CLEAN:
        state.append_event('telemetry.off', {}, root)
    return code


def _send(root, config, args):
    from wuwei import integrity, registry, security
    tele = config['telemetry']
    try:
        if tele['share'] != 'attributed':
            raise LookupError(('telemetry.share is not "attributed" (anonymous weeks leave from the watch); run '
                              'bin/wuwei config set telemetry.share \'"attributed"\' first'))
        found = _final(root, args.week)
        if found.get('shared'):
            raise LookupError(f"{found['week']} was already shared ({found['shared']}); pass another final week")
    except LookupError as exc:
        print(f'wuwei telemetry send: {exc.args[0]}', file=sys.stderr)
        return FINDINGS
    title, body = telemetry.issue(telemetry.validate(telemetry.payload(found)))
    code, reason = security.outbound({'title': title, 'body': body}, root)
    if code:
        print(reason, file=sys.stderr)
        return code
    if not integrity._host_confirm(sha256(f'{title}\n{body}'.encode()).hexdigest(), prompt=(
            f"Open this issue on {tele['repository']} from your gh account (it shows your login):\n{title}\n{body}")):
        print('wuwei telemetry send: declined; nothing sent', file=sys.stderr)
        return FINDINGS
    result = registry.load('code_host', config).issue(tele['repository'], title, body, root=root)
    if result.exit:
        print(f'wuwei telemetry send: {result.reason}', file=sys.stderr)
        return result.exit
    telemetry.save_week(root, {**found, 'shared': 'attributed'})
    state.append_event('telemetry.shared', {'week': found['week'], 'mode': 'attributed'}, root)
    print(f"Opened {(result.data or {}).get('url', title)}")
    return CLEAN


def _proposals(root, config, args):
    from wuwei import decision
    found = telemetry.latest_final(root)
    if not args.widget:
        rows = found.get('proposals', []) if found else []
        print('\n'.join(f"{row['rule']}: {row['evidence']}\n  {row['command']}" for row in rows)
              or 'No proposals')
        return CLEAN
    if not found or found.get('presented') or not found.get('proposals'):
        print('[]')
        return CLEAN
    widgets = [decision.widget(
        decision.gate(root) + f"Telemetry {found['week']}: {row['evidence']}. Apply it?", 'Telemetry',
        [('Yes', f"Recommended. Run {row['command']} in a host terminal."), ('Skip', 'Nothing changes.')],
        row['command']) for row in found['proposals']]
    telemetry.save_week(root, {**found, 'presented': True})
    state.append_event('telemetry.presented', {'week': found['week'], 'count': len(widgets)}, root)
    print(json.dumps(widgets, indent=2))
    return CLEAN
