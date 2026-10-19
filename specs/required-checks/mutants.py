"""Mutants of the required-checks rules. Each runs in a fresh `git archive` copy of the given commit under
<scratch>, applies one textual change to cli/wuwei/<file> and to its vendored copy under .claude/, and runs the
test files that hold the rules. A kill counts only when a test fails (a FAILED line), never on a collection
error, an import error or a timeout; a mutant that no test fails is a hole.
    python -I specs/required-checks/mutants.py <repo> <sha> <scratch> <pytest>
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

KEY = '-{hashlib.sha256(pr["baseRefName"].encode()).hexdigest()[:16]}\''
RAN = "{c.get('name') or c.get('context') for c in rollup or ()}"
UNREAD = "found.append(gap(f'required checks unreadable on {pr[\"baseRefName\"]}: {exc}', actionable=False))"
NOT_RUN = "found.append(gap(f'required check{\"s\" if len(missing) > 1 else \"\"} not run at {head[:7]}: {\", \".join(missing)}'))"
BLOCKED = "if pr.get('mergeableState') == 'blocked' and not blocking(found):"
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
    'E13 a check not run is waiting': ('evidence.py', NOT_RUN, NOT_RUN[:-2] + ", actionable=False))"),
    'E14 a KeyError reads as evidence unreadable': ('evidence.py', 'except (gh.GhError, KeyError, TypeError, AttributeError) as exc:\n            found.append(gap(f\'required',
                                                    'except (gh.GhError, TypeError, AttributeError) as exc:\n            found.append(gap(f\'required'),
    'E15 a TypeError reads as evidence unreadable': ('evidence.py', 'except (gh.GhError, KeyError, TypeError, AttributeError) as exc:\n            found.append(gap(f\'required',
                                                     'except (gh.GhError, KeyError, AttributeError) as exc:\n            found.append(gap(f\'required'),
    'E16 a GhError reads as evidence unreadable': ('evidence.py', 'except (gh.GhError, KeyError, TypeError, AttributeError) as exc:\n            found.append(gap(f\'required',
                                                   'except (KeyError, TypeError, AttributeError) as exc:\n            found.append(gap(f\'required'),
    'E17 always plural': ('evidence.py', '"s" if len(missing) > 1', '"s" if len(missing) > 0'),
    'E18 never plural': ('evidence.py', '"s" if len(missing) > 1', '"s" if len(missing) > 9'),
    'B1 blocked beside another safety gap': ('evidence.py', BLOCKED, "if pr.get('mergeableState') == 'blocked':"),
    'B2 blocked only with no gap at all': ('evidence.py', BLOCKED, "if pr.get('mergeableState') == 'blocked' and not found:"),
    'B3 never blocked': ('evidence.py', BLOCKED, "if pr.get('mergeableState') == 'BLOCKED' and not blocking(found):"),
    'B4 any state but clean': ('evidence.py', BLOCKED, "if pr.get('mergeableState') not in ('clean', None) and not blocking(found):"),
    'B5 blocked is waiting': ('evidence.py', "read the merge box on the PR'))", "read the merge box on the PR', actionable=False))"),
    'G1 the PR read drops mergeable_state': ('gh.py', "'mergeableState': data.get('mergeable_state'),", ''),
    'G2 one page of rules': ('gh.py', "return pages(f'repos/{repo}/rules/branches/{branch}')",
                             "return run(['api', f'repos/{repo}/rules/branches/{branch}'])"),
    'G3 no protection read': ('gh.py', "['required_status_checks']['contexts'] + [", "['required_status_checks']['contexts'] * 0 + ["),
    'G4 no rulesets read': ('gh.py', "for r in rules(repo, branch) if", "for r in () if"),
    'G5 every rule type read': ('gh.py', "if r['type'] == 'required_status_checks' for c", "for c"),
    'G6 no dedupe': ('gh.py', 'return list(dict.fromkeys(run(', 'return list((run('),
    'G7 protection checks for contexts': ('gh.py', "['required_status_checks']['contexts'] + [",
                                          "['required_status_checks'].get('contexts', []) + ["),
}
repo, sha, scratch, pytest = sys.argv[1:5]
holes = 0
for name, (module, old, new) in MUTANTS.items():
    with tempfile.TemporaryDirectory(dir=scratch) as folder:
        archive = subprocess.run(['git', '-C', repo, 'archive', sha], capture_output=True, check=True).stdout
        subprocess.run(['tar', '-x', '-C', folder], input=archive, check=True)
        for path in (Path(folder) / 'cli' / 'wuwei' / module, Path(folder) / '.claude' / 'wuwei' / 'cli' / 'wuwei' / module):
            text = path.read_text(encoding='utf-8')
            assert text.count(old) == 1, (name, old)
            path.write_text(text.replace(old, new), encoding='utf-8')
        run = subprocess.run([pytest, '-q', '-p', 'no:cacheprovider', 'tests/test_evidence.py', 'tests/test_status_perf.py',
                              'tests/test_replay.py', 'tests/test_setup.py'], cwd=folder, capture_output=True, text=True, timeout=900)
        failed = re.findall(r'^FAILED (\S+)', run.stdout, re.M)
        holes += not failed
        print(f"{name}: {'killed' if failed else 'HOLE'}, {len(failed)} failed, first {failed[:1]} "
              f"({run.stdout.strip().splitlines()[-1]})", flush=True)
print(f'{len(MUTANTS)} mutants, {len(MUTANTS) - holes} killed, {holes} holes')
