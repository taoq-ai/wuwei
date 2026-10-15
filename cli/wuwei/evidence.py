"""What a pull request still lacks. One pure reading of the artifacts: it never asks how the work was done."""

import datetime
import fnmatch
import hashlib
from pathlib import Path
import re

from wuwei import gh, plan, ws
from wuwei.verdict import parse

REQUIRED = {'light': ('quality',), 'standard': ('arch', 'quality', 'security'),
            'full': ('arch', 'quality', 'security', 'goal')}
TEST = re.compile(r'(^|/)(tests?|spec|__tests__)/|(^|/)test_[^/]+$|_test\.\w+$|\.(test|spec)\.\w+$')
DOCS = re.compile(r'\.(md|rst|txt|adoc)$|(^|/)docs/|^LICENSE|^NOTICE')
GENERATED = re.compile(r'(^|/)([\w.-]+\.lock|package-lock\.json|pnpm-lock\.yaml|go\.sum)$|\.min\.(js|css)$'
                       r'|(^|/)(dist|vendor|__snapshots__)/')
TEMPLATES = ('.github/pull_request_template.md', '.github/PULL_REQUEST_TEMPLATE.md', 'PULL_REQUEST_TEMPLATE.md',
             'docs/pull_request_template.md')
# Each engine's artifacts per tier, read at the PR head: (path under the feature, rule).
SPEC_RULES = {
    '.specify': (r'^(specs/[^/]+/)(spec\.md)$', {'standard': (('spec.md', 'present'), ('plan.md', 'present'), ('tasks.md', 'checked')),
                                       'full': (('spec.md', 'clarified'), ('analysis.md', 'clean'),
                                                ('checklists/', 'checked'))}),
    'openspec': (r'^(openspec/changes/(?:archive/)?[^/]+/)(proposal\.md|specs/.+)$', {'standard': (('proposal.md', 'present'),
                                                                          ('specs/', 'present'),
                                                                          ('tasks.md', 'checked')),
                                                              'full': ()}),
}
BOX = re.compile(r'^\s*[-*] \[([ xX])\]', re.M)
# Process fit, never a block: recorded at merge for the retro, shown to nobody while the work flows.
PROCESS = re.compile(r"^(specs/|openspec/|no spec in the diff|PR body misses the repository template|\d+ changed lines"
                     r"|open \d+ days|no Rollback: line|not linked to a plan item|no reviewer requested)")
RAISE = {'light': 'standard', 'standard': 'full', 'full': 'full'}
MAX_LINES, STALE_DAYS, BUDGET = 400, 3, 0.15
FAILED = {'FAILURE', 'CANCELLED', 'TIMED_OUT', 'ACTION_REQUIRED', 'STARTUP_FAILURE', 'ERROR'}
DAY = 86400


def gap(text, actionable=True, owner=False):
    return {'text': text, 'actionable': actionable, 'owner': owner, 'kind': 'process' if PROCESS.search(text) else 'safety'}


def blocking(found):
    """The safety gaps: the only ones that hold a merge or reach the team while it works."""
    return [g for g in found if g['kind'] == 'safety']


def item_for(root, pr, repo=None):
    """The plan item a PR names with a WUWEI-Item: trailer, records among its PRs, or whose id starts
    its branch name."""
    match = re.search(r'^WUWEI-Item:[ \t]*(\S+)', pr.get('body') or '', re.M)
    if match:
        return plan.find(root, match[1])
    ref = f'{repo}#{pr.get("number")}' if repo else None
    linked = next((item for item in plan.items(root) if ref and ref in item.get('prs', ())), None)
    if linked:
        return linked
    branch = (pr.get('headRefName') or '').lower()
    return next((item for item in plan.items(root)
                 if branch == item['id'].lower() or branch.startswith(item['id'].lower() + '-')), None)


def _cached(root, name, read, max_age=DAY):
    value = ws.cache_get(root, name, max_age)
    return ws.cache_put(root, name, read()) if value is None else value


def spec_engine(root, repo):
    def read():
        return next((path for path in ('.specify', 'openspec') if gh.has_path(repo, path)), '')
    return _cached(root, 'spec-' + repo.replace('/', '__'), read)


def template_sections(root, repo):
    """The headings of the repository's PR template, which every PR body keeps."""
    def read():
        for path in TEMPLATES:
            try:
                return re.findall(r'^#+\s+(.+?)\s*$', gh.file(repo, path), re.M)
            except gh.GhError:
                continue
        return []
    return _cached(root, 'template-' + repo.replace('/', '__'), read)


DEFERRED = re.compile(r'^(#+)\s+(?:\d+(?:\.\d+)*\.?\s*)?(Deferred|Out of this PR)\b', re.I)
REASON = re.compile(r'\(.+\)|\bbecause\b|\bwaits? on\b|\bblocked by\b|\breason:', re.I)


def _counted(text):
    """The checklist lines that count: a box under a Deferred or Out of this PR heading is left out
    when its line says why (#1037); the section ends at the next heading of the same or a higher level."""
    kept, level = [], None
    for line in text.splitlines():
        heading = re.match(r'^(#+)\s', line)
        if heading and level is not None and len(heading[1]) <= level:
            level = None
        deferred = DEFERRED.match(line)
        if deferred:
            level = len(deferred[1])
            continue
        if level is not None and BOX.match(line) and REASON.search(line):
            continue
        kept.append(line)
    return '\n'.join(kept)


def _unchecked(path, text):
    boxes = BOX.findall(_counted(text))
    open_boxes = sum(1 for box in boxes if box == ' ')
    if not boxes:
        return f'{path} has no checklist items'
    return f'{path} has {open_boxes} unchecked item{"s" if open_boxes > 1 else ""}' if open_boxes else None


def _rule(repo, path, rule, head):
    """None when the artifact at the head meets its rule, else the gap text."""
    if path.endswith('/'):
        entries = gh.listing(repo, path.rstrip('/'), head)
        if not entries:
            return f'{path} missing: run the spec engine step that writes it'
        if rule != 'checked':
            return None
        for entry in (e for e in entries if e.get('type') == 'file' and e['name'].endswith('.md')):
            problem = _unchecked(entry['path'], gh.file(repo, entry['path'], head))
            if problem:
                return problem
        return None
    try:
        text = gh.file(repo, path, head)
    except gh.GhError:
        return f'{path} missing: run the spec engine step that writes it'
    if rule == 'checked':
        return _unchecked(path, text)
    if rule == 'clarified' and not re.search(r'^##\s+(?:\d+(?:\.\d+)*\.?\s*)?Clarifications\b', text, re.M | re.I):
        return f'{path} has no ## Clarifications section: run clarify'
    if rule == 'clean':
        for line in text.splitlines():
            cells = {cell.strip().upper() for cell in line.strip().strip('|').split('|')}
            if line.lstrip().startswith('|') and cells & {'CRITICAL', 'HIGH'}:
                return f'{path} has an open CRITICAL or HIGH finding: {line.strip()[:100]}'
    return None


def spec_gaps(repo, engine, tier, files, head):
    """The spec engine's steps, judged by their artifacts at the head, for each feature whose spec
    (spec-kit spec.md, OpenSpec proposal or spec deltas) the PR adds or edits. A PR that only amends an
    older feature's other files is held to its own scope, not to that feature's whole set (#1032)."""
    if not engine:
        return []
    pattern, rules = SPEC_RULES[engine]
    features = sorted({m[1] for m in (re.match(pattern, path) for path in files) if m})
    if not features:
        if any(path.startswith(('specs/', 'openspec/')) for path in files):
            return []
        return [gap(f'no spec in the diff (the repository uses {engine})')]
    wanted = rules['standard'] + (rules['full'] if tier == 'full' else ())
    found = []
    for feature in features:
        for name, rule in wanted:
            problem = _rule(repo, feature + name, rule, head)
            if problem and gap(problem) not in found:
                found.append(gap(problem))
    return found


def budget(root, repo):
    """The 28-day change failure rate; over BUDGET with five or more merges raises every tier one step."""
    def read():
        import datetime
        since = (ws.now() - datetime.timedelta(days=28)).date().isoformat()
        try:
            merged = [pr for pr in gh.merged_prs(repo, since) if pr.get('mergedAt')]
        except gh.GhError:
            return {'cfr': None, 'merged': 0}
        reverts = sum(1 for pr in merged if pr.get('title', '').startswith('Revert'))
        return {'cfr': round(reverts / len(merged), 2) if merged else None, 'merged': len(merged)}
    found = _cached(root, 'budget-' + repo.replace('/', '__'), read)
    return {**found, 'raised': found['cfr'] is not None and found['merged'] >= 5 and found['cfr'] > BUDGET}


def owner_login(root):
    return _cached(root, 'login', gh.login)


def verdicts(root, item_id):
    """Attested, well-formed verdicts for an item, oldest first. An edited file no longer counts."""
    found = []
    for row in ws.rows(root, 'attest'):
        data = row['data']
        if str(data.get('item', '')).lower() != str(item_id).lower():
            continue
        path = Path(root) / data.get('path', '')
        try:
            body = path.read_bytes()
        except OSError:
            continue
        if hashlib.sha256(body).hexdigest() != data.get('sha256'):
            continue
        if data.get('imported'):
            found.append({'gate': data['gate'], 'verdict': data['verdict'], 'head': data['head']})
            continue
        parsed = parse(body.decode('utf-8', 'replace'))
        if not parsed['errors']:
            found.append(parsed)
    return found


def gate_gaps(root, repo, item_id, tier, head, why=''):
    latest = {}
    for found in verdicts(root, item_id):
        if gh.ancestor(repo, found['head'], head):
            latest[found['gate']] = found
    passed = {gate: v for gate, v in latest.items() if v['verdict'] == 'PASS'}
    missing = [gate for gate in REQUIRED[tier] if gate not in passed]
    if missing:
        return [gap(f'gates missing at head {head[:7]}: {", ".join(missing)}{why}')] + uncounted(root, item_id)
    if not any(head.startswith(v['head']) for v in passed.values()):
        return [gap(f'no gate passed at head {head[:7]} (a delta review)')] + uncounted(root, item_id)
    return []


def uncounted(root, item_id):
    """Verdict files for the item that do not count, each with the reason: never a silent missing gate."""
    base = Path(root) / ws.DIR / 'verdicts'
    if not item_id or not base.is_dir():
        return []
    attested = {row['data'].get('sha256') for row in ws.rows(root, 'attest')}
    found = []
    for path in sorted(base.rglob('*.md')):
        if not (path.parent.name.lower() == item_id.lower() or path.name.lower().startswith(item_id.lower() + '-')):
            continue
        body = path.read_bytes()
        if hashlib.sha256(body).hexdigest() in attested:
            continue
        parsed = parse(body.decode('utf-8', 'replace'))
        why = parsed['errors'][0] if parsed['errors'] else (
            f'not attested: launch the gate as agent type sentinel-{parsed["gate"]} and end its report with '
            f'"Verdict file: {path.relative_to(root)}"')
        found.append(gap(f'verdict {path.relative_to(root)} not counted: {why}'))
    return found


def ci_gaps(rollup):
    failed, running = [], False
    for check in rollup or ():
        name = check.get('name') or check.get('context') or 'check'
        state = (check.get('conclusion') or check.get('state') or '').upper()
        if state in FAILED:
            failed.append(name)
        elif check.get('status', 'COMPLETED').upper() != 'COMPLETED' or state in ('PENDING', 'EXPECTED'):
            running = True
    if failed:
        return [gap('CI failing: ' + ', '.join(failed))]
    return [gap('CI running', actionable=False)] if running else []


def gaps(root, repo, number):
    try:
        pr = gh.pr(repo, number)
        found = []
        item = item_for(root, pr, repo)
        tier = (item or {}).get('tier', 'standard')
        files = [f['path'] for f in pr.get('files') or ()]
        body = pr.get('body') or ''
        head = pr['headRefOid']
        if item is None:
            found.append(gap('not linked to a plan item (add WUWEI-Item: <id> to the PR body)'))
        missing = [s for s in template_sections(root, repo) if s.lower() not in body.lower()]
        if missing:
            found.append(gap(f"PR body misses the repository template's sections: {', '.join(missing)}"))
        if tier != 'light':
            found += spec_gaps(repo, spec_engine(root, repo), tier, files, head)
        code = [path for path in files if not DOCS.search(path) and not path.startswith(('specs/', 'openspec/'))]
        if code and not any(TEST.search(path) for path in files) and not re.search(r'^No test:\s*\S', body, re.M):
            found.append(gap('no test in the diff'))
        size = sum(f.get('additions', 0) + f.get('deletions', 0) for f in pr.get('files') or ()
                   if not GENERATED.search(f['path']))
        if size > MAX_LINES and not re.search(r'^Size:\s*\S', body, re.M):
            found.append(gap(f'{size} changed lines: split it, or add a Size: <reason> line'))
        patterns = ws.config(root)['owner_paths']
        owned = [path for path in files if any(fnmatch.fnmatch(path, p) for p in patterns)]
        if (tier == 'full' or owned) and not re.search(r'^Rollback:\s*\S', body, re.M):
            found.append(gap('no Rollback: line (how to undo this change)'))
        spent = budget(root, repo)
        why = ''
        if spent['raised'] and tier != 'full':
            tier, why = RAISE[tier], f' (tier raised to {RAISE[tier]}: change failure rate {spent["cfr"]:.0%} over 28 days)'
        found += gate_gaps(root, repo, (item or {}).get('id', ''), tier, head, why)
        found += ci_gaps(pr.get('statusCheckRollup'))
        author = (pr.get('author') or {}).get('login', '')
        threads = gh.unanswered_threads(repo, number, author)
        if threads:
            found.append(gap(f'{threads} review thread{"s" if threads > 1 else ""} unanswered'))
        reviewers = [r for r in pr.get('reviews') or () if (r.get('author') or {}).get('login') != author]
        if not pr.get('reviewRequests') and not reviewers:
            found.append(gap('no reviewer requested'))
        if owned and not owner_approved(root, repo, pr):
            found.append(gap(f'owner review needed (owner_paths: {", ".join(owned[:3])})', actionable=False, owner=True))
        age = (ws.now() - datetime.datetime.fromisoformat(pr['createdAt'].replace('Z', '+00:00'))).days
        if age >= STALE_DAYS and pr.get('state', 'OPEN') == 'OPEN':
            found.append(gap(f'open {age} days: finish, rebase or close'))
        return excepted(root, f'{repo}#{number}', head, found)
    except (gh.GhError, KeyError, TypeError) as exc:
        return [gap(f'evidence unreadable: {exc}', actionable=False)]


def excepted(root, ref, head, found):
    """Drop the gaps the owner accepted at this head; each acceptance is an exception on the record."""
    accepted = [row['data'].get('gap', '') for row in ws.rows(root, 'ruling')
                if row['data'].get('kind') == 'exception' and row['data'].get('approved')
                and row['data'].get('pr') == ref and head.startswith(row['data'].get('head') or '-')]
    near = lambda a, g: a.casefold() in g.casefold() or g.casefold() in a.casefold()  # noqa: E731
    return [g for g in found if not any(a and near(a, g['text']) for a in accepted)]


def owner_approved(root, repo, pr):
    login = owner_login(root)
    if any((r.get('author') or {}).get('login') == login and r.get('state') == 'APPROVED' for r in pr.get('reviews') or ()):
        return True
    ref = f'{repo}#{pr["number"]}'
    return any(row['data'].get('pr') == ref and pr['headRefOid'].startswith(row['data'].get('head', '-'))
               and row['data'].get('approved') for row in ws.rows(root, 'ruling'))
