"""Each command module exposes register(subparsers) and sets func(args) -> int."""

# #348: every registered command path is in exactly one set (tests/test_cli_known_command.py).
# A positional named `action` is part of the path (mcp check, calibrate export).
READ_ONLY = frozenset({'board', 'calibrate', 'config check', 'config show', 'doctor', 'drafts show', 'grants', 'guide',
                       'heartbeat', 'outbound explain', 'outbound tiers',
                       'integrity check', 'mcp check', 'memory show', 'memory status', 'plan gate', 'sessions', 'shadow report', 'status',
                       'who', 'why'})
# calibrate only prints with --questions; doctor --fix writes (checked below).
_NEEDS = {'calibrate': '--questions'}
WRITES = frozenset({
    'agents build', 'agents check', 'brief', 'build', 'calibrate export', 'calibrate import',
    'close', 'config add-repo', 'config promote', 'config set', 'consolidate', 'dashboard',
    'decide', 'decision lint', 'decision outcome', 'decision route', 'decision show', 'decision template', 'decision undo',
    'discover', 'dispatch discovery', 'docs page', 'docs publish', 'dispatch next', 'dispatch opinion', 'dispatch receive',
    'drafts approve', 'drafts drop', 'event', 'fast-checks', 'git-hook', 'goals edit', 'grants revoke', 'hook',
    'index', 'init', 'integrity reconfirm', 'listen install', 'listen uninstall', 'mcp decide',
    'memory export', 'memory forget', 'memory lint', 'merge', 'metrics', 'next', 'note add', 'nudges',
    'outbound learn', 'outbound tier', 'payload',
    'plan add', 'plan approve', 'plan carry', 'plan park', 'plan propose', 'plan session', 'plan set',
    'plan template', 'pr act',
    'pr claim', 'pr disposition', 'pr ping', 'pr ping-check', 'pr raise', 'pr reviewers', 'pr state', 'promote',
    'memory lint', 'merge', 'metrics', 'next', 'note add', 'nudges', 'outbound tier', 'payload',
    'plan add', 'plan approve', 'plan carry', 'plan park', 'plan propose', 'plan session', 'plan set', 'plan template',
    'pr act', 'pr claim', 'pr disposition', 'pr ping', 'pr ping-check', 'pr raise', 'pr reviewers', 'pr state',
    'promote',
    'rank', 'remote ack', 'reply', 'report', 'retro', 'runtime continue', 'runtime dispatch',
    'runtime result', 'runtime status', 'seat stop', 'setup', 'shepherd schedule', 'shepherd unschedule', 'signal classify', 'state get',
    'state recover', 'state set', 'state transition', 'steward ack', 'steward run',
    'sweep obligations', 'sweep watch', 'telemetry off', 'telemetry preview', 'telemetry proposals',
    'telemetry send', 'tracker create', 'tracker done', 'tracker log', 'verdict lint', 'voice edit',
    'voice learn',
    'watch install', 'watch uninstall', 'worktree add', 'worktree adopt'})


def read_only(args):
    """#348: True when a CLI call only prints: --help or -h before --, --version first, or a
    READ_ONLY path (the longest registered path the words start with)."""
    args = list(args)
    if args[:1] == ['--workspace']:
        args = args[2:]  # #354: its value is a path, never the command, --help or --
    if '--' in args:
        args = args[:args.index('--')]
    if '-h' in args or '--help' in args or args[:1] == ['--version']:
        return True
    words = [arg for arg in args if not arg.startswith('-')]
    path = max((p for p in READ_ONLY | WRITES if p.split() == words[:len(p.split())]),
               key=lambda p: len(p.split()), default='')
    return path in READ_ONLY and '--fix' not in args and (path not in _NEEDS or _NEEDS[path] in args)
