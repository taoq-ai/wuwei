"""Each mutant in a fresh git archive of the head, applied to cli/wuwei/ and .claude/wuwei/cli/wuwei/, then the focused
files run one suite at a time. A kill is a failing behavioural test (the vendored-copy test is never the only failure)."""
import shutil
import subprocess
import sys
from pathlib import Path

repo, head, base = sys.argv[1], sys.argv[2], Path(sys.argv[3])
G = 'cli/wuwei/guards.py'
H = 'cli/wuwei/hook.py'
W = 'cli/wuwei/ws.py'
READ = "canary = p.read_text(encoding='utf-8').strip() if (p := Path(root) / ws.DIR / 'canary').is_file() else ''"
MUTANTS = {
    'M1 reader drops UnicodeError': (W, 'suppress(OSError, UnicodeError)', 'suppress(OSError)'),
    'M2 reader drops OSError': (W, 'suppress(OSError, UnicodeError)', 'suppress(UnicodeError)'),
    'M3 reader drops is_file': (W, "path.read_text(encoding='utf-8').strip() if (path := Path(root) / DIR / 'canary').is_file() else ''",
                                "(Path(root) / DIR / 'canary').read_text(encoding='utf-8').strip()"),
    'M4 reader drops strip': (W, "read_text(encoding='utf-8').strip() if (path", "read_text(encoding='utf-8') if (path"),
    'M5 reader returns nothing': (W, "        return path.read_text", "        return '' and path.read_text"),
    'M6 _report inline read': (H, "        canary = ws.canary(root)\n        for _ in range(9):", f"        {READ}\n        for _ in range(9):"),
    'M7 kept report inline read': (H, "'reports', ws.canary(root)", "'reports', (c.read_text(encoding='utf-8').strip() if (c := Path(root) / ws.DIR / 'canary').is_file() else '')"),
    'M8 _seat_stop inline read': (H, "text, canary = last_text(payload), ws.canary(root)", "text, canary = last_text(payload), (c.read_text(encoding='utf-8').strip() if (c := Path(root) / ws.DIR / 'canary').is_file() else '')"),
    'M9 seat launch inline read': (H, "        canary = ws.canary(root)\n        item, effort", f"        {READ}\n        item, effort"),
    'M10 delivery inline read': (H, "            canary = ws.canary(root)\n", f"            {READ}\n"),
    'M11 LEDGER drops canary': (G, "LEDGER, CACHE = ('ledger', 'ledger.jsonl', 'canary'),", "LEDGER, CACHE = ('ledger', 'ledger.jsonl'),"),
    'M12 CACHE drops canary': (G, "('ledger', 'ledger.jsonl', 'canary', 'cache')", "('ledger', 'ledger.jsonl', 'cache')"),
    'M13 door word drops canary': (G, '(/ledger|/canary|', '(/ledger|'),
}
TESTS = ['tests/test_ledger.py', 'tests/test_guards.py', 'tests/test_hook.py', 'tests/test_native_evidence.py', 'tests/test_codex.py']
only = sys.argv[4:]
for name, (file, old, new) in MUTANTS.items():
    if only and name.split()[0] not in only:
        continue
    tree = base / name.split()[0]
    shutil.rmtree(tree, ignore_errors=True)
    tree.mkdir(parents=True)
    subprocess.run(f'git -C {repo} archive {head} | tar -x -C {tree}', shell=True, check=True)
    for copy in (tree / file, tree / '.claude/wuwei' / file):
        text = copy.read_text(encoding='utf-8')
        assert text.count(old) == 1, (name, copy, text.count(old))
        copy.write_text(text.replace(old, new), encoding='utf-8')
    pytest = ['uvx', '--python', '3.13', 'pytest', '-q', '-p', 'no:cacheprovider']
    run = subprocess.run([*pytest, '-k', 'canary or route or mask', *TESTS], cwd=tree, capture_output=True, text=True, timeout=1200)
    if ' failed' not in run.stdout.splitlines()[-1]:  # the focused tests hold it: the whole files decide
        run = subprocess.run([*pytest, *TESTS], cwd=tree, capture_output=True, text=True, timeout=2400)
    failed = sorted({l.split(' ')[1].split('[')[0] for l in run.stdout.splitlines() if l.startswith('FAILED')})
    behavioural = [f for f in failed if 'vendored_plugin_matches' not in f]
    print(f'{name}: {"killed" if behavioural else "SURVIVED"} by {len(behavioural)} tests: {", ".join(behavioural[:4])} | {run.stdout.splitlines()[-1] if run.stdout else run.stderr[-200:]}', flush=True)
    shutil.rmtree(tree, ignore_errors=True)
