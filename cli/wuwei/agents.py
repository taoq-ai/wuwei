"""The role agents, generated from the charters: the charters are the one source."""

import json
from pathlib import Path

DESCRIPTIONS = {
    'lead': 'Discovery, scope, tier and ranked candidates for a WUWEI plan pass.',
    'builder': 'Builds one WUWEI plan item test first in its own branch and worktree.',
    'shepherd': 'Owns WUWEI pull requests from raise to merge, with reviewers, threads, CI and conflicts.',
    'steward': 'Reads the WUWEI day at a close and writes the retro with the smallest rule changes.',
    'sentinel-arch': 'Independent WUWEI architecture gate for one item at one head.',
    'sentinel-quality': 'Independent WUWEI quality gate for one item at one head.',
    'sentinel-security': 'Independent WUWEI security gate for one item at one head.',
    'sentinel-goal': 'Independent WUWEI goal gate for one item at one head.',
}
AUTHORING = {'lead', 'builder', 'shepherd', 'steward'}
# charters/planner.md "Model and effort": per role the default (''), the setting at a tier, on those paths, or for a conflict.
PATHS, CONFLICT = 'on risky, owner or contract paths', 'for a conflict where both sides changed logic'
TABLE = {'lead': {'': 'Opus 5.5 xhigh'}, 'sentinel-arch': {'': 'Opus 5.5 high'}, 'sentinel-goal': {'': 'Sonnet 5.5 high'},
         'steward': {'': 'Opus 5.5 high'}, 'shepherd': {'': 'Sonnet 5.5 medium', CONFLICT: 'Opus 5.5 high'},
         'builder': {'': 'Opus 5.5 medium', 'light': 'Sonnet 5.5 medium', 'full': 'Opus 5.5 high', PATHS: 'Opus 5.5 high'},
         'sentinel-security': {'': 'Opus 5.5 high', 'full': 'Opus 5.5 xhigh', PATHS: 'Opus 5.5 xhigh'},
         'sentinel-quality': {'': 'Sonnet 5.5 high', 'full': 'Opus 5.5 high', PATHS: 'Opus 5.5 high'}}


def render(plugin, role, tools):
    charters = Path(plugin) / 'charters'
    parts = ['_common.md'] + (['_common-authoring.md'] if role in AUTHORING else ['_gate.md']) + [f'{role}.md']
    body = '\n\n'.join((charters / part).read_text(encoding='utf-8').strip() for part in parts)
    name, effort = TABLE[role][''].rsplit(' ', 1)
    model = f'model: claude-{name.lower().replace(" ", "-").replace(".", "-")}\neffort: {effort}\n'
    return (f'---\nname: {role}\ndescription: {DESCRIPTIONS[role]}\ntools: {", ".join(tools)}\n{model}---\n\n'
            f'<!-- Generated from charters/ by wuwei agents build; edit the charters, not this file. -->\n\n{body}\n')


def render_codex(plugin, role):
    """A Codex agent role (.codex/agents/<role>.toml) with the same charter text as its instructions.
    No model: Codex chooses its own, and a Claude model name would not resolve there."""
    body = render(plugin, role, []).split('-->\n\n', 1)[1]
    return ('# Generated from charters/ by wuwei init --codex; edit the charters, not this file.\n'
            f'name = {json.dumps(role)}\ndescription = {json.dumps(DESCRIPTIONS[role])}\n'
            f"developer_instructions = '''\n{body}'''\n")


def _grants(plugin):
    return json.loads((Path(plugin) / 'agents' / 'allowlist.json').read_text(encoding='utf-8'))


def build(plugin):
    for role, tools in _grants(plugin).items():
        (Path(plugin) / 'agents' / f'{role}.md').write_text(render(plugin, role, tools), encoding='utf-8')


def stale(plugin):
    base = Path(plugin) / 'agents'
    return [role for role, tools in _grants(plugin).items() if not (base / f'{role}.md').is_file()
            or (base / f'{role}.md').read_text(encoding='utf-8') != render(plugin, role, tools)]
