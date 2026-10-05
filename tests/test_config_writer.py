"""Issue #494: config.toml line model and writer for any layout."""

import difflib
from pathlib import Path
import tomllib

import pytest

from wuwei import calibrate, configtext
from wuwei.commands.init import _preserves_values


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / 'templates/workspace/config.toml').read_text()
REPO = '\n[[repos]]\nname = "acme/widget"\npath = "widget"\ndefault_branch = "main"\n'


def check(raw, text, path, key, value, removed=0):
    """text parses, holds value at path.key, keeps every other value and, in order, every line
    of raw but the `removed` lines of the written span."""
    after = tomllib.loads(text)
    assert calibrate._table(after, path)[key] == value
    before = tomllib.loads(raw)
    (calibrate._table(before, path) or {}).pop(key, None)
    assert _preserves_values(before, after)
    old, new = raw.splitlines(), text.splitlines()
    kept = sum(b.size for b in difflib.SequenceMatcher(None, old, new, autojunk=False).get_matching_blocks())
    assert len(old) - kept <= removed


@pytest.mark.parametrize('value', [
    'x', 'a "q" \\ b', 'tab\there\x7fdel \U0001f600', True, 0, -3, 0.5, [], ['a', 'b'], [1, 2], {},
    {'login': 'x'}, {'slack:U1': {'email': 'a@example.test'}},
    [{'pattern': 'x', 'channel': 'slack'}], [['a'], ['b']], {'t': [{'p': 'x'}]}, [{'t': [{'p': 'x'}]}]])
def test_dumps_round_trips(value):
    assert tomllib.loads('v = ' + configtext.dumps(value))['v'] == value


def test_dumps_layout():
    assert '\n' in configtext.dumps([{'pattern': 'x', 'channel': 'slack'}])
    assert configtext.dumps(['a', 'b']) == '["a", "b"]'
    assert '\n' not in configtext.dumps({'t': [{'p': 'x'}]})  # TOML 1.0: inline tables are one line
    with pytest.raises(ValueError, match='list or table'):
        configtext.dumps(object())


def headers(raw):
    return [path for kind, path, _, _ in configtext.entries(raw)[1] if kind != 'key']


def test_entries_resolve_every_header_of_the_template():
    raw = TEMPLATE + REPO
    parsed, paths = tomllib.loads(raw), headers(raw)
    assert ('repos', 0) in paths and ('outward', 'max_length') in paths
    for path in paths:
        assert isinstance(calibrate._table(parsed, path), dict), path


def test_entries_spaced_and_quoted_headers():
    raw = '[ outward.max_length ]\n[owner."verbosity"]\n[boundary."release/*"]\n'
    assert headers(raw) == [('outward', 'max_length'), ('owner', 'verbosity'), ('boundary', 'release/*')]


def test_entries_spans_and_arrays():
    raw = ('[shepherd]\nreviewers = [\n  [1, 2],\n]\nnote = """\n[x]\n"""\n'
           '[[repos]]\nname = "a"\n[[repos]]\nname = "b"\n[repos.merge]\nauto = false\n')
    lines, items = configtext.entries(raw)
    keys = {path: (start, end) for kind, path, start, end in items if kind == 'key'}
    assert keys[('shepherd', 'reviewers')] == (1, 4) and keys[('shepherd', 'note')] == (4, 7)
    assert headers(raw) == [('shepherd',), ('repos', 0), ('repos', 1), ('repos', 1, 'merge')]
    assert ('repos', 1, 'merge', 'auto') in keys
    assert configtext.entries(raw.replace('\n', '\r\n'))[1] == items


PATTERNS = [{'pattern': 'x', 'channel': 'slack'}]


def line_of(text, needle):
    return next(i for i, line in enumerate(text.splitlines()) if line.startswith(needle))


def test_template_tool_patterns():
    raw = TEMPLATE + REPO
    text = configtext.place(raw, ('outward',), 'tool_patterns', PATTERNS)
    check(raw, text, ('outward',), 'tool_patterns', PATTERNS)
    assert line_of(text, '[outward]') < line_of(text, 'tool_patterns = [') < line_of(text, '[outward.max_length]')


def test_missing_table_and_parents():
    text = configtext.place(TEMPLATE, ('telemetry', 'otlp'), 'endpoint', 'https://example.test')
    check(TEMPLATE, text, ('telemetry', 'otlp'), 'endpoint', 'https://example.test')
    assert line_of(text, '[telemetry]') < line_of(text, '[telemetry.otlp]') < line_of(text, 'endpoint = ')
    two = TEMPLATE + REPO + REPO.replace('widget', 'gadget')
    text = configtext.place(two, ('repos', 0, 'merge'), 'auto', True)
    check(two, text, ('repos', 0, 'merge'), 'auto', True)
    assert line_of(text, 'auto = true') < line_of(text, 'name = "acme/gadget"')
    with pytest.raises(ValueError, match='config add-repo'):
        configtext.place(TEMPLATE + REPO, ('repos', 3), 'merge_deploys', False)


LAYOUTS = {
    'template': TEMPLATE + REPO,
    'subtable': '[outward]\nhumanize = true\n[outward.max_length]\nslack = 10\n',
    'spaced': '[outward]\n[ outward.max_length ]\nslack = 10\n[ outbound ]\nwork_channels = []\n',
    'quoted': '[owner."verbosity"]\ndefault = "brief"\n["outbound"]\ncompany_domains = []\n',
    'inline': 'owner = {name = "Pat"}\noutbound = {code_host_orgs = ["acme"]}\n',
    'array': '[[repos]]\nname = "acme/widget"\npath = "widget"\ndefault_branch = "main"\n'
             '[[outward.tool_patterns]]\npattern = "x"\nchannel = "slack"\n',
    'missing': '[watch]\nclock_seconds = 600\n',
    'comments': '[owner] # who\nname = "Pat" # me\n[outbound] # out\nwork_channels = [] # ids\n',
    'crlf': '[owner]\r\nname = "Pat"\r\n[outbound]\r\nwork_channels = []\r\n[watch]\r\nclock_seconds = 1\r\n',
    'no newline': '[owner]\nname = "Pat"\n[outbound]\ncode_host_orgs = []',
}
KINDS = [(('owner',), 'name', 'Lee'), (('outbound',), 'work_channels', ['C1', 'C2']),
         (('outbound',), 'people', {'slack:U1': {'email': 'a@example.test'}})]


@pytest.mark.parametrize('layout', LAYOUTS)
@pytest.mark.parametrize('path,key,value', KINDS)
def test_corpus(layout, path, key, value):
    raw = LAYOUTS[layout]
    text = configtext.place(raw, path, key, value)
    check(raw, text, path, key, value, removed=1)
    if layout == 'crlf':
        assert '\n' not in text.replace('\r\n', '')


def placed(raw, path, key, value, removed):
    text = configtext.place(raw, path, key, value)
    check(raw, text, path, key, value, removed=removed)
    return text


def test_span_multi_line_list():
    raw = '[shepherd]\nreviewers = [\n  "a",\n]\nmin_reviewers = 1\n'
    text = placed(raw, ('shepherd',), 'reviewers', ['b'], 3)
    assert text == '[shepherd]\nreviewers = ["b"]\nmin_reviewers = 1\n'


def test_span_inline_table_and_inline_repos():
    raw = '[sessions]\nrotate_after = { turns = 200 }\n'
    assert placed(raw, ('sessions', 'rotate_after'), 'turns', 100, 1).endswith('rotate_after = {turns = 100}\n')
    raw = 'repos = [{name = "acme/widget", path = "widget", default_branch = "main"}]\n'
    placed(raw, ('repos', 0), 'merge_deploys', False, 1)


def test_span_array_of_tables():
    raw = ('[outward]\nhumanize = true\n[[outward.tool_patterns]]\npattern = "a"\nchannel = "slack"\n\n'
           '[[outward.tool_patterns]]\npattern = "b"\nchannel = "docs"\n[watch]\nclock_seconds = 1\n')
    text = placed(raw, ('outward',), 'tool_patterns', PATTERNS, 7)
    assert text.count('[[outward.tool_patterns]]') == 1 and text.index('tool_patterns') < text.index('[watch]')


def test_span_header_table_and_dotted_key():
    raw = '[outbound.people]\n"slack:U1" = {email = "a@example.test"}\n[watch]\nclock_seconds = 1\n'
    people = {'slack:U1': {'email': 'a@example.test'}, 'github:dev': {'org': 'acme'}}
    placed(raw, ('outbound',), 'people', people, 1)
    raw = '[[repos]]\nname = "acme/widget"\nmerge.auto = false\n'
    assert 'merge.auto = true\n' in placed(raw, ('repos', 0, 'merge'), 'auto', True, 1)


def test_apply_places_through_the_writer():
    text = calibrate.apply(TEMPLATE, [(('outward',), 'tool_patterns', PATTERNS)])
    check(TEMPLATE, text, ('outward',), 'tool_patterns', PATTERNS)
    raw = '[outward]\nmax_length.slack = 1\n'
    with pytest.raises(ValueError, match='edit by hand') as found:
        calibrate.apply(raw, [(('outward', 'max_length'), 'teams', 2)])
    assert str(found.value).startswith('outward.max_length.teams:')


def write(raw, key, value, mode='replace'):
    from wuwei.commands.setup import write_value
    return write_value(raw, key, value, mode)


@pytest.mark.parametrize('key,value', [('outward.tool_patterns', PATTERNS), ('owner.name', 'Lee'),
                                       ('outbound.people', {'slack:U1': {'email': 'a@example.test'}})])
def test_write_value_twice(key, value):
    once = write(TEMPLATE, key, value)
    assert once != TEMPLATE and write(once, key, value) == once


def test_write_value_modes():
    raw = TEMPLATE.replace('work_channels = []', 'work_channels = ["C1"]')
    text = write(raw, 'outbound.work_channels', ['C1', 'C2'], 'append')
    assert tomllib.loads(text)['outbound']['work_channels'] == ['C1', 'C2']
    assert write(text, 'outbound.work_channels', ['C2'], 'append') == text
    with pytest.raises(ValueError, match='replace'):
        write(raw, 'owner.name', 'Lee', 'append')
    with pytest.raises(ValueError, match='unknown mode'):
        write(raw, 'owner.name', 'Lee', 'x')
    raw = TEMPLATE.replace('deny = []', 'deny = ["make deploy*"]')
    text = write(raw, 'deploy.deny', ['npm publish*'])
    assert tomllib.loads(text)['deploy']['deny'] == ['make deploy*', 'npm publish*']


@pytest.mark.parametrize('path,kind,example', [
    (('cap',), 'an integer', '0'),
    (('repos', 0, 'merge_deploys'), 'true or false', 'true'),
    (('outward', 'tool_patterns'), 'a list of tables', '[{pattern = "text", channel = "text"}]'),
    (('outbound', 'people'), 'a table', '{name = {email = "text", org = "text"}}'),
    (('boundary', 'api'), 'a string', '"text"'),
    (('owner', 'verbosity', 'default'), 'a string', '"brief"'),
    (('outbound', 'work_channels'), 'a list of strings', '["text"]'),
])
def test_declared_and_describe(path, kind, example):
    assert configtext.describe(configtext.declared(path)) == (kind, example)


def test_declared_unknown():
    assert configtext.declared(('nonsense',)) is None


def test_two_tables():
    raw = '[outbound]\nwork_channels = ["C1"]\n[outward]\nwork_channels = ["C1"]\n'
    assert configtext.misplaced(raw) == [
        'work_channels is set in [outbound] (line 2) and [outward] (line 4); '
        '[outward] does not take it, remove line 4']
    raw = '[tracker]\nauto = []\n[[repos]]\nname = "acme/widget"\n[repos.merge]\nauto = false\n'
    assert configtext.misplaced(raw) == []


def test_line_separator_inside_a_string():
    raw = '[owner]\nname = "a b"\n'
    text = configtext.place(raw, ('owner',), 'pronouns', 'they')
    check(raw, text, ('owner',), 'pronouns', 'they')
