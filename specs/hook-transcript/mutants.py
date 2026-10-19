"""hook-transcript mutants: python3 -I mutants.py <sha> <empty scratch folder> [name ...]

Each mutant runs alone in a fresh `git archive` copy with both copies of the runtime (cli/ and .claude/wuwei/cli/) edited,
on the test files that reach the mutated file, with the wall-clock tests (a test body that reads time.monotonic or
time.perf_counter) deselected. A kill counts only when a behavioural test fails.
"""

import ast
from pathlib import Path
import subprocess
import sys

H, G, W = 'cli/wuwei/hook.py', 'cli/wuwei/guards.py', 'cli/wuwei/ws.py'
MUTANTS = {
    'H1 any folder is the projects folder': (H, """if real.is_relative_to(
            ws.PROJECTS.resolve()) and real.is_file()""", 'if real.is_file()'),
    'H2 links and .. left unresolved': (H, 'real = Path(path).resolve(strict=True)', 'real = Path(path).absolute()'),
    'H3 a folder is a transcript': (H, """real.is_relative_to(
            ws.PROJECTS.resolve()) and real.is_file()""", 'real.is_relative_to(\n            ws.PROJECTS.resolve())'),
    'H4 no tool_use needed': (H, """ and any(
        p.get('id') == tid and p.get('name') == 'AskUserQuestion' for p in parts(rows, 'tool_use'))""", ''),
    'H5 any answer counts': (H, "done[-1].get('answers') == kept.get('answers')", 'True'),
    'H6 the first answer row counts': (H, "isinstance(done[-1], dict) and done[-1].get('answers')", "isinstance(done[0], dict) and done[0].get('answers')"),
    'H7 any tool with the id': (H, " and p.get('name') == 'AskUserQuestion' for p", ' for p'),
    'H8 a Stop never gives up': (H, 'if why and not final:', 'if why:'),
    'H9 no claim': (H, """        try:
            path.unlink()
        except OSError:
            continue
        notes +=""", '        notes +='),
    'H10 a lost claim still records': (H, """            path.unlink()
        except OSError:
            continue""", """            path.unlink()
        except OSError:
            pass"""),
    'H11 no wait at a Stop': (H, 'end = [], time.monotonic() + WAIT * final', 'end = [], time.monotonic()'),
    'H12 a Stop is not final': (H, "_confirm(root, session, event == 'Stop')", '_confirm(root, session, False)'),
    'H13 no answer.unconfirmed at once': (H, "if transcript_rows(kept['path'], kept['id'] or '\\0') is None:", 'if False:'),
    'H14 any agent transcript name': (H, " if Path(path).name == f'agent-{agent}.jsonl' else {}", ''),
    'H15 any seat type': (H, "meta.get('toolUseId') if str(meta.get('agentType')).rsplit(':', 1)[-1] == role else None", "meta.get('toolUseId')"),
    'H16 no launch needed': (H, """    if not use or not any(p.get('id') == use and p.get('name') in ('Agent', 'Task')
                          for p in parts(transcript_rows(payload.get('transcript_path'), use) or [], 'tool_use')):""", '    if not use:'),
    'H17 a launch on any tool': (H, " and p.get('name') in ('Agent', 'Task')\n", '\n'),
    'H18 an unconfirmed seat still runs': (H, " - ids['seat.unconfirmed'])", ')'),
    'H19 seat answers confirm too': (H, "    if payload.get('agent_id') or event not in ('PreToolUse', 'PostToolUse', 'Stop')",
                                    "    if event not in ('PreToolUse', 'PostToolUse', 'Stop')"),
    'W1 the projects folder from HOME': (W, 'Path(pwd.getpwuid(os.getuid()).pw_dir)', 'Path.home()'),
    'G1 no transcript door': (G, "    return records(path, ('projects',), cap, '.claude')", '    return False'),
    'G2 redirects pass': (G, '        if any(map(harness, targets)) or writer', '        if writer'),
    'G3 writer arguments pass': (G, ' or writer and any(map(harness, words)) or held', ' or held'),
    'G4 working directories pass': (G, """ or held and (writer or any(
                not re.fullmatch(r'[0-9]*-?|/dev/\\w+', t) for t in targets)):
            return deny(HARNESS)""", """:
            return deny(HARNESS)"""),
    'G5 cd into it is not tracked': (G, "        held = held or program in ('cd', 'pushd') and any(map(harness, argv[1:]))\n", ''),
    'G6 -C and -D values pass': (G, 'harness(cwd) or any(harness(w, 64) for w in wd)', 'harness(cwd)'),
    'G7 a session inside it passes': (G, 'harness(cwd) or any(harness(w, 64) for w in wd)', 'any(harness(w, 64) for w in wd)'),
    'G8 edits pass': (G, " else deny(HARNESS) if any(map(harness, paths)) else None", ' else None'),
    'G9 braces lose the name': (G, 'cap // max(len(alts), 2), name) for a in alts)', 'cap // max(len(alts), 2)) for a in alts)'),
    'G10 find after a wrapper': (G, "READ = {'git', 'gh', 'wuwei', 'sed', 'find'}", "READ = {'git', 'gh', 'wuwei', 'sed'}"),
    'G11 all of .claude': (G, "    return records(path, ('projects',), cap, '.claude')", "    return records(path, None, cap, '.claude')"),
}
TESTS = {H: ['tests/test_hook.py', 'tests/test_codex.py', 'tests/test_models.py'], W: ['tests/test_hook.py', 'tests/test_codex.py'],
         G: ['tests/test_guards.py', 'tests/test_hook.py']}  # the tests that reach the mutated file


def wall_clock(tree, tests):
    found = []
    for name in tests:
        for node in ast.parse((tree / name).read_text(encoding='utf-8')).body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_') and any(
                    isinstance(n, ast.Attribute) and n.attr in ('monotonic', 'perf_counter') for n in ast.walk(node)):
                found.append(f'{name}::{node.name}')
    return found


sha, scratch, chosen = sys.argv[1], Path(sys.argv[2]).resolve(), sys.argv[3:]
for name, (path, old, new) in MUTANTS.items():
    if chosen and name.split()[0] not in chosen:
        continue
    tree = scratch / ('mutant-' + name.split()[0])
    subprocess.run(['rm', '-rf', str(tree)], check=True)
    tree.mkdir(parents=True)
    subprocess.run(['tar', '-x', '-C', str(tree)], input=subprocess.run(['git', 'archive', sha], check=True, capture_output=True).stdout,
                   check=True)
    for copy in (tree / path, tree / '.claude' / 'wuwei' / path):
        text = copy.read_text(encoding='utf-8')
        assert text.count(old) == 1, (name, copy, old)
        copy.write_text(text.replace(old, new), encoding='utf-8')
    deselect = [arg for test in wall_clock(tree, TESTS[path]) for arg in ('--deselect', test)]
    run = subprocess.run(['/root/.local/bin/pytest', '-q', '-p', 'no:cacheprovider', *TESTS[path], *deselect], cwd=tree, capture_output=True,
                         text=True)
    failed = sorted({line.split('::')[1].split('[')[0].split(' ')[0] for line in run.stdout.splitlines() if line.startswith('FAILED')})
    print(f'{name}: {"killed" if failed else "SURVIVED"} by {len(failed)}: {", ".join(failed[:4])}', flush=True)
    subprocess.run(['rm', '-rf', str(tree)], check=True)
