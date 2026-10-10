"""Keep state writes in the CLI and persistent directory changes in the workspace."""

from itertools import chain
import os
from pathlib import Path
import re
import shlex
import sys

from wuwei.guards import Guard
from wuwei.shell import WORKSPACE_ROOT
from wuwei.workspace import contains_workspace, worktree_workspace
from wuwei.exits import DAMAGED, PAYLOAD


_STATE_HINT = ('State and config files are protected; use the wuwei CLI for state changes; '
               'owner edits run outside agent tools.')
# Pattern strings compile on first use (re's cache); most Bash calls never reach them.
# #647: a seat's own scratch scripts are not state, unless the path climbs out with ..
_SCRATCH = r'[\\/]scratch[\\/](?![^\s\x27"]*\.\.)'
_STATE_MENTION = (r'(?i)state\.json|state\.snapshot\.json|events\.jsonl|traces\.jsonl|ledger\.jsonl|'
                  rf'\.wuwei(?!{_SCRATCH})')
_STATE_GLOB = rf'(?i)\.w(?!uwei{_SCRATCH})[\w*?\[]'
_DYNAMIC = r'\$\(|[`*?\[]'
_WRITE_CONSTRUCT = (
    r'>|\b(?:tee|cp|mv|dd|truncate|ln|install|rsync|rm|patch)\b|'
    r'\bsed\s+(?:--in-place\b|-[^\s]*i)')


def _text(value, name):
    if not isinstance(value, str) or not value or '\0' in value:
        raise ValueError(f'missing or invalid {name}; {PAYLOAD}')
    return value


def _wuwei_action(argv):
    program = Path(argv[0]).name if argv else ''
    if program == 'wuwei':
        return argv[1:]
    if re.fullmatch(r'(?:python|pypy)[\d.]*', program):
        for index, arg in enumerate(argv[1:], 1):
            if arg == '-m' and argv[index + 1:index + 2] == ['wuwei']:
                return argv[index + 2:]
            if re.fullmatch(r'-[A-Za-z]*mwuwei', arg):
                return argv[index + 1:]
            if not arg.startswith('-') or arg in ('-c', '-m'):
                break
    return None


_OWNER_ACTIONS = {
    ('decision', 'outcome'): ('The owner records a decision outcome, outside agent tools; show it with bin/wuwei '
                              'decision show <id> --widget. The owner runs bin/wuwei decision outcome <id> '
                              '<option> in a host terminal.'),
    ('drafts', 'approve'): ('The owner approves a draft, outside agent tools; list drafts with bin/wuwei drafts. '
                            'The owner runs bin/wuwei drafts approve <id> in a host terminal.'),
    ('grants', 'revoke'): ('The owner revokes a grant, outside agent tools; list grants with bin/wuwei grants. '
                           'The owner runs bin/wuwei grants revoke <n> in a host terminal.'),
    ('drafts', 'drop'): ('The owner drops a draft, outside agent tools; list drafts with bin/wuwei drafts. '
                         'The owner runs bin/wuwei drafts drop <id> in a host terminal.'),
    ('mcp', 'decide'): ("MCP decisions are the owner's, outside agent tools: show the request, and the owner "
                        'runs bin/wuwei mcp decide <id> <option> in a host terminal.'),
    # A whole group: decide's verb position holds the D-n (#354).
    ('decide', ''): ('The owner answers decisions, outside agent tools; show it with bin/wuwei decision show '
                     '<id> --widget. The owner runs bin/wuwei decide <id> <option> in a host terminal.'),
    ('integrity', 'reconfirm'): ('The owner reconfirms integrity, outside agent tools: the owner '
                                 'runs bin/wuwei integrity reconfirm in a host terminal.'),
    ('state', 'recover'): ('The owner recovers state, outside agent tools: the owner runs bin/wuwei '
                           'state recover in a host terminal; bin/wuwei doctor shows what is damaged.'),
    # An uninstalled watch reads as off, so a seat could silence a dead-watch page.
    ('watch', 'uninstall'): ('Watch uninstall is an owner action, outside agent tools: the owner runs bin/wuwei '
                             'watch uninstall in a host terminal.'),
    # An uninstalled listener reads as off, so a seat could silence a dead-listener report.
    ('listen', 'uninstall'): ('Listener uninstall is an owner action, outside agent tools: the owner runs '
                              'bin/wuwei listen uninstall in a host terminal.'),
    ('goals', 'edit'): ('The owner edits owner memory on the host, outside agent tools; propose the change. '
                        'The owner runs bin/wuwei goals edit in a host terminal.'),
    ('voice', 'edit'): ('The owner edits owner memory on the host, outside agent tools; propose the change. '
                        'The owner runs bin/wuwei voice edit in a host terminal.'),
    # An acknowledged refusal stops paging, so a seat could silence an impostor alert.
    ('remote', 'ack'): ('Remote acknowledgements are an owner action, outside agent tools: the owner runs '
                        'bin/wuwei remote ack in a host terminal.'),
    # config.toml holds executed commands and merge eligibility; seats run wuwei promote.
    ('config', 'promote'): ('The owner promotes calibration, outside agent tools: the owner runs '
                            'bin/wuwei config promote in a host terminal.'),
    ('config', 'set'): ("Config edits are the owner's answer on a card (#529). The planner asks bin/wuwei "
                        'calibrate --questions <id> or a decision with options titled <key> = <value>. Then it '
                        "runs the card's record command; under strict the owner runs bin/wuwei config set <key> "
                        '<value> in a host terminal.'),
    ('config', 'add-repo'): ("Config edits are the owner's, outside agent tools; propose the repository. The owner "
                             'runs bin/wuwei config add-repo --name <owner/repo> --path <dir> --branch <branch> in a host terminal.'),
    # Only the owner lowers the spec requirement for one item (5.10); the planner links an existing
    # ticket (5.11, #636) below strict; other plan verbs are seat commands.
    ('plan', 'set'): ('Spec overrides are an owner action, outside agent tools: the owner runs bin/wuwei plan '
                      'set <item> spec=skipped --reason <why> in a host terminal. To link an existing ticket, '
                      "the planner runs bin/wuwei plan set <item> ticket=<id> after the owner's card answer; "
                      'under strict the owner runs it in a host terminal. A seat or the planner records '
                      "owner_merge=true itself; clearing it (owner_merge=false) is the owner's, in a host terminal."),
    # #636: item tickets are the planner's; a class create (--bug, --triage, --follow-up) is a seat's.
    ('tracker', 'create'): ("Item tickets are the planner's (#636): a seat hands the item back to the planner, "
                            "which proposes the ticket on the item's card and opens it on the owner's answer. "
                            'A seat opens a linked bug with bin/wuwei tracker create --bug <item> "<title>" '
                            '--evidence <file:line>. Under strict the owner runs bin/wuwei tracker create '
                            '<item> in a host terminal.'),
    # An empty verb is the whole group: setup's flags take values, which _pair reads as a verb.
    # An applied forgetting archives a note or drops a charter rule (design 5.14).
    ('memory', 'forget'): ('The owner decides what memory to forget, outside agent tools; show the proposals with '
                           'bin/wuwei consolidate --widget. The owner runs bin/wuwei memory forget <id> '
                           'apply|keep in a host terminal.'),
    ('setup', ''): ('Setup writes config.toml, an owner action outside agent tools: the owner runs bin/wuwei '
                    'setup in a host terminal.'),
    # #492: listing a connector and proposing it is the planner's; strict asks the card.
    ('outbound', 'learn'): ('The registered planner session learns connectors, outside seats; hand back to the '
                            'planner, which runs bin/wuwei outbound learn. The owner can run it in a host terminal.'),
    ('telemetry', 'send'): ('The owner sends telemetry, outside agent tools; show the payload with bin/wuwei '
                            'telemetry preview. The owner runs bin/wuwei telemetry send in a host terminal.'),
}
# #492: config set on these keys gets this reason instead of the table's.
GUARD_KEYS = ('outward', 'security', 'outbound', 'grants')
GUARD_CONFIG = ("Guard settings (outward, outbound, security, grants) are the owner's. An agent tool changes "
                'them only through a card the owner answered (#529); for an unknown connector, channel or '
                'person the planner runs bin/wuwei outbound learn. For another value it asks a decision with '
                'options titled <key> = <value> and runs bin/wuwei config set <key> <value> --from-card D-n.')
_OWNER_GROUPS = {group for group, _ in _OWNER_ACTIONS}
_OWNER_VERBS = tuple(sorted({verb for _, verb in _OWNER_ACTIONS if verb}))
# Owner words as tokens; `_` or `.` may precede them so python snippets such as
# goals.owner_edit( stay relevant.
_OWNER_VERB = r'(?<![A-Za-z0-9])(?:' + '|'.join(_OWNER_VERBS) + r')(?![A-Za-z0-9])'
_OWNER_GROUP = r'(?<![A-Za-z0-9])(?:' + '|'.join(sorted(_OWNER_GROUPS)) + r')(?![A-Za-z0-9])'
_INTERPRETER = r'(?:python|pypy)[\d.]*|node|perl|ruby|php|lua'
# Any mention of the CLI word, path segments included, or a dotted owner call such as
# integrity.reconfirm(); relevance starts here.
_WUWEI = re.compile(r'\bwuwei\b|-[A-Za-z]*mwuwei\b|\b(?:'
                    + '|'.join(rf'{g}\.{v}' for g, v in _OWNER_ACTIONS if v) + r')\b')
# The CLI itself: a path segment such as cli/wuwei/x or .wuwei is a read, not the CLI.
_CLI_WORD = r'(?<![\w.-])wuwei(?![\w/.-])|-[A-Za-z]*mwuwei\b|\b(?:from|import)\s+wuwei\b'
# The CLI with a non-literal group or verb: relevant with no verb in the text.
_CLI_NONLITERAL = (r'(?<![\w.-])wuwei(?:\s+-\S*)*(?:\s+(?:' + '|'.join(sorted(_OWNER_GROUPS))
                   + r'))?(?:\s+-\S*)*\s+[$`]')
# Programs whose arguments are patterns or text, never run (except rg --pre, checked in
# _write_targets), and that write no file by operand or flag (sort -o, uniq's output
# operand and tee do, so they are not here). #471: shell.reads adds the classifier's
# read-only words (cat, jq, sed -n Np, find without an action).
_READERS = ('grep', 'rg', 'echo', 'printf', 'head', 'tail', 'wc', 'cut', 'tr')


def _positional(words):
    # The value after --workspace is a path, not the group (#354).
    return [word for prev, word in zip(['', *words], words)
            if not word.startswith('-') and prev != '--workspace']


def _pair(words):
    return tuple((_positional(words) + ['', ''])[:2])


def _owner_reason(pair):
    """The owner-table reason for a (group, verb) pair, a whole-group row included."""
    return _OWNER_ACTIONS.get(pair) or _OWNER_ACTIONS.get((pair[0], ''))


def _seat_docs_set(action):
    """#419: plan set <item> docs=<value> [--reason <why>] is a seat command; spec= stays the
    owner's. Only this literal shape passes, so no later word can become the assignment."""
    rest = list(action[4:])
    return (len(action) >= 4 and list(action[:2]) == ['plan', 'set'] and not action[2].startswith('-')
            and action[3].startswith('docs=')
            and (not rest or len(rest) == 2 and rest[0] == '--reason'
                 or len(rest) == 1 and rest[0].startswith('--reason='))
            and not any(re.search(r'[$`*?\[{]', word) for word in action))


def _seat_owner_merge(action):
    """#678: the literal plan set <item> owner_merge=true; it only narrows what WUWEI may merge."""
    return (len(action) == 4 and list(action[:2]) == ['plan', 'set'] and not action[2].startswith('-')
            and action[3] == 'owner_merge=true' and not re.search(r'[$`*?\[{]', action[2]))


def _planner_pace_set(action):
    """#579: the literal plan set pace=<word>, nothing after it; the planner's two-way choice."""
    return (len(action) == 3 and list(action[:2]) == ['plan', 'set']
            and re.fullmatch(r'pace=[a-z]+', action[2]) is not None)


def _seat_class_create(action):
    """#636: tracker create with one class flag (before any --) is a seat command."""
    words = list(action[:action.index('--')] if '--' in action else action)
    return (list(action[:2]) == ['tracker', 'create']
            and sum(word in ('--bug', '--triage', '--follow-up') for word in words) == 1
            and not any(re.search(r'[$`*?\[{]', word) for word in action))


def _planner_ticket(action):
    """#636: the literal tracker create <item> or plan set <item> ticket=<id>, nothing more."""
    action = list(action)
    return ((len(action) == 3 and action[:2] == ['tracker', 'create']
             or len(action) == 4 and action[:2] == ['plan', 'set'] and action[3].startswith('ticket='))
            and not action[2].startswith('-')
            and not any(re.search(r'[$`*?\[{]', word) for word in action))


def _strict(cwd):
    """The workspace posture is strict; an unreadable one counts as strict (the owner runs it)."""
    from wuwei import workspace
    try:
        root = _workspace(cwd) or worktree_workspace(cwd)
        return root is None or workspace.posture(workspace.load_config(root))[0] == 'strict'
    except (OSError, ValueError):
        return True


def _owner_relevant(text, script=False):
    """Text only: the CLI word plus an owner group and verb, a non-literal CLI word, or xargs."""
    from wuwei.shell import mentions
    stripped = re.sub(r"['\"\\]", '', text)
    return bool(_WUWEI.search(stripped) and (
        re.search(_CLI_NONLITERAL, stripped) or mentions(text, ('xargs',), script=script)
        or (re.search(_OWNER_GROUP, stripped) or mentions(text, sorted(_OWNER_GROUPS), script=script))
        and (re.search(_OWNER_VERB, stripped) or mentions(text, _OWNER_VERBS, script=script))))


# #357, #354, #493: records the planner may write from its own answered gate question.
_GATE_EDITS = {('goals', 'edit'), ('voice', 'edit'), ('mcp', 'decide'), ('decide', ''),
               ('drafts', 'approve'), ('drafts', 'drop'), ('config', 'set')}


def _gate_edits(payload, root):
    """(topics the planner's gate asked, caller is the planner): only today's registered
    planner session, never a seat; strict records nothing, so the owner runs it."""
    from wuwei import sessions
    if root is None or 'agent_id' in payload:
        return frozenset(), False
    return sessions.gate_topics(root, payload.get('session_id'))


def _owner_action(commands, text, relevant, cwd, script=False, edits=(frozenset(), False)):
    """One rule for every owner-only action; (code, reason) or None."""
    from wuwei.commands import read_only
    from wuwei.shell import _launcher, is_opaque, mentions, reads, snippet_write
    # normalize unwraps xargs, so a CLI command may take its group or verb from stdin.
    xargs = relevant and mentions(text, ('xargs',), script=script)
    unseen = len(_WUWEI.findall(re.sub(r"['\"\\]", '', text)))
    readers = [bool(c.argv) and (Path(c.argv[0]).name in _READERS
                                or reads(c.argv, cwd) and snippet_write(c.argv) != '')
               for c in commands]
    # A pipe feeds an executor unless every later stage is a reader with no redirect.
    feeds = [False] * len(commands)
    for index in range(len(commands) - 2, -1, -1):
        feeds[index] = commands[index].separator == '|' and (
            not readers[index + 1] or bool(commands[index + 1].writes) or feeds[index + 1])
    for index, command in enumerate(commands):
        argv = command.argv
        named = len(_WUWEI.findall(' '.join([*argv, *command.env.values()])))
        # A reader's mentions are only text when it stands alone: no redirect, no group or
        # subshell (scope depth 1, or 2 for a top-level pipe stage), no pipe into an executor.
        piped = command.separator == '|' or index > 0 and commands[index - 1].separator == '|'
        if not readers[index] or (not command.writes and not feeds[index]
                                  and len(command.scope) == (2 if piped else 1)):
            unseen -= named
        action = _wuwei_action(argv)
        # A renamed or symlinked launcher is the CLI too; checked only for a literal owner pair.
        if (action is None and argv and '/' in argv[0] and _owner_reason(_pair(argv[1:]))
                and _launcher(Path(cwd, argv[0]), cwd)):
            action = argv[1:]
        if action is None:
            program = Path(argv[0]).name if argv else ''
            if not relevant or readers[index]:
                continue
            # A directory such as the cli/wuwei package is read, not run.
            words = [word for word in argv[1:]
                     if not ('/' in word and Path(word).name == 'wuwei' and Path(cwd, word).is_dir())]
            if program == 'git':
                # A commit message or a search pattern is not a wuwei action.
                words = [word for before, word in zip([''] + words, words)
                         if not re.fullmatch(r'-[A-Za-z]*m|--message|--grep|-[SG]', before)
                         and not re.fullmatch(r'--(?:message|grep)=.*|-[A-Za-z]*m.+|-[SG].+', word, re.S)]
            # Code from stdin, a heredoc or an inline flag is unseen; a module or file operand is not.
            hidden = (is_opaque(argv) and '-m' not in argv[1:]
                      or re.fullmatch(_INTERPRETER, program) and (named or any(
                          re.fullmatch(r'-(?:[a-zA-Z]*[ceEpr]|-eval)(?:=.*)?', arg, re.S) for arg in argv[1:])))
            if hidden or re.search(_CLI_WORD, ' '.join(words)):
                return 2, ('Opaque owner action: write bin/wuwei <group> <verb> as a plain command so the '
                           'guard can read it; owner actions run in a host terminal.')
            continue
        group, verb = _pair(action)
        if xargs and not (re.fullmatch(r'[a-z][\w-]*', group) and (
                group not in _OWNER_GROUPS or re.fullmatch(r'[a-z][\w-]*', verb))):
            return 2, ('Input-driven owner action: write bin/wuwei <group> <verb> literally instead of from '
                       'input; owner actions run in a host terminal.')
        if re.search(r'[$`]', group) or group in _OWNER_GROUPS and re.search(r'[$`]', verb):
            return 2, ('Not a literal owner action: write bin/wuwei <group> <verb> without variables; owner '
                       'actions run in a host terminal.')
        if read_only(action):  # #348: --help prints usage and runs nothing
            continue
        if (reason := _owner_reason((group, verb))) and not (not xargs and (
                _seat_docs_set(action) or _seat_class_create(action) or _seat_owner_merge(action))):
            if (group, verb) == ('outbound', 'learn') and edits[1]:
                continue  # The registered planner session, in any posture.
            # #579: the registered planner changes the day's pace below strict; strict asks nothing.
            # #636: so it attaches an item ticket after the owner's card answer.
            if (not xargs and (_planner_pace_set(action) or _planner_ticket(action)) and edits[1]
                    and not _strict(cwd)):
                continue
            if (group, verb) == ('config', 'set') and (
                    _positional(action)[2:3] or [''])[0].split('.')[0] in GUARD_KEYS:
                reason = GUARD_CONFIG
            if ((group, verb) in _GATE_EDITS or (group, '') in _GATE_EDITS) and edits[1]:
                if group in edits[0] and any(word == '--file' or word.startswith('--file=')
                                             for word in action):
                    continue
                # Every id word must have been asked, so a --note D-1 cannot carry another record.
                ids = [word for word in action if re.fullmatch(r'D-[1-9][0-9]*|draft-[0-9a-f]{32}', word)]
                if (group, verb) == ('drafts', 'approve'):
                    # #493: approve needs the owner's Send answer; --file/--edit needs Send with an edit.
                    edited = any(word in ('--file', '--edit') or word.startswith('--file=') for word in action)
                    ids = [word + (':edit' if edited else ':send') for word in ids]
                if group in ('mcp', 'decide', 'drafts') and ids and set(ids) <= edits[0]:
                    continue
                # #529: the card the planner asked; the CLI checks the owner's answer itself.
                cards = [value for flag, value in zip(action, action[1:]) if flag == '--from-card']
                cards += [word.split('=', 1)[1] for word in action if word.startswith('--from-card=')]
                if ((group, verb) == ('config', 'set') and not xargs and len(cards) == 1
                        and re.fullmatch(r'D-[1-9][0-9]*', cards[0]) and cards[0] in edits[0]):
                    continue
                return 1, f'{reason} Run it in a host terminal: {shlex.join(argv)}'
            return 1, reason
    # #471: a call made only of readers runs nothing, so a mention in its input is data.
    if relevant and unseen > 0 and not all(readers):
        # A CLI mention sits in a heredoc, comment or other input no argv shows.
        return 2, ('Opaque owner action: write bin/wuwei <group> <verb> as a plain command so the '
                   'guard can read it; owner actions run in a host terminal.')
    return None


def _input(payload, field):
    value = payload.get('tool_input')
    if not isinstance(value, dict):
        raise ValueError(f'missing or invalid tool_input; {PAYLOAD}')
    return value.get(field)


def _path(value, cwd):
    _text(value, 'path')
    if value.startswith('~'):
        raise ValueError('use a literal path instead of tilde expansion')
    return cwd / value


def _protected_name(path, directories=False):
    parts = tuple(part.casefold() for part in path.parts)
    for index, part in enumerate(parts):
        if part != '.wuwei':
            continue
        tail = parts[index + 1:]
        if tail in (('config.toml',), ('env',), ('security.json',), ('.gitignore',), ('merge.lock',), ('executable',), ('calibration.json',), ('graph.json',)) or tail[:1] == ('generated',):
            return True
        if tail[:1] in (('integrity',), ('.git',), ('ziran',), ('inbox',), ('metrics',)):
            return True
        if tail in (('memory', 'voice.md'), ('memory', 'goals.md'), ('memory', 'cruise.json')):
            return True
        if tail and tail[0] == 'archive':
            return True
        if tail[:2] == ('memory', 'archive'):
            return True
        if tail[:2] in (('memory', 'snapshots'), ('memory', 'digests')) or tail == ('memory', 'forget.json'):
            return True
        if directories and (not tail or (len(tail) in (1, 2) and tail[0] == 'days')):
            return True
        if directories and tail in (('memory',), ('memory', 'notes'), ('memory', 'digests'),
                                    ('memory', 'archive'), ('charters',)):
            return True
        if len(tail) == 3 and tail[0] == 'days' and tail[2] in ('state.json', 'state.snapshot.json', 'events.jsonl', 'traces.jsonl', 'undo.jsonl', 'proposal.json', 'plan.md', 'goals.md', 'steward-decisions.json', 'interview.json', 'profile.json'):
            return True
        if tail in (('memory', 'ledger.jsonl'), ('memory', 'targets.json'), ('memory', 'rehearsals.json')):
            return True
        if len(tail) == 2 and tail[0] == 'charters' and tail[1].endswith('.md'):
            return True
        if len(tail) == 3 and tail[:2] == ('memory', 'notes') and tail[2].endswith('.md'):
            return True
    return False


def _hint(path):
    """#349: the one-line reason for a refused write names the command that makes it."""
    parts = tuple(part.casefold() for part in path.parts)
    tail = parts[len(parts) - parts[::-1].index('.wuwei'):] if '.wuwei' in parts else ()
    if tail == ('config.toml',):
        return ('config.toml is protected: the owner runs wuwei config set <key> <value> '
                'in a host terminal, outside agent tools.')
    if tail[:1] == ('days',) and tail[-1:] in (('state.json',), ('state.snapshot.json',)):
        return ('Day state is protected: change it with the wuwei CLI, wuwei state set '
                '<path> <value> or wuwei state transition <item> <phase>.')
    if tail[:1] == ('days',) and tail[-1:] == ('events.jsonl',):
        return 'events.jsonl is protected: append with the wuwei CLI, wuwei event <kind> [payload].'
    if tail[:1] == ('ziran',):
        return ('Registry records are protected: wuwei mcp check writes them and the owner '
                'runs wuwei mcp decide in a host terminal, outside agent tools.')
    if tail in (('memory', 'goals.md'), ('memory', 'voice.md')):
        return ('goals.md and voice.md are protected: after the morning gate the planner runs '
                'wuwei goals edit --file <draft> or wuwei voice edit --file <draft>; other '
                "edits are the owner's, outside agent tools.")
    if tail == ('graph.json',):
        return ('graph.json is the register of people, channels and tools: bin/wuwei config set, the cards '
                'and bin/wuwei init --upgrade write it; bin/wuwei who reads it.')
    if tail == ('memory', 'rehearsals.json'):
        return ('rehearsals.json is the undo rehearsal ledger (design 5.8 Measured reversibility): '
                'only wuwei undo rehearse and wuwei undo write it.')
    if tail == ('memory', 'targets.json'):
        return ('targets.json is the seen set (design 5.8.1 Novelty): the CLI writes it from owner '
                'answers, drafts approve and init --upgrade.')
    if tail[:1] == ('integrity',):
        return ('Integrity records are protected: the owner runs wuwei integrity reconfirm '
                'in a host terminal, outside agent tools.')
    return _STATE_HINT


def _protected(value, cwd, root, directories=False):
    path = _path(value, cwd).resolve()
    if _protected_name(path, directories):
        return True
    root = root or _workspace(path)
    if root is not None:
        from wuwei import security
        data = security.load(root)
        if data:
            decoy = root / '.wuwei' / data['honeytoken_path']
            if (path == decoy or directories and decoy.is_relative_to(path)
                    or path.is_file() and decoy.is_file() and os.path.samefile(path, decoy)):
                return True
    if directories and path.is_dir():
        if root is not None and root.is_relative_to(path):
            return True
        # ponytail: one level only; a recursive walk hung the hook on rm -rf /. Deeper
        # containers are caught when the session runs in the workspace or an anchored worktree.
        if (path / '.wuwei').is_dir() or contains_workspace(path):
            return True
    # Only multiply linked files need a scan; ordinary commands pay no tree walk.
    if root is not None and path.is_file() and path.stat().st_nlink > 1:
        return any(_protected_name(candidate) and os.path.samefile(path, candidate)
                   for candidate in (root / '.wuwei').rglob('*') if candidate.is_file())
    return False


def _workspace(cwd):
    # Without a discoverable root, skip loading workspace configuration.
    if 'WUWEI_WORKSPACE' not in os.environ and not any(
            (path / '.wuwei').is_dir() for path in chain((cwd,), cwd.parents)):
        return None
    from wuwei.workspace import find_workspace
    try:
        root = find_workspace(cwd)
    except FileNotFoundError:
        return None
    return root


def _cwd(payload):
    cwd = Path(_text(payload.get('cwd'), 'cwd'))
    if not cwd.is_absolute():
        raise ValueError(f'cwd must be absolute; {PAYLOAD}')
    return cwd.resolve()


def check_file(payload):
    try:
        cwd = _cwd(payload)
        root = _workspace(cwd) or worktree_workspace(cwd)
        field = 'notebook_path' if payload.get('tool_name') == 'NotebookEdit' else 'file_path'
        value = _input(payload, field)
        if _protected(value, cwd, root):
            return 1, _hint(_path(value, cwd).resolve())
        return 0, ''
    except (ValueError, OSError, RuntimeError) as exc:
        return 2, str(exc)



def check_scratch(payload):
    """#647: a seat's Write into another item's scratch directory: a warning below strict."""
    try:
        if 'agent_id' not in payload:
            return 0, ''
        cwd = _cwd(payload)
        field = 'notebook_path' if payload.get('tool_name') == 'NotebookEdit' else 'file_path'
        parts = _path(_input(payload, field), cwd).resolve().parts
        found = next(((Path(*parts[:index + 1]), parts[index + 1]) for index in range(1, len(parts) - 2)
                      if parts[index] == 'scratchpad'
                      or parts[index] == 'scratch' and parts[index - 1] == '.wuwei'), None)
        if found is None:
            return 0, ''
        root = _workspace(cwd) or worktree_workspace(cwd)
        if root is None:
            return 0, ''
        from wuwei import brief, state, workspace
        data = state.read_state(root)
        seat = brief.seat_of(payload, data)
        base, other = found
        if seat is None or other == seat['item'] or other not in data['items']:
            return 0, ''
        reason = (f"scratch: {Path(*parts)} is in item {other}'s scratch directory; write item "
                  f"{seat['item']}'s temporary files in {base / seat['item'] / seat['role']}/")
        level = workspace.posture(workspace.load_config(root))[1]['seats']
        if level == 'block':
            return 1, reason
        if level == 'warn':
            print(f'warning: {reason}', file=sys.stderr)
        return 0, ''
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        return 2, str(exc)

def _copy_targets(argv, cwd):
    """Parse supported copy/move options; unknown relevant forms fail closed."""
    rsync = Path(argv[0]).name == 'rsync'
    operands, target = [], None
    index, options = 1, True
    while index < len(argv):
        arg = argv[index]
        index += 1
        if options and arg == '--':
            options = False
        elif options and not rsync and arg in ('-t', '--target-directory'):
            if index == len(argv):
                raise ValueError('missing target directory; pass the target directory')
            target = argv[index]
            index += 1
        elif options and not rsync and arg.startswith('--target-directory='):
            target = arg.split('=', 1)[1]
        elif options and not rsync and arg.startswith('-t'):
            target = arg[2:]
        elif options and arg.startswith('-'):
            if not arg[1:] or any(flag not in 'afginoprtuvzRTLHP' for flag in arg[1:]):
                raise ValueError('unsupported copy/move option; use literal file operands')
        else:
            operands.append(arg)
    if target is None:
        if len(operands) < 2:
            raise ValueError('copy/move requires source and destination; pass the source and the destination')
        target = operands.pop()
    if not operands:
        raise ValueError('copy/move requires a source; pass the source and the destination')
    destination = _path(target, cwd)
    targets = [] if destination.is_dir() else [target]
    for source in operands:
        source_path = _path(source, cwd)
        if source_path.is_dir() and Path(argv[0]).name != 'mv':
            raise ValueError('directory copy/move is opaque; use explicit file operations')
        if destination.is_dir():
            targets.append(str(destination / source_path.name))
    if Path(argv[0]).name == 'mv':
        targets.extend(operands)
    return targets


def _write_targets(argv, cwd, root):
    if not argv:
        return []
    program = Path(argv[0]).name
    if program in ('cd', 'pushd', 'popd'):
        return []
    # The CLI is the state writer; its arguments (job JSON, prompts, paths it reads) are data.
    # Only the real CLI: bare wuwei on PATH, the launcher, or python -P -m wuwei (the only
    # interpreter form that reaches here naming state). Any other program named wuwei is checked.
    if _wuwei_action(argv) is not None:
        from wuwei.shell import _launcher
        if program != 'wuwei' or argv[0] == 'wuwei' or _launcher(Path(cwd, argv[0]), cwd):
            return []
    from wuwei.shell import reads
    # Reader arguments are text; their redirects are checked from command.writes.
    # rg --pre runs a command on each searched file, so those operands are checked.
    if program in _READERS and not (
            program == 'rg' and any(a == '--pre' or a.startswith('--pre=') for a in argv[1:])) or reads(argv, cwd):
        return []
    if program in ('ln', 'install', 'rsync', 'rm', 'cp', 'mv', 'tee', 'truncate', 'sed'):
        # Normalized argv has no quote metadata; conservatively check glob matches.
        import glob  # Here, not at module level: most Bash calls never glob.
        argv = [argv[0], *(match for arg in argv[1:]
                          for match in (glob.glob(arg, root_dir=cwd) or [arg]))]
    arguments = {arg for arg in argv[1:] if arg}
    arguments.update(arg.split('=', 1)[1] for arg in argv[1:] if '=' in arg and arg.split('=', 1)[1])
    protected = [arg for arg in arguments
                 if _protected(arg, cwd, root, program in ('rm', 'chmod', 'chown'))]
    if program == 'rm' and protected:
        return protected
    if program in ('cp', 'mv', 'rsync'):
        if program == 'rsync' and '--remove-source-files' in argv and protected:
            return protected
        try:
            return _copy_targets(argv, cwd)
        except ValueError:
            if protected or re.search(_STATE_MENTION, ' '.join(argv)):
                raise
            return []
    if program == 'dd':
        import glob
        return [match for arg in argv[1:] if arg.startswith('of=')
                for match in (glob.glob(arg[3:], root_dir=cwd) or [arg[3:]])]
    if program == 'sed' and not any(
            arg == '--in-place' or arg.startswith('--in-place=') or
            (arg.startswith('-') and not arg.startswith('--') and 'i' in arg)
            for arg in argv[1:]):
        return []
    return protected


def _cd_target(command):
    args = command.argv[1:]
    while args and args[0] in ('-L', '-P'):
        args = args[1:]
    if args and args[0] == '--':
        args = args[1:]
    elif args and args[0].startswith('-') and args[0] != '-':
        raise ValueError('unsupported cd option; use git -C or a subshell')
    if len(args) > 1:
        raise ValueError('cd requires a single literal directory; pass one literal directory to cd')
    env = {**os.environ, **command.env}
    target = args[0] if args else _text(env.get('HOME'), 'HOME')
    if target == '~' or target.startswith('~/'):
        target = _text(env.get('HOME'), 'HOME') + target[1:]
    if target == '-':
        target = _text(env.get('OLDPWD'), 'OLDPWD')
    if env.get('CDPATH') and not Path(target).is_absolute() and not target.startswith(('./', '../')):
        raise ValueError('CDPATH directory search is opaque; use an absolute path')
    return target


def check_bash(payload):
    try:
        cwd = _cwd(payload)
        root = _workspace(cwd) or worktree_workspace(cwd)
        contain_cwd = root is not None and cwd.is_relative_to(root)
        script = _input(payload, 'command')
        if not isinstance(script, str):
            raise ValueError(f'missing or invalid command; {DAMAGED}')
        from wuwei.shell import (NonliteralPathError, ParseError, UNPARSED, classify, normalize, reads,
                                 script_text, snippet_write)
        from wuwei.workspace import guard_scope

        def owner_script(raw):
            # ponytail: one script level; a script run by a script, or written and run in
            # one call, is not read. The next call that runs the saved script is.
            body = script_text(raw, cwd) if root is not None else None
            # Every owner action in a script names the CLI word, so only such a body is parsed.
            if body is None or 'wuwei' not in re.sub(r"['\"\\]", '', body):
                return None
            relevant = _owner_relevant(script + '\n' + body, script=True)
            try:
                found = _owner_action(normalize(body), body, relevant, cwd, script=True)
            except ParseError:
                found = relevant and (2, 'Opaque owner script; use the host terminal.')
            return found if found and guard_scope(payload) is not None else None

        owner_relevant = _owner_relevant(script)
        words = []
        try:
            commands = normalize(script, words=words)
        except ParseError as exc:
            # The literal words, nested sh -c included, still name any script the call runs;
            # only a .sh or executable word can be one, not a source file it reads.
            for word in words:
                if ((word.endswith('.sh') or os.access(Path(cwd, word), os.X_OK))
                        and (found := owner_script(shlex.quote(word)))):
                    return found
            shape = classify(script, cwd=cwd)
            # #347: only text a write can target counts; a word the walk cannot pin may be the CLI.
            if not shape.readonly and (
                    (owner_relevant and guard_scope(payload) is not None
                     and (shape.publishes or _owner_relevant(script, script=True)))
                    or re.search(_STATE_MENTION, shape.written) or re.search(_STATE_GLOB, shape.written)
                    or (root is not None and _protected_name(cwd, directories=True)
                        and (isinstance(exc, NonliteralPathError)
                             or (re.search(_DYNAMIC, script) and re.search(_WRITE_CONSTRUCT, script))))):
                return 2, str(exc)
            if contain_cwd and re.search(r'\b(?:cd|pushd|popd)\b', script, re.I):
                return 2, WORKSPACE_ROOT
            if shape.readonly:
                return 0, ''
            if re.search(_STATE_MENTION, script) or re.search(_STATE_GLOB, script):
                return 2, UNPARSED
            return 0, ''
        # normalize unwraps lists, subshells, wrappers, sh -c and xargs down to each script.
        for command in commands:
            if found := owner_script(shlex.join(command.argv)):
                return found
        edits = _gate_edits(payload, root) if owner_relevant else (frozenset(), False)
        found = _owner_action(commands, script, owner_relevant, cwd, edits=edits)
        if found and guard_scope(payload) is not None:
            return found
        directories = persistent = {cwd}
        for command in commands:
            program = Path(command.argv[0]).name if command.argv else ''
            # #349: a script run with no state operand passes; -m json.tool with one file reads.
            # #643: so does a python -c snippet with no write-like token; a refusal names it.
            if (re.fullmatch(_INTERPRETER, program)
                    and command.argv[1:4] != ['-P', '-m', 'wuwei']
                    and not reads(command.argv)
                    and re.search(_STATE_MENTION, ' '.join(command.argv[1:]))):
                token = snippet_write(command.argv)
                return 2, (f'Opaque interpreter: {token} in the snippet is not a read; use the wuwei '
                           'CLI for state changes.' if token else
                           'Opaque interpreter; use the wuwei CLI for state changes.')
            for directory in directories:
                if program == 'git' and 'apply' in command.argv[1:]:
                    git_directory = directory
                    options = iter(command.argv[1:])
                    for option in options:
                        if option in ('-c', '--git-dir', '--work-tree', '--namespace', '--config-env'):
                            next(options, '')
                        elif option.startswith('-C'):
                            target = next(options, None) if option == '-C' else option[2:]
                            git_directory = _path('.' if target == '' else target, git_directory).resolve()
                        elif not option.startswith('-'):
                            if option == 'apply' and any((base / '.wuwei').is_dir()
                                    for base in (git_directory, *git_directory.parents)):
                                return 1, _STATE_HINT
                            break
                targets = [*command.writes, *_write_targets(command.argv, directory, root)]
                hit = next((target for target in targets if _protected(
                    target, directory, root, program in ('rm', 'mv', 'chmod', 'chown'))), None)
                if hit is not None:
                    return 1, _hint(_path(hit, directory).resolve())
            if program == 'popd' or (program == 'pushd' and (len(command.argv) == 1 or
                    re.fullmatch(r'[+-][0-9]+', command.argv[1]))):
                if contain_cwd and not command.subshell:
                    return 2, WORKSPACE_ROOT
                continue
            if program in ('cd', 'pushd'):
                try:
                    target = _cd_target(command)
                except ValueError:
                    return 2, WORKSPACE_ROOT
                bases = directories if command.subshell else persistent
                destinations = {_path(target, base).resolve() for base in bases}
                if not command.subshell:
                    if contain_cwd and any(not path.is_relative_to(root) for path in destinations):
                        return 1, WORKSPACE_ROOT
                    persistent = persistent | destinations
                # ponytail: flattened commands omit branch and nested-scope identity.
                # Retain possible paths; add scope metadata if false positives matter.
                directories = directories | destinations
                if len(directories) > 64:
                    raise ValueError('too many possible working directories; split the command')
        return 0, ''
    except (ValueError, OSError, RuntimeError) as exc:
        return 2, str(exc)


GUARDS = [Guard('PreToolUse', 'Write|Edit|MultiEdit|NotebookEdit', check_file),
          Guard('PreToolUse', 'Write|Edit|MultiEdit|NotebookEdit', check_scratch),
          Guard('PreToolUse', 'Bash', check_bash)]
