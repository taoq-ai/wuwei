"""What a pull request still lacks. One pure reading of the artifacts: it never asks how the work was done."""

import datetime
import fnmatch
import hashlib
import json
from pathlib import Path
import posixpath
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
# The plan item a PR names: the WUWEI footer ([WUWEI <version>](<site>) · Item <id> · ...), or a WUWEI-Item: line.
ITEM = re.compile(r'(?:WUWEI-Item:|\[WUWEI[^\]\n]*\]\([^)\n]*\)[^\n]*?\bItem\b)[ \t:]*\\?`?([\w.-]+)')
BOX = re.compile(r'^\s*[-*] \[([ xX])\]', re.M)
# Process fit, never a block: recorded at merge for the retro, shown to nobody while the work flows.
PROCESS = re.compile(r"^(specs/|openspec/|no spec in the diff|PR body misses the repository template|[0-9]+ changed lines"
                     r"|open [0-9]+ days|no Rollback: line|not linked to a plan item|no reviewer requested)")
CONTRACT = re.compile(r'(^|/)(openapi|swagger)[^/]*\.(ya?ml|json)$|\.proto$|\.graphql$|\.schema\.json$', re.I)
# Trust paths raise a light item to standard (#1016); with data, infrastructure and dependencies they call security.
TRUST = r'(^|[/_.-])(auth|oauth|login|session|token|secret|password|permission|grant|polic|iam|acl|rbac)'
RISKY = re.compile(TRUST + r'|(^|[/_.-])(crypt|secur|sql|migrat)|(^|/)(infra|terraform|deploy|\.github/workflows)/|Dockerfile'
                   r'|requirements[^/]*\.txt$|package\.json$|pyproject\.toml$|go\.mod$|Cargo\.toml$', re.I)
RAISE = {'light': 'standard', 'standard': 'full', 'full': 'full'}
MAX_LINES, STALE_DAYS, BUDGET, TRIVIAL, WIDE = 400, 3, 0.15, 20, 200
FAILED = {'FAILURE', 'CANCELLED', 'TIMED_OUT', 'ACTION_REQUIRED', 'STARTUP_FAILURE', 'ERROR'}
RELEASE_BOTS = ('github-actions[bot]', 'release-please[bot]')  # the logins release-please opens its PRs as
VERSION_LINE = re.compile(r'[+-][ \t]*"([\w./-]+)":[ \t]*"[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?",?', re.A)
# A duty: work the team owes that does not hold the merge, yet reaches it until done.
DUTY = re.compile(r'^(review not requested|the approval from)')
DEFERRED = re.compile(r'^(#+)\s+(?:[0-9]+(?:\.[0-9]+)*\.?\s*)?(Deferred|Out of this PR)\b', re.I)
REASON = re.compile(r'\(.+\)|\bbecause\b|\bwaits? on\b|\bblocked by\b|\breason:', re.I)
REF = re.compile(r'github\.com/([\w.-]+/[\w.-]+)/pull/([0-9]+)|([\w.-]+/[\w.-]+)#([0-9]+)')


def gap(text, actionable=True, owner=False):
    kind = 'process' if PROCESS.search(text) else 'duty' if DUTY.search(text) else 'safety'
    return {'text': text, 'actionable': actionable, 'owner': owner, 'kind': kind}


def blocking(found):
    """The safety gaps: the only ones that hold a merge."""
    return [g for g in found if g['kind'] == 'safety']


def visible(found):
    """What reaches the team while it works: safety gaps and duties, never process fit."""
    return [g for g in found if g['kind'] != 'process']


def refs(text):
    """The PRs a text names, as lowercase owner/repo#n."""
    return {f'{m[1] or m[3]}#{m[2] or m[4]}'.lower() for m in REF.finditer(text)}


def review_place(root):
    """Where the team asks for reviews: the Review requests: line in .wuwei/standards.md, or ''."""
    path = Path(root) / ws.DIR / 'standards.md'
    match = re.search(r'^[-*\s]*Review requests:[ \t]*(\S.*)$', path.read_text(encoding='utf-8'), re.M) if path.is_file() else None
    return match[1].strip() if match else ''


def review_duty(root, ref, pr):
    """A ready PR is put in front of reviewers where the team asks, until a post names it or a review is in."""
    place = review_place(root)
    author = (pr.get('author') or {}).get('login', '')
    if not place or pr.get('isDraft') or any((r.get('author') or {}).get('login') != author for r in pr.get('reviews') or ()) \
            or any(ref.lower() in row['data'].get('refs', ()) for row in ws.rows(root, 'sent')):
        return []
    return [gap(f'review not requested in {place}: post the PR link there (posted outside this session? '
                f'wuwei sent {ref} <link to the post>)')]


def item_for(root, pr, repo=None):
    """The plan item a PR names in its WUWEI footer, records among its PRs, or whose id starts
    its branch name."""
    if match := ITEM.search(pr.get('body') or ''):
        return plan.find(root, match[1])
    ref = f'{repo}#{pr.get("number")}' if repo else None
    linked = next((item for item in plan.items(root) if ref and ref in item.get('prs', ())), None)
    branch = (pr.get('headRefName') or '').lower()
    return linked or next((item for item in plan.items(root)
                           if branch == item['id'].lower() or branch.startswith(item['id'].lower() + '-')), None)


def release(repo, pr):
    """A release-please PR, read as generated (X-1): a bot author, a release-please-- branch, and only CHANGELOG.md, the
    manifest and the extra-files that release-please-config.json names on the base branch, these changing version lines
    only (a missing patch or a rename does not count). Unreadable keeps every gap."""
    files, allowed = pr.get('files') or (), {'.release-please-manifest.json'}
    if (pr.get('author') or {}).get('login') not in RELEASE_BOTS or not (pr.get('headRefName') or '').startswith('release-please--'):
        return False
    try:
        packages = json.loads(gh.file(repo, 'release-please-config.json', pr['baseRefName']))['packages'].items()
        allowed |= {posixpath.normpath(posixpath.join(where, e if isinstance(e, str) else e['path'])).lstrip('/')
                    for where, package in packages for e in [] + package.get('extra-files', [])}  # [] + refuses a string
    except Exception:  # anything unreadable, malformed or nested too deep counts only the manifest
        pass
    def bumped(f):  # every +/- line, split on \n only as git does, is a whole "key": "<semver>" line; key "version" bar the manifest
        return isinstance(f.get('patch'), str) and f['patch'] != '' and all((m := VERSION_LINE.fullmatch(x)) and (
            m[1] == 'version' or f['path'] == '.release-please-manifest.json') for x in f['patch'].split('\n') if x[:1] in ('+', '-'))
    return bool(files) and all(not f.get('renamed') and (f['path'] == 'CHANGELOG.md' or f['path'] in allowed and bumped(f)) for f in files)


def _cached(root, name, read, max_age=86400):
    value = ws.cache_get(root, name, max_age)
    return ws.cache_put(root, name, read()) if value is None else value


def spec_engine(root, repo):
    return _cached(root, 'spec-' + repo.replace('/', '__'),
                   lambda: next((path for path in ('.specify', 'openspec') if gh.has_path(repo, path)), ''))


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


def _counted(text):
    """The checklist lines that count: a box under a Deferred or Out of this PR heading is left out
    when its line says why (#1037); the section ends at the next heading of the same or a higher level."""
    kept, level = [], None
    for line in text.splitlines():
        heading = re.match(r'^(#+)\s', line)
        if heading and level is not None and len(heading[1]) <= level:
            level = None
        if deferred := DEFERRED.match(line):
            level = len(deferred[1])
            continue
        if level is not None and BOX.match(line) and REASON.search(line):
            continue
        kept.append(line)
    return '\n'.join(kept)


def _unchecked(path, text):
    if not (boxes := BOX.findall(_counted(text))):
        return f'{path} has no checklist items'
    return f'{path} has {boxes.count(" ")} unchecked item{"s" if boxes.count(" ") > 1 else ""}' if ' ' in boxes else None


def _rule(repo, path, rule, head):
    """None when the artifact at the head meets its rule, else the gap text."""
    if path.endswith('/'):
        if not (entries := gh.listing(repo, path.rstrip('/'), head)):
            return f'{path} missing: run the spec engine step that writes it'
        return next((problem for e in entries if rule == 'checked' and e.get('type') == 'file' and e['name'].endswith('.md')
                     if (problem := _unchecked(e['path'], gh.file(repo, e['path'], head)))), None)
    try:
        text = gh.file(repo, path, head)
    except gh.GhError:
        return f'{path} missing: run the spec engine step that writes it'
    if rule == 'checked':
        return _unchecked(path, text)
    if rule == 'clarified' and not re.search(r'^##\s+(?:[0-9]+(?:\.[0-9]+)*\.?\s*)?Clarifications\b', text, re.M | re.I):
        return f'{path} has no ## Clarifications section: run clarify'
    if rule == 'clean':
        for line in text.splitlines():
            cells = {cell.strip().upper() for cell in line.strip().strip('|').split('|')}
            if line.lstrip().startswith('|') and cells & {'CRITICAL', 'HIGH'} and not any(
                    c.startswith(('RESOLVED', 'FIXED', 'CLOSED')) for c in cells):  # a recorded resolution (#1047)
                return f'{path} has an open CRITICAL or HIGH finding: {line.strip()[:100]}'
    return None


def spec_gaps(repo, engine, tier, files, head):
    """The spec engine's steps, judged by their artifacts at the head, for each feature whose spec
    (spec-kit spec.md, OpenSpec proposal or spec deltas) the PR adds or edits. A PR that only amends an
    older feature's other files is held to its own scope, not to that feature's whole set (#1032)."""
    if not engine:
        return []
    pattern, rules = SPEC_RULES[engine]
    if not (features := sorted({m[1] for m in (re.match(pattern, path) for path in files) if m})):
        return [] if any(p.startswith(('specs/', 'openspec/')) for p in files) else [
            gap(f'no spec in the diff (the repository uses {engine})')]
    wanted = rules['standard'] + (rules['full'] if tier == 'full' else ())
    problems = (_rule(repo, feature + name, rule, head) for feature in features for name, rule in wanted)
    return [gap(problem) for problem in dict.fromkeys(problems) if problem]


def budget(root, repo):
    """The 28-day change failure rate; over BUDGET with five or more merges raises every tier one step."""
    def read():
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


def verdicts(root, item_id, ref=''):
    """Attested, well-formed verdicts for an item (or its PR), oldest first. An edited file no longer counts."""
    found = []
    for row in ws.rows(root, 'attest'):
        data = row['data']
        if str(data.get('item', '')).lower() != str(item_id).lower() and not (ref and data.get('pr', '').lower() == ref.lower()):
            continue
        path = Path(root) / data.get('path', '')
        try:
            body = path.read_bytes()
        except OSError:
            continue
        changed = hashlib.sha256(body).hexdigest() != data.get('sha256')
        if changed or data.get('imported'):  # a replaced finding still holds as recorded (#1039)
            if not changed or data.get('verdict') not in (None, 'PASS'):
                found.append({'gate': data['gate'], 'verdict': data['verdict'], 'head': data['head']})
            continue
        parsed = parse(body.decode('utf-8', 'replace'))
        if not parsed['errors']:
            found.append(parsed)
    return found


def needed(root, tier, files):
    """The gates a change needs: the tier is the ceiling, the diff decides (#1050). Docs alone need none;
    security comes for risky or owner paths, arch for a contract or a wide change; full takes all four."""
    code = [f['path'] for f in files if f['path'].endswith('.txt') and RISKY.search(f['path'])
            or not DOCS.search(f['path']) and not f['path'].startswith(('specs/', 'openspec/'))]
    risky = owned(root, code) or any(RISKY.search(p) for p in code)
    if tier == 'full' and code:
        return REQUIRED['full']
    wants = {'quality': code, 'security': tier == 'standard' and risky, 'arch': any(CONTRACT.search(p) for p in code)
             or tier == 'standard' and (lines(files) > WIDE or len(code) > 10)}
    return tuple(g for g in REQUIRED['standard'] if wants[g])


def lines(files):
    return sum(f.get('additions', 0) + f.get('deletions', 0) for f in files if not GENERATED.search(f['path']))


def owned(root, files):
    return [path for path in files if any(fnmatch.fnmatch(path, p) for p in ws.config(root)['owner_paths'])]


def gates_for(root, repo, pr, files, item):
    """(item id, tier, the gates the change needs, why) for a PR, or for a branch about to open one."""
    trailer = ITEM.search(pr.get('body') or '')
    tier, why, spent = (item or {}).get('tier', 'standard'), '', budget(root, repo)
    if spent['raised'] and tier != 'full':
        tier, why = RAISE[tier], f' (tier raised to {RAISE[tier]}: change failure rate {spent["cfr"]:.0%} over 28 days)'
    elif tier == 'light' and any(re.search(TRUST, f['path'], re.I) and not DOCS.search(f['path']) for f in files):
        tier, why = 'standard', ' (tier raised to standard: the diff touches a trust path)'
    gates = REQUIRED[tier] if why else needed(root, tier, files)  # an overrun budget trims nothing
    return (item or {}).get('id') or (trailer[1] if trailer else ''), tier, gates, why


def gate_gaps(root, repo, item_id, gates, head, why='', ref='', tier='standard'):
    """Each gate the change needs passed at an ancestor of the head. Code moved since the last pass is
    re-read by the one gate the delta needs; docs or a small change off risky paths carries the passes."""
    latest, last = {}, None
    for found in verdicts(root, item_id, ref):
        prior = latest.get(found['gate'])
        if prior and prior['verdict'] != 'PASS' and prior['head'][:7] == found['head'][:7]:
            continue  # at one head, a later pass does not outvote a finding
        if gh.ancestor(repo, found['head'], head):
            latest[found['gate']] = found
            last = found['head'] if found['verdict'] == 'PASS' else last
    passed = {gate: v for gate, v in latest.items() if v['verdict'] == 'PASS'}
    if missing := [gate for gate in gates if gate not in passed]:
        return [gap(f'gates missing at head {head[:7]}: {", ".join(missing)}{why}')] + uncounted(root, item_id)
    if not gates or any(head.startswith(v['head']) for v in passed.values()):
        return []
    delta = gh.compare(repo, last, head)['files']
    want = needed(root, 'light' if tier == 'light' else 'standard', delta)
    gate = next((g for g in ('security', 'arch', 'quality') if g in want), '')
    if not gate or lines(delta) <= TRIVIAL and gate == 'quality' or gate in passed and head.startswith(passed[gate]['head']):
        return []
    return [gap(f'no gate passed at head {head[:7]} (a delta review by {gate})')] + uncounted(root, item_id)


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


def breaking_gaps(root, ref, pr, item_id):
    """A breaking change to an outward contract (declared with ! or BREAKING CHANGE:, or found by the arch
    gate) needs an announcement, then the owner's confirmation at this head."""
    body, head = pr.get('body') or '', pr['headRefOid']
    declared = re.match(r'^\w+(\([^)]*\))?!:', pr.get('title') or '') or re.search(r'^BREAKING[ -]CHANGE:', body, re.M)
    if not (declared or any(v.get('breaking') for v in verdicts(root, item_id, ref))):
        return []
    if not re.search(r'^Announcement:[ \t]*\S', body, re.M):
        return [gap('breaking change without an announcement: add "Announcement: <link to the client communication, '
                    'release note or migration guide>"')]
    if any(r['data'].get('kind') == 'breaking' and r['data'].get('approved') and r['data'].get('pr') == ref
           and head.startswith(r['data'].get('head') or '-') for r in ws.rows(root, 'ruling')):
        return []
    return [gap(f'breaking change needs the owner\'s confirmation: ask "breaking: {ref} at {head[:7]}: <what breaks>. '
                'Announced at <link>. Proceed?"', owner=True)]


def review_contexts(root, repo, rollup):
    """Unsettled statuses whose target_url run is of a workflow the repo runs on pull_request_review (1067-probe)."""
    try:
        runs = {c['context']: m[1] for c in rollup or () if 'context' in c and c.get('state') != 'SUCCESS'
                and (m := re.search(rf'github\.com/{re.escape(repo)}/actions/runs/([0-9]+)', c.get('url') or '', re.I))}
        paths = runs and _cached(root, 'review-' + repo.replace('/', '__'), lambda: gh.workflow_paths(repo))
        return {context for context, run in runs.items() if paths and gh.workflow_paths(repo, f'/{run}')[0] in paths}
    except (gh.GhError, AttributeError, KeyError, IndexError, TypeError):
        return set()  # an unreadable Actions host leaves them CI, never a pass


def ci_gaps(rollup, review=()):
    failed, running, found = [], False, []
    for check in rollup or ():
        name = check.get('name') or check.get('context') or 'check'
        state = (check.get('conclusion') or check.get('state') or '').upper()
        if check.get('context') in review:
            found.append(gap(('change request outstanding: ' if state in FAILED else 'waiting on review: ') + name))
        elif state in FAILED:
            failed.append(name)
        elif check.get('status', 'COMPLETED').upper() != 'COMPLETED' or state in ('PENDING', 'EXPECTED'):
            running = True
    return found + ([gap('CI failing: ' + ', '.join(failed))] if failed else [gap('CI running', actionable=False)] if running else [])


def gaps(root, repo, number):
    try:
        pr = gh.pr(repo, number)
        item, ref, generated = item_for(root, pr, repo), f'{repo}#{number}', release(repo, pr)
        found = [] if item else [gap('not linked to a plan item (end the PR body with the WUWEI footer naming its item)')]
        tier = (item or {}).get('tier', 'standard')
        item_id, raised, gates, why = gates_for(root, repo, pr, () if generated else pr.get('files') or (), item)
        files, body, head = [f['path'] for f in pr.get('files') or ()], pr.get('body') or '', pr['headRefOid']
        if missing := [s for s in template_sections(root, repo) if s.lower() not in body.lower()]:
            found.append(gap(f"PR body misses the repository template's sections: {', '.join(missing)}"))
        if tier != 'light':
            # At full tier the spec is part of the safety case; below it, process fit for the retro.
            found += [dict(g, kind='safety') if tier == 'full' else g for g in spec_gaps(repo, spec_engine(root, repo), tier, files, head)]
        code = [] if generated else [path for path in files if not DOCS.search(path) and not path.startswith(('specs/', 'openspec/'))]
        if code and not any(TEST.search(path) for path in files) and not re.search(r'^No test:\s*\S', body, re.M):
            found.append(gap('no test in the diff'))
        if (size := lines(pr.get('files') or ())) > MAX_LINES and not re.search(r'^Size:\s*\S', body, re.M):
            found.append(gap(f'{size} changed lines: split it, or add a Size: <reason> line'))
        owners = owned(root, files)
        if (tier == 'full' or owners) and not re.search(r'^Rollback:\s*\S', body, re.M):
            found.append(gap('no Rollback: line (how to undo this change)'))
        found += gate_gaps(root, repo, item_id, gates, head, why, ref, raised)
        found += breaking_gaps(root, ref, pr, item_id)
        rollup = pr.get('statusCheckRollup')
        found += ci_gaps(rollup, review_contexts(root, repo, rollup))
        try:  # no check run and no status at the head of a repository that ran a pull_request workflow (#1085)
            ci = not rollup and _cached(root, 'ci-' + repo.replace('/', '__'), lambda: gh.workflow_paths(repo, '?event=pull_request&per_page=1'))
        except (gh.GhError, AttributeError, TypeError):
            ci = True  # an unreadable Actions host counts as CI, so the gap shows rather than a pass
        found += [gap(f'CI not started at {head[:7]}', actionable=False)] if ci else []
        author = (pr.get('author') or {}).get('login', '')
        if threads := gh.unanswered_threads(repo, number, author):
            found.append(gap(f'{threads} review thread{"s" if threads > 1 else ""} unanswered'))
        if not pr.get('reviewRequests') and all((r.get('author') or {}).get('login') == author for r in pr.get('reviews') or ()):
            found.append(gap('no reviewer requested'))
        found += review_duty(root, f'{repo}#{number}', pr)
        approvals = [r for r in pr.get('reviews') or () if r.get('state') == 'APPROVED'
                     and (r.get('author') or {}).get('login') != author]
        if approvals and not any(head.startswith(r.get('commit') or '-') for r in approvals) and \
                any(g['text'].startswith(('CI failing', 'change request outstanding')) for g in found):
            last = approvals[-1]
            found.append(gap(f'the approval from {last["author"]["login"]} is for {str(last.get("commit"))[:7]}, not the head '
                             f'{head[:7]}: re-request review if a check wants it at the head'))
        if owners and not owner_approved(root, repo, pr):
            found.append(gap(f'owner review needed (owner_paths: {", ".join(owners[:3])})', actionable=False, owner=True))
        age = (ws.now() - datetime.datetime.fromisoformat(pr['createdAt'].replace('Z', '+00:00'))).days
        if age >= STALE_DAYS and pr.get('state', 'OPEN') == 'OPEN':
            found.append(gap(f'open {age} days: finish, rebase or close'))
        if pr.get('state') == 'MERGED':  # what it lacked when it merged is an escape for the retro (#1050)
            return [dict(g, text='post-merge: ' + g['text']) for g in blocking(found)]
        return excepted(root, ref, head, found)
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
    login, head, ref = owner_login(root), pr['headRefOid'], f'{repo}#{pr["number"]}'  # a review or ruling at the head only (#886)
    return any((r.get('author') or {}).get('login') == login and r.get('state') == 'APPROVED'
               and head.startswith(r.get('commit') or '-') for r in pr.get('reviews') or ()) or \
        any(row['data'].get('pr') == ref and head.startswith(row['data'].get('head', '-')) and row['data'].get('approved')
            for row in ws.rows(root, 'ruling'))
