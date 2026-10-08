"""Week and month digests built from day records in one fixed shape (design 5.14)."""

from datetime import date, timedelta
import json
from pathlib import Path
import re

from wuwei import workspace
from wuwei.exits import SYMLINK

SECTIONS = ('Decisions', 'Lessons', 'Metrics', 'Incidents', 'Items')


def period(day, kind):
    """(name, title, dates) for the ISO week or the calendar month holding day."""
    if kind == 'week':
        year, week, weekday = day.isocalendar()
        monday = day - timedelta(days=weekday - 1)
        dates = [monday + timedelta(days=offset) for offset in range(7)]
        name = f'{year}-W{week:02d}'
        return name, f'# Week {name} ({dates[0]} to {dates[-1]})', dates
    from calendar import monthrange
    name = f'{day.year}-{day.month:02d}'
    return name, f'# Month {name}', [date(day.year, day.month, number)
                                       for number in range(1, monthrange(day.year, day.month)[1] + 1)]


def _clean(free, config):
    """Seat free text joins a digest only when it passes the owner lint and holds no path or secret."""
    from wuwei import outward, redact
    return (outward.lint(free, 'digest', config, to_owner=True)[0] == 0 and '/' not in free
            and redact.known_values(free) == free)


def _field(name, text):
    match = re.search(r'^(?:#{1,6} )?' + name + r':\s*(\S[^\n]*)$', text, re.M)
    return match.group(1).strip() if match else None


def build(root, title, dates, config, dora=()):
    from wuwei import signal
    from wuwei.consolidation import day_records
    root = Path(root)
    sections = {name: [] for name in SECTIONS}
    wanted = {day.isoformat() for day in dates}
    ledger = root / '.wuwei/memory/ledger.jsonl'
    if ledger.is_symlink():
        raise ValueError(f'ledger must not be a symlink; {SYMLINK}')
    rows = [json.loads(line) for line in ledger.read_text(encoding='utf-8').splitlines()
            if line.strip()] if ledger.exists() else []
    for day in sorted(wanted):
        records = day_records(root, day)
        if records is not None:
            decisions = sorted((name for name in records if re.fullmatch(r'decisions/D-\d+\.md', name)),
                               key=lambda name: int(name[11:-3]))
            for name in decisions:
                outcome, question = _field('Outcome', records[name]), _field('Question', records[name])
                if not outcome or outcome == 'pending':
                    continue
                ident = name[10:-3]
                sections['Decisions'].append(
                    f'- {day} {ident}: {question} Outcome: {outcome}' if question and _clean(question, config)
                    else f'- {day} {ident}: decided {outcome}')
            report = records.get('report.md')
            if report is None:
                sections['Metrics'].append(f'- {day} unmeasured')
            else:
                heading = None
                for line in report.splitlines():
                    if line.startswith('## '):
                        heading = line[3:].strip()
                    elif heading in ('Outcome', 'Changed') and line.strip():
                        sections['Metrics'].append(f'- {day} {line.strip().removeprefix("- ")}')
            data = json.loads(records['state.json']) if 'state.json' in records else {}
            pages = {}
            for line in records.get('events.jsonl', '').splitlines():
                event = json.loads(line) if line.strip() else None
                if event and signal.classify(event, data)[0] == 'page':
                    pages[event['kind']] = pages.get(event['kind'], 0) + 1
            sections['Incidents'] += [f'- {day} {kind}: {count}' for kind, count in sorted(pages.items())]
            items = data.get('items') or {}
            if items:
                groups = {'closed': [], 'carried': [], 'parked': []}
                for name, item in sorted(items.items()):
                    phase = item.get('phase') if isinstance(item, dict) else None
                    groups['closed' if phase == 'merged' else 'parked' if phase == 'parked'
                           else 'carried'].append(name)
                sections['Items'].append(f'- {day} ' + '; '.join(
                    f'{group}: {", ".join(names) or "none"}' for group, names in groups.items()))
        for row in rows:
            if row.get('date') == day:
                structured = f'- {day} {row["status"]}: {Path(row["target"]).name} {row["action"]}'
                reason = row.get('reason')
                sections['Lessons'].append(f'{structured}: {reason}' if isinstance(reason, str) and reason
                                           and _clean(reason, config) else structured)
    sections['Metrics'] += dora  # #586: the week's DORA table
    return title + '\n' + ''.join(f'\n## {name}\n' + ('\n'.join(lines) or 'none') + '\n'
                                  for name, lines in sections.items())


def write(root, day, kind):
    """Rebuild memory/digests/<name>.md; writes only when the text changed. None when off."""
    root = Path(root)
    config = workspace.load_config(root)
    if config['memory']['digest'] == 'off':
        return None
    directory = root / '.wuwei/memory/digests'
    if directory.is_symlink() or directory.parent.is_symlink():
        raise ValueError(f'memory/digests must not be a symlink; {SYMLINK}')
    name, title, dates = period(day, kind)
    dora = ()
    if kind == 'week':
        from wuwei import metrics, report
        try:
            dora = report.dora_lines(metrics.dora(root, config, *metrics.week_window(config, dates[0])))
        except (OSError, ValueError):  # a digest reads loose day records; the keys need valid ones
            dora = ['- DORA unmeasured: a day record failed its check; run bin/wuwei doctor']
    text = build(root, title, dates, config, dora)
    path = directory / f'{name}.md'
    if path.is_symlink():
        raise ValueError(f'digest must not be a symlink: {path.name}')
    if not path.is_file() or path.read_text(encoding='utf-8') != text:
        directory.mkdir(parents=True, exist_ok=True)
        workspace.atomic_write(path, text, mode=0o644)
    return path


def latest(root):
    """(newest month digest or None, newest week digest or None)."""
    directory = Path(root) / '.wuwei/memory/digests'
    if directory.is_symlink():
        raise ValueError(f'memory/digests must not be a symlink; {SYMLINK}')
    names = sorted(directory.glob('*.md')) if directory.is_dir() else []
    months = [path for path in names if re.fullmatch(r'\d{4}-\d{2}', path.stem)]
    weeks = [path for path in names if re.fullmatch(r'\d{4}-W\d{2}', path.stem)]
    return (months[-1] if months else None), (weeks[-1] if weeks else None)
