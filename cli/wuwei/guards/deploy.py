"""Refuse deployments in every profile, using normalized argv and port evidence."""

from fnmatch import fnmatchcase
from pathlib import PurePosixPath
import re
from urllib.parse import unquote, urlsplit

from wuwei import registry
from wuwei.guards import Guard
from wuwei.shell import ParseError, is_opaque, mentions, normalize, operands, script_text, unread
from wuwei.workspace import find_workspace, load_config


VERBS = {
    'kubectl': ('apply', 'create', 'replace', 'rollout', 'patch'),
    'helm': ('install', 'upgrade', 'rollback'), 'terraform': ('apply', 'destroy'),
    'tofu': ('apply', 'destroy'), 'pulumi': ('up', 'update'),
    'netlify': ('deploy',), 'ntl': ('deploy',), 'fly': ('deploy', 'launch'),
    'flyctl': ('deploy', 'launch'), 'docker': ('push',), 'podman': ('push',),
}
CLOUD_VERBS = {'deploy', 'deployment', 'deployments', 'create-deployment',
               'create-stack', 'update-stack', 'execute-change-set',
               'update-function-code', 'update-service', 'up', 'start-deployment'}
PROGRAMS = ('git', 'gh', *VERBS, 'vercel', 'vc', 'gcloud', 'aws', 'az')
DEPLOY_ACTIONS = (*PROGRAMS[2:], 'push', 'merge', 'release', 'workflow', 'run', 'api')
# Target-dependent actions stay with the hook.
PERMISSIONS_DENY = [f'Bash({command})' for command in (
    'terraform apply*', 'tofu apply*', 'kubectl apply*', 'helm install*',
    'helm upgrade*', 'pulumi up*', 'vercel*', 'vc *', 'netlify deploy*',
    'ntl deploy*', 'fly deploy*', 'flyctl deploy*', 'docker push*',
    'podman push*', 'gh release create*', 'git push --tags*', 'git push * --tags*',
    'gh pr review --approve*', 'gh pr review * --approve*', 'gh pr review * -a*',
    'gh pr merge * --admin*')]


def deny(rule):
    return 1, f'deploy: refused by {rule}'


def unknown(reason):
    raise ValueError(reason)


def environment(branch, config):
    branch = branch.removeprefix('refs/heads/')
    return any(fnmatchcase(branch, pattern) for pattern in config['environments'])


def workflow(target, config):
    if not target:
        unknown('workflow target is unresolved')
    marked = config['deploy']['workflows']
    if any(target == item or PurePosixPath(target).name == PurePosixPath(item).name
           for item in marked):
        return deny('deploy.workflows')
    if marked and (not target.endswith(('.yml', '.yaml')) or
                   any(not item.endswith(('.yml', '.yaml')) for item in marked)):
        unknown('workflow name or ID requires unavailable workflow resolution')
    return 0, ''


def merge(ref, config, root):
    match = re.fullmatch(r'(?:https://github\.com/([^/]+/[^/]+)/pull/|([^#]+)#)([1-9][0-9]*)', ref)
    if not match:
        unknown('PR reference requires an explicit GitHub.com repository and number')
    expected_repo = match[1] or match[2]
    result = registry.load('code_host', config).pr(ref, root=root)
    if result.exit != 0:
        unknown(result.reason or 'could not read PR deployment target')
    data = result.data
    if (not isinstance(data, dict) or not isinstance(data.get('base'), str)
            or not data['base'] or data.get('repo') != expected_repo):
        unknown('invalid PR deployment target')
    if environment(data['base'], config):
        return deny('environment branch merge')
    repo = next((repo for repo in config['repos'] if repo['name'] == data['repo']), None)
    if repo is None:
        unknown('repository merge_deploys is undeclared')
    if repo['merge_deploys']:
        return deny('merge_deploys')
    return 0, ''


def git(args, env, config):
    override = any(key.startswith('GIT_') for key in env)
    while args and args[0].startswith('-'):
        option = args[0]
        if option in ('-C', '-c', '--git-dir', '--work-tree'):
            if len(args) < 2:
                unknown('missing git option value')
            override |= option != '-C'
            args = args[2:]
        elif option.startswith(('-C', '-c', '--git-dir=', '--work-tree=', '--config-env=')):
            override |= not option.startswith('-C')
            args = args[1:]
        elif option in ('--no-pager', '--paginate'):
            args = args[1:]
        else:
            unknown('unsupported git override')
    if not args:
        return 0, ''
    action, *args = args
    if action == 'push':
        if any(arg in ('--tags', '--follow-tags', '--mirror', 'tag') or
               'refs/tags/' in arg for arg in args):
            return deny('tag push')
        targets, options = operands(args, ('--repo', '--receive-pack', '--exec', '-o', '--push-option'),
                              ('-f', '--force', '-u', '--set-upstream', '--delete', '-d',
                               '--all', '--dry-run', '-n', '--porcelain', '--verbose', '-v', '--quiet', '-q'))
        if '--repo' in options:
            targets.insert(0, options['--repo'])
        if any(key in options for key in ('--receive-pack', '--exec')):
            unknown('git executable override prevents inspection')
        if len(targets) < 2:
            unknown('push destination is unresolved')
        for ref in targets[1:]:
            target = ref.lstrip('+').split(':')[-1]
            if environment(target, config):
                return deny('environment branch push')
            if re.fullmatch(r'v?\d+\.\d+.*', target):
                return deny('tag push')
        if override:
            unknown('git override prevents proving push destination')
        for ref in targets[1:]:
            target = ref.lstrip('+').split(':')[-1]
            if any(c in target for c in '*?['):
                unknown('ambiguous push ref; use a literal branch destination')
        return 0, ''
    if action == 'merge':
        # ponytail: block implicit targets until the vcs port exposes current branch.
        unknown('current branch cannot be established by the vcs port')
    if action not in ('status', 'diff', 'log', 'show', 'rev-parse', 'branch', 'tag',
                      'fetch', 'checkout', 'switch', 'add', 'commit', 'restore', 'reset',
                      'rebase', 'stash', 'ls-files', 'ls-remote', 'remote', 'config',
                      'worktree', 'help', 'version', 'symbolic-ref', 'describe', 'show-ref'):
        unknown('unknown git command or alias')
    return 0, ''


def api(args, config, root):
    targets, options = operands(args, ('-X', '--method', '-f', '-F', '--field', '--raw-field',
                                       '--input', '-H', '--header', '--hostname', '-q', '--jq',
                                       '-t', '--template', '--cache'),
                                ('--paginate', '--slurp', '--silent', '-i', '--include', '--verbose'))
    if len(targets) != 1:
        unknown('API endpoint is unresolved')
    url = urlsplit(targets[0])
    if (url.netloc and url.netloc != 'api.github.com' or
            options.get('--hostname', 'github.com') != 'github.com'):
        unknown('API host is unsupported by the code_host port')
    endpoint = unquote(url.path).strip('/')
    parts = endpoint.split('/')
    if 'deployments' in parts or 'environments' in parts:
        return deny('deployment/environment API')
    method = options.get('-X', options.get('--method', ''))
    writes = method.upper() not in ('GET', 'HEAD') if method else any(
        key in options for key in ('-f', '-F', '--field', '--raw-field', '--input'))
    match = re.fullmatch(r'repos/([^/]+/[^/]+)/pulls/(\d+)/merge', endpoint)
    if match and writes:
        return merge(f'{match[1]}#{match[2]}', config, root)
    if 'dispatches' in parts and 'workflows' in parts:
        return workflow(parts[parts.index('workflows') + 1], config)
    if 'rerun' in parts or 'rerun-failed-jobs' in parts:
        if config['deploy']['workflows']:
            unknown('workflow run requires unavailable workflow resolution')
    if writes and 'releases' in parts:
        return deny('release API')
    if writes and ('refs' in parts or 'tags' in parts):
        return deny('tag or branch ref API')
    if writes and 'merges' in parts:
        for value in options.values():
            if value.startswith('base=') and environment(value[5:], config):
                return deny('environment branch merge API')
        unknown('API merge target cannot be cleared')
    if endpoint == 'graphql':
        unknown('opaque GraphQL deployment or merge API')
    return 0, ''


def gh(args, env, config, root):
    if args in (['--version'], ['--help'], ['-h']) or args[:1] in (['help'], ['version']):
        return 0, ''
    if env.get('GH_HOST', 'github.com') != 'github.com':
        unknown('GH_HOST override is unsupported by the code_host port')
    repo = env.get('GH_REPO')
    # gh accepts persistent repository flags before, between and after subcommands.
    remaining = []
    group = None
    valued = ('--match-head-commit', '-t', '--subject', '-b', '--body', '-F', '--body-file',
              '--ref', '-f', '--field', '--raw-field', '-X', '--method',
              '--input', '-H', '--header', '--hostname', '-q', '--jq', '--template', '--cache')
    index = 0
    while index < len(args):
        arg = args[index]
        index += 1
        if arg == '--':
            remaining.extend([arg, *args[index:]])
            break
        if arg in valued or arg == '-r' and group == 'workflow':
            if index == len(args):
                unknown('missing gh option value')
            remaining.extend([arg, args[index]])
            index += 1
        elif arg in ('-R', '--repo'):
            if index == len(args):
                unknown('missing repository option value')
            repo = args[index]
            index += 1
        elif arg.startswith(('--repo=', '-R')):
            repo = arg.removeprefix('--repo=').removeprefix('-R')
        else:
            remaining.append(arg)
            if group is None and not arg.startswith('-'):
                group = arg
    args = remaining
    if args[:2] == ['release', 'create']:
        return deny('release create')
    if args[:1] == ['api']:
        return api(args[1:], config, root)
    if args[:2] in (['workflow', 'run'], ['workflow', 'rerun'], ['run', 'rerun']):
        targets, _ = operands(args[2:], ('-R', '--repo', '-r', '--ref', '-f', '-F', '--field', '--raw-field'),
                              ('--json', '--failed', '--debug'))
        if args[:2] == ['run', 'rerun']:
            if config['deploy']['workflows']:
                unknown('workflow run requires unavailable workflow resolution')
            return 0, ''
        return workflow(targets[0] if len(targets) == 1 else '', config)
    if args[:2] == ['pr', 'merge']:
        targets, options = operands(args[2:], ('-R', '--repo', '--match-head-commit',
                                              '-t', '--subject', '-b', '--body', '-F', '--body-file'),
                                   ('--squash', '--merge', '--rebase', '--auto', '--admin',
                                    '--delete-branch', '-d', '-s', '-m', '-r'))
        if len(targets) != 1:
            unknown('PR merge reference is unresolved')
        ref = targets[0]
        repo = options.get('-R', options.get('--repo', repo))
        if ref.isdecimal():
            if not repo:
                unknown('PR repository is unresolved; use -R owner/repo')
            ref = f'{repo}#{ref}'
        return merge(ref, config, root)
    if args and args[0] not in ('pr', 'issue', 'workflow', 'run', 'release', 'repo',
                               'auth', 'status', 'search', 'browse', 'help', 'version'):
        unknown('unknown gh command or alias')
    return 0, ''


def check(payload):
    try:
        try:
            root = find_workspace(payload['cwd'])
        except FileNotFoundError:
            return 0, ''
        raw = payload['tool_input']['command']
        try:
            config = load_config(root)
        except (ValueError, OSError):
            if not mentions(raw, DEPLOY_ACTIONS):
                return 0, ''
            raise
        protected = (*PROGRAMS, *(pattern.split()[0] for pattern in config['deploy']['deny']))
        script = script_text(raw, payload['cwd'])
        if script and mentions(script, protected, script=True) and mentions(script, DEPLOY_ACTIONS, script=True):
            unknown('opaque script deployment command; use a plain command')
        if not mentions(raw, protected):
            return 0, ''
        try:
            commands = normalize(raw, protected=protected)
        except ParseError:
            if not mentions(raw, (*DEPLOY_ACTIONS, *protected[len(PROGRAMS):])):
                return 0, ''
            if (found := unread(raw, protected[2:])) is None:
                raise
            return found
        if (found := unread(raw, protected[2:])) is not None:
            return found
        for index, command in enumerate(commands):
            argv, env = command.argv, command.env
            if not argv:
                continue
            fed = bool(command.reads) or index > 0 and commands[index - 1].separator == '|'
            if is_opaque(argv, fed) and mentions(raw, ('git', 'gh')):
                unknown(f'opaque deployment command: {" ".join(argv)}; use a plain command')
            program, *args = argv
            program = PurePosixPath(program).name
            text = ' '.join([program, *args])
            for pattern in config['deploy']['deny']:
                if fnmatchcase(text, pattern) or text.startswith(pattern + ' '):
                    return deny(f'deploy.deny: {pattern}')
            # Matching any argv verb is conservative and also catches global options.
            for verb in VERBS.get(program, ()):
                if verb in args:
                    return deny(f'{program} {verb}')
            if program == 'kubectl' and any(args[i:i + 2] == ['set', 'image']
                                           for i in range(len(args) - 1)):
                return deny('kubectl set image')
            if program in ('docker', 'podman') and 'build' in args:
                for index, arg in enumerate(args):
                    if arg == '--push' or arg.startswith('--push='):
                        return deny(f'{program} build --push')
                    output = (args[index + 1] if arg in ('--output', '-o') and index + 1 < len(args)
                              else arg.removeprefix('--output=') if arg.startswith('--output=')
                              else arg[2:].lstrip('=') if arg.startswith('-o') else '')
                    if 'type=registry' in output.split(','):
                        return deny(f'{program} build registry output')
            if program in ('vercel', 'vc') and (not args or args[0] not in (
                    'ls', 'list', 'inspect', 'logs', 'whoami', 'help', '--help', '--version')):
                return deny(f'{program} deployment')
            if program in ('gcloud', 'aws', 'az') and CLOUD_VERBS.intersection(args):
                return deny(f'{program} deployment')
            if program in ('git', 'gh'):
                result = git(args, env, config) if program == 'git' else gh(args, env, config, root)
                if result[0]:
                    return result
        return 0, ''
    except (ParseError, ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
        return 2, f'deploy: could not inspect: {exc}'


GUARDS = [Guard('PreToolUse', 'Bash', check)]
