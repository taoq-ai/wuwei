"""Compile the steward's dated review from recorded day evidence."""

import json
from hashlib import sha256
from pathlib import Path
import re

from wuwei import metrics, state, verdict, watch, workspace
from wuwei.promotion import safe_path


def compile(root=None):
    root = workspace.find_workspace(root)
    day = workspace.day_dir(root)
    roles = {}
    for row in watch.records(day / 'events.jsonl'):
        if row['kind'] != 'retro.captured':
            continue
        record = row['payload']
        path = safe_path(root, record['evidence'], label='retro evidence')
        if path.parent != day / 'retro':
            raise ValueError('retro evidence must belong to today')
        evidence = json.loads(path.read_text(encoding='utf-8'))
        if any(evidence.get(key) != record.get(key) for key in
               ('agent_id', 'agent_type', 'fields', 'missing', 'invalid')):
            raise ValueError('captured retro evidence mismatch')
        if evidence['missing'] or evidence['invalid']:
            raise ValueError('captured retro note is incomplete')
        roles.setdefault(record['agent_type'].rsplit(':', 1)[-1], []).append(evidence['fields'])
    if not roles:
        raise ValueError('no captured role evidence')
    proposals = day / 'proposals'
    proposals.mkdir(exist_ok=True)
    for row in watch.records(day / 'events.jsonl'):
        if row['kind'] != 'retro.captured':
            continue
        record = row['payload']
        change = record['fields']['Change'].strip()
        if change.casefold() == 'none':
            continue
        ident = sha256(record['evidence'].encode()).hexdigest()[:12]
        if change.casefold().startswith('hard rule:'):
            decision = day / 'decisions' / f'D-{int(ident, 16)}.md'
            if not decision.exists():
                decision.parent.mkdir(exist_ok=True)
                summary = change.removeprefix('Hard rule:').strip().replace('|', '/')
                if '\n' in summary or not summary:
                    raise ValueError('hard-rule change must be one nonempty line')
                workspace.atomic_write(decision, f'''Question: Should the hard rule change to {summary}?
Context: Captured role evidence at {record['evidence']}.
Options:
| Option | Description |
| --- | --- |
| A | Propose {summary} for implementation |
| B | Defer this hard-rule change |
Musts:
| Criterion | A | B |
| --- | --- | --- |
| Owner review | pass | pass |
Wants:
| Criterion | Weight | A | B |
| --- | --- | --- | --- |
| Evidence before rule change | 5 | 5 | 8 |
Recommendation: B
Confidence: medium
Reversibility: one-way
Blast radius: Guard behavior across the workspace
Pre-mortem: A broad refusal could block legitimate work.
Revisit: After owner review of the recorded evidence.
Decided-by: owner
Outcome: pending
''')
            continue
        role = record['agent_type'].rsplit(':', 1)[-1]
        if not (Path(__file__).resolve().parents[2] / 'charters' / f'{role}.md').is_file():
            raise ValueError(f'unknown charter role: {role}')
        proposal = proposals / f'retro-{ident}.json'
        if not any(proposal.with_suffix(suffix).exists() for suffix in ('.json', '.landed', '.rejected')):
            workspace.atomic_write(proposal, json.dumps({
                'target': f'.wuwei/charters/{role}.md', 'action': 'add',
                'text': '- ' + change, 'reason': record['fields']['Gap'],
                'evidence': record['evidence']}, allow_nan=False) + '\n')
    measured = metrics.collect(root)
    data = state.read_state(root)
    lines = ['# Steward retro ' + day.name, '', '## Per-role review',
             '| Role | Blocked | Gap | Change |', '| --- | --- | --- | --- |']
    for role, notes in sorted(roles.items()):
        for fields in notes:
            lines.append('| ' + ' | '.join([role] + [fields[key].replace('|', '/')
                for key in ('Blocked', 'Gap', 'Change')]) + ' |')
    lines += ['', '## Cycle', '| Item | Phase | Status | Fix rounds |',
              '| --- | --- | --- | --- |']
    rounds = measured['fix_rounds_per_item']
    for name, item in sorted(data['items'].items()):
        lines.append(f"| {name} | {item['phase']} | {item['status']} | "
                     f"{rounds.get(name, 0) if isinstance(rounds, dict) else 'unmeasured'} |")
    lines += ['', '## Gate verdicts', '| Record | Verdict |', '| --- | --- |']
    gates = sorted((day / 'decisions').glob('[gG][aA][tT][eE]-*.[mM][dD]'))
    for path in gates:
        if path.is_symlink():
            raise ValueError('gate verdict must not be a symlink')
        text = verdict.active_text(path.read_text(encoding='utf-8'))
        results = re.findall(verdict.VERDICT_ROW, text, re.M)
        if len(results) != 1:
            raise ValueError(f'invalid gate verdict: {path.name}')
        lines.append(f'| {path.name} | {results[0]} |')
    if not gates:
        lines.append('| none | unmeasured |')
    pending = sorted(proposals.glob('*.json')) if proposals.exists() else []
    rejected = sorted(proposals.glob('*.rejected')) if proposals.exists() else []
    applied = sorted(proposals.glob('*.landed')) if proposals.exists() else []
    def targets(paths):
        return [json.loads(path.read_text(encoding='utf-8'))['target'] for path in paths]
    from wuwei import interview
    lines += ['', '## Owner preferences', *(interview.reask(root) or ['none'])]
    lines += ['', '## Metrics', json.dumps(measured, sort_keys=True), '',
              '## Applied', *(['- `' + p + '`' for p in targets(applied)] or ['none']),
              '## Proposed', *(['- `' + p + '`' for p in targets([*pending, *rejected])] or ['none']), '']
    path = day / 'retro' / (day.name + '.md')
    workspace.atomic_write(path, '\n'.join(lines))
    return path
