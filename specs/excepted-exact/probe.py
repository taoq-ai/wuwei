"""Probe evidence.excepted over generated (accepted gap x printed gap) pairs, at one tree.

    python3 -I specs/excepted-exact/probe.py run <tree> <out.json>    # waived pairs at <tree>
    python3 -I specs/excepted-exact/probe.py diff <main.json> <head.json> [<changes.tsv>]

An accepted gap "names" a printed gap when it equals the gap's text, or the gates a gate gap names, with
case, spacing, end marks (trailing .,;:!?) and a printed " [waiting]" aside (canon below, written apart from the code under
test). Accepted gaps are generated as variants of each printed gap and of its gates, and as parts of it
(word spans, character prefixes and suffixes, superstrings, single characters). A hole is a waived pair
the accepted gap does not name; a miss is a named pair left standing. The question pass
builds "exception: acme/app#42 at aaaaaaa: <printed gap><tail>" for each printed gap, keeps the ones
guards.pre_tool lets through, records the gap with hook.exception_refs and checks it waives its gap.
"""
import functools
import hashlib
import itertools
import json
import sys

HEAD, REF = 'aaaaaaa' + '0' * 33, 'acme/app#42'
GATES = ('arch', 'quality', 'security', 'goal')
WHY = (' (tier raised to standard: the diff touches a trust path)', ' (tier raised to full: change failure rate 20% over 28 days)')


def printed():
    """Gap texts as evidence.gaps prints them, one per producer, with gate gaps for every gate list."""
    lists = [', '.join(c) for n in range(1, 5) for c in itertools.combinations(GATES, n)]
    gate = [f'gates missing at head aaaaaaa: {g}{w}' for g in lists for w in ('', *WHY)]
    gate += [f'no gate passed at head aaaaaaa (a delta review by {g})' for g in ('arch', 'quality', 'security')]
    other = ['no test in the diff', 'CI running', 'CI failing: test', 'CI failing: test, lint',
             'CI failing: gates missing at head aaaaaaa: security', 'CI not started at aaaaaaa',  # a check name is the author's
             'CI not started at aaaaaaa (Actions host unreadable: HTTP 502)', '1 review thread unanswered',
             '2 review threads unanswered', 'owner review needed (owner_paths: infra/main.tf)',
             'owner review needed (owner_paths: infra/main.tf, cli/wuwei/guards.py)', 'no reviewer requested',
             'change request outstanding: Review Gate', 'waiting on review: Review Gate',
             'verdict .wuwei/verdicts/I-1/security-aaaaaaa.md not counted: not attested',
             'breaking change without an announcement: add "Announcement: <link to the client communication, '
             'release note or migration guide>"', 'no Rollback: line (how to undo this change)',
             'not linked to a plan item (end the PR body with the WUWEI footer naming its item)',
             'the approval from alice is for bbbbbbb, not the head aaaaaaa: re-request review if a check wants it at the head',
             'evidence unreadable: HTTP 404', 'open 4 days: finish, rebase or close', '512 changed lines: split it, or add a Size: <reason> line',
             'no spec in the diff (the repository uses spec-kit)']
    return gate + other


def gates_of(text):
    for head in ('gates missing at head aaaaaaa: ', 'no gate passed at head aaaaaaa (a delta review by '):
        if text.startswith(head):
            rest = text[len(head):]
            return rest.split(' (')[0].rstrip(')')
    return None


def same(text):
    """Variants of one text that name it: case, spacing, end marks, a printed [waiting]."""
    words = text.split(' ')
    return {text, text.upper(), text.lower(), text.title(), '  '.join(words), '\t'.join(words), f'  {text}  ', f'{text}\n',
            f'{text}.', f'{text}?', f'{text} .', f'{text}!', f'{text}:', f'{text};', f'{text},', f'{text}...',
            f'{text} [waiting]', f'{text} [waiting].', f'{text.upper()} [WAITING]'}


def partial(text):
    """Texts that do not name it: every shorter word span, every character prefix and suffix, superstrings."""
    words, out = text.split(' '), set()
    for i in range(len(words)):
        for j in range(i + 1, len(words) + 1):
            if j - i < len(words):
                out.add(' '.join(words[i:j]))
    out |= {text[:n] for n in range(1, len(text))} | {text[n:] for n in range(1, len(text))}
    out |= {text + ' and more', 'x ' + text, text + ', quality', text + ' (tier raised)'}
    return out


@functools.cache
def canon(text):
    """The rule, written apart from evidence.excepted: case and spacing aside, end marks and a printed [waiting] aside."""
    text = ' '.join(text.casefold().split()).rstrip(' .,;:!?')
    return text[:-len('[waiting]')].rstrip(' .,;:!?') if text.endswith('[waiting]') else text


def names(a, g):
    return bool(canon(a)) and (canon(a) == canon(g) or gates_of(g) is not None and canon(a) == canon(gates_of(g)))


def pairs():
    """The printed gaps and each accepted gap with how it was generated: a variant of a gap, or a part of one."""
    gaps, accepted = printed(), {}
    for g in gaps:
        for a in same(g) | (same(gates_of(g)) if gates_of(g) else set()):
            accepted.setdefault(a, 'variant')
        for a in partial(g) | {'e', 'a', 'E', '.', '?', ' ', ''}:
            accepted.setdefault(a, 'part')
    return gaps, accepted


def run(tree, out):
    sys.path.insert(0, tree + '/cli')
    from wuwei import evidence, guards, hook, ws
    gaps, accepted = pairs()
    found = [evidence.gap(g) for g in gaps]
    waived = []
    for a in sorted(accepted):
        ws.rows = lambda root, kind, a=a: [{'data': {'kind': 'exception', 'pr': REF, 'head': HEAD[:7], 'gap': a, 'approved': True}}]
        left = {g['text'] for g in evidence.excepted('.', REF, HEAD, found)}
        waived += [[a, g] for g in gaps if g not in left]
    asked = []
    for g in gaps:
        for tail in ('. Accept?', '? ', '.', '', ' ?', '. Proceed? (recommended: accept)', '.\nAccept?', '\nAccept?'):
            q = f'exception: {REF} at aaaaaaa: {g}{tail}'
            passed = guards.pre_tool('.', {'tool_name': 'AskUserQuestion', 'tool_input': {'questions': [{'question': q}]}}) is None
            recorded = hook.exception_refs(q)[1] if passed else ''
            ws.rows = lambda root, kind, r=recorded: [{'data': {'kind': 'exception', 'pr': REF, 'head': HEAD[:7], 'gap': r,
                                                                'approved': True}}]
            left = {x['text'] for x in evidence.excepted('.', REF, HEAD, found)}
            asked.append({'gap': g, 'tail': tail, 'passed': passed, 'recorded': recorded, 'waived': sorted(set(gaps) - left)})
    json.dump({'waived': waived, 'asked': asked}, open(out, 'w'))
    named = sum(1 for a in accepted for g in gaps if names(a, g))
    holes = sum(1 for a, g in waived if not names(a, g))
    misses = named - (len(waived) - holes)
    edge = sum(1 for a, g in waived if names(a, g) and accepted[a] == 'part')
    print(f'{tree}: {len(gaps)} printed gaps, {len(accepted)} accepted gaps, {len(gaps) * len(accepted)} pairs, '
          f'{len(waived)} waived, {holes} holes (waived, not named), {misses} misses (named, not waived); '
          f'{named} pairs named, {edge} of them by a part of a longer gap that equals this gap up to end marks or spacing')
    ok = [x for x in asked if x['passed']]
    print(f"questions: {len(asked)} built, {len(ok)} pass the guard, "
          f"{sum(1 for x in ok if x['gap'] in x['waived'])} waive their own gap, "
          f"{sum(1 for x in ok if x['gap'] not in x['waived'])} leave it standing, "
          f"{sum(1 for x in ok for w in x['waived'] if not names(x['recorded'], w))} waive a gap the recorded text does not name")
    for x in ok:
        if x['gap'] not in x['waived']:
            print(f"  standing: {x['gap']!r} with tail {x['tail']!r}, recorded {x['recorded']!r}")


def diff(main, head, out=None):
    gaps, accepted = pairs()
    a, b = ({tuple(p) for p in json.load(open(f))['waived']} for f in (main, head))
    rows = sorted((x, g, 'main' if (x, g) in a else 'head', 'names' if names(x, g) else 'does not name') for x, g in a ^ b)
    by = {}
    for x, g, side, kind in rows:
        by[side, kind] = by.get((side, kind), 0) + 1
    print(f'pairs whose waiver changes: {len(rows)}')
    for (side, kind), n in sorted(by.items()):
        print(f'  waived only at {side}, the accepted gap {kind} the gap: {n}')
    print('| printed gap | waived only at main | waived only at head |\n|---|---|---|')
    for g in gaps:
        print(f"| {g} | {sum(1 for r in rows if r[1] == g and r[2] == 'main')} | {sum(1 for r in rows if r[1] == g and r[2] == 'head')} |")
    text = 'accepted\tgap\twaived only at\tthe accepted gap\n' + ''.join(f'{json.dumps(x)}\t{g}\t{s}\t{k}\n' for x, g, s, k in rows)
    print(f'every changed pair: {len(rows)} rows, sha256 {hashlib.sha256(text.encode()).hexdigest()}')
    if out:
        open(out, 'w').write(text)


if __name__ == '__main__':
    {'run': run, 'diff': diff}[sys.argv[1]](*sys.argv[2:])
