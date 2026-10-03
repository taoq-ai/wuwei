"""Seeded synthetic .wuwei/ corpus and the 30-question golden set (spike #444).

Throwaway PoC code, never imported by cli/. Shapes follow the records on main. Three
things are synthetic extensions today's records do not carry: `files` on pr.raised, the
pr.reverted event and incidents/INC-n.md.
"""

from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import random

LAST_DAY = date(2026, 9, 29)
TYPES = ('why', 'touched', 'lesson', 'revert', 'reversed')
MODULES = ('billing', 'export', 'search', 'auth', 'notify', 'report')
FILES = ('api.py', 'models.py', 'jobs.py', 'views.py', 'utils.py', 'tests.py')
PEOPLE = ('dev-a', 'dev-b', 'dev-c', 'dev-d', 'dev-e')
STOP = {'on', 'for', 'of', 'the', 'to', 'a', 'in'}

# Planted facts, six per type; each answer phrase occurs nowhere else in the corpus.
SETTINGS = ('retry limit on export jobs', 'session timeout for admin users',
            'page size of search results', 'batch window for notify digests',
            'cache lifetime of report tiles', 'lockout threshold for auth failures')
TOUCHED = ('billing/rounding_legacy.py', 'export/csv_writer_v1.py', 'search/synonyms.py',
           'auth/otp_fallback.py', 'notify/sms_gateway.py', 'report/pdf_footer.py')
SYMPTOMS = ('flaky e2e login test', 'stale cache after deploy', 'timeout in nightly export',
            'duplicate webhook delivery', 'missing index on search table',
            'slow report rendering on large tenants')
REASONS = ('duplicate invoice emails', 'blank search page on mobile',
           'expired tokens accepted at login', 'missing rows in csv export',
           'digest sent twice per night', 'wrong totals on monthly report')

# Noise reuses the planted words (retry, limit, flaky, revert, module names), never a phrase.
VERBS = ('Split', 'Keep', 'Drop', 'Rename', 'Cache', 'Raise', 'Lower', 'Move')
OBJECTS = ('the retry backoff', 'the rate limit', 'the audit log', 'the error banner',
           'the job queue', 'the flaky check', 'the session store', 'the export button',
           'the search index', 'the report header')
RULES = ('Run the {m} checks before raising a PR', 'Retry a flaky {m} test once, then file a ticket',
         'Keep {m} migrations in their own PR', 'Ask before changing the {m} rate limit',
         'Read the {m} incident log before a revert')
NOISE_REASONS = ('broke the {m} build', 'failed the {m} smoke check', 'slowed the {m} jobs')
NOISE_INCIDENTS = ('Error spike in {m} after deploy', 'Queue backlog in {m}', 'Slow pages in {m}')
TASKS = ('Read the ticket and the {m} module first.', 'Keep the change inside {m}.',
         'Add a test that fails before the fix.', 'Run the fast checks before raising the PR.',
         'Write a decision record if you change a default.', 'Note any retry or limit you touch.')


def decision_text(question, context, option='A'):
    """A record in the `wuwei decision template` shape that decision.evaluate accepts."""
    return f'''Question: {question}
Context: {context}
Options:
| Option | Description |
| --- | --- |
| A | Make the scoped change |
| B | Defer until more evidence exists |
Musts:
| Criterion | A | B |
| --- | --- | --- |
| Safe | pass | pass |
Wants:
| Criterion | Weight | A | B |
| --- | --- | --- | --- |
| Outcome | 10 | 8 | 2 |
Recommendation: A
Confidence: medium
Reversibility: two-way
Blast radius: Own branch and PR.
Pre-mortem: The change misses an edge case.
Revisit: Reopen if tests fail.
Decided-by: seat
Outcome: {option}
'''


def generate(root, days=90, seed=444):
    """Write root/.wuwei for `days` days ending LAST_DAY; return the golden set."""
    rng = random.Random(seed)
    root = Path(root)
    n = lambda volume: max(1, round(volume * days / 90))  # noqa: E731
    dates = [(LAST_DAY - timedelta(days=days - 1 - i)).isoformat() for i in range(days)]
    day = [{'events': [], 'decisions': [], 'incidents': [], 'retros': [], 'candidates': [],
            'briefs': {}, 'closed': set(), 'approved': []} for _ in dates]
    counters = {'pr': 100, 'inc': 0}
    charters = {'builder': [], 'reviewer': []}
    ledger = []
    noise_prs = []

    def wu(index, name):
        return f'.wuwei/days/{dates[index]}/{name}'

    def event(index, kind, payload):
        day[index]['events'].append({'kind': kind, 'payload': payload})
        return [wu(index, 'events.jsonl'), len(day[index]['events'])]

    def raise_pr(index, item, files):
        counters['pr'] += 1
        ref = f'example/app#{counters["pr"]}'
        where = event(index, 'pr.raised', {'pr': ref, 'item': item['id'],
                                           'head': f'wuwei/{item["id"]}', 'files': files})
        event(index, 'merge.auto', {'pr': ref})
        day[index]['closed'].add(item['id'])
        return ref, where

    def revert(index, item, ref, reason):
        counters['pr'] += 1
        return event(index, 'pr.reverted', {'pr': f'example/app#{counters["pr"]}', 'reverts': ref,
                                            'item': item['id'], 'by': rng.choice(PEOPLE),
                                            'reason': reason})

    def incident(index, item, ref, title):
        counters['inc'] += 1
        name = f'INC-{counters["inc"]:03d}'
        day[index]['incidents'].append((name, f'Title: {title}\nCaused by: {ref}\nItem: {item["id"]}\n'))
        return name, [wu(index, f'incidents/{name}.md'), 1]

    def decide(index, item, question, context, reversed_=False):
        records = day[index]['decisions']
        records.append(decision_text(question, context))
        name = f'D-{len(records)}'
        event(index, 'decision.decided', {'id': name, 'option': 'A', 'decided_by': 'seat',
                                          'item': item['id']})
        if reversed_:
            event(index, 'decision.reversed', {'id': name, 'option': 'A', 'decided_by': 'seat',
                                               'item': item['id']})
        return name, [wu(index, f'decisions/{name}.md'), 1]

    def lesson(index, role, text):
        retro = {'agent_id': f'a{index}{len(day[index]["retros"])}', 'agent_type': role,
                 'fields': {'Blocked': 'none', 'Gap': 'none', 'Change': text},
                 'missing': [], 'invalid': []}
        body = json.dumps(retro)
        path = wu(index, f'retro/{hashlib.sha256(body.encode()).hexdigest()}.json')
        day[index]['retros'].append((path, body))
        event(index, 'retro.captured', {'agent_type': role, 'evidence': path})
        name = f'L-{len(ledger) + 1:03d}'
        charters[role].append(f'- {text} ({name})')
        ledger.append({'target': f'.wuwei/charters/{role}.md', 'action': 'add',
                       'reason': 'promoted from retro', 'lesson': name, 'evidence': path,
                       'date': dates[index]})
        return [f'.wuwei/charters/{role}.md', len(charters[role]) + 2], [path, 1]

    # Items, tickets, plans, proposals and briefs.
    n_items, n_tickets = n(120), n(200)
    items = []
    for k in range(n_items):
        item = {'id': f'I-{k + 1:03d}', 'module': rng.choice(MODULES), 'start': k * days // n_items}
        items.append(item)
        here, m = day[item['start']], item['module']
        here['approved'].append(item['id'])
        ticket = rng.randrange(n_tickets) + 1
        here['candidates'].append({'id': item['id'], 'goal': 'ship planned work',
                                   'evidence': f'TK-{ticket:03d} {m} {rng.choice(OBJECTS)} request',
                                   'scope': m})
        tasks = rng.sample(TASKS, rng.randint(4, 6))
        here['briefs'][item['id']] = (
            'Charter: charters/_common.md\nCharter: charters/builder.md\n'
            f'Written: {dates[item["start"]]}T08:00:00+00:00\nItem: {item["id"]}\n'
            'Seat policy: {"model": "sonnet"}\n\n'
            f'Scope: {m}\n' + ''.join(t.format(m=m) + '\n' for t in tasks))
    for index in range(days):
        event(index, 'plan.approved', {'approved_items': day[index]['approved']})

    def later(item):
        return min(item['start'] + rng.randrange(4), days - 1)

    # Noise: PRs, decisions, incidents, reverts and lessons.
    for _ in range(n(400)):
        item = rng.choice(items)
        index = later(item)
        files = [f'{item["module"]}/{f}' for f in rng.sample(FILES, rng.randint(1, 3))]
        noise_prs.append((index, item, raise_pr(index, item, files)[0]))
    for _ in range(n(300)):
        item = rng.choice(items)
        decide(later(item), item, f'{item["id"]}: {rng.choice(VERBS)} {rng.choice(OBJECTS)} in {item["module"]}?',
               f'Seen in review; asked by {rng.choice(PEOPLE)}.')
    for _ in range(n(20)):
        index, item, ref = rng.choice(noise_prs)
        incident(index, item, ref, rng.choice(NOISE_INCIDENTS).format(m=item['module']))
    for _ in range(n(10)):
        index, item, ref = rng.choice(noise_prs)
        revert(index, item, ref, rng.choice(NOISE_REASONS).format(m=item['module']))
    for _ in range(n(60)):
        index, item, ref = rng.choice(noise_prs)
        lesson(index, rng.choice(('builder', 'reviewer')),
               rng.choice(RULES).format(m=item['module']) + f' after {ref}')

    # Planted facts: fact i has type TYPES[i % 5] on day index i * days // 30.
    golden = []
    for i in range(30):
        kind, j, index = TYPES[i % 5], i // 5, i * days // 30
        item = items[i * n_items // 30]
        if kind == 'why':
            phrase = SETTINGS[j]
            _, where = decide(index, item, f'{item["id"]}: Change the {phrase}?',
                              f'Asked by {rng.choice(PEOPLE)} after load tests.')
            expected, words = [where], [w for w in phrase.split() if w not in STOP]
            key, text, form = ' '.join(words[:2]), f'Why was the {phrase} changed?', ['ask', words]
        elif kind == 'touched':
            phrase = TOUCHED[j]
            expected = [raise_pr(min(index + k, days - 1), item, [phrase])[1] for k in range(3)]
            words = [phrase]
            key, text, form = phrase, f'What touched {phrase} before?', ['around', f'file:{phrase}', ['touches'], 1]
        elif kind == 'lesson':
            phrase = SYMPTOMS[j]
            expected = list(lesson(index, 'builder',
                                   f'When you see a {phrase}, rerun it with tracing before any retry'))
            words = [w for w in phrase.split() if w not in STOP]
            key, text, form = phrase, f'Which lesson applies to a {phrase}?', ['ask', words]
        elif kind == 'revert':
            phrase = REASONS[j]
            ref, _ = raise_pr(index, item, [f'{item["module"]}/{rng.choice(FILES)}'])
            where = revert(index, item, ref, phrase)
            expected = [where, incident(index, item, ref, f'{phrase[0].upper()}{phrase[1:]} after release')[1]]
            words = [ref, 'revert']
            key, text, form = ref, f'Who reverted {ref} and why?', ['around', f'pr:{ref}', ['reverted', 'caused'], 1]
        else:
            first = min(index, days - 2) if days > 1 else 0
            second = first + 1 if days > 1 else first
            name, one = decide(first, item, f'{item["id"]}: Keep the {item["module"]} change behind a flag?',
                               f'Asked by {rng.choice(PEOPLE)} before release.')
            phrase = f'Reverses {dates[first]} {name}'
            _, two = decide(second, item, f'{item["id"]}: Ship the {item["module"]} change without the flag?',
                            f'{phrase}; the flag hid a bug in review.', reversed_=True)
            # The second record's Context line (2) carries the answer phrase.
            expected, words, key = [one, [two[0], 2]], [item['id'], 'Reverses'], item['id']
            text, form = (f'Which decisions on {item["id"]} were reversed?',
                          ['around', f'item:{item["id"]}', ['decided_in', 'supersedes'], 1])
        golden.append({'id': f'Q{i + 1:02d}', 'type': kind, 'text': text, 'words': words, 'key': key,
                       'form': form, 'expected': expected, 'answer': phrase})

    # Write everything in a fixed order.
    def write(rel, text):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    for role, rules in charters.items():
        write(f'.wuwei/charters/{role}.md', f'# {role} overrides\n\n' + ''.join(r + '\n' for r in rules))
    write('.wuwei/memory/ledger.jsonl', ''.join(json.dumps(r) + '\n' for r in ledger))
    for index, here in enumerate(day):
        start = datetime.fromisoformat(dates[index] + 'T09:00:00+00:00')
        write(wu(index, 'events.jsonl'), ''.join(
            json.dumps({**e, 'ts': (start + timedelta(minutes=k)).isoformat()}) + '\n'
            for k, e in enumerate(here['events'])))
        for k, text in enumerate(here['decisions'], 1):
            write(wu(index, f'decisions/D-{k}.md'), text)
        for name, text in here['incidents']:
            write(wu(index, f'incidents/{name}.md'), text)
        for path, body in here['retros']:
            write(path, body + '\n')
        for name, text in here['briefs'].items():
            write(wu(index, f'briefs/{name}-builder.md'), text)
        write(wu(index, 'proposal.json'), json.dumps(
            {'goals': ['ship planned work'], 'cap': 6, 'candidates': here['candidates']}) + '\n')
        carried = [i for i in here['approved'] if i not in here['closed']]
        write(wu(index, 'report.md'), f'{dates[index]}: {len(here["closed"])} items closed, '
              f'{len(carried)} carried\n' + ''.join(f'{i} closed\n' for i in sorted(here['closed']))
              + ''.join(f'{i} carried\n' for i in carried))

    # A planted phrase anywhere outside its expected records would make the golden set lie.
    texts = {str(p.relative_to(root)): p.read_text(encoding='utf-8').lower()
             for p in sorted((root / '.wuwei').rglob('*')) if p.is_file()}
    for q in golden:
        expected = {path for path, _ in q['expected']}
        leaks = sorted(p for p, t in texts.items() if q['answer'].lower() in t and p not in expected)
        if leaks:
            raise ValueError(f'{q["id"]}: answer phrase {q["answer"]!r} leaks into {leaks[0]}')
    return golden
