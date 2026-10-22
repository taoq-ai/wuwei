"""Mutants of each new condition in the answer-confirm path, applied to both copies of hook.py, one at a time.

Run from a copy of the tree (never the builder's worktree), with pytest on PATH:
    python3 specs/1211-confirm/mutants.py <tree copy>
Prints each mutant with the first test that fails (a kill) or SURVIVED.
"""

import subprocess
import sys
from pathlib import Path

MUTANTS = {
    'M1 a missing question matches a None answer': ('q in said and said[q] == a', 'said.get(q) == a'),
    'M2 no pending state': ("if p.get('tool_use_id') == tid]):\n        return None", "if p.get('tool_use_id') == tid]) and False:\n        return None"),
    'M3 no bound': ('final or shown is None and ws.cache_get(root, path.stem, BOUND) is not None', 'final or shown is None'),
    'M4 never pending': ('final or shown is None and ws.cache_get(root, path.stem, BOUND) is not None', 'final'),
    'M5 a one-minute bound': ('WAIT, BOUND = 1.5, 600', 'WAIT, BOUND = 1.5, 60'),
    'M6 every payload answer recorded': ("{**kept, 'answers': same,", "{**kept, 'answers': kept.get('answers'),"),
    'M7 every question in the prompt row': ("'questions': [q for q in kept.get('questions') or () if q in same]})",
                                            "'questions': kept.get('questions') or []})"),
    'M8 the note names every question': ('if q not in same]), ', ']), '),
    'M9 an empty payload answer is silent': (" or (\n        '' if same else 'the payload holds no answer')", ''),
    'M10 a prompt row with no answer': ('if same and all(', 'if all('),
    'M11 no unconfirmed row beside a recorded answer': ('if why else []', 'if why and not same else []'),
    'M12 values not truncated': ("{str(said.get(q))[:60]!r}, not {str(a)[:60]!r}", "{str(said.get(q))!r}, not {str(a)!r}"),
    'M13 any tool name': ("p.get('id') == tid and p.get('name') == 'AskUserQuestion'", "p.get('id') == tid"),
    'M14 the first tool_result row': ('done[-1], dict(', 'done[0], dict('),
    'M15 the replay check gone': ("if same and all(r['data'].get('id') != kept['id'] for r in ws.rows(root, 'prompt')):", 'if same:'),
    'M16 a Stop records an unrecorded answer': ('if why and (final or shown', 'if why and (False or shown'),
    'M17 no text fallback': ("said = result['answers'] if own else {", "said = result['answers'] if own else {} if True else {"),
    'M18 a text pair not held by its neighbour': ('json.dumps(f\'"{q}"="{a}"{after[q]}\')', 'json.dumps(f\'"{q}"="{a}"\')'),
    'M19 a text question the tool_use did not ask': ('if q in after and json.dumps', 'if json.dumps'),
    'M20 a toolUseResult answers list read as answers': ("isinstance(result, dict) and isinstance(result.get('answers'), dict)",
                                                         "isinstance(result, dict) and result.get('answers') is not None"),
    'M21 the no tool_use check gone': ("        return {}, f'the transcript holds no AskUserQuestion tool_use {tid}'\n", "        pass\n"),
    'M22 the reason drops its text prefix': (" * (not own) + why", " * False + why"),
}
tree = Path(sys.argv[1]).resolve()
copies = [tree / 'cli' / 'wuwei' / 'hook.py', tree / '.claude' / 'wuwei' / 'cli' / 'wuwei' / 'hook.py']
original = copies[0].read_text(encoding='utf-8')
for name, (old, new) in MUTANTS.items():
    assert original.count(old) == 1, name
    for path in copies:
        path.write_text(original.replace(old, new), encoding='utf-8')
    try:
        run = subprocess.run(['pytest', '-q', '-x', '-p', 'no:cacheprovider', 'tests/test_hook.py', 'tests/test_codex.py',
                              '--deselect', 'tests/test_hook.py::test_a_stop_waits_for_an_answer_row_the_harness_is_still_writing'],
                             cwd=tree, capture_output=True, text=True)
    finally:
        for path in copies:
            path.write_text(original, encoding='utf-8')
    failed = [line.split(' ')[1] for line in run.stdout.splitlines() if line.startswith('FAILED ')]
    print(f'{name}: ' + (f'killed by {failed[0]}' if failed else 'SURVIVED' if run.returncode == 0 else f'error {run.stdout[-300:]}'),
          flush=True)
