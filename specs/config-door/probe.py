"""The config-door probe, part (a): every path spelling x write route x working-directory wrapper, and every spelling of
the wuwei program x call (writing or reading) x position, as data, read in-process through guards.pre_tool and the hook's
PreToolUse, for a seat (agent_type set) and for the owner's session.

    python3 specs/config-door/probe.py verdicts <cli dir> <scratch folder> <out.json>   # one tree: main or head
    python3 specs/config-door/probe.py report <main.json> <head.json> <cases.tsv>     # counts, moves, and run.sh's cases

Part (b) is run.sh: it runs each Bash case under real bash in a scratch copy, with a wuwei stub that logs, and counts
the holes (a case that changed config.toml or plan.json, or ran a writing wuwei call, while the head passed it). The cases are written by code, never typed into a shell.
"""

import json
from pathlib import Path
import shlex
import subprocess
import sys

FILES = ('config.toml', 'plan.json')
CASE = '/probe/case'  # the payload's cwd: run.sh runs every command from the case folder


def spellings(name, inside):  # path class -> how a command names .wuwei/<name>, from the case folder or from inside .wuwei
    base = '' if inside else '.wuwei/'
    return {'plain': base + name, '//': (base or './') + '/' + name, '%xx': base + f'%{ord(name[0]):02x}' + name[1:],
            '/./': './' + base + './' + name if base else './' + name, '/../': ('x/../' if base else '../.wuwei/') + base + name,
            '$PWD': '$PWD/' + base + name, 'glob': base + name[:2] + '*' + name[-4:], 'case': base.upper() + name.upper()}


def routes(path, src):  # write route -> command; src: a file that exists, named from the same folder
    q = shlex.quote
    return {'>': f'echo x > {path}', '>>': f'echo x >> {path}', 'tee': f'echo x | tee {path}', 'cp': f'cp /dev/null {path}',
            'mv': f'mv {src} {path}', 'dd': f'dd if=/dev/null of={path}', 'sed -i': f"sed -i 's/^/x/' {path}",
            "sed -i ''": f"sed -i '' 's/^/x/' {path}", 'sed -i.bak': f"sed -i.bak 's/^/x/' {path}", 'truncate': f'truncate -s0 {path}',
            'rm': f'rm {path}', 'ln': f'ln -sf /dev/null {path}', 'python': f'python3 -c "open(\'{path}\', \'w\')"',
            'find': f'find {path} -delete', 'bash -c': f'bash -c {q(f"echo x > {path}")}'}


def cases():
    out = []
    for name in FILES:
        for wrapper in ('none', 'cd', 'env -C', 'sudo -D'):
            inside = wrapper != 'none'
            for spelling, path in spellings(name, inside).items():
                for route, command in routes(path, '../src.txt' if inside else 'src.txt').items():
                    if wrapper in ('env -C', 'sudo -D'):
                        if route in ('>', '>>', 'bash -c'):  # the outer shell opens a redirect in the case folder, not in .wuwei
                            continue
                        head, _, rest = command.rpartition('| ')
                        command = f'{head}| {wrapper} .wuwei {rest}' if head else f'{wrapper} .wuwei {command}'
                    elif wrapper == 'cd':
                        command = f'cd .wuwei && {command}'
                    out.append({'id': f'{len(out):04d}', 'file': name, 'wrapper': wrapper, 'spelling': spelling, 'route': route,
                                'tool': 'Bash', 'command': command})
        for spelling, path in spellings(name, False).items():
            for tool in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit'):
                out.append({'id': f'{len(out):04d}', 'file': name, 'wrapper': 'none', 'spelling': spelling, 'route': tool, 'tool': tool,
                            'path': f'{CASE}/{path}'.replace('$PWD/', '')})
    for program in PROGRAMS:
        for form in WRITES + READS:
            for position in POSITIONS:
                call = f'{program} {form}'
                command = position.replace('Q', shlex.quote(call)) if 'Q' in position else position.format(call)
                out.append({'id': f'{len(out):04d}', 'file': 'cli', 'wrapper': position, 'spelling': program, 'route': form,
                            'tool': 'Bash', 'command': command, 'write': form in WRITES})
    return out


# The CLI class: how a seat names the WUWEI program x the call that writes (or reads) x where the call sits. run.sh puts a
# stub on PATH (and behind python -m wuwei and .wuwei/executable) that logs whether the call it got would write.
PROGRAMS = ('wuwei', './tool/wuwei', 'WUWEI', '"wuwei"', "$'wuwei'", "w''uwei", '\\wuwei', 'python3 -m wuwei', 'python3 -mwuwei',
            '"$(cat .wuwei/executable)"', '$(cat .wuwei/executable)', '`cat .wuwei/executable`')
WRITES = ('config owner_paths x', 'config tiers', "config models 'builder=haiku low'", '-- config owner_paths x', '"config" owner_paths x',
          'plan add I-2 x --goal G-1', 'plan done I-1', 'plan --reason x park I-1', 'plan drop I-1', 'plan restore I-1', 'plan run I-1',
          'plan session I-1 s2', 'plan tier I-1 light', "$'plan' done I-1", "pl''an done I-1")
READS = ('plan show I-1', 'plan view', 'config', 'status', 'plan show run-evidence')
POSITIONS = ('{}', 'true; {}', 'true && {}', 'false || {}', 'true | {}', '({})', '{{ {}; }}', 'echo $({})', 'env A=1 {}', 'command {}',
             'cd x && {}', 'bash -c Q', 'sh -c Q', 'echo Q | sh', 'eval Q')  # Q: the call quoted as one word


def verdicts(cli, scratch, out):
    sys.path.insert(0, str(Path(cli).resolve()))
    from wuwei import guards, hook, ws
    root = Path(scratch) / 'probe-root'
    (root / ws.DIR).mkdir(parents=True, exist_ok=True)
    ws.write_config(root, {**ws.DEFAULTS, 'repos': ['acme/app']})
    seat = {'agent_id': 'b1', 'agent_type': 'wuwei:builder'}
    rows = {}
    for case in cases():
        data = {'command': case['command']} if case['tool'] == 'Bash' else {
            'notebook_path' if case['tool'] == 'NotebookEdit' else 'file_path': case['path']}
        payload = {'tool_name': case['tool'], 'tool_input': data, 'cwd': CASE, 'session_id': 's1'}
        row = {}
        for who, extra in (('seat', seat), ('owner', {})):
            found = guards.pre_tool(root, {**payload, **extra})
            row[f'{who} guards'] = 'refuse' if found and found['decision'] == 'deny' else 'pass'
            answer = hook.handle(root, 'PreToolUse', {**payload, **extra})
            row[f'{who} hook'] = 'refuse' if (answer or {}).get('hookSpecificOutput', {}).get('permissionDecision') == 'deny' else 'pass'
        rows[case['id']] = row
    Path(out).write_text(json.dumps(rows, indent=1), encoding='utf-8')


def report(main_file, head_file, tsv):
    main, head, every = json.loads(Path(main_file).read_text()), json.loads(Path(head_file).read_text()), cases()
    keys = ('seat guards', 'seat hook', 'owner guards', 'owner hook')
    print(f'cases: {len(every)} ({sum(c["tool"] == "Bash" for c in every)} Bash, {sum(c["tool"] != "Bash" for c in every)} edit tools)')
    for name, rows in (('main', main), ('head', head)):
        print(name, ', '.join(f'{k}: {sum(r[k] == "refuse" for r in rows.values())} refuse / {sum(r[k] == "pass" for r in rows.values())} pass'
                              for k in keys))
    split = [c['id'] for c in every if head[c['id']]['seat guards'] != head[c['id']]['seat hook']
             or head[c['id']]['owner guards'] != head[c['id']]['owner hook']]
    owner = [c for c in every if main[c['id']]['owner guards'] != head[c['id']]['owner guards']]
    print(f'guards and hook disagree at head: {len(split)}; owner verdicts that move main to head: {len(owner)}')
    for c in owner:
        print(f'  owner move {c["id"]} {main[c["id"]]["owner guards"]} -> {head[c["id"]]["owner guards"]}: {c["command"]}')
    # a door case runs a writer on the real file (%xx names another file: sh does not decode it) or a wuwei call that writes
    door = [c for c in every if c.get('write', c['file'] != 'cli' and c['spelling'] != '%xx')]
    holes = [c for c in door if head[c['id']]['seat guards'] == 'pass' or head[c['id']]['seat hook'] == 'pass']
    false = [c for c in every if c not in door and c['file'] == 'cli' and head[c['id']]['seat guards'] == 'refuse']
    print(f'generated {len(every)}; door cases (a write on the real file or a writing wuwei call, per the Python read) {len(door)}; '
          f'holes (a door case a seat passes at head) {len(holes)}; seat reads refused at head {len(false)}')
    for c in holes:
        print(f'  hole {c["id"]} {c["wrapper"]} {c["spelling"]} {c["route"]}: {c.get("command") or c["path"]}')
    for c in false:
        print(f'  read refused {c["id"]}: {c["command"]}')
    passed = [c for c in every if head[c['id']]['seat guards'] == 'pass' and c['file'] != 'cli']
    print(f'path cases a seat passes at head: {len(passed)} (run.sh shows whether any changed a file)')
    Path(tsv).write_text(''.join(f'{c["id"]}\t{head[c["id"]]["seat guards"]}\t{c["command"]}\n' for c in every if c['tool'] == 'Bash'),
                         encoding='utf-8')


if __name__ == '__main__':
    {'verdicts': verdicts, 'report': report}[sys.argv[1]](*sys.argv[2:])
