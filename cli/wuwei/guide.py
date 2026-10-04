"""The plugin reference a session reads at start, generated from the CLI's own tables (#476).
Never imported on a hook path: SessionStart only points at `wuwei guide`."""

import argparse
import hashlib
from importlib import import_module
import pkgutil

from wuwei import commands, integrity, memory, shell, workspace
from wuwei.commands import next as next_command
from wuwei.guards import protect_state

START, END = '<!-- wuwei:guide:start -->', '<!-- wuwei:guide:end -->'
# The commands that print an AskUserQuestion widget or the questions to ask (#359);
# tests/test_guide.py pins this to every parser that defines --widget.
WIDGETS = ('decision show D-n --widget', 'mcp check --widget', 'doctor --fix --widget',
           'close --widget', 'consolidate --widget', 'telemetry proposals --widget',
           'plan gate', 'calibrate --questions', 'drafts show <id> --widget')
# Paths under .wuwei/; <date> is today.
RECORDS = (
    ('`config.toml`', '`setup`, `config set`, `config add-repo` (owner)'),
    ('`days/<date>/state.json`, `events.jsonl`', 'the CLI'),
    ('`days/<date>/plan.md`', '`plan propose`'),
    ('`days/<date>/briefs/`', '`brief`'),
    ('gate verdicts, in `state.json`', '`dispatch receive`'),
    ('`days/<date>/decisions/`', '`decision`'),
    ('`days/<date>/report.md`', '`report`'),
    ('`days/<date>/retro/`', '`retro`'),
    ('`memory/`', '`note`, `promote`'),
)


def text():
    """The reference: no workspace data and no absolute path, so agent.md prints the same text."""
    from wuwei.__main__ import GROUPS
    parser = argparse.ArgumentParser(prog='wuwei')
    subparsers = parser.add_subparsers()
    for module in pkgutil.iter_modules(commands.__path__, commands.__name__ + '.'):
        if not module.name.rsplit('.', 1)[-1].startswith('_'):
            import_module(module.name).register(subparsers)
    helps = {action.dest: action.help or '' for action in subparsers._choices_actions}
    listed = [name for heading, names in GROUPS if heading.startswith(('Daily', 'Recovery'))
              for name in names.split() if name in helps]
    read = sorted(f'{path} {commands._NEEDS[path]}' if path in commands._NEEDS else path
                  for path in commands.READ_ONLY)
    owner = sorted(' '.join(pair).strip() for pair in protect_state._OWNER_ACTIONS)
    cd = shell.WORKSPACE_ROOT.removeprefix('workspace guard: ')
    postures = tuple(workspace.POSTURES)
    lines = [
        'WUWEI plugin reference, generated from the plugin tables; `wuwei guide` prints it.',
        'Run `wuwei next` and do the step it names; run every action a command returns unchanged.',
        '',
        '## Commands the session runs',
        f'{next_command.EXECUTABLE}. Exit 0 is clean, 1 is a finding to resolve with the owner, '
        '2 means it could not run: show the reason and stop that path.',
        *(f'- {name}: {helps[name]}' for name in listed),
        f'Read-only, never refused: {", ".join(read)}, and --help on any command.',
        '',
        '## Owner only: ask the owner to run these in a host terminal',
        ', '.join(owner) + '.',
        '',
        '## Command forms',
        '- One plain command per Bash call.',
        f'- Variables, loops, pipes or substitutions: {shell.UNPARSED.removeprefix("unparsed: ")}.',
        f'- {cd[:1].upper()}{cd[1:]}.',
        '- Python only with -P; the CLI also runs as python3 -P -m wuwei.',
        '',
        '## Records and questions',
        f'- {protect_state._STATE_HINT}',
        '- The workflow writes the records through the CLI; the owner answers cards and never edits a file.',
        '- Ask the owner with AskUserQuestion, using the widget a command prints unchanged: '
        + ', '.join(f'`wuwei {entry}`' for entry in WIDGETS) + '. Record the answer with the '
        "widget's `record` command; when it runs in a host terminal, show the owner that line. Without "
        'AskUserQuestion (a headless run), write the decision record and run `wuwei decision route D-n` '
        'so it reaches the DM.',
        '',
        '## Guard areas by posture',
        '| Area | ' + ' | '.join(postures) + ' |',
        '| --- |' + ' --- |' * len(postures),
        *(f'| {area} | ' + ' | '.join(workspace.POSTURES[p][area] for p in postures) + ' |'
          for area in workspace.AREAS),
        '',
        'Floors in every posture: ' + ', '.join(f'{area} {level}' for area, level in workspace.FLOORS.items())
        + '; the owner-only commands are refused in every posture. A refusal names its reason and the '
        'accepted form and ends with a `posture:` line: use that form, never a way around it.',
        '',
        '## Where records live',
        'Paths are under `.wuwei/`; `<date>` is today.',
        '',
        '| Record | Written by |',
        '| --- | --- |',
        *(f'| {record} | {writer} |' for record, writer in RECORDS),
    ]
    return '\n'.join(lines) + '\n'


def export(root, write=True, raw=None):
    """Write the stamped reference block into the memory.export_to file. (path, changed)."""
    body = text()
    stamp = (f'<!-- generated by wuwei init from the plugin tables: plugin {integrity.version()}, '
             f'tables {hashlib.sha256(body.encode()).hexdigest()[:12]}; edits here are overwritten -->')
    block = '\n'.join([START, stamp, body.rstrip('\n'), END]) + '\n'
    return memory.write_block(root, START, END, block, 'bin/wuwei init --upgrade', write, raw)
