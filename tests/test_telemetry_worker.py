"""The project's collector (#422, design 5.13): the pure accept function and the summary."""

from datetime import date
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 10, 3)  # 2026-W40: 2026-W36 to 2026-W39 are accepted


def load(name):
    # As the deploy bundle runs: telemetry.py importable as a top-level module beside the worker.
    sys.path.insert(0, str(ROOT / 'cli/wuwei'))
    try:
        spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts/telemetry-worker' / f'{name}.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(ROOT / 'cli/wuwei'))


def payload(**changes):
    return json.dumps({'schema': 1, 'week': '2026-W39', 'token': 'a' * 32,
                       'versions': {'plugin': '0.12.0', 'python': '3.12', 'os': 'linux'},
                       'config': {'posture': 'guarded', 'profile': 'strict', 'adapters': {'tracker': 'none'},
                                  'repositories': 1},
                       'metrics': {'days': 5, 'refusals': {'pr': 2}}, **changes})


@pytest.mark.parametrize('body, kwargs, status', [
    (payload(), {}, 201),
    ('{nope', {}, 400),
    (payload(metrics={'days': 'acme/widget'}), {}, 400),
    (json.dumps({k: v for k, v in json.loads(payload()).items() if k != 'token'}), {}, 400),
    (payload(week='2026-W40'), {}, 422),
    (payload(week='2026-W35'), {}, 422),
    (payload(week='2026-W36'), {}, 201),
    (payload(), {'seen': {('a' * 32, '2026-W39')}}, 409),
    (payload(), {'ip_count': 10}, 429),
    (payload(), {'writes': 1000}, 429),
])
def test_accept(body, kwargs, status):
    worker = load('worker')
    found = worker.accept(body, **{'today': TODAY, 'seen': set(), 'ip_count': 0, 'writes': 0, **kwargs})
    assert found[0] == status
    if status == 201:
        assert found[1] == f"data/{json.loads(body)['week']}/{'a' * 32}.json"


def test_summary_counts_workspaces_and_sums_integers(tmp_path):
    summary = load('summary')
    for token, days, refusals in (('a', 5, 2), ('b', 3, 'unmeasured')):
        path = tmp_path / 'data/2026-W39' / f'{token * 32}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'week': '2026-W39', 'metrics': {
            'days': days, 'refusals': {'pr': refusals} if isinstance(refusals, int) else refusals,
            'refusal_rate': 0.5}}))
    assert summary.summarise(tmp_path / 'data') == {
        '2026-W39': {'workspaces': 2, 'metrics': {'days': 8, 'refusals.pr': 2}}}
