"""#552: walk the register of people, channels and tools; read-only."""

import json
import sys

from wuwei import graph, outward, workspace
from wuwei.exits import CLEAN, FINDINGS, UNRUN

ROUTINE = 'tests passed'  # A routine status reply: what the tier table and the umbrella decide alone.
TIERS = {'send': 'send', 'draft': 'ask', 'block': 'block'}


def register(subparsers):
    parser = subparsers.add_parser('who', help='Show a person, channel, connector or login, its edges and its tier')
    parser.add_argument('name', help='a node id, a channel or user id, a name, a login or an MCP tool name')
    parser.add_argument('--json', action='store_true', help='print a JSON list for the planner')
    parser.set_defaults(func=run)


def _tier(root, config, register, node, tool):
    """(label, tier, rule) of a routine message at node, or None where no tier applies."""
    kind, _, rest = node.partition(':')
    if kind == 'channel':
        call = ('a routine message here', 'slack', {'channel': rest}, None)
    elif node.startswith('person:slack:'):
        call = ('a routine direct message', 'slack', {'channel': rest.partition(':')[2]}, None)
    elif kind == 'address' or node.startswith('person:email:'):
        call = ('a routine mail', 'mail', {'recipients': [rest.rpartition(':')[2]]}, None)
    elif kind == 'connector':
        sends = next((edge['to'] for edge in graph.related(register, node)
                      if edge['from'] == node and edge['type'] == 'sends_through'), 'other')
        call = ('a routine write through it', sends, {}, tool if tool and tool.startswith('mcp__') else f'mcp__{rest}__send')
    elif kind == 'login' or node.startswith('person:github:'):
        login = 'login:' + rest.rpartition(':')[2]
        person = next((edge['to'] for address in [edge['from'] for edge in register['edges']
                                                  if edge['to'] == login and edge['type'] == 'maps_to']
                       for edge in register['edges']
                       if edge['from'] == address and edge['to'].startswith('person:slack:')), None)
        if person is None:
            return 'no tier here', None, 'the pull request rules decide on the code host'
        label, tier, rule = _tier(root, config, register, person, None)
        return f'{label} to {person}', tier, rule
    else:
        return None
    label, kind, context, tool = call
    why = []
    code, decision = outward.classify(ROUTINE, root, config, context, kind=kind, why=why, tool=tool)
    return label, TIERS[decision] if code != UNRUN else 'unknown', why[0] if why else None


def _about(register, node):
    """A person's name and classes, for the people line of a channel."""
    classes = [edge['to'] for edge in graph.related(register, node) if edge['from'] == node and edge['type'] == 'class']
    return ', '.join(filter(None, [register['nodes'][node].get('name'), *classes]))


def run(args):
    try:
        root = workspace.find_workspace()
        config = workspace.load_config(root)
        register = graph.load(root)
    except (OSError, ValueError) as exc:
        print(f'wuwei who: {exc}', file=sys.stderr)
        return UNRUN
    if register is None:
        print(f'wuwei who: no .wuwei/{graph.NAME}; run bin/wuwei init --upgrade', file=sys.stderr)
        return FINDINGS
    found = graph.find(register, args.name)
    if not found:
        print(f'wuwei who: no node {args.name} in .wuwei/{graph.NAME}; people and channels are learned '
              'with bin/wuwei outbound learn', file=sys.stderr)
        return FINDINGS
    rows, lines = [], []
    for node in found:
        name = register['nodes'][node].get('name')
        edges = graph.related(register, node)
        tier = _tier(root, config, register, node, args.name)
        rows.append({'node': node, 'name': name, 'edges': edges,
                     'tier': tier and tier[1], 'rule': tier and tier[2]})
        lines.append(node + (f' ({name})' if name else ''))
        lines += [f"class {edge['to']} ({edge['view']})" for edge in edges
                  if edge['from'] == node and edge['type'] == 'class' and 'view' in edge]
        members = [edge['from'] for edge in edges if edge['to'] == node and edge['type'] == 'member_of'
                   and edge['from'].startswith('person:')]
        if members:
            lines.append('people: ' + ', '.join(f'{person} ({_about(register, person)})' for person in members))
        if tier:
            lines.append(f'{tier[0]}: {tier[1]}' + (f' ({tier[2]})' if tier[2] else '') if tier[1]
                         else f'{tier[0]}: {tier[2]}')
        lines += [f'edge: {graph.line(edge)}' for edge in edges]
        if node.startswith('login:'):  # The chat person a login maps to, through its address.
            addresses = {edge['from'] for edge in edges if edge['type'] == 'maps_to'}
            lines += [f'edge: {graph.line(edge)}' for edge in register['edges']
                      if edge['from'] in addresses and edge not in edges]
    print(json.dumps(rows, indent=2) if args.json else '\n'.join(lines))
    return CLEAN
