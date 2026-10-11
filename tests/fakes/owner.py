"""#831: the owner's answer to an Owner step card, recorded through the real PostToolUse hook."""

import json

from wuwei.guards.decision import record_gate


def _record(root, card, reply, session, agent):
    question = {key: value for key, value in card.items() if key != 'record'}
    payload = {'cwd': str(root), 'session_id': session, 'tool_name': 'AskUserQuestion',
               'tool_input': {'questions': [question]},
               'tool_response': {'answers': {card['question']: reply}}}
    if agent:
        payload['agent_id'] = agent
    result = record_gate(payload)
    assert result == (0, ''), result
    return result


def answer(root, command, token='', reply='Yes', session='planner-session', agent=None, detail='x'):
    """The owner answers the card needs_owner(root, command, detail, token) prints."""
    from wuwei.sessions import owner_card
    return _record(root, owner_card(command, detail, token), reply, session, agent)


def answer_card(root, text, reply='Yes', session='planner-session'):
    """Answer the Owner step card a refusal printed, as the planner asks it."""
    card, _ = json.JSONDecoder().raw_decode(text[text.index('{"question": "Owner step: '):])
    return _record(root, card, reply, session, None)
