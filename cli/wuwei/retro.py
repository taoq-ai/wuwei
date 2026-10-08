"""Compile the steward's dated review from recorded day evidence."""

import json
from hashlib import sha256
from pathlib import Path
import re

from wuwei import metrics, state, verdict, watch, workspace
from wuwei.promotion import safe_path
from wuwei.exits import DAMAGED, SYMLINK


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
            raise ValueError('retro evidence must belong to today; capture it again with the retro session (bin/wuwei retro)')
        evidence = json.loads(path.read_text(encoding='utf-8'))
        if any(evidence.get(key) != record.get(key) for key in
               ('agent_id', 'agent_type', 'fields', 'missing', 'invalid')):
            raise ValueError('captured retro evidence mismatch; capture it again with the retro session (bin/wuwei retro)')
        if evidence['missing'] or evidence['invalid']:
            raise ValueError('captured retro note is incomplete; capture it again with the retro session (bin/wuwei retro)')
        roles.setdefault(record['agent_type'].rsplit(':', 1)[-1], []).append(evidence['fields'])
    if not roles:
        raise ValueError(f'no captured role evidence; {DAMAGED}')
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
                    raise ValueError('hard-rule change must be one nonempty line; write the change as one line')
                workspace.atomic_write(decision, f'''Question: Should the hard rule change to {summary}?
Class: other
Context: Captured role evidence at {record['evidence']}.
Options:
| Option | Title | Rationale | Consequence |
| --- | --- | --- | --- |
| A | Propose the rule | Passes owner review but scores lower on evidence before a rule change. | {summary} is proposed for implementation. |
| B | Defer the rule change | Passes owner review and waits for more evidence. | The hard rule stays as it is. |
Musts:
| Criterion | A | B |
| --- | --- | --- |
| Owner review | pass | pass |
Wants:
| Criterion | Weight | A | B |
| --- | --- | --- | --- |
| Evidence before rule change | 5 | 5 | 8 |
Recommendation: B
Reasoning: Evidence before a rule change decided it; more captured evidence would flip it.
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
            raise ValueError(f'gate verdict must not be a symlink; {SYMLINK}')
        text = verdict.active_text(path.read_text(encoding='utf-8'))
        results = re.findall(verdict.VERDICT_ROW, text, re.M)
        if len(results) != 1:
            raise ValueError(f'invalid gate verdict: {path.name}')
        lines.append(f'| {path.name} | {results[0]} |')
    if not gates:
        lines.append('| none | unmeasured |')
    lines += _second_opinion(data['gate_verdicts'])
    path = day / 'retro' / (day.name + '.md')
    window = watch.days(root)[:7]
    quality = metrics.bands(root, window)
    margin = workspace.load_config(root)['metrics']['band_margin']
    lines += ['', '## Quality by band (last 7 days)']
    for key, title in (('hour', 'Hour'), ('session_age', 'Session age')):
        lines += [*metrics.band_lines(title, quality[key]), '']
        found = metrics.worst(quality[key], margin)
        lines.append(f'Worst {title.lower()} band: ' + (
            f'{found[0]} (FIX rate {found[1]:.2f}; others at most {found[2]:.2f})' if found else 'none'))
        if not found:
            continue
        name = f"quality-{key.replace('_', '-')}-{re.sub(r'[^a-z0-9]+', '-', found[0]).strip('-')}"
        # ponytail: the dedupe looks back seven days only; a band that stays worst re-proposes weekly.
        if any((directory / 'proposals' / f'{name}{suffix}').exists()
               for directory in window for suffix in ('.json', '.landed', '.rejected')):
            continue
        workspace.atomic_write(proposals / f'{name}.json', json.dumps({
            'target': '.wuwei/charters/planner.md', 'action': 'add',
            'text': (f'- Gate FIX rate is highest in the {found[0]} {title.lower()} band over the last '
                     f'7 days ({found[1]:.2f}, others at most {found[2]:.2f}): set '
                     'sessions.rotate_after so the planner session rotates before it.'),
            'reason': 'quality by band', 'evidence': path.relative_to(root).as_posix()},
            allow_nan=False) + '\n')
    pending = sorted(proposals.glob('*.json')) if proposals.exists() else []
    rejected = sorted(proposals.glob('*.rejected')) if proposals.exists() else []
    applied = sorted(proposals.glob('*.landed')) if proposals.exists() else []
    def targets(paths):
        return [json.loads(path.read_text(encoding='utf-8'))['target'] for path in paths]
    from wuwei import interview
    from wuwei import calibration_scores
    lines += ['', '## Calibration', *calibration_scores.lines(root, workspace.load_config(root))]
    lines += ['', '## Owner preferences', *(interview.reask(root) or ['none'])]
    lines += ['', '## Metrics', json.dumps(measured, sort_keys=True), '',
              '## Applied', *(['- `' + p + '`' for p in targets(applied)] or ['none']),
              '## Proposed', *(['- `' + p + '`' for p in targets([*pending, *rejected])] or ['none']), '']
    workspace.atomic_write(path, '\n'.join(lines))
    return path


def _second_opinion(records):
    """Findings each model raised alone in the initial round, and what each verdict cost."""
    seconds = sorted((record for record in records.values()
                      if record.get('runtime') and record.get('round') == 'initial'),
                     key=lambda record: record['item'])
    if not seconds:
        return []

    def keyed(record):
        # ponytail: matched on the first file:line citation, so one defect cited on two lines
        # counts twice; compare finding text if that misleads the owner.
        return {(found[0].lower() if (found := re.search(verdict.CITATION, text))
                 else ' '.join(text.lower().split())): text for text in record.get('findings', [])}
    lines = ['', '## Second opinion', '| Item | Found only by | Finding |', '| --- | --- | --- |']
    costs = ['', '| Item | Gate | Model | Cost | Duration |', '| --- | --- | --- | --- | --- |']
    for second in seconds:
        item, role = second['item'], second['role'].partition('@')[0]
        first = records.get(f'{item}:{role}:initial', {})
        mine, theirs = keyed(second), keyed(first)
        for label, own, other in ((f"{second['role']} {second['model']}", mine, theirs),
                                  (role, theirs, mine)):
            lines += [f"| {item} | {label} | {text.splitlines()[0].replace('|', '/')} |"
                      for key, text in own.items() if key not in other] or [f'| {item} | {label} | none |']
        for gate, record in ((role, first), (second['role'], second)):
            usage = record.get('usage', {})
            costs.append(f"| {item} | {gate} | " + ' | '.join(
                str(usage.get(key, 'unmeasured')) for key in ('model', 'cost', 'duration')) + ' |')
    return lines + costs
