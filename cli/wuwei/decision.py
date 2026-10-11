"""Card helpers for the morning and close gates, and readers of past days' D-n records."""

from pathlib import Path
import re

from wuwei import workspace
from wuwei.verdict import active_text


def widget(question, header, options, record, *, multi=False):
    """One AskUserQuestion question (the session passes all but `record`) and the one command
    that records its answer. options: (label, description) pairs, the recommended first."""
    if len(header) > 12 or not 2 <= len(options) <= 4:
        raise ValueError(f'widget {header}: expected a header of at most 12 characters and 2 to 4 options; pass a shorter header and 2 to 4 options')
    return {'question': question, 'header': header, 'multiSelect': multi,
            'options': [{'label': label, 'description': text} for label, text in options],
            'record': record}


def gate(root):
    """The morning gate citation the question guard accepts for questions without a record."""
    return f'Morning gate (days/{workspace.day_dir(root).name}/plan.md): '


def naming(directory, items):
    """Map each D-n and C-n record of a day to the items its Question: or Context: line names."""
    found = {}
    for path in sorted((Path(directory) / 'decisions').glob('[DC]-*.md')):
        if path.is_symlink() or not re.fullmatch(r'[DC]-[1-9][0-9]*', path.stem):
            continue
        lines = [line for line in active_text(path.read_text(encoding='utf-8')).splitlines()
                 if re.match(r'(?:#{1,6} )?(?:Question|Context):', line)]
        found[path.stem] = [item for item in items if any(
            re.search(r'(?<![\w-])' + re.escape(item) + r'(?![\w-])', line) for line in lines)]
    return found


def answered(data, identifier):
    """Return the owner's recorded option for a decision, or None while it is unanswered."""
    record = data.get('decision_outcomes', {}).get(identifier)
    return record.get('option') if isinstance(record, dict) and record.get('decided_by') == 'owner' else None
