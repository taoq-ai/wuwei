"""The owner's answers to cards asked in the session, recorded for the commands that read them."""

from pathlib import Path
import re

from wuwei import workspace
from wuwei.guards import Guard
from wuwei.guards.verdict import required_text
from wuwei.workspace import scope


def _answer(payload, text):
    """The owner's answer to the question text, stripped, or None."""
    response = payload.get('tool_response')
    answers = response.get('answers') if isinstance(response, dict) else None
    answer = answers.get(text) if isinstance(answers, dict) else None
    return answer.strip() if isinstance(answer, str) and answer.strip() else None


def record_gate(payload):
    """PostToolUse: record the owner's reply to an Owner step card from any main session (#831)."""
    try:
        cwd = Path(required_text(payload, 'cwd')).resolve()
        if 'agent_id' in payload:
            return 0, ''
        try:
            context = scope(cwd)
        except workspace.ConfigError:  # #831: an Owner step answer repairs a config that does not load
            context = (workspace.find_workspace(cwd, use_environment=False), None)
        if context is None:
            return 0, ''
        root, _ = context
        from wuwei import state
        from wuwei.sessions import OWNER_STEP, owner_topic, step
        session = payload.get('session_id')
        questions = payload['tool_input']['questions']
        # #831: the owner's reply to an Owner step card, from any main session, before state:
        # the asked topic, the answer bound to the question (#856), and the command part and the
        # token it carries, which only name a card that did not match.
        owner = [question for question in questions if question.get('header') == OWNER_STEP
                 and required_text(question, 'question').startswith(f'{OWNER_STEP}: ')]
        found = set()
        for question in owner:
            if reply := _answer(payload, question['question']):
                found.update((owner_topic(question['question']), owner_topic(question['question'], reply),
                              owner_topic(step(question['question']))))
                if token := re.search(r'\([0-9a-f]{12}\)$', question['question'].strip()):
                    found.add(owner_topic(token[0]))
        if found:
            state.append_event('gate.asked', {'session_id': session, 'topics': sorted(found)}, root)
        return 0, ''
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
        return 2, f'gate record: {exc}'


GUARDS = [Guard('PostToolUse', 'AskUserQuestion', record_gate)]
