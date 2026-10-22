"""hook.exception_refs at main and at the head over the questions of the question probe.

    python3 -I specs/spec-gap-exception/refs_differential.py <main tree> <head tree> <probe output> [<probe output> ...]

Each probe output line gives a question and the gap wuwei evidence printed for it. Both trees read every question; a
question whose recorded gap matches its printed gap at main (as evidence.excepted compares them) and not at the head
is printed as its own row.
"""
import json
import subprocess
import sys

READ = ('import json, sys; sys.path.insert(0, sys.argv[1] + "/cli"); from wuwei import hook; '
        'print(json.dumps([hook.exception_refs(q)[1] for q in json.load(sys.stdin)]))')


def norm(text):  # evidence.excepted's comparison
    return ' '.join(text.casefold().split()).rstrip(' .,;:!?').removesuffix('[waiting]').rstrip(' .,;:!?')


main, head, *outputs = sys.argv[1:]
cases = {}
for path in outputs:
    with open(path, encoding='utf-8') as lines:
        for line in lines:
            row = json.loads(line)
            cases[row['question']] = row['printed']
questions = sorted(cases)
read = {tree: json.loads(subprocess.run([sys.executable, '-I', '-c', READ, tree], input=json.dumps(questions),
                                        capture_output=True, text=True, check=True).stdout) for tree in (main, head)}
right = {tree: [norm(gap) == norm(cases[q]) for q, gap in zip(questions, read[tree])] for tree in (main, head)}
rows = [q for i, q in enumerate(questions) if right[main][i] and not right[head][i]]
print(f'questions {len(questions)}; recorded gap differs {sum(a != b for a, b in zip(read[main], read[head]))}; '
      f'right at main {sum(right[main])}; right at head {sum(right[head])}; right at main and wrong at the head {len(rows)}')
for q in rows:
    print('ROW', json.dumps(q))
