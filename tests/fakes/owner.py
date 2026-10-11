"""#831: the owner's answer to an Owner step card, recorded through the real PostToolUse hook."""

import json

from wuwei.guards.decision import record_gate


def _record(root, question, reply, session, agent):
    payload = {'cwd': str(root), 'session_id': session, 'tool_name': 'AskUserQuestion',
               'tool_input': {'questions': [{'header': 'Owner step', 'question': question, 'multiSelect': False,
                                             'options': [{'label': 'Yes', 'description': 'go'},
                                                         {'label': 'No', 'description': 'stop'}]}]},
               'tool_response': {'answers': {question: reply}}}
    if agent:
        payload['agent_id'] = agent
    result = record_gate(payload)
    assert result == (0, ''), result
    return result


def answer(root, command, token='', reply='Yes', session='planner-session', agent=None):
    question = f'Owner step: {command}' + (f' ({token})' if token else '')
    return _record(root, question, reply, session, agent)


def answer_card(root, text, reply='Yes', session='planner-session'):
    """Answer the Owner step card a refusal printed, as the planner asks it."""
    card, _ = json.JSONDecoder().raw_decode(text[text.index('{"question": "Owner step: '):])
    return _record(root, card['question'], reply, session, None)
