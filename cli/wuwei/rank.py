"""Validate and rank candidate evidence without external calls."""

import math


WSJF = ('value', 'time_criticality', 'risk_reduction', 'job_size')
RICE = ('reach', 'impact', 'confidence', 'effort')
FIBONACCI = (1, 2, 3, 5, 8, 13, 20)


def validate(item, framework, goals):
    if framework not in ('wsjf', 'rice'):
        raise ValueError('framework must be wsjf or rice')
    if not isinstance(item, dict) or not isinstance(item.get('id'), str):
        raise ValueError('candidate id required')
    name = item['id']
    goal = item.get('goal', 'unplanned' if item.get('unplanned') is True else None)
    if goal != 'unplanned' and goal not in goals:
        raise ValueError(f'{name}: goal must be confirmed or unplanned')
    score = item.get('score')
    evidence = item.get('evidence_lines')
    if not isinstance(score, dict) or not isinstance(evidence, dict):
        raise ValueError(f'{name}: score and evidence_lines required')
    for key in WSJF if framework == 'wsjf' else RICE:
        value = score.get(key)
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f'{name}: {key} component required')
        allowed = FIBONACCI if framework == 'wsjf' else {'impact': (.25, .5, 1, 2, 3),
                                                           'confidence': (.5, .8, 1)}.get(key)
        if allowed is not None and value not in allowed or allowed is None and value <= 0:
            raise ValueError(f'{name}: {key} out of range')
        line = evidence.get(key)
        if not isinstance(line, str) or not line.strip() or '\n' in line:
            raise ValueError(f'{name}: {key} evidence line required')
    return item


def rank(candidates, framework, goals):
    """Return new ordered list; caller-owned rows are unchanged."""
    if not isinstance(candidates, list):
        raise ValueError('candidates must be a list')
    for item in candidates:
        validate(item, framework, goals)

    def key(item):
        s = item['score']
        score = ((s['value'] + s['time_criticality'] + s['risk_reduction']) / s['job_size']
                 if framework == 'wsjf' else
                 s['reach'] * s['impact'] * s['confidence'] / s['effort'])
        priority = goals.get(item.get('goal'), {}).get('priority', float('inf'))
        return (-score, priority, item['id'])

    return sorted(candidates, key=key)
