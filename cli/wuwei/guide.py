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
        next_command.LOOP + ' Run every action a command returns unchanged.',
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
        '- Review comments, threads and the reviewer list: `wuwei pr state <ref>` and '
        '`wuwei pr ping-check <ref>`; use them before writing a loop.',
        f'- Variables, loops, pipes or substitutions: {shell.UNPARSED.removeprefix("unparsed: ")}.',
        f'- {cd[:1].upper()}{cd[1:]}.',
        '- Python only with -P; the CLI also runs as python3 -P -m wuwei.',
        '',
        '## Records and questions',
        f'- {protect_state._STATE_HINT}',
        '- The workflow writes the records through the CLI; the owner answers cards and never edits a file.',
        '- Ask the owner with AskUserQuestion, using the widget a command prints unchanged: '
        + ', '.join(f'`wuwei {entry}`' for entry in WIDGETS) + '. Record the answer with the '
        "widget's `record` command (for example `wuwei calibrate --answer`); when it runs in a host "
        'terminal, show the owner that line. A decision record command that exits non-zero on the '
        'confirmation: run the `record` command `wuwei decision show D-n --widget` prints (`wuwei '
        'decide D-n "<label>" --card <hash>`) without asking the card again. Below strict, never show '
        'the owner a host-terminal command for a card they answered. Without AskUserQuestion (a headless run), write the '
        'decision record and run `wuwei decision route D-n` so it reaches the DM, and keep working '
        'with assume-and-record where the mandate allows. A seat refusal that starts `publish:` and '
        'names `wuwei decision show D-n --widget` is a card: ask it and record the answer; on an '
        'allow answer continue the seat so it runs the same command, on `Keep owner-only` show the '
        "owner the command for a host terminal. Never ask the owner what a seat's mandate lets it "
        'decide: a `negotiation.loop` nudge is a report, and a SubagentStop question note '
        '(`<item>-question-<agent>`) is acknowledged only after its decision record exists.',
        '- With `outbound.owner_channel = "dm"`, also post each digest, nudge and report shown to the '
        "owner to the owner's own DM with the connector's send tool: `outbound.owner.slack.dm`, or "
        '`outbound.owner.slack.user` when `dm` is empty. A held send or refusal that names '
        '`bin/wuwei outbound learn --tool <tool>` (with `--owner <file>`, `--channels`, `--people` or '
        '`--thread <file>`): run it and do what it prints; for a thread, write the replies tool\'s '
        '`channel`, `thread_ts` and `participants` as the JSON file it names.',
        '',
        '## Guard areas by posture',
        '| Area | ' + ' | '.join(postures) + ' |',
        '| --- |' + ' --- |' * len(postures),
        *(f'| {area} | ' + ' | '.join(workspace.POSTURES[p][area] for p in postures) + ' |'
          for area in workspace.AREAS),
        '',
        'Floors in every posture: ' + ', '.join(f'{area} {level}' for area, level in workspace.FLOORS.items())
        + '. Below strict an owner-only action asks the owner on a card the reason names; merges and '
        'approvals stay owner-only. A refusal names its reason and the accepted form, and a levelled '
        'one ends with a `posture:` line: use that form, never a way around it.',
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
