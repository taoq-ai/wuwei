"""Scoped decision write lint and grounded owner questions."""

from pathlib import Path
import re

from wuwei import workspace
from wuwei.decision import lint_file, record_rejection, today_path
from wuwei.guards import Guard
from wuwei.guards.verdict import INTERPRETERS, required_text
from wuwei.workspace import scope
from wuwei.shell import ParseError, is_opaque, mentions, normalize


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
            raise ValueError('missing or invalid tool_input')
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
                results.append((2, 'decision lint: opaque command; use a plain file write'))
            for path in sorted((workspace.day_dir(root) / 'decisions').glob('D-*.md')):
                if scope(path.resolve()) is not None:
                    results.append(lint_file(path, root=root, record=path.resolve() in named))
        return (max((code for code, _ in results), default=0),
                '\n'.join(message for code, message in results if code))
    except (OSError, ValueError, RuntimeError, TypeError) as exc:
        message = f'decision lint: {exc}'
        return (record_rejection(path, 2, message, root=root)
                if root and payload.get('tool_name') != 'Bash' else (2, message))


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
            raise ValueError('missing or invalid tool_input')
        questions = tool_input.get('questions')
        if payload.get('tool_name') != 'AskUserQuestion' and questions is None:
            questions = [tool_input]
        if not isinstance(questions, list) or not questions:
            raise ValueError('expected nonempty questions')
        results = []
        checked = set()
        for question in questions:
            if not isinstance(question, dict):
                raise ValueError('invalid question')
            text = required_text(question, 'question')
            header = question.get('header', '')
            morning = text.startswith('Morning gate') or (
                isinstance(header, str) and header.startswith('Morning gate'))
            plan = workspace.day_dir(root) / 'plan.md'
            citations = (str(plan), plan.relative_to(root).as_posix(),
                         plan.relative_to(root / '.wuwei').as_posix())
            if (morning and plan.is_file() and plan.resolve() == plan
                    and any(re.search(r'(?<![\w./-])' + re.escape(citation) + r'(?![\w./-])', text)
                            for citation in citations)):
                continue
            ids = re.findall(r'(?<![\w-])[DC]-[1-9][0-9]*(?![\w-])', text)
            if not ids:
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
        return 2, f'decision question: {exc}\n{hint}'


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
          Guard('SubagentStop', None, check_stop)]
