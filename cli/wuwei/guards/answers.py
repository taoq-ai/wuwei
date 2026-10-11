"""The owner's answers to cards asked in the session, recorded for the commands that read them."""

from pathlib import Path
import re

from wuwei import workspace
from wuwei.guards import Guard
from wuwei.guards.verdict import required_text
from wuwei.workspace import scope


DRAFT_ID = r'(?<![\w-])draft-[0-9a-f]{32}(?![\w-])'


def _pending_drafts(root):
    """Ids of today's pending drafts (#493): a card may cite only those."""
    from wuwei import drafts, state
    return {key for key, row in drafts.read(state.read_state(root)).items() if row['status'] == 'pending'}


def _draft_answer(payload, text):
    """The owner's answer to a Draft card as a topic suffix (#493): ':send' for Send now,
    ':edit' for Send with an edit, ':text:<sha256>' for text the owner typed, else None."""
    from hashlib import sha256
    answer = _answer(payload, text)
    if answer is None:
        return None
    label = answer.removesuffix(' (Recommended)')
    if label in ('Keep as draft', 'Drop'):
        return None
    return {'Send now': ':send', 'Send with an edit': ':edit'}.get(
        label, ':text:' + sha256(answer.encode()).hexdigest())


def _answer(payload, text):
    """The owner's answer to the question text, stripped, or None."""
    response = payload.get('tool_response')
    answers = response.get('answers') if isinstance(response, dict) else None
    answer = answers.get(text) if isinstance(answers, dict) else None
    return answer.strip() if isinstance(answer, str) and answer.strip() else None


def record_gate(payload):
    """PostToolUse: record the owner's reply to an Owner step card from any main session (#831),
    and on the planner's session row which D-n records (by header `D-n` citing today's
    record, #354) and pending drafts (#493) it asked; the record commands read them."""
    from wuwei.decision import DECISION_ID, today_path
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
        from wuwei.sessions import OWNER_STEP, owner_topic
        session = payload.get('session_id')
        questions = payload['tool_input']['questions']
        # #831: the owner's reply to an Owner step card, from any main session, before state:
        # the asked topic and the answer bound to the options as asked.
        owner = [question for question in questions if question.get('header') == OWNER_STEP
                 and required_text(question, 'question').startswith(f'{OWNER_STEP}: ')]
        found = set()
        for question in owner:
            if reply := _answer(payload, question['question']):
                found.add(owner_topic(question['question'], (), ''))
                try:
                    found.add(owner_topic(question['question'], question['options'], reply))
                except (KeyError, TypeError):
                    pass  # options not as printed: only the asked topic, which counts as no
        if found:
            state.append_event('gate.asked', {'session_id': session, 'topics': sorted(found)}, root)
        if len(owner) == len(questions):
            return 0, ''
        if not session or session != state.read_state(root).get('planner_session_id'):
            return 0, ''
        topics = set()
        for question in questions:
            header, text = question.get('header'), required_text(question, 'question')
            if (isinstance(header, str) and re.fullmatch(DECISION_ID, header)
                    and re.search(rf'(?<![\w-]){header}(?![\w-])', text) and today_path(header, root).is_file()):
                topics.add(header)
            elif header == 'Draft':
                asked = set(re.findall(DRAFT_ID, text)) & _pending_drafts(root)
                topics.update(asked)  # drop needs only the asked card
                topics.update(f'{draft_id}{suffix}' for draft_id in asked
                              if (suffix := _draft_answer(payload, text)))
        if not topics:
            return 0, ''

        def update(data):
            row = data['sessions'][session]
            row['gate_asked'] = sorted(topics | set(row.get('gate_asked', ())))

        state._write_state(update, root, reserved=False, kind='gate.asked',
                           payload={'session_id': session, 'topics': sorted(topics)})
        return 0, ''
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
        return 2, f'gate record: {exc}'


GUARDS = [Guard('PostToolUse', 'AskUserQuestion', record_gate)]
