"""The canary-guard probe, part (a): every path class x working-directory wrapper x write route on .wuwei/canary, read
in-process through guards.pre_tool and the hook's PreToolUse at one tree, each beside the same case on .wuwei/ledger.jsonl.

    python3 -I specs/canary-guard/probe.py verdicts <cli dir> <scratch folder> <out.json>   # one tree: main or head
    python3 -I specs/canary-guard/probe.py report <main.json> <head.json> <cases.tsv>     # counts, moves, run.sh's cases

Part (b) is run.sh, for the owner: it runs each Bash case under real bash in a scratch case folder and counts the cases
whose write reached the canary file, and the holes (such a case the head passes). Cases are written by code, never typed.
"""

import json
from pathlib import Path
import sys

CASE = '/probe/case'  # the payload's cwd; run.sh runs every command from its case folder
CLASSES = {'plain': '.wuwei/canary', '//': '.wuwei//canary', '%xx': 'x%2F/../.wuwei/canary', '/./': './.wuwei/./canary',
           '/../': 'x/../.wuwei/canary', '%xx name': '.wuwei/%63anary'}  # sh never decodes %xx: the last names another file
WRAPPERS = {'none': '{}', 'cd': 'cd src && {}', 'env -C': 'env -C src {}', 'sudo -D': 'sudo -D src {}', 'cd .wuwei': 'cd .wuwei && {}',
            'env -C .wuwei': 'env -C .wuwei {}'}
ROUTES = {'>': 'echo x > {}', '>>': 'echo x >> {}', 'tee': 'tee {} < /dev/null', 'cp': 'cp /dev/null {}', 'mv': 'mv {src} {}',
          'rm': 'rm {}', 'dd': 'dd if=/dev/null of={}', 'sed -i': "sed -i.bak 's/^/x/' {}", 'truncate': 'truncate -s0 {}',
          'chmod': 'chmod 000 {}', 'ln': 'ln -sf /dev/null {}', 'python': 'python3 -c "open(\'{}\', \'w\')"',
          'find': 'find {} -delete', 'bash -c': "bash -c 'echo x > {}'", 'multi-line': 'true\necho x > {}'}


INSIDE = {'plain': 'canary', '//': './/canary', '%xx': 'x%2F/../canary', '/./': '././canary', '/../': '../.wuwei/canary',
          '%xx name': '%63anary'}  # the same classes named from inside .wuwei


def cases():
    out = []
    for kind, spelling in CLASSES.items():
        for wrapper, shape in WRAPPERS.items():
            path = INSIDE[kind] if wrapper.endswith('.wuwei') else spelling if wrapper == 'none' else '../' + spelling
            src = 'a.txt' if wrapper == 'none' else '../a.txt'
            for route, form in ROUTES.items():
                command = shape.format(form.format(path, src=src))
                out.append({'id': f'{len(out):04d}', 'class': kind, 'wrapper': wrapper, 'route': route, 'tool': 'Bash',
                            'command': command, 'door': kind != '%xx name'})
        for tool in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit'):
            out.append({'id': f'{len(out):04d}', 'class': kind, 'wrapper': 'none', 'route': tool, 'tool': tool,
                        'path': f'{CASE}/{spelling}', 'door': kind != '%xx name'})
    return out


def payload(case, name):
    swap = lambda text: text.replace('canary', name).replace('%63anary', '%63anary' if name == 'canary' else '%6cedger.jsonl')
    data = {'command': swap(case['command'])} if case['tool'] == 'Bash' else {
        'notebook_path' if case['tool'] == 'NotebookEdit' else 'file_path': swap(case['path'])}
    return {'tool_name': case['tool'], 'tool_input': data, 'cwd': CASE, 'session_id': 's1', 'agent_id': 'b1', 'agent_type': 'wuwei:builder'}


def verdicts(cli, scratch, out):
    sys.path.insert(0, str(Path(cli).resolve()))
    from wuwei import guards, hook, ws
    root = Path(scratch) / 'probe-root'
    (root / ws.DIR).mkdir(parents=True, exist_ok=True)
    ws.write_config(root, {**ws.DEFAULTS, 'repos': ['acme/app']})
    rows = {}
    for case in cases():
        row = {}
        for name in ('canary', 'ledger.jsonl'):
            found = guards.pre_tool(root, payload(case, name))
            row[f'{name} guards'] = found['decision'] if found else 'pass'
            answer = (hook.handle(root, 'PreToolUse', payload(case, name)) or {}).get('hookSpecificOutput', {})
            row[f'{name} hook'] = answer.get('permissionDecision') or 'pass'
        rows[case['id']] = row
    Path(out).write_text(json.dumps(rows, indent=1), encoding='utf-8')


def report(main_file, head_file, tsv):
    main, head, every = json.loads(Path(main_file).read_text()), json.loads(Path(head_file).read_text()), cases()
    door = [c for c in every if c['door']]
    print(f'generated {len(every)} ({sum(c["tool"] == "Bash" for c in every)} Bash, {sum(c["tool"] != "Bash" for c in every)} edit tools); '
          f'door cases (a write that resolves to .wuwei/canary) {len(door)}')
    for name, rows in (('main', main), ('head', head)):
        print(name, ', '.join(f'{k}: {sum(r[k] == "deny" for r in rows.values())} deny' for k in rows[every[0]['id']]))
    holes = [c for c in door if 'pass' in (head[c['id']]['canary guards'], head[c['id']]['canary hook'])]
    split = [c for c in every if head[c['id']]['canary guards'] != head[c['id']]['ledger.jsonl guards']]
    moved = [c for c in every if main[c['id']]['ledger.jsonl guards'] != head[c['id']]['ledger.jsonl guards']]
    print(f'holes (a door case the head passes) {len(holes)}; canary and ledger verdicts differ at head {len(split)}; '
          f'ledger verdicts that move main to head {len(moved)}')
    for c in holes + split + moved:
        print(f'  {c["id"]} {c["class"]} | {c["wrapper"]} | {c["route"]}: {c.get("command") or c["path"]!r} {head[c["id"]]}')
    Path(tsv).write_text(''.join(f'{c["id"]}\t{head[c["id"]]["canary guards"]}\t{int(c["door"])}\t{json.dumps(c["command"])}\n'
                                 for c in every if c['tool'] == 'Bash'), encoding='utf-8')


if __name__ == '__main__':
    {'verdicts': verdicts, 'report': report}[sys.argv[1]](*sys.argv[2:])
