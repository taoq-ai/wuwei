import pytest

from wuwei import plan, ws


def scores(value=8, time=5, risk=3, size=2):
    return {'value': value, 'time': time, 'risk': risk, 'size': size}


def test_wsjf_ranks_the_queue(root):
    plan.add(root, 'I-1', 'small win', 'G-1', 'acme/app', 'light', scores(size=1))
    plan.add(root, 'I-2', 'big job', 'G-1', 'acme/app', 'standard', scores(size=13))
    assert [item['id'] for item in plan.items(root)] == ['I-1', 'I-2']
    assert plan.items(root)[0]['score'] == 16.0


def test_rice_when_configured(root):
    ws.set_config(root, 'prioritisation', 'rice')
    item = plan.add(root, 'I-1', 't', 'G-1', 'acme/app', 'light',
                    {'reach': 100, 'impact': 2, 'confidence': 0.8, 'effort': 4})
    assert item['score'] == 40.0


@pytest.mark.parametrize('bad', [scores(value=4), scores(size=0), {'value': 1}])
def test_scores_outside_the_scale_are_refused(root, bad):
    with pytest.raises(ValueError):
        plan.add(root, 'I-1', 't', 'G-1', 'acme/app', 'light', bad)


def test_parked_items_sink_and_are_recorded(root):
    plan.add(root, 'I-1', 'a', 'G-1', 'acme/app', 'light', scores(size=1))
    plan.add(root, 'I-2', 'b', 'G-1', 'acme/app', 'light', scores(size=2))
    plan.mark(root, 'I-1', 'parked', 'two fix rounds without a pass')
    assert [item['id'] for item in plan.items(root)] == ['I-2', 'I-1']
    assert ws.rows(root, 'item.parked')[0]['data']['reason'] == 'two fix rounds without a pass'


def test_a_duplicate_id_is_refused(root):
    plan.add(root, 'I-1', 'a', 'G-1', 'acme/app', 'light', scores())
    with pytest.raises(ValueError):
        plan.add(root, 'i-1', 'a', 'G-1', 'acme/app', 'light', scores())
