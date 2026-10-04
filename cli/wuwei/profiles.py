"""Shareable calibration profiles: export without anything personal, import as a proposal."""

import fnmatch
import json
from pathlib import Path
import re
import urllib.request

from wuwei import calibrate, decision, workspace
from wuwei.notes import SLUG_RE
from wuwei.exits import DAMAGED, SYMLINK


PLUGIN = Path(__file__).resolve().parents[2]
STARTERS = PLUGIN / 'templates/profiles'
ROLES = sorted(path.stem for path in (PLUGIN / 'charters').glob('*.md') if SLUG_RE.fullmatch(path.stem))
# Keys that name a person, a repository, a channel or this machine: never exported, never imported.
PRIVATE = ('owner', 'control_plane.owner', 'repos.name', 'repos.path', 'repos.default_branch',
           'repos.identity', 'repos.merge.bot_login', 'voice', 'outbound.work_channels',
           'outbound.external_channels', 'outbound.company_domains', 'outbound.code_host_orgs',
           'outbound.people', 'outbound.tiers', 'outbound.channel_classes',
           'shepherd.review_channel', 'shepherd.lead_login', 'shepherd.authors',
           'shepherd.reviewers', 'shepherd.reviewers_exclude', 'repos.shepherd',
           'tracker.backlog_filter', 'retro.repo', 'metrics.transcripts', 'scanner.mcp', 'guards',
           'security')
FLOORS = workspace.SCHEMA['repos'][0]['gates']['floor'][2]
# #313: what a profile may never carry, as (key pattern, refused(new, current)).
DENIED = (
    ('decisions.cruise.enabled', lambda new, old: new is True and old is False),
    ('decisions.cruise.levels.*', lambda new, old: new > old),
    ('repos.gates.floor', lambda new, old: FLOORS.index(new) < FLOORS.index(old)),
    ('repos.merge.auto', lambda new, old: new is True),
    ('shepherd.autostart', lambda new, old: new is True),
    ('gates.second_opinion', lambda new, old: new != 'off'),
    *((pattern, lambda new, old: True)
      for pattern in ('adapters.*', 'calendar.url', 'watch.ping_url', 'codex.command', 'telemetry.*')),
)
OUTSIDE = 'outside what a profile may carry'
# Private keys whose values say nothing about a person, so they are not searched for in text.
NOT_LITERALS = ('owner.verbosity', 'guards', 'security', 'repos.default_branch')
# ponytail: a one-segment /name (a slash command) is not a path; a path-shaped CODEOWNERS key
# such as /src/api/ is dropped, which is conservative.
ABSOLUTE = re.compile(r'''(?:^|[\s"'`=(,])(?:~/|[A-Za-z]:[\\/]|/[^\s/]+/)''')


def _leaves(tree, path=()):
    """(path, key, value) for every non-table value."""
    for key, value in tree.items():
        if isinstance(value, dict):
            yield from _leaves(value, (*path, key))
        else:
            yield path, key, value


def _nest(rows):
    tree = {}
    for path, key, value in rows:
        table = tree
        for part in path:
            table = table.setdefault(part, {})
        table[key] = value
    return tree


def _dotted(path, key):
    return '.'.join(map(str, (*path, key)))


def _strings(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for key, item in value.items() for s in (key, *_strings(item))]
    if isinstance(value, list):
        return [s for item in value for s in _strings(item)]
    return []


def _current(config, path, key):
    if path == ('decisions', 'cruise', 'levels'):
        return decision.level(config, key)
    return (calibrate._table(config, path) or {}).get(key)


def _under(dotted, prefixes):
    return any(dotted == prefix or dotted.startswith(prefix + '.') for prefix in prefixes)


def refusal(dotted, new, current):
    """Why a profile may not carry this key at this value, or None."""
    if _under(dotted, PRIVATE):
        return 'personal'
    for pattern, refused in DENIED:
        if fnmatch.fnmatchcase(dotted, pattern):
            try:
                if refused(new, current):
                    return OUTSIDE
            except (TypeError, ValueError, KeyError):
                return OUTSIDE
    return None


def _shape(profile):
    """The profile if it has the profile shape, else ValueError."""
    if not isinstance(profile, dict) or profile.get('wuwei_profile') != 1:
        raise ValueError('not a WUWEI profile (expected "wuwei_profile": 1); pass a file written by bin/wuwei calibrate export')
    if not isinstance(profile.get('name'), str) or not SLUG_RE.fullmatch(profile['name']):
        raise ValueError('profile name must be a lowercase slug; use lowercase letters, digits and dashes')
    profile.setdefault('config', {})
    profile.setdefault('charters', {})
    if not isinstance(profile['config'], dict) or not isinstance(profile['config'].get('repos', {}), dict):
        raise ValueError('profile config must be an object, and its repos one table; write the profile config as one object with one repos table')
    if not isinstance(profile['charters'], dict):
        raise ValueError(f'profile charters must be an object; {DAMAGED}')
    for role, block in profile['charters'].items():
        if (role not in ROLES or not isinstance(block, dict) or not isinstance(block.get('text'), str)
                or not isinstance(block.get('reasons'), list)
                or not all(isinstance(r, str) for r in block['reasons'])):
            raise ValueError(f'charters.{role}: expected a shipped role with text and a list of reasons; use a shipped role with text and a list of reasons')
    return profile


def read(source):
    """A profile from a starter name, an https URL or a file, at most 1 MiB."""
    if SLUG_RE.fullmatch(source) and (STARTERS / f'{source}.json').is_file():
        source = str(STARTERS / f'{source}.json')
    if re.match(r'[A-Za-z][A-Za-z0-9+.-]*://', source):
        if not source.startswith('https://'):
            raise ValueError('only https URLs are read; use an https URL')
        with urllib.request.urlopen(source, timeout=30) as response:
            if not response.geturl().startswith('https://'):
                raise ValueError('only https URLs are read; the source redirected elsewhere; use the final https URL')
            data = response.read(calibrate.MAX_BYTES + 1)
    else:
        with open(source, 'rb') as stream:
            data = stream.read(calibrate.MAX_BYTES + 1)
    if len(data) > calibrate.MAX_BYTES:
        raise ValueError('profile is over 1 MiB; split it or trim it below 1 MiB')
    try:
        return _shape(json.loads(data))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'profile is not JSON: {exc}') from None


def _targets(config, names):
    return [i for i, repo in enumerate(config['repos']) if repo['name'] in names]


def _expand(config, names, path):
    """A profile path as workspace paths: one per target repository for the repos table."""
    if path[:1] != ('repos',):
        return [path]
    return [('repos', index, *path[1:]) for index in _targets(config, names)]


def review(profile, config, names):
    """(accepted, refused [(key, why)], flagged [(where, rule)]) for the target repositories."""
    rows = list(_leaves(profile['config']))
    if 'repos' in profile['config'] and not _targets(config, names):
        raise ValueError(calibrate.NO_REPOS)
    refused = sorted({(_dotted(path, key), why) for path, key, value in rows
                      for where in _expand(config, names, path)
                      for why in [refusal(_dotted(path, key), value, _current(config, where, key))] if why})
    flagged, keep = [], []
    for path, key, value in rows:
        hits = [(_dotted(path, key), rule) for text in (_dotted(path, key), *_strings(value))
                for _, rule in calibrate.instruction_like(text)]
        flagged += dict.fromkeys(hits)
        if not hits:
            keep.append((path, key, value))
    charters = {}
    for role, block in profile['charters'].items():
        hits = [(f'charters.{role}:{line}', rule) for line, rule in calibrate.instruction_like(block['text'])]
        hits += [(f'charters.{role} reason {n}', rule) for n, reason in enumerate(block['reasons'], 1)
                 for _, rule in calibrate.instruction_like(reason)]
        flagged += dict.fromkeys(hits)
        if not hits:
            charters[role] = block
    accepted = {'wuwei_profile': 1, 'name': profile['name'], 'config': _nest(keep), 'charters': charters}
    return accepted, refused, flagged


def settings(accepted, config, names):
    """The accepted config as calibrate (path, key, value) settings."""
    return [(where, key, value) for path, key, value in _leaves(accepted['config'])
            for where in _expand(config, names, path)]


def skip(profile, accepted, keys):
    """The accepted part without the dotted config keys or charters.<role> blocks the owner skips."""
    known = {_dotted(path, key) for path, key, _ in _leaves(profile['config'])}
    known |= {f'charters.{role}' for role in profile['charters']}
    unknown = [key for key in keys if key not in known]
    if unknown:
        raise ValueError(('--skip names nothing in the profile: ' + ', '.join(unknown)
                         + '; pass names the profile has'))
    return {**accepted, 'config': _nest(row for row in _leaves(accepted['config']) if _dotted(*row[:2]) not in keys),
            'charters': {role: block for role, block in accepted['charters'].items()
                         if f'charters.{role}' not in keys}}


def record(root, accepted, names):
    """Write today's profile.json and one charter add proposal per role; return the proposal paths."""
    from wuwei import promotion

    day = workspace.day_dir(root)
    (day / 'proposals').mkdir(parents=True, exist_ok=True)
    evidence = f'.wuwei/days/{day.name}/profile.json'
    workspace.atomic_write(day / 'profile.json',
                           json.dumps({**accepted, 'repos': names}, indent=2, sort_keys=True) + '\n')
    written = []
    for role in ROLES:
        path = day / 'proposals' / f'profile-{role}.json'
        block = accepted['charters'].get(role)
        text = ''
        if block:
            target = f'.wuwei/charters/{role}.md'
            override = promotion.safe_path(root, target, label='charter')
            present = promotion._lines((override if override.exists() else PLUGIN / 'charters' / f'{role}.md')
                                       .read_text(encoding='utf-8'))
            text = ''.join(line + '\n' for line in block['text'].splitlines()
                           if line.strip() and line.strip().casefold() not in present)
        if text:
            reasons = '; '.join(block['reasons'])
            workspace.atomic_write(path, json.dumps({
                'target': target, 'action': 'add', 'text': text,
                'reason': f"profile {accepted['name']}" + (f': {reasons}' if reasons else ''),
                'evidence': evidence}, indent=2) + '\n')
            written.append(f'.wuwei/days/{day.name}/proposals/{path.name}')
        elif path.exists() or path.is_symlink():
            path.unlink()
    return written


def load(root, config):
    """Today's imported profile as (name, settings), re-checked against the current config."""
    path = workspace.day_dir(root) / 'profile.json'
    if path.is_symlink():
        raise ValueError(f'profile.json must not be a symlink; {SYMLINK}')
    if not path.exists():
        return None, []
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        names = data.pop('repos', None) if isinstance(data, dict) else None
        configured = [repo['name'] for repo in config['repos']]
        if not isinstance(names, list) or not all(name in configured for name in names):
            raise ValueError('repos must list configured repositories; use names from [[repos]]')
        profile = _shape(data)
        accepted, refused, flagged = review(profile, config, names)
        if refused or flagged:
            raise ValueError('carries ' + ', '.join([key for key, _ in refused] + [where for where, _ in flagged]))
    except ValueError as exc:
        raise ValueError(f'profile.json: {exc}') from None
    return profile['name'], settings(accepted, config, names)


def _template():
    """The shipped template config, validated, with one default repository as its repos table."""
    import tomllib

    text = (PLUGIN / 'templates/workspace/config.toml').read_text(encoding='utf-8')
    base = workspace._validate(tomllib.loads(text), workspace.SCHEMA, (), text)
    base['repos'] = workspace._validate({'name': '-', 'path': '-', 'default_branch': '-'},
                                        workspace.SCHEMA['repos'][0], ('repos', 0), '')
    return base


def _changed(current, base):
    return [(path, key, value) for path, key, value in _leaves(current)
            if key not in (calibrate._table(base, path) or {}) or calibrate._table(base, path)[key] != value]


def _literals(root, config, base):
    """One pattern matching, as a whole word, any value that names a person, repository or machine."""
    found = {str(root), str(Path.home()), *config['outbound']['people'], *config['shepherd']['authors']}
    for repo in config['repos'] or [base['repos']]:
        found.update(s for path, key, value in _changed({**config, 'repos': repo}, base)
                     if _under(_dotted(path, key), PRIVATE) and not _under(_dotted(path, key), NOT_LITERALS)
                     for s in _strings(value))
    words = sorted((s for s in found if re.search(r'\w', s)), key=len, reverse=True)
    return re.compile(r'(?<!\w)(?:' + '|'.join(map(re.escape, words)) + r')(?!\w)', re.I)


def _why(text, literals, redactor, root):
    """Why this text may not leave the workspace, or None; a redactor that cannot run raises."""
    if literals.search(text):
        return 'personal'
    if ABSOLUTE.search(text):
        return 'absolute path'
    result = redactor.redact(text, root=root)
    try:
        if result.exit not in (0, 1):
            raise ValueError
        kinds = sorted({finding['kind'] for finding in result.data['findings']})
    except (AttributeError, KeyError, TypeError, ValueError):
        raise OSError(f"redactor could not run: {getattr(result, 'reason', '') or 'malformed result'}") from None
    return ', '.join(kinds) if result.exit else None


def export(root, config, name, repo=None):
    """The profile of this workspace: config and charter additions, minus anything personal."""
    from wuwei import promotion, registry

    if not SLUG_RE.fullmatch(name):
        raise ValueError('profile name must be a lowercase slug; use lowercase letters, digits and dashes')
    chosen = next((r for r in config['repos'] if repo in (None, r['name'])), None)
    if repo and chosen is None:
        raise ValueError(f'unknown repository {repo!r}; use a configured repos.name')
    base = _template()
    literals, redactor = _literals(root, config, base), registry.load('redactor', config)

    def why(*texts):
        return next(filter(None, (_why(text, literals, redactor, root) for text in texts)), None)

    dropped, keep = [], []
    for path, key, value in _changed({**config, 'repos': chosen or base['repos']}, base):
        dotted = _dotted(path, key)
        reason = refusal(dotted, value, _current(base, path, key)) or why(dotted, *_strings(value))
        if reason:
            dropped.append({'where': f'config.{dotted}', 'why': reason})
        else:
            keep.append((path, key, value))
    ledger = promotion.safe_path(root, '.wuwei/memory/ledger.jsonl', label='ledger')
    try:
        rows = [json.loads(line) for line in (ledger.read_text(encoding='utf-8') if ledger.exists() else '')
                .splitlines() if line.strip()]
        if not all(isinstance(row, dict) for row in rows):
            raise ValueError(f'expected one object per line; {DAMAGED}')
    except ValueError as exc:
        raise ValueError(f'ledger.jsonl: {exc}') from None
    charters = {}
    for role in ROLES:
        target = f'.wuwei/charters/{role}.md'
        override = promotion.safe_path(root, target, label='charter')
        if not override.exists():
            continue
        shipped = promotion._lines((PLUGIN / 'charters' / f'{role}.md').read_text(encoding='utf-8'))
        text = ''
        for number, line in enumerate(override.read_text(encoding='utf-8').splitlines(), 1):
            if line.strip() and line.strip().casefold() not in shipped:
                reason = why(line)
                if reason:
                    dropped.append({'where': f'charters.{role}:{number}', 'why': reason})
                else:
                    text += line + '\n'
        reasons = []
        landed = dict.fromkeys(row['reason'] for row in rows if row.get('status') == 'landed'
                               and row.get('target') == target and isinstance(row.get('reason'), str))
        for number, line in enumerate(landed, 1):
            reason = why(line)
            if reason:
                dropped.append({'where': f'charters.{role} reason {number}', 'why': reason})
            else:
                reasons.append(line)
        if text:
            charters[role] = {'text': text, 'reasons': reasons}
    return {'wuwei_profile': 1, 'name': name, 'config': _nest(keep), 'charters': charters, 'dropped': dropped}
