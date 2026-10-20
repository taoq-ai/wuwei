"""Mutants of the team row and the Stop guard (AGENTS.md, "Mutants").

Each mutant goes into a fresh git archive copy of the head under the given scratch folder, applied
to cli/wuwei/ and .claude/wuwei/cli/wuwei/ alike, and runs the board and Stop tests one mutant at a
time. A kill counts only when a test fails. The copies are deleted afterwards.

    python -I specs/orchestration-gap/mutants.py <repository> <head sha> <scratch folder> [name part]
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

BOARD, HOOK, EVIDENCE = 'wuwei/board.py', 'wuwei/hook.py', 'wuwei/evidence.py'
MUTANTS = {
    'more than one PR needs a shepherd': (BOARD, "r['pr'] for r in prs}) > 2", "r['pr'] for r in prs}) > 1"),
    'more than three PRs need a shepherd': (BOARD, "r['pr'] for r in prs}) > 2", "r['pr'] for r in prs}) > 3"),
    'a running shepherd never clears the line': (BOARD, "> 2 and 'shepherd' not in seats", "> 2 and True"),
    'a running gate seat never clears the line': (BOARD, "(owed and not any(str(s).startswith('sentinel-') for s in seats))", "(owed and True)"),
    'CI running or failing still owes a gate seat': (BOARD, " and not any(g['text'].startswith(('CI ', 'required check')) for g in r['gaps'])", ''),
    'a missing required check still owes a gate seat': (BOARD, "startswith(('CI ', 'required check'))", "startswith('CI ')"),
    'an unconfirmed seat still runs': (BOARD, "('seat.stopped', 'seat.unconfirmed')", "('seat.stopped',)"),
    'a stopped seat still runs': (BOARD, "('seat.stopped', 'seat.unconfirmed')", "('seat.unconfirmed',)"),
    'a seat of any session runs': (BOARD, "if session and r['data'].get('session') == session", "if True"),
    'no session matches a seat with none': (BOARD, "if session and r['data'].get('session')", "if r['data'].get('session')"),
    'a seat of any day runs': (BOARD, "ws.rows(root, 'seat.started', ws.today())", "ws.rows(root, 'seat.started')"),
    'status reads no session': (BOARD, "running(root, os.environ.get('CLAUDE_CODE_SESSION_ID'))", "running(root, None)"),
    'the Stop guard reads no session': (HOOK, "board.running(root, payload.get('session_id'))", "board.running(root, None)"),
    'the Stop guard counts any seat today': (HOOK, "board.running(root, payload.get('session_id'))",
                                             "any(r['data'].get('agent') for r in ws.rows(root, 'seat.started', ws.today()))"),
    'the team lines hold the merge': (EVIDENCE, "|the approval from|orchestration:)", "|the approval from)"),
    'the team row is never added': (BOARD, "* bool(duties)", "* 0"),
}


def main(repo, sha, scratch, only=''):
    scratch, results = Path(scratch).resolve(), []
    for name, (path, old, new) in MUTANTS.items():
        if only and only not in name:
            continue
        tree = scratch / 'mutant'
        shutil.rmtree(tree, ignore_errors=True)
        tree.mkdir(parents=True)
        subprocess.run(f'git -C {repo} archive {sha} | tar -x -C {tree}', shell=True, check=True)
        for base in ('cli', '.claude/wuwei/cli'):
            file = tree / base / path
            text = file.read_text(encoding='utf-8')
            assert text.count(old) == 1, (name, base)
            file.write_text(text.replace(old, new), encoding='utf-8')
        env = {k: v for k, v in os.environ.items() if k != 'CLAUDE_CODE_SESSION_ID'}
        run = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', 'tests/test_watch.py',
                              'tests/test_hook.py', 'tests/test_status_perf.py'], cwd=tree, env=env, capture_output=True, text=True)
        last = run.stdout.strip().splitlines()[-1] if run.stdout.strip() else run.stderr[-200:]
        results.append((name, 'killed' if run.returncode == 1 else 'SURVIVED' if run.returncode == 0 else 'error', last))
        print(f'{results[-1][1]:<8} {name}: {last}', flush=True)
    shutil.rmtree(scratch / 'mutant', ignore_errors=True)
    print(f"{sum(r[1] == 'killed' for r in results)} of {len(results)} killed")


if __name__ == '__main__':
    main(*sys.argv[1:5])
