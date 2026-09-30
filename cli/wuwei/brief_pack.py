"""Deterministic owner briefing pack and defend drill."""

from datetime import datetime, timedelta
import hashlib
import html
import os
import re
from pathlib import Path

from wuwei import metrics, registry, state, workspace


SECTIONS = ('Headline', 'Changed', 'Decided', 'At risk', 'You will be asked')


def _read(result, label):
    if result.exit != 0:
        raise ValueError(f'{label} unavailable')
    return result.data


def _clean(value, secret):
    text = str(value).replace('\n', ' ').replace('\r', ' ').strip()
    if secret:
        text = text.replace(secret, '[REDACTED]')
    return html.escape(re.sub(r'\s+', ' ', text)[:300])


def _evidence(root, secret):
    from wuwei import report
    data = state.read_state(root)
    items = sorted(data['items'].items(), key=lambda row: (row[1]['phase'] != 'merged', row[0]))
    changed = [_clean(f"{name}: {item['phase']}" + (f" ({item['pr']})" if item.get('pr') else ''), secret)
               for name, item in items if item['phase'] != 'planned']
    outcomes = report.decisions(workspace.day_dir(root), data)
    decided = [_clean(f'{ident}: {outcome}', secret) for ident, outcome in sorted(outcomes.items())
               if outcome.lower() != 'pending']
    risk = [_clean(f"{name}: {item['phase']}", secret) for name, item in sorted(data['items'].items())
            if item['phase'] in ('parked', 'escalated')]
    risk += [_clean(f'{ident}: pending owner decision', secret)
             for ident, outcome in sorted(outcomes.items()) if outcome.lower() == 'pending']
    actions = data.get('watch', {}).get('actions', {})
    risk += [_clean(f"{ref}: {actions[ref]['state']}: {actions[ref]['action']}", secret)
             for ref in sorted(set(data.get('raised_prs', []) + data.get('claimed_prs', [])))
             if ref in actions]
    return changed, decided, risk


def _meeting(root, config, secret):
    now = workspace.now()
    end = now + timedelta(minutes=config['brief']['lead_minutes'])
    calendar = registry.load('calendar', config)
    events = _read(calendar.events(now.isoformat(), end.isoformat(), root=root), 'calendar')
    if not isinstance(events, list):
        raise ValueError('calendar returned invalid events')
    due = [event for event in events if isinstance(event, dict) and event.get('attendees')
           and isinstance(event.get('summary'), str) and isinstance(event.get('uid'), str)
           and now <= datetime.fromisoformat(event['start']) <= end]
    if not due:
        raise ValueError('no attendee meeting in lead window')
    selected = min(due, key=lambda row: row['start'])
    return {**selected, 'summary': _clean(selected['summary'], secret)}


def relative_path(day_name, key):
    return Path('.wuwei/days') / day_name / 'briefs' / f'pack-{key}.md'


def pack(*, meeting=False, root=None):
    root = workspace.find_workspace(root)
    config = workspace.load_config(root)
    secret = os.environ.get('WUWEI_CALENDAR_URL') or config['calendar']['url']
    event = _meeting(root, config, secret) if meeting else None
    key = ('meeting-' + hashlib.sha256(event['uid'].encode()).hexdigest()[:16]
           if event else 'daily')
    directory = workspace.day_dir(root)
    relative = relative_path(directory.name, key)
    output = root / relative
    if output.parent.resolve() != output.parent or output.is_symlink():
        raise ValueError('brief pack path must not be a symlink')
    if output.is_file():
        return str(relative)
    changed, decided, risk = _evidence(root, secret)
    recent = _read(registry.load('transcripts', config).recent(
        workspace.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
        root=root), 'transcripts')
    if not isinstance(recent, list):
        raise ValueError('transcripts returned invalid records')
    changed.extend(_clean(row['summary'], secret) for row in recent
                   if isinstance(row, dict) and isinstance(row.get('summary'), str))
    measured = metrics.collect(root)
    rounds = measured.get('fix_rounds_per_item', {})
    metric_lines = ([f'{_clean(item, secret)}: {count} fix rounds' for item, count in rounds.items()]
                    if isinstance(rounds, dict) else [])
    headline = risk[0] if risk else changed[0] if changed else 'No recorded changes'
    change = changed[0] if changed else 'No recorded changes'
    decision = decided[0] if decided else 'No recorded decisions'
    danger = risk[0] if risk else 'No recorded risks'
    asked = f'What should we know about {event["summary"]}?' if event else 'What changed today?'
    values = (headline, change, decision, danger, asked)
    if config['brief']['style']['length'] == 'concise':
        values = tuple(value[:120] for value in values)
    chapter_text = '\n'.join(f'{name}. {value}' for name, value in zip(SECTIONS, values))
    if len(chapter_text.split()) > 600:
        raise ValueError('brief exceeds five-minute audio limit')
    questions = [
        {'question': f'What is the main risk for {event["summary"] if event else "today"}?', 'answer': danger},
        {'question': 'What changed?', 'answer': change},
        {'question': 'What was decided?', 'answer': decision},
    ]
    title = f'Meeting: {event["summary"]}' if event else 'Daily brief'
    lines = [f'# {title}', '']
    for name, value in zip(SECTIONS, values):
        lines += [f'## {name}', '', value, '']
    lines += ['## What changed', '', f'**{change}**', '']
    lines.extend(metric_lines)
    for extra in changed[1:4]:
        lines += [f'<details><summary>Deep dive: {extra[:60]}</summary>', '', extra, '', '</details>', '']
    lines += ['## Meeting card', '', f'- {headline}', f'- {decision}', f'- {asked}', '',
              '## Defend drill', '']
    for number, row in enumerate(questions, 1):
        lines.append(f'{number}. {row["question"]}')
    lines += ['', '## Audio', '']
    tts = registry.load('tts', config)
    audio_path = output.with_suffix('.aiff')
    if audio_path.is_symlink():
        raise ValueError('brief audio path must not be a symlink')
    output.parent.mkdir(parents=True, exist_ok=True)
    result = _read(tts.speak(chapter_text, config['brief']['style']['speed'], audio_path, root=root), 'tts')
    if not isinstance(result, dict) or type(result.get('performed')) is not bool:
        raise ValueError('tts returned invalid result')
    if result['performed']:
        lines.append(f'Audio: {audio_path.name} (five chapters)')
    else:
        lines.append('Audio unavailable (tts: none)')
    workspace.atomic_write(output, '\n'.join(lines) + '\n')
    def update(data):
        data.setdefault('brief_packs', {})[key] = {'path': str(relative), 'questions': questions,
                                                  'answers': {}}
        data.setdefault('brief_drill', {'answered': 0, 'correct': 0, 'streak': 0})
    state._write_state(update, root, reserved=False, kind='brief.pack', payload={'key': key})
    return str(relative)


def answer(number, text, *, meeting=False, root=None):
    root = workspace.find_workspace(root)
    key = 'meeting-' if meeting else 'daily'
    data = state.read_state(root)
    packs = data.get('brief_packs', {})
    if meeting:
        names = [name for name in packs if name.startswith(key)]
        if not names:
            raise ValueError('no meeting pack')
        key = names[-1]
    if key not in packs:
        raise ValueError('no pack to answer')
    if number not in (1, 2, 3):
        raise ValueError('question must be 1, 2 or 3')
    expected = packs[key]['questions'][number - 1]['answer']
    terms = {word.lower() for word in re.findall(r'[A-Za-z0-9]{4,}', expected)}
    supplied = {word.lower() for word in re.findall(r'[A-Za-z0-9]{4,}', text)}
    correct = bool(terms & supplied)
    def update(data):
        entry = data['brief_packs'][key]
        if str(number) in entry['answers']:
            raise ValueError('question already answered')
        score = data['brief_drill']
        score['answered'] += 1
        score['correct'] += int(correct)
        score['streak'] = score['streak'] + 1 if correct else 0
        feedback = ('Correct' if correct else 'Incorrect') + f'. Expected: {expected}'
        config = workspace.load_config(root)
        secret = os.environ.get('WUWEI_CALENDAR_URL') or config['calendar']['url']
        entry['answers'][str(number)] = {'correct': correct, 'answer': _clean(text, secret),
                                         'feedback': feedback, 'streak': score['streak']}
    result = state._write_state(update, root, reserved=False, kind='brief.answer',
                                payload={'key': key, 'question': number, 'correct': correct})
    return f'{"Correct" if correct else "Incorrect"}. Expected: {expected}. Streak: {result["brief_drill"]["streak"]}'
