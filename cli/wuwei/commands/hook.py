"""Translate Claude Code lifecycle hooks into registered guard calls."""

import json
import os
from pathlib import Path
import re
import shlex
import sys

from wuwei.exits import CLEAN, FINDINGS, UNRUN, DAMAGED, PAYLOAD
from wuwei.guards import EVENTS, SELECTION, discover, profile_result
from wuwei.workspace import ConfigError

# The watch heartbeat's probe calls; their refusals are measurements, not seat refusals.
HEARTBEAT_SESSION = 'wuwei-heartbeat'
# #326: events whose answer to a config.toml that does not load is config_failure.
CONFIG_EVENTS = ('PreToolUse', 'Stop')
# #326: with a broken config these reads still pass, so the session can show the line.
REPAIR_READS = {'Read': 'file_path', 'Grep': 'path', 'Glob': 'path'}


def register(subparsers):
    parser = subparsers.add_parser('hook', help='Run guards for a Claude Code hook')
    parser.add_argument('event', choices=EVENTS)
    parser.set_defaults(func=run)


def run(args):
    try:
        payload = json.load(sys.stdin, parse_constant=invalid_constant)
    except BaseException as exc:
        reason = (f'wuwei hook: {type(exc).__name__}: could not read PostToolUse payload'
                  if args.event == 'PostToolUse' else f'wuwei hook: {type(exc).__name__}: {exc}')
        return refuse(args.event, reason, malformed=True)
    try:
        validate(payload, args.event)
        payload = as_bash(payload)
    except BaseException as exc:
        return refuse(args.event, f'wuwei hook: {type(exc).__name__}: {exc}',
                      malformed=True)
    try:
        from wuwei import env, workspace
        cwd = Path(payload['cwd']).resolve()
        try:
            root = workspace.find_workspace(cwd)
        except FileNotFoundError:
            root = None
        if root is None or not cwd.is_relative_to(root):
            root = workspace.guard_scope(payload)
        if not reaches_workspace(payload, root):
            return CLEAN
        if root is not None:
            env.load(root)
            if args.event in CONFIG_EVENTS:
                try:
                    config = workspace.load_config(root)
                except OSError:
                    pass  # A missing or unreadable file stays the guards' to measure, as before.
                else:
                    if args.event == 'PreToolUse' and payload['session_id'] != HEARTBEAT_SESSION:
                        newer_template(root, payload, config)
        if args.event == 'SubagentStop' and root is not None:
            fill_stop_text(payload)
        token = SELECTION.set((args.event, payload.get('tool_name', '')))
        try:
            guards = discover()
        finally:
            SELECTION.reset(token)
    except BaseException as exc:
        if isinstance(exc, ConfigError) and args.event in CONFIG_EVENTS:
            return config_failure(args.event, payload, str(exc))
        reason = (f'{type(exc).__name__}: could not discover guards' if args.event == 'PostToolUse'
                  else f'wuwei hook: {type(exc).__name__}: {exc}')
        return refuse(args.event, reason, malformed=True)
    selected = [guard for guard in guards if guard.event == args.event]

    def outcome(guard):
        """('skipped' | 'ran' | 'raised', value) for one guard; never raises."""
        try:
            if guard.matcher is not None and not re.fullmatch(guard.matcher, payload.get('tool_name', '')):
                return 'skipped', None
            return 'ran', guard.check(payload)
        except BaseException as exc:
            return 'raised', exc
    if args.event == 'SessionStart':
        # #346: SessionStart's guards are independent reads, each with its own records; run
        # together, one's git and ssh-keygen children and fsyncs overlap the other's work.
        from wuwei.registry import together
        outcomes = together(*(lambda guard=guard: outcome(guard) for guard in selected))
    else:
        outcomes = map(outcome, selected)  # One at a time, in order, as before.
    refusals, context = [], []
    for guard, (how, result) in zip(selected, outcomes):
        if how == 'skipped':
            continue
        try:
            if how == 'raised':
                raise result
            if (not isinstance(result, tuple) or len(result) != 2
                    or type(result[0]) is not int or result[0] not in (CLEAN, FINDINGS, UNRUN)
                    or not isinstance(result[1], str) or (result[0] and not result[1].strip())):
                raise ValueError(f'invalid guard result; expected (0|1|2, message); {PAYLOAD}')
            code, message = result
            if code == FINDINGS and guard.profile_relaxable:
                from wuwei import workspace
                scope = workspace.guard_scope(payload)
                profile = workspace.load_config(scope)['profile'] if scope is not None else 'strict'
                code, message = profile_result(result, profile, scope, payload.get('tool_name'))
        except BaseException as exc:
            code = UNRUN
            message = (f'{type(exc).__name__}: could not run PostToolUse guard'
                       if args.event == 'PostToolUse' else f'{type(exc).__name__}: {exc}')
        if code:
            refusals.append((guard.check, message, code))
        elif message:
            context.append(message)
    # #362: the most specific refusal first: a finding before a could-not-run, integrity last.
    if args.event != 'SessionStart':
        refusals.sort(key=lambda row: (row[2], module(row[0]) == 'integrity'))
    enforced = [(module(check), message, '', code) for check, message, code in refusals]
    if (refusals and args.event != 'SessionStart'
            and payload.get('session_id') != HEARTBEAT_SESSION):
        enforced = posture(payload, refusals, root)
    reasons = [f'{message}\n{line}' if line else message for _, message, line, _ in enforced]
    if args.event == 'SessionStart' and (context or reasons):
        from wuwei.commands.next import HEADER  # Not guards: hook tests replace their __path__.
        parts = sorted(context + reasons, key=lambda text: not text.startswith(HEADER))
        print(json.dumps({'hookSpecificOutput': {
            'hookEventName': args.event, 'additionalContext': '\n'.join(parts)}}))
        if reasons:
            print('\n'.join(reasons), file=sys.stderr)
        return CLEAN
    if reasons and args.event == 'PreToolUse' and payload.get('tool_name') == 'Bash':
        from wuwei.shell import constructed  # #671: only once a Bash call is refused
        inputs = payload.get('tool_input') if isinstance(payload.get('tool_input'), dict) else {}
        try:
            runs = constructed(str(inputs.get('command', '')))
        except Exception:  # the refusal stands without the name
            runs = ''
        if runs:
            reasons[0] += f'\nresolved: {runs}'
    if reasons:
        return refuse(args.event, reasons[0], cwd=payload.get('cwd'),
                      record=payload.get('session_id') != HEARTBEAT_SESSION,
                      refusals=[(guard, message, code) for guard, message, _, code in enforced],
                      payload=payload)
    if args.event == 'Stop' and context:
        print('\n'.join(context), file=sys.stderr)
    return CLEAN


def fill_stop_text(payload):
    """#473: a background seat ends with a SubagentHandback and no last_assistant_message;
    every SubagentStop guard reads the report its transcript holds. Unreadable: left as is,
    and agent_launch.stop stops the seat as unmeasured with the reason."""
    from wuwei.guards import wuwei_role  # Not a guard module: hook tests replace their __path__.
    text = payload.get('last_assistant_message')
    if isinstance(text, str) and text.strip() or not wuwei_role(payload.get('agent_type')):
        return
    from wuwei.brief import stop_text  # SubagentStop of a WUWEI seat only (#346)
    try:
        payload['last_assistant_message'] = stop_text(payload)
    except (OSError, ValueError):
        pass


def newer_template(root, payload, config):
    """#353: one config.newer_template event per session and day when config.toml was
    written by a newer plugin; recording never refuses."""
    try:
        from wuwei import integrity
        found = integrity.newer_template(config)
        if found is None:
            return
        # Only now: watch (brief, discovery, obligations, hashlib) stays off a current install's path.
        from wuwei import state, watch, workspace
        if any(
                row['kind'] == 'config.newer_template' and row['payload'].get('session') == payload['session_id']
                for row in watch.records(workspace.day_dir(root) / 'events.jsonl')):
            return
        state.append_event('config.newer_template', {
            'plugin': found[0], 'template': found[1], 'session': payload['session_id']}, root)
    except Exception as exc:
        print(f'wuwei hook: could not record config.newer_template: {exc}; run bin/wuwei doctor', file=sys.stderr)


def config_failure(event, payload, reason):
    """A config.toml that does not load (#326): Stop prints it and lets the turn end;
    PreToolUse lets ToolSearch and reads of the config and charters through so the session
    can show the line, and refuses everything else with the error."""
    if event == 'Stop':
        print(reason, file=sys.stderr)
        return CLEAN
    if repair_read(payload):
        return CLEAN
    return refuse(event, reason, cwd=payload.get('cwd'),
                  record=payload.get('session_id') != HEARTBEAT_SESSION, payload=payload)


def repair_read(payload):
    """ToolSearch, or a Read, Grep or Glob whose path is a workspace's .wuwei/config.toml,
    its .wuwei/charters directory or a file in it."""
    tool = payload.get('tool_name')
    if tool == 'ToolSearch':
        return True
    inputs = payload.get('tool_input')
    if not isinstance(tool, str) or tool not in REPAIR_READS or not isinstance(inputs, dict):
        return False
    value = inputs.get(REPAIR_READS[tool])
    if not isinstance(value, str) or not value:
        return False
    from wuwei import workspace
    try:
        target = (Path(payload['cwd']) / Path(value).expanduser()).resolve()
        base = workspace.find_workspace(target, use_environment=False) / '.wuwei'
    except (OSError, ValueError, RuntimeError):
        return False
    return target == base / 'config.toml' or target.is_relative_to(base / 'charters')


def reaches_workspace(payload, root):
    """Design 9.1 before any guard parses: the cwd or a file target (root), a
    WUWEI_WORKSPACE selection, or a path word of the call (literal, tilde or the hook's
    own environment variables expanded) lies in, is, or
    directly contains a workspace or managed worktree."""
    if root is not None or 'WUWEI_WORKSPACE' in os.environ:
        return True
    from wuwei import workspace
    cwd = Path(payload['cwd']).resolve()
    inputs = payload.get('tool_input') if isinstance(payload.get('tool_input'), dict) else {}
    words = {inputs.get('notebook_path'), os.environ.get('GIT_DIR'), os.environ.get('GIT_WORK_TREE')}
    if isinstance(inputs.get('command'), str):
        words.update(re.sub(r'^-\w(?=[~./])', '', word)
                     for word in re.split(r'''[\s;&|()<>'"`=\\]+''', inputs['command']))
    # ponytail: each word walks its own parents through workspace.scope; dedupe the walk if
    # a large heredoc shows in the latency figures. Nonliteral targets (cd $P, bare cd,
    # cd -, CDPATH) are not resolved; the code host and the pre-push hook are the anchors.
    for word in words:
        if not isinstance(word, str) or not word:
            continue
        try:
            path = (cwd / Path(os.path.expandvars(word)).expanduser()).resolve()
            if '/' not in word and not path.exists():
                continue
        except (OSError, ValueError, RuntimeError):
            continue
        try:
            if workspace.scope(path) is not None or path.is_dir() and workspace.contains_workspace(path):
                return True
        except Exception:
            return True  # A broken marker or anchor is WUWEI-shaped; the guards report it.
    return False


def module(check):
    return check.__module__.rsplit('.', 1)[-1]


def posture(payload, refusals, root):
    """#331, at the point #308 shadow mode used: per refusal, off drops it, warn records
    guard.would_refuse and lets the call through, block enforces it with its posture line.
    Returns (guard, reason, line, exit); the config is read only because a guard refused."""
    from wuwei import state, workspace
    from wuwei.guards import MERGE, NO_REVIEWER, RAISE, RECORDS_FLOOR, level
    try:
        if root is None:
            raise LookupError('no workspace; run bin/wuwei init')
        config = workspace.load_config(root)
        name, levels = workspace.posture(config)
    except BaseException:  # No workspace or an unreadable config enforces, as before #331.
        return [(module(check), reason, '', code) for check, reason, code in refusals]
    from wuwei.shell import UNKNOWN_GIT, UNPARSED, WORKSPACE_ROOT
    enforced, shown, seen, opaque = [], None, set(), None

    def opaque_reason():
        """#530: what the guards could not read in a call naming no publish target, else ''."""
        try:
            from wuwei import shell
            from wuwei.guards import deploy
            command, cwd = payload['tool_input']['command'], payload['cwd']
            what = shell.unreadable(command, cwd)
            if not what or deploy.floor_named(command + '\n' + (shell.script_text(command, cwd) or ''), config):
                return ''
            return f'opaque: {what}; the guards could not read it, so it ran with this warning (strict refuses it)'
        except Exception:  # fail closed: the refusal stands
            return ''
    for check, reason, code in refusals:
        guard, area, decided, line = level(check, levels)
        if reason.startswith(RECORDS_FLOOR):
            line = 'posture: records = block (floor; no setting lowers it)'
        elif line.endswith('(owner-only action; no setting lowers it)') and name != 'strict' \
                and not reason.startswith(MERGE):
            line = ''  # #530: below strict an owner-only refusal names its card or its fix
        if guard == 'pr' and (reason == NO_REVIEWER or reason.startswith(RAISE)):
            # #530: raising a PR is gated by evidence under the publish area, never owner-only.
            decided, line = levels['publish'], f'posture: publish = {levels["publish"]} (set security.areas.publish)'
        if reason == NO_REVIEWER or reason.startswith('publish: '):
            line = ''  # It names its own ways out (#478: the owner's card); still blocked.
        if guard == 'outward' and reason.startswith('outward: draft '):
            line = f'posture: {area} = {decided}; a draft is one card away'  # #526: a row lowers it.
        # #347, #470: decided by the reason, not the area; only deploy says unknown git
        if reason in (UNPARSED, WORKSPACE_ROOT) or guard == 'deploy' and reason.startswith(UNKNOWN_GIT):
            if reason in seen:
                continue
            seen.add(reason)
            decided = 'block' if reason != WORKSPACE_ROOT and name == 'strict' else 'warn'
            line = ''
        elif (area == 'publish' and code == UNRUN and name != 'strict'
              and payload.get('tool_name') == 'Bash'
              and (opaque := opaque_reason() if opaque is None else opaque)):
            if opaque in seen or UNPARSED in seen:
                continue
            seen.update((opaque, UNPARSED))
            reason, decided, line = opaque, 'warn', ''
        if decided == 'off':
            continue
        if decided == 'block':
            enforced.append((guard, reason, line, code))
            continue
        try:
            if shown is None:
                shown = redacted_target(payload, root)
            state.append_event('guard.would_refuse', {
                'guard': guard, 'area': area, 'level': decided, 'posture': name,
                'reason': reason, 'exit': code, 'target': shown, 'session': payload['session_id'],
                'item': claimed(root, payload['session_id'])}, root)
        except BaseException as exc:
            print(f'wuwei hook: could not record shadow refusal: {exc}; run bin/wuwei doctor', file=sys.stderr)
            enforced.append((guard, reason, line, code))
    return enforced


def redacted_target(payload, root):
    """The normalised target as refusal records store it, credentials and canaries redacted."""
    from wuwei import security
    from wuwei.redact import redact
    return security.redact(redact(target(payload)), security.load(root))


def target(payload):
    """The normalised Bash command, else the file path, else the tool or event name."""
    inputs = payload.get('tool_input') if isinstance(payload.get('tool_input'), dict) else {}
    command = inputs.get('command')
    if isinstance(command, str):
        from wuwei import shell
        try:
            return '; '.join(shlex.join(found.argv) for found in shell.normalize(command))
        except Exception:
            return command
    return next((inputs[key] for key in ('file_path', 'notebook_path', 'path')
                 if isinstance(inputs.get(key), str)),
                payload.get('tool_name') or payload['hook_event_name'])


def claimed(root, session):
    """The first item this session claims, or None; never blocks a shadowed refusal."""
    from wuwei import state
    try:
        claims = state.read_state(root).get('claims', {})
        return next((item for item, holder in sorted(claims.items()) if holder == session), None)
    except Exception:
        return None


def invalid_constant(value):
    raise ValueError(f'invalid JSON constant; {PAYLOAD}')


def validate(payload, event):
    if not isinstance(payload, dict):
        raise ValueError(f'hook payload must be a JSON object; {PAYLOAD}')
    for field in ('session_id', 'transcript_path', 'cwd', 'hook_event_name'):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise ValueError(f'missing or invalid {field}; {DAMAGED}')
    if payload['hook_event_name'] != event:
        raise ValueError(f'hook_event_name does not match command event; {PAYLOAD}')


TERMINAL = 'mcp__terminal__run_in_terminal'  # #727: types one shell command line


def as_bash(payload):
    """#727: a terminal tab's command is judged as the Bash call it types, in the tab's cwd."""
    if payload.get('tool_name') != TERMINAL or payload['hook_event_name'] != 'PreToolUse':
        return payload
    inputs = payload.get('tool_input')
    if (not isinstance(inputs, dict) or not isinstance(inputs.get('command'), str)
            or not isinstance(inputs.get('cwd', ''), str)):
        raise ValueError(f'terminal command and cwd must be strings; {PAYLOAD}')
    cwd = Path(payload['cwd']) / Path(inputs.get('cwd') or '.').expanduser()
    return {**payload, 'tool_name': 'Bash', 'tool_input': {'command': inputs['command']},
            'cwd': str(cwd)}


def refuse(event, reason, *, malformed=False, cwd=None, record=True, refusals=(), payload=None):
    print(reason, file=sys.stderr)
    if event == 'SessionStart':
        print(json.dumps({'hookSpecificOutput': {
            'hookEventName': event, 'additionalContext': f'session unmeasured: {reason}'}}))
        return CLEAN
    if event == 'PreToolUse' and not malformed and record:
        from wuwei import state, workspace
        try:
            root = workspace.find_workspace(cwd)
        except FileNotFoundError:
            root = None
        if root is not None:
            details = {'reason': reason}
            if refusals:
                details['refusals'] = [{'guard': guard, 'reason': message, 'exit': code}
                                   for guard, message, code in refusals]
                try:
                    details['target'] = redacted_target(payload, root)
                except Exception:
                    pass  # wuwei why prints "not recorded"; never lose the refusal over its target.
            try:
                state.append_event('hook.refusal', details, root)
            except BaseException as exc:
                print(f'wuwei hook: could not record refusal: {exc}; run bin/wuwei doctor', file=sys.stderr)
    if event == 'PreToolUse':
        print(json.dumps({'hookSpecificOutput': {
            'hookEventName': event, 'permissionDecision': 'deny',
            'permissionDecisionReason': reason}}))
    elif event in ('Stop', 'SubagentStop'):
        print(json.dumps({'decision': 'block', 'reason': reason}))
    # Ordinary PreCompact findings must not prevent compaction (design 4.1).
    return FINDINGS if event == 'PreCompact' and not malformed else UNRUN
