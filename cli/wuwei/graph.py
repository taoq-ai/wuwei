"""#552: the register of people, channels and tools, .wuwei/graph.json. The config sections it
models are views over it: config.offer and init --upgrade write both from the same text, the
guards keep reading config.toml. An explanation record, never a guard input: no hook imports it."""

import json
from pathlib import Path
import re
import sys

from wuwei.outward import SLACK_SHAPE

NAME = 'graph.json'
TYPES = ('member_of', 'class', 'sends_through', 'mode', 'maps_to', 'reviews')
VIEWS = ('outbound.people', 'outbound.channel_classes', 'outbound.work_channels', 'outbound.external_channels',
         'outbound.owner.slack.user', 'outbound.owner.slack.dm', 'outbound.owner.mail', 'outbound.owner.code_host',
         'outward.servers', 'outward.modes', 'outward.classes', 'shepherd.authors', 'owner.handles',
         'voice.sources', 'repos.shepherd.reviewers')
COMMENT = ('# A view of .wuwei/graph.json: bin/wuwei config set and the cards write both; '
           'bin/wuwei who walks it.')
TABLES = ('owner', 'voice.sources', 'outward.servers', 'outward.modes', 'outward.classes', 'outbound',
          'outbound.people', 'outbound.channel_classes', 'outbound.owner', 'outbound.owner.slack',
          'shepherd.authors')
FIX = 'move .wuwei/graph.json aside and run bin/wuwei init --upgrade'
# The owner's identity per channel: (view key, path in outbound.owner, node prefix).
OWNER = (('outbound.owner.slack.user', ('slack', 'user'), 'person:slack:'),
         ('outbound.owner.slack.dm', ('slack', 'dm'), 'channel:'),
         ('outbound.owner.mail', ('mail',), 'address:'),
         ('outbound.owner.code_host', ('code_host',), 'login:'))


def sections(config):
    """{view key: value} as the loaded config holds them."""
    outbound, owner = config['outbound'], config['outbound']['owner']
    found = {'outbound.people': outbound['people'], 'outbound.channel_classes': outbound['channel_classes'],
             'outbound.work_channels': outbound['work_channels'],
             'outbound.external_channels': outbound['external_channels'],
             'outward.servers': config['outward']['servers'], 'outward.modes': config['outward']['modes'],
             'outward.classes': config['outward']['classes'], 'shepherd.authors': config['shepherd']['authors'],
             'owner.handles': config['owner']['handles'], 'voice.sources': config['voice']['sources'],
             'repos.shepherd.reviewers': {}}
    for key, path, _ in OWNER:
        found[key] = owner[path[0]][path[1]] if len(path) == 2 else owner[path[0]]
    for repo in config['repos']:
        if repo['shepherd']['reviewers']:
            found['repos.shepherd.reviewers'].setdefault(repo['name'], []).extend(repo['shepherd']['reviewers'])
    return json.loads(json.dumps(found))


def build(config, previous=None, add=(), names=None):
    """The register: view edges from config, then previous's register-only edges, then add."""
    nodes, edges = {}, []

    def edge(source, kind, to, view):
        edges.append({'from': source, 'type': kind, 'to': to, 'view': view})

    found = sections(config)
    for key, entry in found['outbound.people'].items():
        nodes[f'person:{key}'] = {'view': 'outbound.people'}
        for field, kind, prefix in (('email', 'maps_to', 'address:'), ('org', 'member_of', 'org:'),
                                    ('class', 'class', '')):
            if entry[field]:
                edge(f'person:{key}', kind, prefix + entry[field], 'outbound.people')
    for channel, value in found['outbound.channel_classes'].items():
        edge(f'channel:{channel}', 'class', value, 'outbound.channel_classes')
    for key, value in (('outbound.work_channels', 'team'), ('outbound.external_channels', 'client')):
        for channel in found[key]:
            edge(f'channel:{channel}', 'class', value, key)
    for key, _, prefix in OWNER:
        if found[key]:
            edge('person:owner', 'maps_to', prefix + found[key], key)
    for key, kind in (('outward.servers', 'sends_through'), ('outward.modes', 'mode'), ('outward.classes', 'class')):
        for server, value in found[key].items():
            edge(f'connector:{server}', kind, value, key)
    for address, entry in found['shepherd.authors'].items():
        nodes[f'address:{address}'] = {'view': 'shepherd.authors'}
        for prefix, value in (('login:', entry['login']), ('person:slack:', entry['mention'])):
            if value:
                edge(f'address:{address}', 'maps_to', prefix + value, 'shepherd.authors')
    for handle in found['owner.handles']:
        prefix = 'person:slack:' if re.fullmatch(SLACK_SHAPE['user'], handle) else 'login:'
        edge('person:owner', 'maps_to', prefix + handle, 'owner.handles')
    for audience, channels in found['voice.sources'].items():
        nodes[f'voice:{audience}'] = {'view': 'voice.sources'}
        for channel in channels:
            edge(f'channel:{channel}', 'member_of', f'voice:{audience}', 'voice.sources')
    for repo, logins in found['repos.shepherd.reviewers'].items():
        for login in logins:
            edge(f'login:{login}', 'reviews', f'repo:{repo}', 'repos.shepherd.reviewers')
    for extra in [*((previous or {}).get('edges', [])), *add]:
        if 'view' not in extra and extra not in edges:
            edges.append(dict(extra))
    for item in edges:
        for end in (item['from'], item['to']):
            if ':' in end:
                nodes.setdefault(end, {})
    for node, attrs in nodes.items():
        name = (names or {}).get(node) or (previous or {}).get('nodes', {}).get(node, {}).get('name')
        if name:
            attrs['name'] = name
    return {'version': 1, 'nodes': nodes, 'edges': edges}


def views(register):
    """{view key: value} computed from the register, in the loaded config's shape."""
    found = {key: [] if key in ('outbound.work_channels', 'outbound.external_channels', 'owner.handles')
             else '' if key.startswith('outbound.owner.') else {} for key in VIEWS}
    for node, attrs in register['nodes'].items():
        if attrs.get('view') == 'outbound.people':
            found['outbound.people'][node[7:]] = {'email': '', 'org': '', 'class': ''}
        elif attrs.get('view') == 'shepherd.authors':
            found['shepherd.authors'][node[8:]] = {'login': '', 'mention': ''}
        elif attrs.get('view') == 'voice.sources':
            found['voice.sources'][node[6:]] = []
    for edge in register['edges']:
        view, source, to = edge.get('view'), edge['from'], edge['to']
        rest = source.partition(':')[2]
        if view == 'outbound.people':
            field = {'maps_to': 'email', 'member_of': 'org', 'class': 'class'}[edge['type']]
            found[view][rest][field] = to.partition(':')[2] if field != 'class' else to
        elif view == 'outbound.channel_classes' or view in ('outward.servers', 'outward.modes', 'outward.classes'):
            found[view][rest] = to
        elif view in ('outbound.work_channels', 'outbound.external_channels'):
            found[view].append(rest)
        elif view and view.startswith('outbound.owner.'):
            found[view] = to.removeprefix(dict((k, p) for k, _, p in OWNER)[view])
        elif view == 'shepherd.authors':
            field = 'login' if to.startswith('login:') else 'mention'
            found[view][rest][field] = to.removeprefix('login:').removeprefix('person:slack:')
        elif view == 'owner.handles':
            found[view].append(to.removeprefix('person:slack:') if to.startswith('person:slack:')
                               else to.removeprefix('login:'))
        elif view == 'voice.sources':
            found[view][to[6:]].append(rest)
        elif view == 'repos.shepherd.reviewers':
            found[view].setdefault(to[5:], []).append(rest)
    return found


def drift(register, config):
    """The view keys where the register and config.toml differ."""
    have, want = views(register), sections(config)
    return [key for key in VIEWS if have[key] != want[key]]


def _path(root):
    return Path(root) / '.wuwei' / NAME


def load(root):
    """The register, None when missing; ValueError naming the fix when damaged."""
    path = _path(root)
    if path.is_symlink():
        raise ValueError(f'{NAME} is damaged (a symlink); move .wuwei/graph.json aside and run bin/wuwei init --upgrade')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f'{NAME} is damaged ({type(exc).__name__}); move .wuwei/graph.json aside and run bin/wuwei init --upgrade') from None

    def bad(what):
        raise ValueError(f'{NAME} is damaged ({what}); move .wuwei/graph.json aside and run bin/wuwei init --upgrade')

    if not isinstance(data, dict) or set(data) != {'version', 'nodes', 'edges'}:
        bad('not a register')
    if data['version'] != 1 or not isinstance(data['nodes'], dict) or not isinstance(data['edges'], list):
        bad('not version 1')
    for node, attrs in data['nodes'].items():
        if (not re.fullmatch(r'[a-z]+:.+', node) or not isinstance(attrs, dict) or set(attrs) - {'name', 'view'}
                or not isinstance(attrs.get('name', ''), str) or attrs.get('view', VIEWS[0]) not in VIEWS):
            bad(f'invalid node {node!r}')
    for edge in data['edges']:
        if (not isinstance(edge, dict) or not {'from', 'type', 'to'} <= set(edge)
                or set(edge) - {'from', 'type', 'to', 'view', 'card'} or {'view', 'card'} <= set(edge)
                or edge['type'] not in TYPES or not all(isinstance(edge[k], str) for k in ('from', 'to'))
                or edge['from'] not in data['nodes'] or edge.get('view', VIEWS[0]) not in VIEWS
                or not re.fullmatch(r'D-[1-9][0-9]*', edge.get('card', 'D-1'))):
            bad(f'invalid edge {edge!r}')
    return data


def save(root, register):
    from wuwei import workspace
    workspace.atomic_write(_path(root), json.dumps(register, indent=2) + '\n')


def sync(root, config, add=(), names=None):
    """Write the register built from config when it differs; True when written. A damaged
    register raises ValueError and stays as it is."""
    previous = load(root)
    register = build(config, previous, add, names)
    if register == previous:
        return False
    save(root, register)
    return True


def warn(label, exc):
    print(f'wuwei {label}: warning: .wuwei/{NAME} not updated: {exc}; move .wuwei/graph.json aside and run bin/wuwei init --upgrade', file=sys.stderr)


def find(register, name):
    """Node ids named by an id, a bare id, its last part, a name (# or @ optional) or a tool."""
    tool = re.fullmatch(r'mcp__(.+)__[^_].*|tool:([^/]+)/.+', name)
    if tool:
        server = (name[5:].rpartition('__')[0] if name.startswith('mcp__') else tool[2]).casefold()
        return [node for node in register['nodes'] if node.casefold() == f'connector:{server}']
    def match(fold):
        wanted = {fold(name), fold(name.lstrip('#@'))} - {''}
        return [node for node, attrs in register['nodes'].items()
                if wanted & {fold(node), fold(node.partition(':')[2]), fold(node.rpartition(':')[2]),
                             fold(attrs.get('name', ''))}]

    return match(str) or match(str.casefold)  # Ids are case-sensitive, as the guards read them.


def related(register, node):
    return [edge for edge in register['edges'] if node in (edge['from'], edge['to'])]


def cite(register, text, tool=None):
    """The edges that decided a reason: their view key is in the text and their node is named
    in it or is the tool's connector."""
    named = {node for token in text.split() for node in find(register, token.strip('@<>[](),.;:'))
             if token.strip('@<>[](),.;:')}
    if isinstance(tool, str) and tool.startswith('mcp__'):
        named.update(find(register, tool))
    found = []
    for edge in register['edges']:
        if edge.get('view') and re.search(rf'(?<![\w.]){re.escape(edge["view"])}(?![\w.])', text) \
                and edge['from'] in named and edge not in found:
            found.append(edge)
    return found


def line(edge):
    source = (f"({edge['view']})" if 'view' in edge else f"(card {edge['card']})" if 'card' in edge
              else '(learned)')
    return f"{edge['from']} {edge['type']} {edge['to']} {source}"


def annotate(raw):
    """raw with COMMENT above each modeled table header, once."""
    from wuwei import configtext
    lines, items = configtext.entries(raw)
    at = {start for kind, path, start, _ in items
          if kind == 'table' and all(isinstance(p, str) for p in path) and '.'.join(path) in TABLES
          and not (start and lines[start - 1].rstrip('\r\n') == COMMENT)}
    nl = '\r\n' if '\r\n' in raw else '\n'
    return ''.join((COMMENT + nl if i in at else '') + text for i, text in enumerate(lines))
