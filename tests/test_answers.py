"""The owner's answers recorded by the PostToolUse AskUserQuestion hook (guards/answers.py)."""

import json

import pytest

from wuwei import state
from wuwei.guards.answers import record_gate
from wuwei.workspace import day_dir


@pytest.fixture
def planner(tmp_path, monkeypatch):
    from wuwei import plan
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    root = tmp_path / 'workspace'
    (root / '.wuwei').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text('')
    day_dir(root).mkdir(parents=True, exist_ok=True)
    (day_dir(root) / 'plan.md').write_text('# Morning plan\n')
    plan.session('planner-1', root)
    return root


def events(root):
    return [json.loads(line) for line in (day_dir(root) / 'events.jsonl').read_text().splitlines()]


def asked(root, header, text, session='planner-1', **extra):
    return {'cwd': str(root), 'session_id': session, 'tool_name': 'AskUserQuestion',
            'tool_input': {'questions': [{'question': text, 'header': header}]}, **extra}


def test_morning_gate_and_other_questions_record_nothing(planner):
    gate = f'Morning gate ({day_dir(planner).relative_to(planner / ".wuwei").as_posix()}/plan.md): confirm goals?'
    for payload in (asked(planner, 'Goals', gate, tool_response={'answers': {gate: 'Yes'}}),
                    asked(planner, 'Pick', 'Choose D-3 for the build?')):
        assert record_gate(payload) == (0, '')
    assert 'gate_asked' not in state.read_state(planner)['sessions']['planner-1']
    assert 'gate.asked' not in [row['kind'] for row in events(planner)]


def test_record_gate_notes_asked_decisions(planner):
    from test_decision import save
    save(planner)
    for payload in (asked(planner, 'D-3', 'Which option?'), asked(planner, 'D-9', 'D-9: Which option?'),
                    asked(planner, 'D-3', 'D-3: Which option?', agent_id='a1'),
                    asked(planner, 'D-3', 'D-3: Which option?', 'other'),
                    asked(planner, 'D-3', 'D-30: Which option?')):
        assert record_gate(payload) == (0, '')
    assert 'gate_asked' not in state.read_state(planner)['sessions']['planner-1']
    assert record_gate(asked(planner, 'D-3', 'D-3: Which option?')) == (0, '')
    assert state.read_state(planner)['sessions']['planner-1']['gate_asked'] == ['D-3']


def test_owner_step_answer_is_recorded_from_any_main_session(planner):
    from fakes import owner
    from wuwei import sessions
    command = 'bin/wuwei plan resume A'
    assert owner.answer(planner, command, session='any-main') == (0, '')
    assert sessions.needs_owner(planner, command, 'x') is None
    assert owner.answer(planner, 'bin/wuwei plan resume B', agent='a1') == (0, '')
    assert sessions.needs_owner(planner, 'bin/wuwei plan resume B', 'x') is not None


def test_answers_is_the_one_ask_user_question_guard():
    from wuwei import guards
    assert guards.MODULES['answers'] == {'PostToolUse': 'AskUserQuestion'}
    assert 'decision' not in guards.MODULES and 'answers' in guards.FLOOR
