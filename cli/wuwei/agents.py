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
# One gate on a different model than the session's, so the reviews do not share every blind spot.
MODELS = {'sentinel-quality': 'sonnet'}


def render(plugin, role, tools):
    charters = Path(plugin) / 'charters'
    parts = ['_common.md'] + (['_common-authoring.md'] if role in AUTHORING else ['_gate.md']) + [f'{role}.md']
    body = '\n\n'.join((charters / part).read_text(encoding='utf-8').strip() for part in parts)
    model = f'model: {MODELS[role]}\n' if role in MODELS else ''
    return (f'---\nname: {role}\ndescription: {DESCRIPTIONS[role]}\ntools: {", ".join(tools)}\n{model}---\n\n'
            f'<!-- Generated from charters/ by wuwei agents build; edit the charters, not this file. -->\n\n{body}\n')


def _grants(plugin):
    return json.loads((Path(plugin) / 'agents' / 'allowlist.json').read_text(encoding='utf-8'))


def build(plugin):
    for role, tools in _grants(plugin).items():
        (Path(plugin) / 'agents' / f'{role}.md').write_text(render(plugin, role, tools), encoding='utf-8')


def stale(plugin):
    out = []
    for role, tools in _grants(plugin).items():
        path = Path(plugin) / 'agents' / f'{role}.md'
        if not path.is_file() or path.read_text(encoding='utf-8') != render(plugin, role, tools):
            out.append(role)
    return out
