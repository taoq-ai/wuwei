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


def test_adding_an_id_again_rescores_it_and_reopens_a_dropped_item(root):
    plan.add(root, 'I-1', 'a', 'G-1', 'acme/app', 'light', scores())
    plan.mark(root, 'I-1', 'dropped', 'wrong scores')
    item = plan.add(root, 'i-1', 'a better title', 'G-1', 'acme/app', 'standard', scores(value=13))
    assert (item['id'], item['title'], item['tier'], item['status'], item['score']) == ('I-1', 'a better title', 'standard', 'open', 10.5)
    assert len(plan.items(root)) == 1 and ws.rows(root, 'item.updated')


def test_restore_reopens_a_parked_or_dropped_item(root):
    plan.add(root, 'I-1', 'a', 'G-1', 'acme/app', 'light', scores())
    plan.mark(root, 'I-1', 'parked', 'later')
    assert plan.restore(root, 'I-1')['status'] == 'open'
    with pytest.raises(ValueError):
        plan.restore(root, 'I-9')


def test_candidates_are_added_from_the_lead_file_with_its_own_field_names(root, tmp_path):
    import json
    lead = tmp_path / 'lead.json'
    lead.write_text(json.dumps({'candidates': [
        {'id': 'TIN-1', 'title': 'routing', 'goal': 'G-1', 'repository': 'acme/app', 'tier': 'standard',
         'scores': {'business_value': 8, 'time_criticality': 5, 'risk_reduction': 3, 'job_size': 2},
         'why': 'every call routes wrong', 'promise': 'calls route to their client',
         'acceptance': ['given a Gong call, when it arrives, then it lands with its client']}]}))
    [item] = plan.add_from(root, lead)
    assert (item['repo'], item['score'], item['promise']) == ('acme/app', 8.0, 'calls route to their client')
    assert item['acceptance'] == ['given a Gong call, when it arrives, then it lands with its client']


def test_a_seat_reads_its_item_promise_from_the_plan(root, monkeypatch, capsys):
    import json
    from wuwei import __main__ as cli
    monkeypatch.chdir(root)
    assert cli.main(['plan', 'add', 'I-7', 'mid-day item', '--goal', 'G-1', '--repo', 'acme/app', '--value', '5',
                     '--time', '3', '--risk', '2', '--size', '2', '--promise', 'one route per client',
                     '--accept', 'given A, when B, then C']) == 0
    capsys.readouterr()
    assert cli.main(['plan', 'show', 'I-7']) == 0
    item = json.loads(capsys.readouterr().out)
    assert (item['promise'], item['acceptance']) == ('one route per client', ['given A, when B, then C'])
