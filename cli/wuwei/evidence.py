"""What a pull request still lacks. One pure reading of the artifacts: it never asks how the work was done."""

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


def gate_gaps(root, repo, item_id, tier, head):
    latest = {}
    for found in verdicts(root, item_id):
        if gh.ancestor(repo, found['head'], head):
            latest[found['gate']] = found
    passed = {gate: v for gate, v in latest.items() if v['verdict'] == 'PASS'}
    missing = [gate for gate in REQUIRED[tier] if gate not in passed]
    if missing:
        return [gap(f'gates missing at head {head[:7]}: {", ".join(missing)}')]
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
        if item is None:
            found.append(gap('not linked to a plan item (add WUWEI-Item: <id> to the PR body)'))
        if tier != 'light':
            engine = spec_engine(root, repo)
            if engine and not any(path.startswith(('specs/', 'openspec/')) for path in files):
                found.append(gap(f'no spec in the diff (the repository uses {engine})'))
        code = [path for path in files if not DOCS.search(path) and not path.startswith(('specs/', 'openspec/'))]
        if code and not any(TEST.search(path) for path in files) and not re.search(r'^No test:\s*\S', body, re.M):
            found.append(gap('no test in the diff'))
        found += gate_gaps(root, repo, (item or {}).get('id', ''), tier, pr['headRefOid'])
        found += ci_gaps(pr.get('statusCheckRollup'))
        author = (pr.get('author') or {}).get('login', '')
        threads = gh.unanswered_threads(repo, number, author)
        if threads:
            found.append(gap(f'{threads} review thread{"s" if threads > 1 else ""} unanswered'))
        reviewers = [r for r in pr.get('reviews') or () if (r.get('author') or {}).get('login') != author]
        if not pr.get('reviewRequests') and not reviewers:
            found.append(gap('no reviewer requested'))
        patterns = ws.config(root)['owner_paths']
        owned = [path for path in files if any(fnmatch.fnmatch(path, p) for p in patterns)]
        if owned and not owner_approved(root, repo, pr):
            found.append(gap(f'owner review needed (owner_paths: {", ".join(owned[:3])})', actionable=False, owner=True))
        return found
    except (gh.GhError, KeyError, TypeError) as exc:
        return [gap(f'evidence unreadable: {exc}', actionable=False)]


def owner_approved(root, repo, pr):
    login = owner_login(root)
    if any((r.get('author') or {}).get('login') == login and r.get('state') == 'APPROVED' for r in pr.get('reviews') or ()):
        return True
    ref = f'{repo}#{pr["number"]}'
    return any(row['data'].get('pr') == ref and pr['headRefOid'].startswith(row['data'].get('head', '-'))
               and row['data'].get('approved') for row in ws.rows(root, 'ruling'))
