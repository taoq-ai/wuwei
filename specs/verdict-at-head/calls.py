"""Compare calls gate_gaps makes on a long history: N heads on one line, three gates verdicted per head.

Usage: python3 -I calls.py <tree> <case scratch folder>
Shapes: fix-then-pass (FIX at every head but the last, PASS there), pass-each (PASS at every head),
ping (FIX and PASS alternating, PASS at the head).
"""
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]) / 'cli'))
from wuwei import evidence, gh, ws  # noqa: E402

GATES = ('arch', 'quality', 'security')
calls = []


def fake(args, timeout=30):
    calls.append(tuple(args))
    older, newer = args[1].split('/compare/')[1].split('...')
    a, b = int(older[:7], 16), int(newer[:7], 16)
    return {'status': 'identical' if a == b else 'ahead' if a < b else 'behind',
            'files': [{'filename': 'src/app.py', 'additions': 300, 'deletions': 0}]}


gh.run = fake


def head(i):
    return f'{i + 1:07x}' + 'f' * 33


for shape in ('fix-then-pass', 'pass-each', 'ping'):
    for n in (1, 5, 10, 20, 40):
        root = Path(tempfile.mkdtemp(dir=sys.argv[2]))
        (root / ws.DIR).mkdir()
        ws.write_config(root, {**ws.DEFAULTS, 'repos': ['acme/app'], 'owner_paths': []})
        k = 0
        for i in range(n):
            verdict = 'PASS' if i == n - 1 or shape == 'pass-each' or shape == 'ping' and i % 2 else 'FIX'
            for gate in GATES:
                path = root / ws.DIR / 'verdicts' / 'I-1' / f'{gate}-{k}.md'
                k += 1
                path.parent.mkdir(parents=True, exist_ok=True)
                said = 'Breaking: no\n' if gate == 'arch' else ''
                path.write_text(f'Verdict: {verdict}\nGate: {gate}\nItem: I-1\nPR: acme/app#42\nHead: {head(i)}\n'
                                f'Confidence: high\n{said}\n## Findings\nnone\n')
                ws.record(root, 'attest', {'path': str(path.relative_to(root)),
                                           'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                           'gate': gate, 'item': 'I-1', 'head': head(i), 'verdict': verdict})
        before = len(calls)
        found = [g['text'] for g in evidence.gate_gaps(root, 'acme/app', 'I-1', GATES, head(n - 1), ref='acme/app#42')]
        print(f'{shape} heads={n} verdicts={k} calls={len(calls) - before} distinct={len(set(calls[before:]))} gaps={found}')
        shutil.rmtree(root)
