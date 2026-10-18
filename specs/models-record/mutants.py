"""Mutants for models-record: each one breaks one new condition in a fresh copy of the tree and runs the
tests that should catch it. A mutant that survives (its tests pass) is a hole.

    python -I specs/models-record/mutants.py <tree> <empty scratch dir> [pytest]
"""

import shutil
import subprocess
import sys
from pathlib import Path

H, R, W, S, A = 'cli/wuwei/hook.py', 'cli/wuwei/report.py', 'cli/wuwei/ws.py', 'cli/wuwei/setup.py', 'cli/wuwei/agents.py'
MUTANTS = [
    ('M1 never advise', H, 'if reason and not floor or any(', 'if True or any('),
    ('M2 a reason line ignored', H, 'if reason and not floor or', 'if False and reason or'),
    ('M3 no Haiku floor', H, "floor = role.startswith('sentinel-') and fam(model) == 'haiku'", 'floor = False'),
    ('M4 effort ignored', H, "s.rsplit(' ', 1)[1] == effort)", 'True)'),
    ('M5 model ignored', H, "fam(s.rsplit(' ', 1)[0]) == fam(model))", 'True)'),
    ('M6 owner rows ignored', H, "if (own := rows.get(f'{role} {tier}') or rows.get(role))", 'if (own := None)'),
    ('M7 owner role row ignored', H, "rows.get(f'{role} {tier}') or rows.get(role))", "rows.get(f'{role} {tier}'))"),
    ('M8 raised tier ignored', H, 'tier = evidence.RAISE.get(tier, tier)', 'tier = tier'),
    ('M9 paths setting not allowed', H, "if ' ' in when]", 'if False]'),
    ('M10 effort variable ignored', H, "os.environ.get('CLAUDE_CODE_EFFORT_LEVEL') or ", ''),
    ('M11 model variable ignored', H, "os.environ.get('CLAUDE_CODE_SUBAGENT_MODEL') or ", ''),
    ('M12 brief Model line ignored', H, 'or line and line[1]', 'or None'),
    ('M13 Codex spawn advised', H, " or not data.get('prompt')", ''),
    ('M14 resolvedModel not recorded', H, "str(response.get('resolvedModel') or 'unmeasured')", "'unmeasured'"),
    ('M15 attest does not copy the model', H, "seat.get('model', 'unrecorded')", "'unrecorded'"),
    ('M16 blocking findings not counted', H, "sum(1 for f in parsed['findings'] if f['blocks'])", '0'),
    ('M17 stop effort not recorded', H, "str(effort.get('level') or 'unmeasured')", "'unmeasured'"),
    ('M18 one-word models value kept', W, "isinstance(v, str) and len(v.split()) > 1}", 'isinstance(v, str)}'),
    ('M19 models listed as retired', W, " and key != 'models'", ''),
    ('M20 models written as JSON', W, '    if isinstance(value, dict):\n', '    if False:\n'),
    ('M21 escapes not traced', R, "escaped.update(d['agent'] for d in passing if d.get('agent'))", 'pass'),
    ('M22 fix rounds count every launch', R, '(on_items - len(items))', '(on_items)'),
    ('M23 unmeasured not counted', R, "{'unrecorded', 'unmeasured'} &", "{'unrecorded'} &"),
    ('M24 doctor silent', S, 'if os.environ.get(var)]', 'if False]'),
    ('M25 no effort frontmatter', A, '\\neffort: {effort}\\n', '\\n'),
    ('M26 table drifts from the charter', A, "'full': 'Opus 5.5 xhigh'", "'full': 'Opus 5.5 high'"),
    ('M27 item line unread', H, r"r'\bItem:", r"r'\bItemX:"),
    ('M28 a launch with no model compared to opus', H, "str(data.get('model') or table[''].rsplit(' ', 1)[0])", "str(data.get('model') or 'opus')"),
    ('M29 asked model not recorded', H, "'asked': str(data.get('model') or 'unrecorded')", "'asked': 'unrecorded'"),
    ('M30 reason not recorded', H, "'reason': reason, 'item': item", "'reason': None, 'item': item"),
]
TESTS = ['tests/test_models.py', 'tests/test_ledger.py', 'tests/test_report.py', 'tests/test_setup.py', 'tests/test_hook.py']


def main(tree, scratch, pytest):
    survived = 0
    for name, path, old, new in MUTANTS:
        copy = Path(scratch) / name.split()[0]
        shutil.copytree(tree, copy)
        text = (copy / path).read_text(encoding='utf-8')
        if text.count(old) != 1:
            print(f'{name}: pattern found {text.count(old)} times, not run')
            survived += 1
            continue
        (copy / path).write_text(text.replace(old, new), encoding='utf-8')
        if name.startswith(('M25', 'M26')):  # the agent files are generated: rebuild them as wuwei agents build would
            subprocess.run([sys.executable, '-I', str(copy / 'bin' / 'wuwei'), 'agents', 'build'], cwd=copy, capture_output=True)
        run = subprocess.run([pytest, '-q', '-x', '-p', 'no:cacheprovider', *TESTS], cwd=copy, capture_output=True, text=True)
        caught = run.returncode != 0
        survived += not caught
        print(f"{name}: {'killed' if caught else 'SURVIVED'} ({run.stdout.strip().splitlines()[-1] if run.stdout.strip() else run.stderr[-200:]})")
    print(f'{len(MUTANTS)} mutants, {survived} survived')
    return 1 if survived else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 'pytest'))
