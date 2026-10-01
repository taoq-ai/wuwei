"""Profile a checkout and propose workspace configuration; repository text is data, never a rule."""

from collections import Counter
from datetime import datetime
import difflib
import fnmatch
import json
import os
from pathlib import Path
import re
import statistics
import tomllib

from wuwei import registry, workspace
from wuwei.commands.init import _preserves_values, _sections
from wuwei.guards.deploy import VERBS
from wuwei.workspace import MERGE_SCHEMA


MAX_BYTES = 1 << 20
CONVENTION_FILES = (
    'AGENTS.md', 'CLAUDE.md', 'CONTRIBUTING.md', '.github/CONTRIBUTING.md', 'docs/CONTRIBUTING.md',
    '.specify/memory/constitution.md', 'CODEOWNERS', '.github/CODEOWNERS', 'docs/CODEOWNERS',
    '.github/pull_request_template.md', '.github/PULL_REQUEST_TEMPLATE.md')
INFRA_PATHS = ('k8s', 'kubernetes', 'helm', 'charts', 'terraform', 'ansible', 'kustomize',
               'fly.toml', 'vercel.json', 'netlify.toml', 'Procfile', 'app.yaml',
               'serverless.yml', 'skaffold.yaml')
DEPLOY_NAMES = ('deploy', 'release', 'publish')
DEPLOY_ACTION = re.compile(r'deploy|release-please|gh-release|publish', re.I)
# ponytail: phrase list flags the obvious; route convention files through the scanner port if
# injections get subtler. A hit on a negated rule only drops that source (fail closed).
INSTRUCTION_LIKE = tuple((rule, re.compile(pattern, re.I)) for rule, pattern in (
    ('override', r'\b(?:ignore|disregard|forget|override)\b[^.\n]{0,40}\b(?:previous|prior|above|'
                 r'earlier|all|your|system)\b[^.\n]{0,20}\b(?:instructions?|rules|prompts?|guidelines)\b'),
    ('role', r'\byou are now\b|\bnew instructions\s*:|\bsystem prompt\b'),
    ('exfiltrate', r'\b(?:send|post|upload|exfiltrate)\b[^.\n]{0,40}\b(?:tokens?|secrets?|'
                   r'credentials|api keys?)\b'),
    ('push', r'\bpush\b[^.\n]{0,30}\b(?:main|master|default branch)\b'),
    ('bypass', r'\b(?:disable|bypass|skip|turn off)\b[^.\n]{0,30}\b(?:hooks?|guards?|review|checks?)\b'
               r'|--no-verify'),
))


def _present(checkout, relative):
    """Exact-case existence, so a case-insensitive file system does not report one file twice."""
    path = checkout / relative
    try:
        return path.name in os.listdir(path.parent)
    except OSError:
        return False


def _read(checkout, relative, findings):
    """Return text, or None; a symlink, non-file, outside or over 1 MiB file is reported as skipped."""
    if not _present(checkout, relative):
        return None
    path = checkout / relative
    reason = ('symlink' if path.is_symlink() else 'not a file' if not path.is_file()
              else 'outside the checkout' if not path.resolve().is_relative_to(checkout.resolve())
              else 'over 1 MiB' if path.stat().st_size > MAX_BYTES else None)
    if reason:
        findings.append(_finding('skipped', reason, relative, 1))
        return None
    return path.read_text(encoding='utf-8', errors='replace')


def instruction_like(text):
    """Return (line, rule) for each line that reads like an instruction to an agent."""
    return [(number, rule) for number, line in enumerate(text.splitlines(), 1)
            for rule, pattern in INSTRUCTION_LIKE if pattern.search(line)]


def _finding(kind, value, relative, line):
    return {'kind': kind, 'value': value, 'source': f'{relative}:{line}'}


def _line(text, pattern):
    match = re.search(pattern, text, re.M)
    return text.count('\n', 0, match.start()) + 1 if match else 1


def _deploy_command(line):
    if re.search(r'\bgh\s+release\s+create\b', line):
        return True
    words = line.split()
    return any(program in words and set(verbs) & set(words[words.index(program) + 1:])
               for program, verbs in VERBS.items())


def toolchain(checkout, repo):
    found = []
    text = _read(checkout, 'pyproject.toml', found)
    if text is not None:
        found.append(_finding('language', 'python', 'pyproject.toml', 1))
        if 'pytest' in text:
            found.append(_finding('fast_check', 'python3 -m pytest -q', 'pyproject.toml',
                                  _line(text, 'pytest')))
        elif _present(checkout, 'pytest.ini'):
            found.append(_finding('fast_check', 'python3 -m pytest -q', 'pytest.ini', 1))
        for table, command in (('ruff', 'ruff check .'), ('black', 'black --check .')):
            if re.search(rf'^\[tool\.{table}', text, re.M):
                found.append(_finding('fast_check', command, 'pyproject.toml',
                                      _line(text, rf'^\[tool\.{table}')))
    text = _read(checkout, 'package.json', found)
    if text is not None:
        found.append(_finding('language', 'javascript', 'package.json', 1))
        try:
            scripts = json.loads(text).get('scripts', {})
        except (ValueError, AttributeError):
            scripts = {}
        scripts = scripts if isinstance(scripts, dict) else {}
        test = scripts.get('test')
        if isinstance(test, str) and 'no test specified' not in test:
            found.append(_finding('fast_check', 'npm test', 'package.json', _line(text, r'"test"\s*:')))
        if isinstance(scripts.get('lint'), str):
            found.append(_finding('fast_check', 'npm run lint', 'package.json', _line(text, r'"lint"\s*:')))
    for name, language, command in (('Cargo.toml', 'rust', 'cargo test'),
                                    ('go.mod', 'go', 'go test ./...')):
        if _read(checkout, name, found) is not None:
            found.append(_finding('language', language, name, 1))
            found.append(_finding('fast_check', command, name, 1))
    if not any(f['kind'] == 'language' for f in found):
        text = _read(checkout, 'Makefile', found) or ''
        for number, line in enumerate(text.splitlines(), 1):
            match = re.match(r'(test|lint|check)\s*:(?!=)', line)
            if match:
                found.append(_finding('fast_check', f'make {match[1]}', 'Makefile', number))
    return found


def _workflows(checkout, found):
    directory = checkout / '.github/workflows'
    names = sorted(os.listdir(directory)) if directory.is_dir() and not directory.is_symlink() else []
    for name in names:
        if name.endswith(('.yml', '.yaml')):
            relative = f'.github/workflows/{name}'
            text = _read(checkout, relative, found)
            if text is not None:
                yield name, relative, _workflow(text)


def _scalar(value):
    return value.split(' #', 1)[0].strip().strip('\'"')


def _workflow(text):
    """Triggers, push branches and jobs of a workflow file.

    ponytail: line regexes over workflow YAML; anchors, multi-document files and flow
    mappings are not read. Add a YAML reader if a real repository needs them.
    """
    triggers, branches, jobs = set(), [], []
    section = trigger = sub = child = prop = job = matrix = environment = None
    for number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        key, _, value = line.partition(':')
        key, value = key.strip('\'"'), value.strip()
        if indent == 0:
            section = {'on': 'on', 'true': 'on', 'jobs': 'jobs'}.get(key)
            child = job = None
            if section == 'on' and value:
                triggers |= set(re.findall(r'[a-z_]+', value))
            continue
        if child is None:
            child = indent
        if section == 'on':
            if indent == child:
                trigger, sub = line.lstrip('- ').partition(':')[0].strip(), None
                triggers.add(trigger)
            elif trigger == 'push' and not line.startswith('-'):
                sub = key
                if key == 'tags':
                    branches.append(('tags', number))
                if key == 'branches' and value.startswith('['):
                    branches += [(_scalar(b), number) for b in value.strip('[]').split(',') if b.strip()]
            elif trigger == 'push' and sub == 'branches':
                branches.append((_scalar(line[1:]), number))
        elif section == 'jobs':
            if indent == child:
                job = {'name': (key, number), 'continue': False, 'matrix': None,
                       'environment': None, 'signals': []}
                jobs.append(job)
                prop = matrix = environment = None
                continue
            if job is None:
                continue
            if prop is None:
                prop = indent
            if indent == prop:
                matrix = environment = None
                if key == 'name' and value:
                    job['name'] = (_scalar(value), number)
                elif key == 'continue-on-error':
                    job['continue'] = _scalar(value) == 'true'
                elif key == 'environment':
                    job['environment'] = (_scalar(value), number)
                    environment = not value
                elif key == 'strategy':
                    matrix = 'strategy'
            elif environment and key == 'name':
                job['environment'], environment = (_scalar(value), number), False
            elif matrix == 'strategy' and key == 'matrix':
                matrix = indent
            elif type(matrix) is int and indent > matrix:
                if job['matrix'] is None and value.startswith('[') and value.endswith(']'):
                    job['matrix'] = ([_scalar(v) for v in value[1:-1].split(',') if v.strip()], number)
                else:
                    job['matrix'] = 'other'
            uses = re.match(r'-?\s*uses:\s*(\S+)', line)
            if (uses and DEPLOY_ACTION.search(uses[1])) or _deploy_command(line):
                job['signals'].append(number)
    return {'triggers': triggers, 'branches': branches, 'jobs': jobs}


def ci_checks(checkout, repo):
    found = []
    for _, relative, flow in _workflows(checkout, found):
        if not flow['triggers'] & {'pull_request', 'pull_request_target'}:
            continue
        for job in flow['jobs']:
            name, line = job['name']
            found.append(_finding('ci_check', name, relative, line))
            if job['continue'] or job['matrix'] == 'other':
                continue
            if job['matrix']:
                values, number = job['matrix']
                found += [_finding('required_check', f'{name} ({v})', relative, number) for v in values]
            else:
                found.append(_finding('required_check', name, relative, line))
    return found


def conventions(checkout, repo):
    found = []
    directory = checkout / '.github/ISSUE_TEMPLATE'
    templates = (sorted(f'.github/ISSUE_TEMPLATE/{n}' for n in os.listdir(directory))
                 if directory.is_dir() and not directory.is_symlink() else [])
    for relative in (*CONVENTION_FILES, *templates):
        text = _read(checkout, relative, found)
        if text is None:
            continue
        found.append(_finding('convention', relative, relative, 1))
        if relative.endswith('CODEOWNERS'):
            for number, line in enumerate(text.splitlines(), 1):
                parts = line.split('#', 1)[0].split()
                if len(parts) > 1 and parts[0] != '*':
                    found.append(_finding('boundary', (parts[0], 'owned by ' + ' '.join(parts[1:])),
                                          relative, number))
    return found


def deploy_signals(checkout, repo):
    found = []
    for name, relative, flow in _workflows(checkout, found):
        pushes = 'push' in flow['triggers'] and (
            not flow['branches'] or any(b in (repo['default_branch'], 'tags') for b, _ in flow['branches']))
        if not (pushes or 'release' in flow['triggers']):
            continue
        signals = [number for job in flow['jobs'] for number in
                   ([job['environment'][1]] if job['environment'] else []) + job['signals']]
        if not signals:
            continue
        found.append(_finding('deploy_workflow', name, relative, min(signals)))
        for job in flow['jobs']:
            if job['environment']:
                value, number = job['environment']
                found.append(_finding('skipped', 'dynamic environment', relative, number)
                             if '${{' in value or not value else
                             _finding('environment', value, relative, number))
        found += [_finding('environment', branch, relative, number)
                  for branch, number in flow['branches'] if branch not in (repo['default_branch'], 'tags')]
    text = _read(checkout, 'Makefile', found) or ''
    target = None
    denied = set()
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r'([A-Za-z0-9_.-]+)\s*:(?!=)', line)
        if match:
            target = match[1]
        if target and target not in denied and (
                (match and target in DEPLOY_NAMES) or (line.startswith('\t') and _deploy_command(line))):
            denied.add(target)
            found.append(_finding('deploy_deny', f'make {target}*', 'Makefile', number))
    text = _read(checkout, 'package.json', found)
    if text is not None:
        try:
            scripts = json.loads(text).get('scripts', {})
        except (ValueError, AttributeError):
            scripts = {}
        for script in scripts if isinstance(scripts, dict) else ():
            if script in DEPLOY_NAMES:
                found.append(_finding('deploy_deny', f'npm run {script}*', 'package.json',
                                      _line(text, rf'"{script}"\s*:')))
    defaults = MERGE_SCHEMA['never_auto_paths'][1]
    for entry in INFRA_PATHS:
        if _present(checkout, entry):
            pattern = f'{entry}/*' if (checkout / entry).is_dir() else entry
            if not any(fnmatch.fnmatchcase(pattern, default) for default in defaults):
                found.append(_finding('never_auto', pattern, entry, 1))
    return found


DETECTORS = (toolchain, ci_checks, conventions, deploy_signals)
SAFE = re.compile(r'[A-Za-z0-9 ._/()*@+-]{1,100}')
FLAGS = ('instruction_like', 'unsafe', 'skipped')
DRIFT = ('fast_checks', 'ci_checks', 'deploy_workflows', 'environments', 'deploy_deny', 'never_auto')


def profile(checkout, repo):
    """Run every detector; a file with instruction-like text, an instruction-like value and unsafe
    values contribute nothing."""
    checkout = Path(checkout)
    found = [finding for detector in DETECTORS for finding in detector(checkout, repo)]
    findings = [f for f in found if f['kind'] == 'skipped']
    flagged = {}
    for source in dict.fromkeys(f['source'].rpartition(':')[0] for f in found if f['kind'] != 'skipped'):
        text = _read(checkout, source, [])
        flagged[source] = instruction_like(text) if text is not None else []
        findings += [_finding('instruction_like', rule, source, line) for line, rule in flagged[source]]
    for finding in found:
        path = finding['source'].rpartition(':')[0]
        if finding['kind'] == 'skipped' or flagged.get(path):
            continue
        values = finding['value'] if isinstance(finding['value'], tuple) else (finding['value'],)
        hits = [rule for value in values for _, rule in instruction_like(value)]
        if hits:
            findings.append({**finding, 'kind': 'instruction_like', 'value': hits[0]})
        elif all(SAFE.fullmatch(value) for value in values):
            findings.append(finding)
        else:
            findings.append({**finding, 'kind': 'unsafe', 'value': finding['kind']})

    def values(kind):
        return sorted({f['value'] for f in findings if f['kind'] == kind})
    facts = {key: values(kind) for key, kind in (
        ('languages', 'language'), ('fast_checks', 'fast_check'), ('ci_checks', 'ci_check'),
        ('required_checks', 'required_check'), ('conventions', 'convention'),
        ('deploy_workflows', 'deploy_workflow'), ('deploy_deny', 'deploy_deny'),
        ('never_auto', 'never_auto'))}
    facts['environments'] = dict(sorted(
        (f['value'], 'deploy target in ' + f['source'].rpartition(':')[0])
        for f in findings if f['kind'] == 'environment'))
    facts['boundary'] = dict(sorted(f['value'] for f in findings if f['kind'] == 'boundary'))
    facts['merge_deploys'] = bool(facts['deploy_workflows'] or facts['deploy_deny'] or facts['never_auto'])
    return {'findings': findings, 'facts': facts}


def drift_facts(facts):
    return {key: sorted(facts[key]) for key in DRIFT}


CONVENTIONAL = re.compile(r'[a-z]+(?:\(([^)]+)\))?!?: ')
SCOPE = re.compile(r'[a-z0-9][a-z0-9-]{0,30}')


def commit_style(commits):
    """Conventional when at least 80 percent of subjects match; scopes are checked words only."""
    matches = [CONVENTIONAL.match(c['subject']) for c in commits]
    count = len(commits)
    scopes = Counter(m[1] for m in matches if m and m[1] and SCOPE.fullmatch(m[1]))
    return {'conventional': bool(count) and sum(map(bool, matches)) >= 0.8 * count,
            'scopes': [scope for scope, _ in sorted(scopes.items(), key=lambda s: (-s[1], s[0]))[:5]],
            'sign_off': bool(count) and sum(c['signed_off'] for c in commits) >= 0.8 * count,
            'commits': count}


def baseline(prs):
    """Advisory steward input: merged pull request size and creation-to-merge hours."""
    if not prs:
        return {'prs': 0}
    hours = [(datetime.fromisoformat(p['merged_at']) - datetime.fromisoformat(p['created_at']))
             .total_seconds() / 3600 for p in prs]
    return {'prs': len(prs),
            'median_changed_lines': int(statistics.median(p['additions'] + p['deletions'] for p in prs)),
            'median_cycle_hours': round(statistics.median(hours), 1)}


COMMENT = '# Added by wuwei config promote from calibration.\n'
LAYOUT = 'cannot place calibration keys in this config.toml layout; edit by hand'


def _table(value, path):
    for part in path:
        if isinstance(part, int):
            value = value[part] if isinstance(value, list) and part < len(value) else None
        else:
            value = value.get(part) if isinstance(value, dict) else None
    return value if isinstance(value, dict) else None


def _labelled(raw):
    """Sections of the raw text addressed by path; [[repos]] tables by their index."""
    sections, repo = [], -1
    for label, lines in _sections(raw):
        parts = label.split('.') if label else []
        if label == '[[repos]]':
            repo += 1
            path = ('repos', repo)
        elif parts[:1] == ['repos']:
            path = ('repos', repo, *parts[1:])
        else:
            path = tuple(parts)
        sections.append((path, lines))
    return sections


def _empty_list(key, line):
    return re.fullmatch(rf'{key}\s*=\s*\[\]\s*(#.*)?', line.strip())


def _assignment(key, line):
    """A complete one-line `key = value` assignment of exactly this key."""
    if not re.match(rf'\s*{re.escape(key)}\s*=', line):
        return False
    try:
        return list(tomllib.loads(line)) == [key]
    except tomllib.TOMLDecodeError:
        return False


def proposal(raw, targets):
    """Additive config proposal for [(repo index, facts)]: (additions, hand edits).

    Only keys absent from the raw TOML are added, plus deploy lists still at a one-line [];
    any other present key that differs is listed for a hand edit. Never proposes a weakening.
    """
    present = tomllib.loads(raw)
    defaults = MERGE_SCHEMA['never_auto_paths'][1]
    wanted, deploy, registers = [], {'workflows': set(), 'deny': set()}, {'environments': {}, 'boundary': {}}
    for index, facts in targets:
        base = ('repos', index)
        for key, value in (('fast_checks', facts['fast_checks']),
                           ('review_required_checks', facts['required_checks']),
                           ('merge_deploys', facts['merge_deploys'] or None)):
            if value:
                wanted.append((base, key, value))
        if facts['never_auto']:
            wanted.append(((*base, 'merge'), 'never_auto_paths',
                           [*defaults, *(p for p in facts['never_auto'] if p not in defaults)]))
        deploy['workflows'].update(facts['deploy_workflows'])
        deploy['deny'].update(facts['deploy_deny'])
        registers['environments'].update(facts['environments'])
        registers['boundary'].update(facts['boundary'])
    wanted += [(('deploy',), key, sorted(values)) for key, values in deploy.items() if values]
    wanted += [((table,), name, text) for table, names in registers.items() for name, text in names.items()]
    deploy_lines = [line for path, lines in _labelled(raw) if path == ('deploy',) for line in lines]
    additions, edits = [], []
    for path, key, value in wanted:
        table = _table(present, path)
        if table is None or key not in table:
            additions.append((path, key, value))
        elif path[0] in registers:
            continue
        elif path == ('deploy',) and table[key] == [] and any(_empty_list(key, l) for l in deploy_lines):
            additions.append((path, key, value))
        elif (not set(value) <= set(table[key]) if isinstance(value, list) else table[key] != value):
            edits.append(('.'.join(map(str, (*path, key))), table[key], value))
    return additions, edits


def apply(raw, additions):
    """Place additions in their sections and prove every other owner value is unchanged."""
    if not additions:
        return raw
    sections, replaced, commented = _labelled(raw), [], set()
    for path, key, value in additions:
        line = f'{json.dumps(key) if path[0] in ("environments", "boundary") else key} = {json.dumps(value)}\n'
        lines = next((lines for p, lines in sections if p == path), None)
        if lines is None:
            if path[0] != 'repos':
                sections.append((path, ['\n', f'[{".".join(path)}]\n']))
            elif len(path) == 3 and any(p[:2] == path[:2] for p, _ in sections):
                last = max(i for i, (p, _) in enumerate(sections) if p[:2] == path[:2])
                sections.insert(last + 1, (path, ['\n', f'[repos.{path[2]}]\n']))
            else:
                raise ValueError(LAYOUT)
            lines = next(lines for p, lines in sections if p == path)
        match = next((i for i, old in enumerate(lines) if _assignment(key, old)), None)
        if match is not None:
            lines[match] = line
            replaced.append((path, key))
            continue
        end = len(lines)
        while end > 1 and not lines[end - 1].strip():
            end -= 1
        if not lines[end - 1].endswith('\n'):
            lines[end - 1] += '\n'
        lines[end:end] = [line] if path in commented else [COMMENT, line]
        commented.add(path)
    text = ''.join(''.join(lines) for _, lines in sections)
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        raise ValueError(LAYOUT) from None
    before = tomllib.loads(raw)
    for path, key in replaced:
        _table(before, path).pop(key)
    if not _preserves_values(before, parsed) or any(
            (_table(parsed, path) or {}).get(key) != value for path, key, value in additions):
        raise ValueError(LAYOUT)
    workspace._validate(parsed, workspace.SCHEMA, (), text)
    return text


def charter_proposals(repo, facts, style):
    """Builder and quality sentinel charter blocks from paths, fixed phrases, scope words and commands."""
    bullets = []
    if facts['conventions']:
        bullets.append('- Read the convention sources before changing code: '
                       + ', '.join(facts['conventions']) + '.')
    if style and (style['conventional'] or style['sign_off']):
        parts = []
        if style['conventional']:
            parts.append('Commit subjects follow Conventional Commits, type(scope): summary'
                         + (f"; common scopes: {', '.join(style['scopes'])}" if style['scopes'] else ''))
        if style['sign_off']:
            parts.append('every commit carries a Signed-off-by trailer')
        bullets.append('- ' + '; '.join(parts) + '.')
    if facts['fast_checks']:
        bullets.append('- Run the fast checks before handing off: ' + '; '.join(facts['fast_checks']) + '.')
    if not bullets:
        return {}
    text = f"## Repository conventions: {repo['name']}\n" + '\n'.join(bullets) + '\n'
    return {'builder': text, 'sentinel-quality': text}


NO_REPOS = ('no [[repos]] entry in config.toml; add name, path and default_branch for each '
            'repository first')


def _port(result, reader):
    """Port data through a pure reader; None is unmeasured, never clean."""
    if not isinstance(result, registry.Result) or result.exit or not isinstance(result.data, list):
        return None
    try:
        return reader(result.data)
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def survey(root, config, selected, *, style=True):
    """Profile each selected (index, repo), then read commit style and the PR baseline."""
    results = []
    for index, repo in selected:
        checkout = (Path(root) / Path(repo['path']).expanduser()).resolve()
        if not checkout.is_dir():
            raise OSError(f"{repo['name']}: checkout {repo['path']} is not a directory")
        results.append({'index': index, 'repo': repo, 'checkout': checkout, **profile(checkout, repo)})
    vcs = registry.load('vcs', config) if style else None
    host = registry.load('code_host', config)
    for result in results:
        result['style'] = (_port(vcs.recent_commits(str(result['checkout']), root=root), commit_style)
                           if style else None)
        result['baseline'] = _port(host.merged_prs(result['repo']['name'], root=root), baseline)
    return results


def settle(raw, settings):
    """Owner answers as (additions, hand edits): absent keys added, one-line assignments replaced.

    A deploy list keeps every present item, so an answer never removes a deploy-ban pattern.
    """
    present, sections = tomllib.loads(raw), _labelled(raw)
    additions, edits = [], []
    for path, key, value in settings:
        table = _table(present, path)
        if table is None or key not in table:
            additions.append((path, key, value))
            continue
        current = table[key]
        if path == ('deploy',) and isinstance(current, list):
            value = [*current, *(item for item in value if item not in current)]
        if current == value:
            continue
        if any(_assignment(key, line) for p, lines in sections if p == path for line in lines):
            additions.append((path, key, value))
        else:
            edits.append(('.'.join(map(str, (*path, key))), current, value))
    return additions, edits


def propose(raw, results, settings=()):
    """Return the proposed config text, its diff and the hand edits; owner settings apply last."""
    additions, edits = proposal(raw, [(r['index'], r['facts']) for r in results])
    text = apply(raw, additions)
    extra, more = settle(text, settings)
    text, edits = apply(text, extra), edits + more
    diff = ''.join(difflib.unified_diff(raw.splitlines(keepends=True), text.splitlines(keepends=True),
                                        'config.toml', 'config.toml (proposed)'))
    return text, diff, edits


SECTIONS = (
    ('Toolchain', ('language', 'fast_check')), ('CI checks', ('ci_check', 'required_check')),
    ('Conventions', ('convention', 'boundary')),
    ('Deploy signals', ('deploy_workflow', 'environment', 'deploy_deny', 'never_auto')),
    ('Instruction-like text (never quoted, never proposed)', ('instruction_like',)),
    ('Unsafe values (dropped)', ('unsafe',)), ('Skipped files', ('skipped',)))
LABELS = {'language': 'language', 'fast_check': 'fast check', 'ci_check': 'CI check',
          'required_check': 'required check', 'convention': 'convention source',
          'boundary': 'boundary candidate', 'deploy_workflow': 'deploy workflow',
          'environment': 'environment', 'deploy_deny': 'deploy command',
          'never_auto': 'never-auto path', 'instruction_like': 'rule', 'unsafe': 'unsafe value',
          'skipped': 'skipped'}


def report(results, diff, edits, written, error=None):
    """Markdown report: every finding with its file and line, then the proposal and next step."""
    lines = ['# Calibration', '']
    for result in results:
        lines += [f"## {result['repo']['name']}", '']
        for title, kinds in SECTIONS:
            rows = [f for f in result['findings'] if f['kind'] in kinds]
            if rows or title in ('Toolchain', 'CI checks', 'Conventions', 'Deploy signals'):
                lines.append(f'### {title}')
                lines += [f"- {': '.join(f['value']) if isinstance(f['value'], tuple) else f['value']} "
                          f"({f['source']}) {LABELS[f['kind']]}" for f in rows] or ['- none found']
                lines.append('')
        style = result['style']
        lines += ['### Commit style', '- unmeasured' if style is None else
                  f"- {'conventional' if style['conventional'] else 'not conventional'} "
                  f"over {style['commits']} commits; scopes: {', '.join(style['scopes']) or 'none'}; "
                  f"sign-off: {'yes' if style['sign_off'] else 'no'}", '']
        lines += ['### PR baseline', '- unmeasured' if result['baseline'] is None else
                  '- ' + json.dumps(result['baseline'], sort_keys=True), '']
    lines += ['## Proposed config.toml changes', '']
    lines += ([f'Could not place the proposal: {error}', ''] if error else
              ['```diff', diff.rstrip('\n'), '```', ''] if diff else ['No config.toml changes', ''])
    if edits:
        lines += ['## Config differs; edit by hand', '']
        lines += [f'- {key}: config has {json.dumps(current)}, detected {json.dumps(detected)}'
                  for key, current, detected in edits] + ['']
    lines += ['## Charter proposals', ''] + [f'- {path}' for path in written] + (
        [] if written else ['- none']) + ['']
    lines += ['## Next step', '',
              '- Review this report, then run `bin/wuwei config promote` in a host terminal to apply '
              'the config proposal and record the approved calibration.',
              '- Run `bin/wuwei promote` to land the charter proposals.', '']
    return '\n'.join(lines)


def approved(root):
    """The owner-approved calibration snapshot; absent is {}."""
    path = Path(root) / '.wuwei/calibration.json'
    if path.is_symlink():
        raise ValueError('calibration.json must not be a symlink')
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not all(isinstance(v, dict) for v in data.values()):
        raise ValueError('malformed calibration.json')
    return data


def drift(root):
    """Compare each calibrated repository with its approved facts; one event per drift per day."""
    from wuwei import state, watch

    snapshot = approved(root)
    if not snapshot:
        return []
    seen = [row['payload'] for row in watch.records(workspace.day_dir(root) / 'events.jsonl')
            if row['kind'] == 'calibration.drift']
    drifts = []
    for repo in workspace.load_config(root)['repos']:
        if repo['name'] not in snapshot:
            continue
        checkout = (Path(root) / Path(repo['path']).expanduser()).resolve()
        try:
            if not checkout.is_dir():
                raise OSError('checkout is not a directory')
            current = drift_facts(profile(checkout, repo)['facts'])
            changed = [key for key in DRIFT if current[key] != snapshot[repo['name']].get(key)]
        except OSError:
            changed = ['unmeasured']
        if changed:
            payload = {'repo': repo['name'], 'changed': changed}
            if payload not in seen:
                state.append_event('calibration.drift', payload, root)
                seen.append(payload)
            drifts.append(payload)
    return drifts
