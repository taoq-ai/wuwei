"""Each command module exposes register(subparsers) and sets func(args) -> int."""

# #348: every registered command path is in exactly one set (tests/test_cli_known_command.py).
# A positional named `action` is part of the path (mcp check, calibrate export).
READ_ONLY = frozenset({'board', 'calibrate', 'config check', 'doctor', 'heartbeat',
                       'integrity check', 'mcp check', 'sessions', 'shadow report', 'status',
                       'why'})
# calibrate only prints with --questions; doctor --fix writes (checked below).
_NEEDS = {'calibrate': '--questions'}
WRITES = frozenset({
    'agents build', 'agents check', 'brief', 'build', 'calibrate export', 'calibrate import',
    'close', 'config add-repo', 'config promote', 'config set', 'consolidate', 'dashboard',
    'decide', 'decision lint', 'decision outcome', 'decision route', 'decision show', 'decision template',
    'discover', 'dispatch discovery', 'dispatch next', 'dispatch opinion', 'dispatch receive',
    'drafts approve', 'drafts drop', 'event', 'fast-checks', 'git-hook', 'goals edit', 'hook',
    'index', 'init', 'integrity reconfirm', 'listen install', 'listen uninstall', 'mcp decide',
    'memory lint', 'merge', 'metrics', 'next', 'note add', 'nudges', 'outbound tier', 'payload',
    'plan add', 'plan approve', 'plan propose', 'plan session', 'plan template', 'pr act',
    'pr claim', 'pr disposition', 'pr ping', 'pr ping-check', 'pr raise', 'pr state', 'promote',
    'rank', 'remote ack', 'reply', 'report', 'retro', 'runtime continue', 'runtime dispatch',
    'runtime result', 'runtime status', 'setup', 'signal classify', 'state get',
    'state recover', 'state set', 'state transition', 'steward ack', 'steward run',
    'sweep obligations', 'sweep watch', 'verdict lint', 'voice edit', 'voice learn',
    'watch install', 'watch uninstall', 'worktree add'})


def read_only(args):
    """#348: True when a CLI call only prints: --help or -h before --, --version first, or a
    READ_ONLY path (the longest registered path the words start with)."""
    args = list(args)
    if '--' in args:
        args = args[:args.index('--')]
    if '-h' in args or '--help' in args or args[:1] == ['--version']:
        return True
    words = [arg for arg in args if not arg.startswith('-')]
    path = max((p for p in READ_ONLY | WRITES if p.split() == words[:len(p.split())]),
               key=lambda p: len(p.split()), default='')
    return path in READ_ONLY and '--fix' not in args and (path not in _NEEDS or _NEEDS[path] in args)
