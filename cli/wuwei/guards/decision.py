"""Scoped decision write lint and grounded owner questions."""

from pathlib import Path
import re

from wuwei import workspace
from wuwei.decision import DECISION_ID, lint_file, record_rejection, today_path
from wuwei.guards import Guard
from wuwei.guards.verdict import INTERPRETERS, required_text
from wuwei.workspace import scope
from wuwei.shell import UNPARSED, ParseError, classify, is_opaque, mentions, normalize
from wuwei.exits import DAMAGED, PAYLOAD


def is_decision(path):
    return any(p.parent.name == 'decisions' and re.fullmatch(r'D-.*\.md', p.name)
               for p in (path, path.resolve()))


def opaque(argv):
    if is_opaque(argv):
        return True
    if not argv:
        return False
    program = Path(argv[0]).name
    for pattern, flags in INTERPRETERS:
        if re.fullmatch(pattern, program):
            return any(re.match(r'-[a-zA-Z]*[' + flags + r']', arg) or
                       arg == '--eval' or arg.startswith('--eval=') for arg in argv[1:])
    return False


def check_write(payload):
    root, path = None, '<decision write>'
    try:
        cwd = Path(required_text(payload, 'cwd')).resolve()
        tool_input = payload.get('tool_input')
        if not isinstance(tool_input, dict):
            if scope(cwd) is None:
                return 0, ''
            raise ValueError(f'missing or invalid tool_input; {PAYLOAD}')
        if payload.get('tool_name') != 'Bash':
            key = 'notebook_path' if payload.get('tool_name') == 'NotebookEdit' else 'file_path'
            path = cwd / required_text(tool_input, key)
            if not is_decision(path):
                return 0, ''
            context = scope(path.resolve())
            root = context[0] if context else None
            return (0, '') if root is None else lint_file(path, root=root)
        raw = required_text(tool_input, 'command', blank=True)
        if not mentions(raw, {'D-'}):
            return 0, ''
        context = scope(cwd)
        root = context[0] if context else None
        try:
            commands = normalize(raw)
        except ParseError:
            if root is None:
                try:
                    anchor = workspace.find_workspace(cwd)
                except FileNotFoundError:
                    return 0, ''
                # Raw membership hints only, never a second shell parser.
                targets = [anchor, *[(anchor / Path(repo['path']).expanduser()).resolve()
                           for repo in workspace.load_config(anchor)['repos']]]
                if not any(str(target) + '/' in raw for target in targets):
                    return 0, ''
                root = anchor
            shape = classify(raw, cwd=cwd)
            if shape.readonly:
                return 0, ''
            # #347: inline code is a file the lint cannot read; a write names its D- record.
            if shape.inline or 'D-' not in shape.written:
                return 2, UNPARSED
            raise ValueError('could not inspect decision record; use a plain file write')
        roots = {root} if root else set()
        named = set()
        # Named targets identify rejections; the day scan only supplies feedback.
        for command in commands:
            for value in (*command.argv[1:], *command.writes):
                if value.startswith(('of=', '--')) and '=' in value:
                    value = value.split('=', 1)[1]
                if 'D-' in value or command.argv[:1] in (['cd'], ['pushd']):
                    target = (cwd / value).resolve()
                    named.add(target)
                    context = scope(target)
                    if context:
                        roots.add(context[0])
        if not roots:
            return 0, ''
        results = []
        for root in sorted(roots):
            if any(opaque(command.argv) for command in commands):
                results.append((2, UNPARSED))
            for path in sorted((workspace.day_dir(root) / 'decisions').glob('D-*.md')):
                if scope(path.resolve()) is not None:
                    results.append(lint_file(path, root=root, record=path.resolve() in named))
        return (max((code for code, _ in results), default=0),
                '\n'.join(message for code, message in results if code))
    except (OSError, ValueError, RuntimeError, TypeError) as exc:
        message = f'decision lint: {exc}'
        return (record_rejection(path, 2, message, root=root)
                if root and payload.get('tool_name') != 'Bash' else (2, message))


def _morning(question, text):
    header = question.get('header', '')
    return text.startswith('Morning gate') or (isinstance(header, str) and header.startswith('Morning gate'))


def gate_question(question, root):
    """The question is marked Morning gate and cites today's plan file."""
    text = required_text(question, 'question')
    morning = _morning(question, text)
    plan = workspace.day_dir(root) / 'plan.md'
    citations = (str(plan), plan.relative_to(root).as_posix(),
                 plan.relative_to(root / '.wuwei').as_posix())
    return bool(morning and plan.is_file() and plan.resolve() == plan
                and any(re.search(r'(?<![\w./-])' + re.escape(citation) + r'(?![\w./-])', text)
                        for citation in citations))


TOPICS = {'goals', 'voice'}
DRAFT_ID = r'(?<![\w-])draft-[0-9a-f]{32}(?![\w-])'


def _pending_drafts(root):
    """Ids of today's pending drafts (#493): a card may cite only those."""
    from wuwei import drafts, state
    return {key for key, row in drafts.read(state.read_state(root)).items() if row['status'] == 'pending'}


def _draft_answer(payload, text):
    """The owner's answer to a Draft card as a topic suffix (#493): ':send' for Send now,
    ':edit' for Send with an edit, ':text:<sha256>' for text the owner typed, else None."""
    from hashlib import sha256
    response = payload.get('tool_response')
    answers = response.get('answers') if isinstance(response, dict) else None
    answer = answers.get(text) if isinstance(answers, dict) else None
    if not isinstance(answer, str) or not answer.strip():
        return None
    label = answer.strip().removesuffix(' (Recommended)')
    if label in ('Keep as draft', 'Drop'):
        return None
    return {'Send now': ':send', 'Send with an edit': ':edit'}.get(
        label, ':text:' + sha256(answer.strip().encode()).hexdigest())


def record_gate(payload):
    """PostToolUse: note on the planner's session row which records (goals, voice) its
    answered morning gate questions asked, by header `Goals` or `Voice` only, and which
    decisions it asked, by header `D-n` citing today's record (#354); protect_state lets the
    planner record them."""
    try:
        context = scope(Path(required_text(payload, 'cwd')).resolve())
        if context is None or 'agent_id' in payload:
            return 0, ''
        root, _ = context
        from wuwei import state
        session = payload.get('session_id')
        if not session or session != state.read_state(root).get('planner_session_id'):
            return 0, ''
        topics = set()
        for question in payload['tool_input']['questions']:
            header = question.get('header')
            topic = header.strip().lower() if isinstance(header, str) else None
            if gate_question(question, root) and topic in TOPICS:
                topics.add(topic)
            elif (isinstance(header, str) and re.fullmatch(DECISION_ID, header)
                  and re.search(rf'(?<![\w-]){header}(?![\w-])', required_text(question, 'question'))
                  and today_path(header, root).is_file()):
                topics.add(header)
            elif header == 'Draft':
                text = required_text(question, 'question')
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


def check_question(payload):
    """Shared citation check for AskUserQuestion and future control-plane escalation."""
    hint = ('Cite a decision D-n or clarification C-n whose record exists today and passes lint, '
            'or mark Morning gate and cite today\'s plan file.')
    try:
        context = scope(Path(required_text(payload, 'cwd')).resolve())
        if context is None:
            return 0, ''
        root, _ = context
        tool_input = payload.get('tool_input')
        if not isinstance(tool_input, dict):
            raise ValueError(f'missing or invalid tool_input; {PAYLOAD}')
        questions = tool_input.get('questions')
        if payload.get('tool_name') != 'AskUserQuestion' and questions is None:
            questions = [tool_input]
        if not isinstance(questions, list) or not questions:
            raise ValueError(f'expected nonempty questions; {DAMAGED}')
        results = []
        checked = set()
        for question in questions:
            if not isinstance(question, dict):
                raise ValueError(f'invalid question; {DAMAGED}')
            text = required_text(question, 'question')
            if gate_question(question, root):
                continue
            ids = re.findall(r'(?<![\w-])[DC]-[1-9][0-9]*(?![\w-])', text)
            cited = [] if ids else re.findall(DRAFT_ID, text)
            if cited:
                if missing := sorted(set(cited) - _pending_drafts(root)):
                    results.append((1, f"draft {', '.join(missing)} not pending today; "
                                       'bin/wuwei drafts lists the queue'))
            elif not ids and _morning(question, text):
                plan = workspace.day_dir(root) / 'plan.md'
                results.append((1, f"Morning gate questions cite {plan.relative_to(root / '.wuwei').as_posix()}"
                                + ('' if plan.is_file() else '; run bin/wuwei plan propose <lead.json> first')))
            elif not ids:
                results.append((1, hint))
            for decision_id in ids:
                if decision_id not in checked:
                    checked.add(decision_id)
                    clarification = decision_id.startswith('C-')
                    path = today_path(decision_id, root, clarification=clarification)
                    code, message = lint_file(path, root=root, record=False, clarification=clarification)
                    if code:
                        results.append((code, f'decision {decision_id}: {message}\n{hint}'))
        return (max((code for code, _ in results), default=0),
                '\n'.join(message for _, message in results))
    except (OSError, ValueError, RuntimeError, TypeError) as exc:
        return 2, f'decision question: {exc}\n{hint}; fix the record, then check it with bin/wuwei decision lint <file>'


# ponytail: a line ending in '?' is a question; tighten if retro gaps show false positives.
QUESTION = re.compile(r'\?\s*$', re.M)


def unrecorded(text, root):
    """A seat's final text asking the owner something must cite a valid record."""
    from wuwei.verdict import active_text
    if not QUESTION.search(active_text(text)):
        return 0, ''
    return check_question({'cwd': str(root), 'tool_name': 'SubagentStop',
                           'tool_input': {'question': text}})


def check_stop(payload):
    """SubagentStop: flag a WUWEI seat that stops on an unrecorded owner question."""
    from wuwei.guards.agent_launch import stopping_seat, wuwei_role
    if payload.get('stop_hook_active') is True or not wuwei_role(payload.get('agent_type')):
        return 0, ''
    try:
        root = workspace.guard_scope(payload)
        if root is None:
            return 0, ''
        code, message = unrecorded(required_text(payload, 'last_assistant_message', blank=True), root)
        if code != 1:
            return code, message
        from wuwei import brief, state, steward
        try:
            directory, name, role = stopping_seat(payload, root)
            item = brief.seats(state.read_state(directory=directory))[name]['item']
        except (OSError, ValueError, KeyError, TypeError):
            return code, message  # No seat binding: flagged, but no item to note.
        agent = re.sub(r'[^A-Za-z0-9_.-]', '-', str(payload.get('agent_id', '')))
        note_id = f'{item}-question-{agent}'
        if steward.SAFE_ID.fullmatch(item) and steward.SAFE_ID.fullmatch(note_id):
            steward.add_notes(root, [{'id': note_id, 'item': item, 'text': (
                f'{item}: a {role} seat asked the owner a question without a decision record; '
                'write it (wuwei decision template), route it and cite D-n, or record the '
                'assumption under Assumptions:')}])
        return code, message
    except (OSError, ValueError, RuntimeError, TypeError) as exc:
        return 2, f'decision question: {exc}'


GUARDS = [Guard('PostToolUse', 'Write|Edit|MultiEdit|NotebookEdit|Bash', check_write),
          Guard('PreToolUse', 'AskUserQuestion', check_question),
          Guard('PostToolUse', 'AskUserQuestion', record_gate),
          Guard('SubagentStop', None, check_stop)]
