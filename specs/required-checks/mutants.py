"""Mutants of the required-checks rules. Each runs in a fresh `git archive` copy of the given commit under
<scratch>, applies one textual change to cli/wuwei/<file> and to its vendored copy under .claude/, and runs the
test files that hold the rules. A kill counts only when a test fails (a FAILED line), never on a collection
error, an import error or a timeout; a mutant that no test fails is a hole. Pass mutant name prefixes after
<pytest> to run only those (R runs fix round 1's).
    python -I specs/required-checks/mutants.py <repo> <sha> <scratch> <pytest> [prefix ...]
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

KEY = '-{hashlib.sha256(pr["baseRefName"].encode()).hexdigest()[:16]}\''
RAN = "{c.get('name') or c.get('context') for c in rollup or ()}"
UNREAD = "found.append(gap(f'required checks unreadable on {pr[\"baseRefName\"]}: {exc}', actionable=False))"
BLOCKED = "if pr.get('mergeableState') == 'blocked' and not blocking(found):"
EXCEPT = 'except (gh.GhError, KeyError, TypeError, AttributeError) as exc:\n            found.append(gap(f\'required'
SETTLED = "settled = all(c.get('status', 'COMPLETED') == 'COMPLETED' and c.get('state') not in ('PENDING', 'EXPECTED') for c in"
AUTO = "AUTO = re.compile(r'^(CI running$|required checks? not run yet at |GitHub reports the merge blocked)')"
BRANCH = "f'repos/{repo}/branches/{quote(branch, safe=\"/\")}'"
RULES = "pages(f'repos/{repo}/rules/branches/{quote(branch, safe=\"/\")}')"
CONTEXTS = "['protection']['required_status_checks']['contexts']\n"
MUTANTS = {
    'E1 a status context is not a run': ('evidence.py', RAN, "{c.get('name') for c in rollup or ()}"),
    'E2 a check run name is not a run': ('evidence.py', RAN, "{c.get('context') for c in rollup or ()}"),
    'E3 every required check reads as missing': ('evidence.py', f'if c not in {RAN}]', f'if c not in {RAN} or True]'),
    'E4 no required check reads as missing': ('evidence.py', f'if c not in {RAN}]', f'if c not in {RAN} and False]'),
    'E5 the key without the branch': ('evidence.py', KEY, "'"),
    'E6 the key by the branch with / as __': ('evidence.py', KEY, '-{pr["baseRefName"].replace("/", "__")}\''),
    'E7 the key without the repository': ('evidence.py', 'required-{repo.replace("/", "__")}-', 'required-'),
    'E8 kept a day': ('evidence.py', "gh.required_checks(repo, pr['baseRefName']), PR_TTL)", "gh.required_checks(repo, pr['baseRefName']))"),
    'E9 never kept': ('evidence.py', "_cached(root, key, lambda: gh.required_checks(repo, pr['baseRefName']), PR_TTL)",
                      "gh.required_checks(repo, pr['baseRefName'])"),
    'E10 the head branch read': ('evidence.py', "gh.required_checks(repo, pr['baseRefName'])", "gh.required_checks(repo, pr['headRefName'])"),
    'E11 an unreadable read passes': ('evidence.py', UNREAD, 'pass'),
    'E12 an unreadable read is actionable': ('evidence.py', UNREAD, UNREAD.replace(', actionable=False', '')),
    'E13 a settled check not run is waiting': ('evidence.py', 'actionable=settled))', 'actionable=False))'),
    'E14 a KeyError reads as evidence unreadable': ('evidence.py', EXCEPT, EXCEPT.replace('KeyError, ', '')),
    'E15 a TypeError reads as evidence unreadable': ('evidence.py', EXCEPT, EXCEPT.replace('TypeError, ', '')),
    'E16 a GhError reads as evidence unreadable': ('evidence.py', EXCEPT, EXCEPT.replace('gh.GhError, ', '')),
    'E17 always plural': ('evidence.py', '"s" if len(missing) > 1', '"s" if len(missing) > 0'),
    'E18 never plural': ('evidence.py', '"s" if len(missing) > 1', '"s" if len(missing) > 9'),
    'B1 blocked beside another safety gap': ('evidence.py', BLOCKED, "if pr.get('mergeableState') == 'blocked':"),
    'B2 blocked only with no gap at all': ('evidence.py', BLOCKED, "if pr.get('mergeableState') == 'blocked' and not found:"),
    'B3 never blocked': ('evidence.py', BLOCKED, "if pr.get('mergeableState') == 'BLOCKED' and not blocking(found):"),
    'B4 any state but clean': ('evidence.py', BLOCKED, "if pr.get('mergeableState') not in ('clean', None) and not blocking(found):"),
    'G1 the PR read drops mergeable_state': ('gh.py', "'mergeableState': data.get('mergeable_state'),", ''),
    'G3 no protection read': ('gh.py', CONTEXTS, CONTEXTS[:-1] + ' * 0\n'),
    'G4 no rulesets read': ('gh.py', "for r in rules(repo, branch) if", "for r in () if"),
    'G5 every rule type read': ('gh.py', "if r['type'] == 'required_status_checks' for c", "for c"),
    'G6 no dedupe': ('gh.py', 'return list(dict.fromkeys(found + [', 'return list((found + ['),
    'G7 protection checks for contexts': ('gh.py', CONTEXTS, "['protection']['required_status_checks'].get('contexts', [])\n"),
    # fix round 1
    'R1 auto-merge held by a check not run yet': ('evidence.py', AUTO, AUTO.replace('required checks? not run yet at |', '')),
    'R2 auto-merge held by the blocked gap': ('evidence.py', AUTO, AUTO.replace('|GitHub reports the merge blocked', '')),
    'R3 auto-merge passes a settled check not run': ('evidence.py', AUTO, AUTO.replace('not run yet at ', 'not run')),
    'R4 auto-merge passes any CI gap': ('evidence.py', AUTO, AUTO.replace('CI running$', 'CI')),
    'R5 a direct merge passes what auto-merge may': ('guards.py', 'if not (auto and evidence.AUTO.match', 'if not (evidence.AUTO.match'),
    'R6 auto-merge passes only CI running': ('guards.py', "auto and evidence.AUTO.match(g['text'])", "auto and g['text'] == 'CI running'"),
    'R7 CI always settled': ('evidence.py', SETTLED, "settled = True or all(c.get('status', 'COMPLETED') == 'COMPLETED' and c.get('state') "
                                                     "not in ('PENDING', 'EXPECTED') for c in"),
    'R8 a pending status is settled': ('evidence.py', SETTLED, "settled = all(c.get('status', 'COMPLETED') == 'COMPLETED' for c in"),
    'R9 a check not run yet is actionable': ('evidence.py', 'actionable=settled))', 'actionable=True))'),
    'R10 the release hint on every PR': ('evidence.py', "if generated and settled else ''", "if settled else ''"),
    'R11 the release hint while CI runs': ('evidence.py', "if generated and settled else ''", "if generated else ''"),
    'R12 the blocked gap is actionable': ('evidence.py', "read the merge box on the PR', False))", "read the merge box on the PR'))"),
    'R13 the branch read raw': ('gh.py', BRANCH, "f'repos/{repo}/branches/{branch}'"),
    'R14 the rules read raw': ('gh.py', RULES, "pages(f'repos/{repo}/rules/branches/{branch}')"),
    'R15 the branch read encodes /': ('gh.py', BRANCH, BRANCH.replace('safe="/"', 'safe=""')),
    'R16 one page of rules': ('gh.py', RULES, RULES[:-1] + ', 1)'),
    'R17 the PR kept while CI runs': ('evidence.py', 'if sig and not hit and rollup and settled:', 'if sig and not hit and rollup:'),
}
repo, sha, scratch, pytest, *only = sys.argv[1:]
chosen = {name: m for name, m in MUTANTS.items() if not only or name.split()[0].startswith(tuple(only))}
holes = 0
for name, (module, old, new) in chosen.items():
    with tempfile.TemporaryDirectory(dir=scratch) as folder:
        archive = subprocess.run(['git', '-C', repo, 'archive', sha], capture_output=True, check=True).stdout
        subprocess.run(['tar', '-x', '-C', folder], input=archive, check=True)
        for path in (Path(folder) / 'cli' / 'wuwei' / module, Path(folder) / '.claude' / 'wuwei' / 'cli' / 'wuwei' / module):
            text = path.read_text(encoding='utf-8')
            assert text.count(old) == 1, (name, old)
            path.write_text(text.replace(old, new), encoding='utf-8')
        run = subprocess.run([pytest, '-q', '-p', 'no:cacheprovider', 'tests/test_evidence.py', 'tests/test_status_perf.py',
                              'tests/test_replay.py', 'tests/test_setup.py', 'tests/test_guards.py'],
                             cwd=folder, capture_output=True, text=True, timeout=900)
        failed = re.findall(r'^FAILED (\S+)', run.stdout, re.M)
        holes += not failed
        print(f"{name}: {'killed' if failed else 'HOLE'}, {len(failed)} failed, first {failed[:1]} "
              f"({run.stdout.strip().splitlines()[-1]})", flush=True)
print(f'{len(chosen)} mutants, {len(chosen) - holes} killed, {holes} holes')
