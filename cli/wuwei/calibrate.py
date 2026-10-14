"""Profile a checkout and propose workspace configuration; repository text is data, never a rule."""

from datetime import datetime
import difflib
import fnmatch
import json
import os
from pathlib import Path
import re
import statistics
from time import monotonic
import tomllib

from wuwei import configtext, registry, workspace
from wuwei.commands.init import _preserves_values, _sections
from wuwei.guards.edges import VERBS
from wuwei.workspace import MERGE_SCHEMA
from wuwei.exits import DAMAGED, SYMLINK


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
    # #600: a repository with no code (a paper) still declares its checks
    for names, command in ((MARKDOWNLINT, 'markdownlint .'), (('.latexmkrc', 'latexmkrc'), 'latexmk')):
        name = next((name for name in names if _read(checkout, name, found) is not None), None)
        if name:
            found.append(_finding('fast_check', command, name, 1))
    if not any(f['kind'] == 'fast_check' for f in found):  # only then a CI test step
        for _, relative, flow in _workflows(checkout, found):
            if flow['triggers'] & {'pull_request', 'push'}:
                found += [_finding('fast_check', command, relative, number) for job in flow['jobs']
                          if re.search(r'(?i)test|check|lint', job['id'] + ' ' + job['name'][0])
                          for command, number in job['runs']
                          if TEST_STEP.match(command) and not re.search(r'[;&|<>$`]', command)]
    return found


MARKDOWNLINT = ('.markdownlint.json', '.markdownlint.jsonc', '.markdownlint.yaml', '.markdownlint.yml',
                '.markdownlintrc')
# ponytail: a line regex over single-line run steps; an install step naming a test word is the
# ceiling. A YAML reader if a real repository needs one. A line with a shell control or expansion
# character is never one simple command, so it is never proposed (#600 review F1).
TEST_STEP = re.compile(r'(?!(?:pip3?|npm (?:ci|install)|apt(?:-get)?|brew|sudo|cd|echo)\b)'
                       r'.*\b(?:pytest|test|tests|check|lint|latexmk|markdownlint)\b')
LINT = ('ruff check .', 'black --check .', 'npm run lint', 'make lint', 'markdownlint .')
UNMEASURED = 'test runner, unmeasured; run bin/wuwei config promote --measure'


NEAR = 0.8  # #724: a measured run at 80 % of its limit proposes twice the limit


def classify(checkout, commands, runner, seconds, root=None, timeout=300, measured=None):
    """{command: (fast, note)}: lint and format are fast; a test runner only when measured fast."""
    checks = {}
    for command in commands:
        if command in LINT:
            checks[command] = (True, 'lint or format')
        elif runner is None:
            checks[command] = (False, UNMEASURED)
        else:
            # ponytail: one full timed run, capped by repos.<n>.check_timeout_seconds; add a
            # collect-only command if --measure proves too slow.
            start = monotonic()
            result = runner.run(str(checkout), command, timeout=timeout, root=root)
            took = monotonic() - start
            if measured is not None:
                measured[command] = took
            ok = isinstance(result, registry.Result) and result.exit == 0
            note = f'test runner, measured {took:.1f} s, threshold {seconds} s'
            if not ok:
                note += f", exit {getattr(result, 'exit', 2)}" + (
                    f': {result.reason}' if getattr(result, 'reason', '') else '')
            if took >= NEAR * timeout:
                note += f', near the {timeout} s check timeout'
            checks[command] = (ok and took <= seconds, note)
    return checks


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
    listed = step = at = block = base = None  # #733: steps indent, open step, its key indent, run block
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
                job = {'name': (key, number), 'id': key, 'continue': False, 'matrix': None,
                       'environment': None, 'signals': [], 'runs': [], 'steps': []}
                jobs.append(job)
                prop = matrix = environment = listed = step = block = None
                continue
            if job is None:
                continue
            if prop is None:
                prop = indent
            flush = listed and indent == prop and line.startswith('-')  # steps: list at its key's indent
            if block and indent > at:
                # ponytail: blank and comment lines inside a run block are dropped with the rest
                base = indent if base is None else base
                step['run'] = (step['run'] + '\n' if step['run'] else '') + raw[base:].rstrip()
            elif listed and (indent > prop or flush):
                block = None
                listed = indent if listed is True else listed
                dash = indent == listed and line.startswith('-')
                if dash:
                    step = {'name': None, 'run': None, 'line': number}
                    job['steps'].append(step)
                    rest = line[1:].lstrip()
                    at = indent + len(line) - len(rest)
                    key, _, value = rest.partition(':')
                    key, value = key.strip('\'"'), value.strip()
                if step and (dash or indent == at) and key in ('name', 'run'):
                    block = key == 'run' and re.fullmatch(r'[|>][-+]?\s*(#.*)?', value)
                    base = None
                    if not block:
                        step[key] = _scalar(value)
            else:
                block = None
            if indent == prop and not flush:
                matrix = environment = None
                listed = key == 'steps' or None
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
            run = re.match(r'-?\s*run:\s*([^\s|>].*)', line)  # #600: single-line steps only
            if run:
                job['runs'].append((_scalar(run[1]), number))
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
    facts['merge_deploys'] = deploys(facts)
    return {'findings': findings, 'facts': facts}


def deploys(facts):
    """Whether the measured facts say a merge deploys: a deploy workflow, deny command or never-auto path."""
    return bool(facts['deploy_workflows'] or facts['deploy_deny'] or facts['never_auto'])


def drift_facts(facts):
    return {key: sorted(facts[key]) for key in DRIFT}


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
LAYOUT = 'cannot place this value in this config.toml layout; edit by hand, then run bin/wuwei config check'


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


def proposal(raw, targets):
    """Additive config proposal for [(repo index, facts)]: (additions, hand edits).

    Only keys absent from the raw TOML are added, plus deploy lists and fast_checks still at a
    one-line [];
    any other present key that differs is listed for a hand edit. Never proposes a weakening.
    """
    present = tomllib.loads(raw)
    defaults = MERGE_SCHEMA['never_auto_paths'][1]
    wanted, deploy, registers = [], {'deny': set()}, {'environments': {}, 'boundary': {}}
    for index, facts in targets:
        base = ('repos', index)
        for key, value in (('fast_checks', facts['fast_checks']),
                           ('review_required_checks', facts['required_checks']),
                           ('merge_deploys', facts['merge_deploys'] or None),
                           ('check_timeout_seconds', facts.get('check_timeout_seconds'))):
            if value:
                wanted.append((base, key, value))
        if facts['never_auto']:
            wanted.append(((*base, 'merge'), 'never_auto_paths',
                           [*defaults, *(p for p in facts['never_auto'] if p not in defaults)]))
        deploy['deny'].update(facts['deploy_deny'])
        registers['environments'].update(facts['environments'])
        registers['boundary'].update(facts['boundary'])
    wanted += [(('deploy',), key, sorted(values)) for key, values in deploy.items() if values]
    wanted += [((table,), name, text) for table, names in registers.items() for name, text in names.items()]
    sections = _labelled(raw)
    additions, edits = [], []
    for path, key, value in wanted:
        table = _table(present, path)
        if table is None or key not in table:
            additions.append((path, key, value))
        elif path and path[0] in registers:
            continue
        elif ((path == ('deploy',) or key == 'fast_checks') and table[key] == []
              and any(_empty_list(key, l) for p, lines in sections if p == path for l in lines)):
            additions.append((path, key, value))
        elif (not set(value) <= set(table[key]) if isinstance(value, list) else table[key] != value):
            edits.append(('.'.join(map(str, (*path, key))), table[key], value))
    return additions, edits


def apply(raw, additions):
    """Place additions through the config writer and prove every other owner value is unchanged."""
    if not additions:
        return raw
    text, commented, before = raw, set(), tomllib.loads(raw)
    for path, key, value in additions:
        dotted = '.'.join(map(str, (*path, key)))
        absent = key not in (_table(tomllib.loads(text), path) or {})
        try:
            text = configtext.place(text, path, key, value,
                                    COMMENT if absent and path not in commented else None)
            tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            raise ValueError(f'{dotted}: {LAYOUT}') from None
        if absent:
            commented.add(path)
    parsed = tomllib.loads(text)
    for path, key, _ in additions:
        (_table(before, path) or {}).pop(key, None)
    if not _preserves_values(before, parsed):
        path, key, _ = additions[0]
        raise ValueError(f"{'.'.join(map(str, (*path, key)))}: {LAYOUT}")
    for path, key, value in additions:
        if (_table(parsed, path) or {}).get(key) != value:
            raise ValueError(f"{'.'.join(map(str, (*path, key)))}: {LAYOUT}")
    workspace._validate(parsed, workspace.SCHEMA, (), text)
    return text


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


def measure_checks(root, config, result, runner):
    """Classify a surveyed result's checks; a run near its limit proposes twice the limit (#724)."""
    limit, measured = result['repo']['check_timeout_seconds'], {}
    result['checks'] = classify(result['checkout'], result['facts']['fast_checks'], runner,
                                config['calibrate']['fast_check_seconds'], root, limit, measured)
    result['check_timeout'] = 2 * limit if max(measured.values(), default=0) >= NEAR * limit else None


def survey(root, config, selected, *, measure=False):
    """Profile and classify each selected (index, repo), then read the PR baseline.

    Test runners run only with measure, through the checks port.
    """
    results = []
    runner = registry.load('checks', config) if measure else None
    for index, repo in selected:
        checkout = (Path(root) / Path(repo['path']).expanduser()).resolve()
        if not checkout.is_dir():
            raise OSError(f"{repo['name']}: checkout {repo['path']} is not a directory; restore the checkout, or the owner fixes repos.<n>.path with bin/wuwei config set")
        result = {'index': index, 'repo': repo, 'checkout': checkout, **profile(checkout, repo)}
        measure_checks(root, config, result, runner)
        results.append(result)
    host = registry.load('code_host', config)
    for result in results:
        result['baseline'] = _port(host.merged_prs(result['repo']['name'], root=root), baseline)
    return results


def proposed(result):
    """The facts to propose: only the fast checks; result['facts'] stays raw for drift."""
    return {**result['facts'], 'fast_checks': [c for c, (fast, _) in result['checks'].items() if fast],
            'check_timeout_seconds': result.get('check_timeout')}


def ci_only(results):
    """(repo name, command, note) for every check not proposed as a fast check."""
    return [(r['repo']['name'], c, note) for r in results for c, (fast, note) in r['checks'].items()
            if not fast]


def grows(path, current):
    """A deploy list only grows: an answer never removes a deploy-ban pattern."""
    return path == ('deploy',) and isinstance(current, list)


def settle(raw, settings):
    """Owner answers as (additions, hand edits): absent keys added, present ones replaced in place;
    a table answered with a non-table is a hand edit.

    A deploy list keeps every present item, so an answer never removes a deploy-ban pattern.
    """
    present = tomllib.loads(raw)
    additions, edits = [], []
    for path, key, value in settings:
        table = _table(present, path)
        if table is None or key not in table:
            additions.append((path, key, value))
            continue
        current = table[key]
        if grows(path, current):
            value = [*current, *(item for item in value if item not in current)]
        if current == value:
            continue
        if isinstance(current, dict) and not isinstance(value, dict):
            edits.append(('.'.join(map(str, (*path, key))), current, value))
        else:
            additions.append((path, key, value))
    return additions, edits


def propose(raw, results):
    """Return the proposed config text, its diff and the hand edits."""
    additions, edits = proposal(raw, [(r['index'], proposed(r)) for r in results])
    text = apply(raw, additions)
    diff = ''.join(difflib.unified_diff(raw.splitlines(keepends=True), text.splitlines(keepends=True),
                                        'config.toml', 'config.toml (proposed)'))
    return text, diff, edits


def approved(root):
    """The owner-approved calibration snapshot; absent is {}."""
    path = Path(root) / '.wuwei/calibration.json'
    if path.is_symlink():
        raise ValueError(f'calibration.json must not be a symlink; {SYMLINK}')
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not all(isinstance(v, dict) for v in data.values()):
        raise ValueError(f'malformed calibration.json; {DAMAGED}')
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
                raise OSError('checkout is not a directory; restore the checkout, or the owner fixes repos.<n>.path with bin/wuwei config set')
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
