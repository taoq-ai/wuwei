"""Mutants of the handback-transcript change, one at a time, each applied to both runtime copies in a fresh copy of the head tree.

python3 -I mutants.py <head tree> <work dir>
"""

import shutil
import subprocess
import sys
from pathlib import Path

MUTANTS = {
    'M1 a payload text the transcript does not hold is taken': (
        "        if not text or text in said:\n", "        if True:\n"),
    'M2 the hand-back attests the payload message': (
        "    problem = isinstance(report, str) and _verdict_problem(root, {**payload, 'last_assistant_message': report}, role)",
        "    problem = report is not False and _verdict_problem(root, {**payload, 'last_assistant_message': str((payload.get('tool_input') or {}).get('message', ''))}, role)"),
    'M3 no report is collected': ("                said.append(found)\n", "                pass\n"),
    'M4 no reread of a transcript still being written': (
        "            if (text in said if text else found.strip()) or not Path(path).is_file():", "            if True:"),
    'M5 the stop keeps the payload text': (
        "    payload = {**payload, 'last_assistant_message': report}", "    payload = {**payload, 'last_assistant_message': text or report}"),
    'M6 the seat transcript is read unconfined': (
        "        for row in transcript_rows(payload.get('agent_transcript_path'), '') or ():",
        "        for row in [json.loads(x) for x in Path(payload.get('agent_transcript_path')).read_text().splitlines()]:"),
    'M7 an unconfirmed launch still reads the transcript': (
        "    if use and any(p.get('id') == use", "    if True or use and any(p.get('id') == use"),
    'M8 the unconfirmed reason always names the launch': (
        "        why = f'the transcript of {role} {agent} does not hold the report its payload carries'\n", ""),
    'M9 no seat transcript derived for PreToolUse': (
        "Path(str(payload.get('transcript_path')).removesuffix('.jsonl'), 'subagents', f'agent-{agent}.jsonl'))", "'')"),
    'M10 an empty report is not linted': ("    problem = isinstance(report, str) and", "    problem = bool(report) and"),
    'M11 the last report replaces a held text': ("            return text or found\n", "            return found\n"),
}


def main(head, work, only=''):
    work = Path(work)
    for name, (old, new) in MUTANTS.items():
        if only and name.split()[0] not in only.split(','):
            continue
        tree = work / name.split()[0]
        shutil.rmtree(tree, ignore_errors=True)
        shutil.copytree(head, tree)
        for copy in (tree / 'cli' / 'wuwei' / 'hook.py', tree / '.claude' / 'wuwei' / 'cli' / 'wuwei' / 'hook.py'):
            text = copy.read_text()
            assert text.count(old) == 1, (name, copy)
            copy.write_text(text.replace(old, new))
        run = subprocess.run(['pytest', '-q', '-p', 'no:cacheprovider', 'tests/test_hook.py', 'tests/test_codex.py'], cwd=tree,
                             capture_output=True, text=True)
        failed = [line.split('::')[1].split(' ')[0] for line in run.stdout.splitlines() if line.startswith('FAILED')]
        print(f"{name}: {'killed' if failed else 'SURVIVED'} ({len(failed)} failed){': ' + ', '.join(failed[:4]) if failed else ''}", flush=True)
        shutil.rmtree(tree)


if __name__ == '__main__':
    main(*sys.argv[1:])
