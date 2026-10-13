"""Brief evidence and ordered source refusals shared with launch checks."""

import json
from pathlib import Path
import re
import shlex

from wuwei import registry, security, sessions, state, workspace
from wuwei.exits import ADAPTER_DATA, DAMAGED, PAYLOAD, SYMLINK


REFERENCE_PREFIX = 'WUWEI brief: '


def launch_prompt(brief_path, charter, *, root=None):
    """Format every Claude seat's instructions with a workspace-relative reference."""
    root = workspace.find_workspace(root)
    relative = Path(brief_path).resolve(strict=True).relative_to(root)
    header = Path(brief_path).read_text(encoding='utf-8').split('\n\n', 1)[0]
    found = re.search(r'^Depth: .+$', header, re.M)  # #567: the seat never decides its depth
    return (f'{REFERENCE_PREFIX}{relative}\nRead instructions {charter} and brief {relative}.'
            + '\n\n' + mandate(root) + ('\n' + found[0] if found else ''))


LIGHT_GATE = ('Depth: light; skip: gate step zero, the Probe or Mutation row, the class-sweep line, '
              'the Simplicity and Design rows, the retro note when every line would be none; '
              'verdict: Verdict:, Head:, findings')
# #667: the values the day changes under a seat are read live, never copied into the brief.
LIVE = ('Live: run bin/wuwei why {item} --json when you start and again before your verdict or handoff; '
        'its ticket and spec fields are the record at that moment. This brief copies none of them.')
# #645: one doctor for every seat; install findings belong to the owner. #907: a diagnosis after an
# actual failure, never a start step (doctor reads every adapter; a refusal already names its fix).
DOCTOR = ('Doctor: only when a WUWEI command fails and its refusal names no fix, run the launcher in '
          '.wuwei/executable with doctor once; another copy hands over to it. Its Install rows and its '
          "workspace executable row are the owner's: name them in your handoff, never as a Next: step, "
          'and never run their fix.')


def depth_line(role, value, worktree, paths=(), trust_paths=(), flags=None):
    """#567: the brief's Depth: line (design 5.3, process depth follows the tier)."""
    from wuwei import dispatch
    if role == 'builder':
        sweep = 'wuwei build classes ' + shlex.quote(worktree)
        if value == 'light':
            return (f'Depth: light; skip: the class sweep while {sweep} prints Depth: light, '
                    'and the retro note when every line would be none')
        return f'Depth: {value}; before handoff run {sweep} and report one CLASS line per class it lists'
    zero = dispatch.step_zero(value, paths, trust_paths, flags)
    if zero is None:
        return LIGHT_GATE
    run, reason = zero
    if not run:
        return f'Depth: {value}; step zero: skip ({reason}); write Mutation: skipped (depth {value})'
    return f'Depth: {value}; step zero: run' + (f' ({reason})' if reason else '')


# #733: the conclusions pr_actions._fix reports as red (everything but success, neutral, skipped)
RED = ('failure', 'error', 'cancelled', 'timed_out', 'action_required', 'stale', 'startup_failure')


def ci_jobs(text, tree):
    """#733: sorted '<workflow path>#<job id>' of each worktree workflow job the text names:
    'job <name>', '<name> job', or the fix-feedback line '<name>[ (<matrix>)]: <red conclusion>',
    <name> being the job id or its name:."""
    from wuwei import calibrate
    found = set()
    for _, relative, flow in calibrate._workflows(Path(tree), []):
        for job in flow['jobs']:
            for name in {job['id'], job['name'][0]}:
                name, quote = re.escape(name), '[`\'"]?'
                if (re.search(rf'(?<![\w-])job[ \t]+{quote}{name}{quote}(?![\w-])', text, re.I)
                        or re.search(rf'(?<![\w-]){quote}{name}{quote}[ \t]+job\b', text, re.I)
                        or re.search(rf'^[ \t]*{name}(?: \([^)\n]*\))?:[ \t]*(?:{"|".join(RED)})\b', text, re.M)):
                    found.add(f"{relative}#{job['id']}")
    return sorted(found)


def ci_steps(refs, tree):
    """#733: (steps, missing) for recorded refs. steps: one dict per run step in ref order and
    file order, numbered from 1: {'n', 'label', 'source', 'run'}. missing: refs whose job is
    not in the worktree at this head. Raises ValueError when a recorded workflow is unreadable."""
    from wuwei import calibrate
    tree, found, jobs = Path(tree), [], {}
    if refs and (tree / '.github/workflows').is_symlink():
        raise ValueError('CI workflow directory .github/workflows is a symlink; fix it, then retry')
    for _, relative, flow in calibrate._workflows(tree, found):
        jobs.update({f"{relative}#{job['id']}": (relative, job) for job in flow['jobs']})
    files = {ref.rpartition('#')[0] for ref in refs}
    for row in found:
        path = row['source'].rpartition(':')[0]
        if row['kind'] == 'skipped' and path in files:
            raise ValueError(f"CI workflow {path} unreadable ({row['value']}); fix the file, then retry")
    steps, missing = [], [ref for ref in refs if ref not in jobs]
    for ref in refs:
        relative, job = jobs.get(ref, (None, {'steps': []}))
        for step in job['steps']:
            if step['run']:
                steps.append({'n': len(steps) + 1, 'label': f"{job['id']} / {step['name'] or 'unnamed'}",
                              'source': f"{relative}:{step['line']}", 'run': step['run']})
    return steps, missing


def ci_block(refs, tree):
    """#733: the step block for recorded refs, ending in a newline; '' when there are none."""
    if not refs:
        return ''
    steps, missing = ci_steps(refs, tree)
    named = ', '.join('{1} ({0})'.format(*ref.rpartition('#')[::2])
                      for ref in [r for r in refs if r not in missing] or refs)
    lines = [f'CI steps: this item fixes CI job {named}. Run every step below locally from the worktree '
             'root, not only the one that was red, and cite each as one row in your verdict or handoff: '
             'CI step <n>: PASS|FAIL|NOT RUN <what ran and what it showed>.']
    for step in steps:
        lines.append(f"CI step {step['n']}: {step['label']} ({step['source']})")
        lines += ['    ' + line for line in step['run'].splitlines()]
    lines += [f'CI job {ref}: not in the workflow file at this head' for ref in missing]
    return '\n'.join(lines) + '\n'


def mandate(root):
    """Design 5.2: what a seat decides alone, records, or names for the owner."""
    config = workspace.load_config(root)
    owner = ("Name a one-way, scope, goal or trust-boundary question in your result (a sentinel's "
             "ESCALATE, a builder's Blocked: line); wuwei next asks the owner.")
    if config['deploy']['deny']:
        owner += f' Commands the owner runs: {", ".join(config["deploy"]["deny"])}.'
    return '\n'.join(['Mandate (design 5.2):',
                      'Decide alone: what the brief, your charter and the engineering standards '
                      'already answer.',
                      'Record two-way choices under Assumptions: in the spec or PR body (what was '
                      'assumed, why, what would overturn it).', owner])


def seat_action(role, brief_path, worktree, root, runtime=None):
    """The launch action every Claude seat caller hands to the planner; `runtime` (#845) is a
    routed builder's, else the role's policy runtime."""
    config = workspace.load_config(root)
    return {'action': 'launch', 'brief': str(brief_path), 'worktree': str(worktree),
            'runtime': runtime or registry.runtime_config(role, config, root)['adapters']['runtime'],
            'agent_type': 'wuwei:' + role,
            'prompt': launch_prompt(brief_path, security.agent_path(root, role), root=root)}


def events(root):
    """Today's event rows, refused when any row is malformed."""
    rows = [json.loads(line) for line in (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines()]
    if any(not isinstance(row, dict) or not isinstance(row.get('payload'), dict)
           or not isinstance(row.get('kind'), str) for row in rows):
        raise ValueError(f'invalid build event record; {DAMAGED}')
    return rows


class Refused(ValueError):
    """A measured policy finding, exit 1."""


def read(call, *args, root):
    result = call(*args, root=root)
    if type(result.exit) is not int or result.exit not in (0, 1, 2):
        raise ValueError(f'invalid adapter result; {ADAPTER_DATA}')
    if result.exit:
        raise ValueError(result.reason or 'adapter read unavailable; retry; if it repeats, run bin/wuwei doctor, which tests the adapters')
    return result.data


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value):
        raise ValueError('invalid brief role, item or name; pass a known role, an item from today\'s plan and a safe seat name')
    return value


def read_day(root):
    directory = workspace.day_dir(root)
    if not state.day_started(directory):
        raise ValueError('no state.json for this day; run the morning plan (/wuwei:wuwei-plan) first')
    return directory, state.read_state(root)


def _user_messages(path):
    """The text of each user row of a transcript, in order."""
    with Path(path).open(encoding='utf-8') as transcript:
        for line in transcript:
            row = json.loads(line)
            if row.get('type') != 'user':
                continue
            content = row['message']['content']
            if isinstance(content, list):
                content = '\n'.join(part['text'] for part in content if part.get('type') == 'text')
            yield content


def reference(text):
    """#660: the brief path of the first line of text that starts with the marker, else None."""
    return next((line[len(REFERENCE_PREFIX):] for line in text.splitlines()
                 if line.startswith(REFERENCE_PREFIX)), None)


def transcript_reference(path):
    """Bind from the launch prompt; later continue messages cannot change seats."""
    prompt = first_prompt(path)
    return reference(prompt) if prompt is not None else None


def subagent_transcript(payload):
    """The subagent transcript of a hook call with agent_id (#473), else None."""
    agent_id = payload.get('agent_id')
    if agent_id is None:
        return None
    if not isinstance(agent_id, str) or not agent_id.strip():
        raise ValueError(f'invalid agent_id; {PAYLOAD}')
    if not payload.get('transcript_path'):
        return None
    return Path(payload['transcript_path']).parent / payload['session_id'] / 'subagents' / f'agent-{agent_id}.jsonl'


def seat_of(payload, data):
    """#647: the seat whose brief the calling subagent's transcript names, else None."""
    path = subagent_transcript(payload)
    if path is None:
        return None
    try:
        reference = transcript_reference(path)
        if reference is None:
            prompt = first_prompt(path)
            name = adhoc_seat(data, prompt_digest(prompt),
                              f"{payload.get('session_id', '')}:{payload['agent_id']}",
                              role=payload.get('agent_type', '').rsplit(':', 1)[-1]) if prompt else None
            return seats(data).get(name)
    except OSError:
        return None
    return next((seat for seat in seats(data).values() if seat.get('brief') == reference), None)


def first_prompt(path):
    """#676: the first user message of a transcript: a subagent's launch prompt, or None."""
    return next(_user_messages(path), None)


def prompt_digest(text):
    """#676: the key an adhoc seat is matched by: sha256 of the stripped prompt."""
    import hashlib
    return hashlib.sha256(text.strip().encode()).hexdigest()


def adhoc_seat(data, digest, session, *, role=None):
    """A prompt-bound seat: its bound session, else the oldest unbound running match.
    #955: role is part of identity; a bound seat remains identifiable after stopping."""
    parent, _, agent = session.rpartition(':')
    matches = [(name, seat) for name, seat in seats(data).items()
               if seat.get('prompt_sha256') == digest
               and (not role or seat['role'] in ('adhoc', role))]
    bound = next((name for name, seat in matches
                  if session in seat.get('trace_sessions', ())
                  or agent and seat.get('agent_id') == agent and seat.get('launcher_session_id') == parent), None)
    # ponytail: identical prompts in one role/session use launch order until a trace binds them.
    return bound or next((name for name, seat in matches if seat['status'] == 'running'
                          and not seat.get('trace_sessions') and not seat.get('agent_id')
                          and seat.get('launcher_session_id', parent) == parent), None)


HANDBACK = 'SubagentHandback'  # the harness's structured hand-back tool (#473)


def _entry(line):
    """(text, handback message or None) of an assistant transcript line, else None."""
    if not line.strip():
        return None
    row = json.loads(line)
    if not isinstance(row, dict) or row.get('type') != 'assistant':
        return None
    try:
        content = row['message']['content']
        if isinstance(content, str):
            return content, None
        text = '\n'.join(part['text'] for part in content if part.get('type') == 'text')
        return text, next((part['input'].get('message') for part in content
                           if part.get('type') == 'tool_use' and part.get('name') == HANDBACK), None)
    except (KeyError, TypeError, AttributeError):
        raise ValueError(f'malformed transcript entry; {PAYLOAD}') from None


def last_turn(path):
    """(completion, text, handback) of a transcript's last assistant entry. completion is
    [line index, sha256 of the line], the builder binding; text joins the text blocks, or is
    a SubagentHandback's input.message (a background seat's report, #473); handback says
    which. Read from the end, so a torn last line raises ValueError."""
    import hashlib
    lines = Path(path).read_text(encoding='utf-8').splitlines()
    for index in range(len(lines) - 1, -1, -1):
        entry = _entry(lines[index])
        if entry is None:
            continue
        text, handback = entry
        completion = [index, hashlib.sha256(lines[index].encode()).hexdigest()]
        if isinstance(handback, str):
            return completion, handback, True
        return completion, text, False
    raise ValueError(f'transcript has no assistant turn; {PAYLOAD}')


def tail_turn(path):
    """(text, completed handback) of the last assistant entry, read from the end (#516).
    ponytail: an assistant entry far back still reads most of the file; fine for transcripts."""
    with open(path, 'rb') as stream:
        size = stream.seek(0, 2)
        window = 64 * 1024
        while True:
            start = max(0, size - window)
            stream.seek(start)
            lines = stream.read(size - start).split(b'\n')
            if start:
                lines = lines[1:]  # a partial line; the next window reads it whole
            ended = set()
            resumed = False
            for line in reversed(lines):
                row = json.loads(line) if line.strip() else {}
                if not isinstance(row, dict):
                    continue
                message = row.get('message')
                content = message.get('content', []) if isinstance(message, dict) else []
                if row.get('type') == 'user' and (not isinstance(content, list) or any(
                        not isinstance(part, dict) or part.get('type') != 'tool_result' for part in content)):
                    resumed = True
                if not resumed and isinstance(content, list) and row.get('toolEndsTurn') is True:
                    ended.update(part.get('tool_use_id') for part in content
                                 if isinstance(part, dict) and part.get('type') == 'tool_result'
                                 and not part.get('is_error'))
                entry = _entry(line.decode('utf-8'))
                if entry is not None:
                    text, handback = entry
                    if isinstance(handback, str):
                        completed = any(part.get('id') in ended for part in row['message']['content']
                                        if part.get('type') == 'tool_use' and part.get('name') == HANDBACK)
                        return handback, completed
                    return text, False
            if not start:
                raise ValueError(f'transcript has no assistant turn; {PAYLOAD}')
            window *= 4


def stop_text(payload):
    """A seat's final report: a non-blank last_assistant_message, else the last assistant
    turn of agent_transcript_path (#473). OSError or ValueError when neither reads."""
    text = payload.get('last_assistant_message')
    if isinstance(text, str) and text.strip():
        return text
    path = payload.get('agent_transcript_path')
    if not isinstance(path, str) or not path.strip():
        raise ValueError(f'missing or invalid agent_transcript_path; {PAYLOAD}')
    text = tail_turn(path)[0]
    if not text.strip():
        raise ValueError(f'transcript last assistant turn has no report; {PAYLOAD}')
    return text


def keep_report(root, directory, name, text):
    """#905: keep a seat's report its stop could not record, for wuwei seat stop --verdict:
    {report: path relative to the workspace, report_sha256: digest of the kept text}."""
    import hashlib
    path = Path(directory) / 'reports' / f'{identifier(name)}.md'
    path.parent.mkdir(exist_ok=True)
    if path.parent.is_symlink():
        raise ValueError(f'{path.parent} is a symlink; {SYMLINK}')
    workspace.atomic_write(path, text)
    return {'report': path.relative_to(root).as_posix(),
            'report_sha256': hashlib.sha256(text.encode()).hexdigest()}


def recovery(name, seat):
    """Record the terminal report of a stuck seat."""
    return f'wuwei seat stop {name} --verdict'


def stuck(data):
    """Seats that need bin/wuwei seat stop (#473), sorted: running with a recorded transcript
    whose hand-back has a successful terminal tool result. An unmeasured stop alone
    is not completion evidence: the hook may have blocked and the task continued."""
    found = []
    for name, seat in seats(data).items():
        if (seat['status'] in ('running', 'unmeasured') and seat.get('by') != 'owner'
                and isinstance(seat.get('transcript'), str)):
            try:
                if tail_turn(seat['transcript'])[1]:
                    found.append(name)
            except (OSError, ValueError):
                pass  # ponytail: an unreadable transcript is no evidence of an end; the reservation timeout still reports the seat
    return sorted(found)


def live(data):
    """#898: the seats that hold a slot: running, registered on a brief (not adhoc) and not
    handed back (stuck)."""
    done = set(stuck(data))
    return [seat for name, seat in seats(data).items()
            if seat['status'] == 'running' and seat['role'] != 'adhoc' and name not in done]


def seats(data):
    records = data.get('seats')
    if not isinstance(records, dict):
        raise ValueError(f'seats must be an object; {DAMAGED}')
    for seat in records.values():
        if (not isinstance(seat, dict) or seat.get('status') not in (*state.STATUSES, 'stopped', 'unmeasured')
                or not isinstance(seat.get('role'), str) or not seat['role']
                or not isinstance(seat.get('item'), str) or not seat['item']):
            raise ValueError(f'invalid seat record; {DAMAGED}')
    return records


def gate_ready(data, item, head=None):
    """head (#901 review): the worktree HEAD the gate would read; it must be the head the item's
    fast checks passed on."""
    if item not in data['items']:
        raise ValueError(f'unknown gate item: {item}')
    checked = (data.get('builds', {}).get(item) or {}).get('checked')
    if head and checked and head != checked:
        raise Refused(f'{item} HEAD {head[:12]} is not the head its fast checks passed on ({checked[:12]}); '
                      f'run bin/wuwei dispatch next {item}, which sends it back to its fast checks')
    phase = data['items'][item]['phase']
    if phase not in ('gate', 'delta', 'raised', 'merged'):
        raise Refused(f"gate brief while item phase is '{phase}'; finish the build loop first (wuwei build next {item} returns done)")
    for seat in seats(data).values():
        if seat['item'] == item and seat['role'] == 'builder' and seat['status'] == 'running':
            raise Refused('gate refused: builder is live; wait for its SubagentStop before the gate brief')


def status(vcs, tree, root):
    changes = read(vcs.status, tree, root=root)
    if not isinstance(changes, list) or any(
            not isinstance(row, dict) or not isinstance(row.get('path'), str)
            or not row['path'] for row in changes):
        raise ValueError(f'invalid worktree status; {DAMAGED}')
    return changes


def rulings(body, directory, tree, data):
    ids = sorted(set(re.findall(r'(?<![A-Za-z0-9/_-])D-[A-Z0-9]+(?:-[A-Za-z0-9]+)+', body)))
    ids = [key for key in ids if not key.endswith('-N')]
    if not ids:
        return []
    paths = sorted((directory / 'decisions').glob('*.md'))
    paths += sorted(p for p in directory.parent.glob('*/decisions/*.md') if p not in paths)
    if tree:
        paths += sorted((tree / 'specs').rglob('*.md'))
    lines = [(str(path), number, line) for path in paths if not path.name.startswith('gate-')
             for number, line in enumerate(path.read_text().splitlines(), 1)]
    lines += [('state.json:gate_policy', 1, json.dumps(data.get('gate_policy', '')))]
    result, missing = [], []
    for key in ids:
        exact = re.compile(r'(?<![\w-])' + re.escape(key) + r'(?![\w-])')
        hits = [row for row in lines if exact.search(row[2])]
        prefix, _, number = key.rpartition('-')
        if not hits and number.isdigit():
            ranges = re.compile(re.escape(prefix) + r'-(\d+)\.\.(?:' + re.escape(prefix) + r'-)?(\d+)')
            hits = [row for row in lines if any(int(a) <= int(number) <= int(b)
                    for a, b in ranges.findall(row[2]))]
        if not hits:
            missing.append(key)
            continue
        _, _, text = hits[0]
        # ponytail: preserve source keyword status until rulings have a structured schema.
        label = 'OPEN' if re.search('pending|open|recommend', text, re.I) and not re.search(
            'ruled|accept', text, re.I) else 'RULED'
        result.append(f'Ruling {key} [{label}] {text}')
    if missing:
        raise Refused(('ruling id(s) ' + ' '.join(missing) + ' resolve in no decisions, specs or gate_policy'
                     + "; correct the ids, or write the ruling into the item's spec first"))
    return result


def candidates(root):
    """The discovered candidates and every source not measured, one line each."""
    from wuwei import discovery
    try:
        found = discovery.discover(root)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        return f'\nCandidates: unmeasured: {exc}\n'
    lines = [f'Source {name}: {value if isinstance(value, str) else f"measured, {len(value)} rows"}'
             for name, value in sorted(found['sources'].items())]
    lines += ['Candidate: ' + json.dumps(row, sort_keys=True) for row in found['candidates']]
    return '\n' + '\n'.join(lines) + '\n'


def worktree_repo(root, config, tree):
    """The repository whose default branch supplies brief path evidence."""
    repo = next((r for r in config['repos'] if (root / r['path']).resolve() == tree), None)
    if repo is None and config['repos']:
        from wuwei.commit_push import context
        repo = context(tree, {}, {}, root, identity=False)[0]
    return repo or {}


def check_paths(body, paths, config, track):
    """The protected-path boundary for file briefs and ad-hoc launch prompts."""
    for line in body.splitlines():
        if line.startswith('Paths:'):
            paths.extend(re.split(r'[,\s]+', line[6:].strip()))
    patterns = [re.compile(p, re.I) for p in config['brief']['full_path_patterns']]
    protected = [path for path in paths if any(p.search(path) for p in patterns)]
    if track == 'SLICE' and protected:
        raise Refused('SLICE brief touches protected paths: ' + ', '.join(protected) + '; use --track FULL')


def write(role, item, name, body, *, worktree=None, pr=None, gate=False, track=None, second_opinion=None,
          root=None):
    root = workspace.find_workspace(root)
    directory, data = read_day(root)
    for value in (role, item, name):
        identifier(value)
    config = workspace.load_config(root)
    gate = gate or role.startswith('sentinel-')
    output = directory / 'briefs' / (name + '.md')
    output.parent.mkdir(exist_ok=True)
    if output.parent.resolve() != output.parent:
        raise ValueError(f'brief directory must not be a symlink; {SYMLINK}')
    lead = candidates(root) if role == 'lead' else ''  # S5: the scanner audit runs outside brief.lock
    # ponytail: serialize brief publication for this day.
    with (directory / 'brief.lock').open('a') as lock:
        state.lock_ex(lock, 'brief.lock')
        if output.exists() or output.is_symlink():
            raise Refused('brief exists (one brief per name); use a new seat name for a new brief')
        _, data = read_day(root)
        if gate and re.search(r'return (the verdict )?inline|verdict inline|no verdict file|retro( note)? inline', body, re.I):
            raise Refused('gate verdict goes in its verdict file, never inline; remove the return-inline wording; wuwei adds the verdict file line itself')
        if gate and 'decisions/gate-' in body:
            raise Refused('body restates a verdict path; remove the decisions/gate-... path from the body; wuwei adds the verdict file line itself')
        current = data['items'].get(item, {})
        track = track or current.get('track', 'SLICE')
        if track not in ('SLICE', 'FULL'):
            raise Refused('track must be SLICE or FULL; use SLICE or FULL')
        tree_arg = worktree or current.get('worktree')
        tree = (root / tree_arg).resolve() if tree_arg else None
        if gate and tree is None:
            raise ValueError('gate requires a worktree; pass --worktree <path>, or create one with bin/wuwei worktree add <item>')
        vcs = registry.load('vcs', config) if tree or gate else None
        now = workspace.now().isoformat()
        charter_root = Path(__file__).resolve().parents[2] / 'charters'
        charters = ['_common'] + ([] if role.startswith('sentinel-') else ['_common-authoring']) + [role]
        secured = security.load(root) is not None
        if secured:
            from wuwei.commands.agents import write_workspace
            write_workspace(charter_root.parent, root / '.wuwei')
        header = []
        for charter in charters:
            local = root / '.wuwei/charters' / (charter + '.md')
            path = (root / '.wuwei/generated/charters' / (charter + '.md') if secured
                    else local if local.is_file() else charter_root / (charter + '.md'))
            if not path.is_file():
                raise ValueError(f'unknown charter: {charter}')
            header.append(f'Charter: {path}')
        header += [f'Written: {now}', f'Item: {item}', f'Seat policy: {json.dumps(data["seat_policy"])}']
        scratch = root / workspace.SCRATCH / item / role  # #647: one scratch directory per seat
        if role == 'builder' and current.get('kind') == 'measure':
            header.append(f'Scratch: {scratch}/')
        else:
            header.append(f'Scratch: <your scratchpad>/{item}/{role}/, or {scratch}/ when your host names '
                          'no scratchpad; create it if missing, or move it aside with a timestamp suffix '
                          'when it holds files you did not write, and write every temporary file there, '
                          "never at the scratchpad root or in another item's directory")
        if gate:  # #672: a gate probe never writes in the builder's worktree
            header.append('Probe env: PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX='
                          f'{shlex.quote(str(scratch / "pycache"))}; set it on every command that '
                          'runs code, and run every probe, test and mutant in a copy of the worktree '
                          'under your scratch directory, never in the worktree itself')
        header.append(DOCTOR)
        if second_opinion:
            header.append(f'Model: {second_opinion["model"]}')
        changed = []
        if tree:
            changed = status(vcs, tree, root)
            head = read(vcs.head, tree, root=root)['sha']
            repo = worktree_repo(root, config, tree)
            remote = config['brief']['remote']
            ref = remote + '/' + repo.get('default_branch', 'main')
            try:
                base = read(vcs.merge_base, tree, ref, root=root)['sha']
            except ValueError as exc:
                raise ValueError(f"no merge base with {ref} in {repo.get('name', tree.name)} ({exc}); "
                                 f'run git -C {tree} fetch {remote}, then write the brief again') from None
            prior = read(vcs.branches, tree, config['brief']['prior_branch_pattern'].format(item=item.lower()), root=root)
            header += [f'Worktree: {tree}', f'HEAD: {head}', f'Merge-base: {base} ({ref})',
                       f'Status: {json.dumps(changed)}', f'Prior branches: {json.dumps(prior)}']
            if gate and changed:
                raise Refused(('gate brief on a dirty tree: ' + ', '.join(row['path'] for row in changed)
                              + '; ask the builder to commit or discard them, then write the gate brief again'))
            changed += read(vcs.diff_stat, tree, base, head, root=root)
        else:
            header += ['Worktree: none', 'HEAD: not applicable', 'Merge-base: not applicable',
                       'Status: not applicable', 'Prior branches: not applicable']
        paths = [row['path'] for row in changed]
        paths += [row['original_path'] for row in changed if row.get('original_path')]
        if tree:
            paths.append(tree.name + '/')
        check_paths(body, paths, config, track)
        header.append(f'Track: {track}')
        if role == 'builder':
            from wuwei import specmode
            line = specmode.brief_line(config, item, current, tree, False)
            if line:
                header.append(line)
        # #664: after the body, never in the header: the header is cut at its first blank line.
        block = ''
        if role == 'builder' and tree:
            from wuwei import specmode
            block = specmode.brief_block(config, item, current, tree)
        refs, ci = [], ''
        if (role == 'builder' or gate) and tree:  # #733: the CI job this item fixes, every step
            refs = sorted({*current.get('ci_jobs', ()), *ci_jobs(body + '\n' + (current.get('title') or ''), tree)})
            ci = ci_block(refs, tree)
            ci = '' if ci.rstrip('\n') in body else ci  # a second opinion copies the block
        depth = None
        if role == 'builder' or gate:
            from wuwei import dispatch
            depth = (dispatch.depth(current, gate=True) if gate else dispatch.depth({'gates': dispatch.tier(
                root, config, {'flags': {}, **current, 'worktree': str(tree) if tree else None})}))
            header.append(depth_line(role, depth, str(tree) if tree else '<worktree>',
                                     [row['path'] for row in changed],
                                     (repo or {}).get('gates', {}).get('trust_paths', []) if tree else [],
                                     current.get('flags')))
        if role == 'builder' and tree and repo and current.get('kind') != 'measure':
            from wuwei import fast_checks  # #520: the builder never improvises an interpreter
            for command in repo.get('fast_checks', []):
                found = fast_checks.interpreter(command, tree, repo, root, config)
                if found and found[1] == 'missing':
                    header.append(f'Check interpreter: {command} has no interpreter in the worktree or '
                                  'the main worktree; report it, do not build one')
                elif found:
                    header.append(f'Check interpreter: {command} runs with {found[0]} ({found[1]})')
            if not repo.get('fast_checks'):  # #600: nothing runs locally
                header.append(f'{fast_checks.NONE[0].upper()}{fast_checks.NONE[1:]}. '
                              'Write "checks: none configured" in the PR body.')
        host = registry.load('code_host', config) if pr else None
        pull = read(host.pr, pr, root=root) if pr else None
        if pr and current.get('kind') == 'review':
            if pull.get('head') != head or pull.get('state') != 'open':
                raise Refused(f'review PR {pr} is not open at worktree HEAD {head}; update the worktree and write a new brief')
        header.append('PR head (no-cache): ' + (json.dumps(pull) if pr else 'not applicable'))
        if gate:
            gate_ready(data, item, head)
        row = [value for key, value in data['gate_verdicts'].items()
               if key == item or value.get('item') == item or value.get('pr') in (item, pr) and value.get('pr')]
        header.append(f'Gate row: {json.dumps(row)}')
        if gate:
            verdict = (directory / 'decisions' / ('gate-' + name + '.md')).relative_to(root)
            if second_opinion:  # #871 L1: a sandboxed runtime seat cannot write the day directory
                header.append(f'Verdict file: {verdict} (WUWEI writes your final message there; write no '
                              'file, and put your whole verdict, retro note and any out-of-scope bug '
                              'included, in your final message).')
            else:
                header.append(f'Verdict file: {verdict} (the only file you write; an out-of-scope bug you '
                              'find you file yourself with bin/wuwei tracker create --bug, common rule 7). '
                              'Include the retro note here.')
            header.append("Assumptions: review the item's Assumptions: in its spec and PR body as "
                          'findings of kind Assumption: (severity, file:line, failure scenario, '
                          'blocks yes or no).')
        if role == 'builder' or gate:
            header.append(LIVE.format(item=item))
            if current.get('approved_as'):  # #731: the owner's recorded approval settles the scope question
                header.append(f"Approved as: {current['approved_as']}")
        header += rulings(body, directory, tree, data)
        from wuwei import derive  # #907: a counterpart is optional evidence, read from the day's listing
        found = derive.listing(directory)
        for repo in config['repos']:
            for other in sorted(set(re.findall(re.escape(repo['name']) + r'#[0-9]+', body))):
                if other == pr:
                    continue
                listed = found['repos'].get(repo['name']) or {}
                if other in found['pulls'] and not listed.get('failed'):  # #900: a failed read is unmeasured
                    at = listed.get('at') or found['fetched_at']
                    header.append(f"Counterpart {other} (PR listing {at}): {json.dumps(found['pulls'][other])}")
                else:  # #740: a ticket is an issue, never in the listing; it stays a reference
                    header.append(f"Counterpart {other}: not in the day's measured PR listing; kept as a reference")
        block += lead  # #848: the lead reads the day's candidates here
        text = '\n'.join(header) + '\n\n' + body + '\n' + block + ci
        relative = str(output.relative_to(root))
        import hashlib
        payload = {'name': name, 'item': item, 'role': role, 'path': relative, 'gate': gate,
                   'worktree': str(tree) if tree else None, 'pr': pr,
                   'head': head if tree else None,
                   'sha256': hashlib.sha256(text.encode()).hexdigest()}
        if second_opinion:
            payload['second_opinion'] = f'{second_opinion["runtime"]}:{second_opinion["model"]}'
        session = sessions.current()
        if role == 'builder' and session:
            payload['session'] = session
        created = False
        try:
            def update(fresh):
                nonlocal created
                if gate:
                    gate_ready(fresh, item, head)
                    fresh_changes = status(vcs, tree, root)
                    if fresh_changes:
                        raise Refused(('gate brief on a dirty tree: ' + ', '.join(row['path'] for row in fresh_changes)
                                             + '; ask the builder to commit or discard them, then write the gate brief again'))
                if (fresh['items'].get(item) != data['items'].get(item)
                        or fresh['seat_policy'] != data['seat_policy']
                        or fresh['gate_verdicts'] != data['gate_verdicts']
                        or fresh.get('gate_policy') != data.get('gate_policy')):
                    raise ValueError('state changed while collecting brief evidence; retry')
                if role != 'steward' and item in fresh['items']:
                    fresh['items'][item]['track'] = track
                    if tree:
                        fresh['items'][item]['worktree'] = str(tree)
                if role == 'builder' and item in fresh['items']:
                    fresh['items'][item]['depth'] = depth
                if refs and item in fresh['items']:
                    fresh['items'][item]['ci_jobs'] = refs
                workspace.atomic_write(output, text, replace=False)
                created = True
            state._write_state(update, root, kind='brief written', payload=payload)
        except BaseException:
            if created:
                output.unlink()
            raise
        if scratch.is_dir() and any(scratch.iterdir()):  # #734: a new seat never inherits files
            # ponytail: one move per timestamp; a fixed WUWEI_NOW moving twice is an OSError (exit 2)
            scratch.rename(scratch.with_name(f'{role}.{workspace.now():%Y%m%dT%H%M%S.%f}'))
        scratch.mkdir(parents=True, exist_ok=True)
        return relative
