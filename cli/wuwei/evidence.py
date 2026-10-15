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
RAISE = {'light': 'standard', 'standard': 'full', 'full': 'full'}
MAX_LINES, STALE_DAYS, BUDGET = 400, 3, 0.15
FAILED = {'FAILURE', 'CANCELLED', 'TIMED_OUT', 'ACTION_REQUIRED', 'STARTUP_FAILURE', 'ERROR'}
DAY = 86400


def gap(text, actionable=True, owner=False):
    return {'text': text, 'actionable': actionable, 'owner': owner}


def item_for(root, pr):
    """The plan item a PR names with a WUWEI-Item: trailer, or whose id starts its branch name."""
    match = re.search(r'^WUWEI-Item:[ \t]*(\S+)', pr.get('body') or '', re.M)
    if match:
        return plan.find(root, match[1])
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
        return [gap(f'gates missing at head {head[:7]}: {", ".join(missing)}{why}')]
    if not any(v['head'] == head for v in passed.values()):
        return [gap(f'no gate passed at head {head[:7]} (a delta review)')]
    return []


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
        item = item_for(root, pr)
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
            engine = spec_engine(root, repo)
            if engine and not any(path.startswith(('specs/', 'openspec/')) for path in files):
                found.append(gap(f'no spec in the diff (the repository uses {engine})'))
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
    return [g for g in found if not any(a and g['text'].startswith(a) for a in accepted)]


def owner_approved(root, repo, pr):
    login = owner_login(root)
    if any((r.get('author') or {}).get('login') == login and r.get('state') == 'APPROVED' for r in pr.get('reviews') or ()):
        return True
    ref = f'{repo}#{pr["number"]}'
    return any(row['data'].get('pr') == ref and pr['headRefOid'].startswith(row['data'].get('head', '-'))
               and row['data'].get('approved') for row in ws.rows(root, 'ruling'))
