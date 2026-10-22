"""Fitness tests for the charters and skills: the plain-tone rule, the agents' size, one home per rule,
and the skills' triggers. They hold the set to the practices it asks of its seats."""

import json
import re
from pathlib import Path

import pytest

from wuwei import evidence

PLUGIN = Path(__file__).resolve().parents[1]
CHARTERS = sorted((PLUGIN / 'charters').glob('*.md'))
SKILLS = sorted((PLUGIN / 'skills').glob('*/SKILL.md'))
AGENT_WORDS = 2250  # the ceiling on one generated agent; the steward proposes deletions before it is raised


def sentences(path):
    """The prose sentences of a Markdown file. Front matter, code, headings, tables and <placeholders> are
    left out, a code span counts as one word, and a list item or a paragraph is its own block."""
    text = re.sub(r'^---\n.*?\n---\n', '', path.read_text(encoding='utf-8'), flags=re.S)
    text = re.sub(r'```.*?```', '', text, flags=re.S)
    blocks, current = [], []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(('#', '|', '<')):
            blocks.append(' '.join(current))
            current = []
        elif re.match(r'(-|\d+\.)\s', stripped):
            blocks.append(' '.join(current))
            current = [re.sub(r'^(-|\d+\.)\s+', '', stripped)]
        else:
            current.append(stripped)
    blocks.append(' '.join(current))
    found = []
    for block in blocks:
        block = re.sub(r'`[^`]*`', 'Code', block)
        found += [s.strip() for s in re.split(r'(?<=;)\s+|(?<=[.:?!])\s+(?=[A-Z(])', block) if len(s.split()) > 2]
    return found


@pytest.mark.parametrize('path', CHARTERS + SKILLS, ids=lambda p: p.relative_to(PLUGIN).as_posix())
def test_no_sentence_is_over_35_words(path):
    long = [s for s in sentences(path) if len(s.split()) > 35]
    assert long == [], long


@pytest.mark.parametrize('path', CHARTERS + SKILLS, ids=lambda p: p.relative_to(PLUGIN).as_posix())
def test_sentences_average_under_20_words(path):
    found = sentences(path)
    assert sum(len(s.split()) for s in found) / len(found) < 20


@pytest.mark.parametrize('path', sorted((PLUGIN / 'agents').glob('*.md')), ids=lambda p: p.stem)
def test_a_generated_agent_stays_under_the_word_ceiling(path):
    assert len(path.read_text(encoding='utf-8').split()) <= AGENT_WORDS


@pytest.mark.parametrize('path', sorted((PLUGIN / 'agents').glob('*.md')), ids=lambda p: p.stem)
def test_a_generated_agent_leaves_100_words_of_room_under_the_ceiling(path):
    assert len(path.read_text(encoding='utf-8').split()) <= AGENT_WORDS - 100


@pytest.mark.parametrize('path', CHARTERS + SKILLS, ids=lambda p: p.relative_to(PLUGIN).as_posix())
def test_a_charter_names_no_issue_number_and_no_file_of_this_repository(path):
    text = path.read_text(encoding='utf-8')
    assert not re.search(r'#\d{3,}', text), 'an issue number belongs in the plan or standards, not a charter'
    for lesson in ('guards.py', 'hook.py', 'routes.json'):
        assert lesson not in text, lesson


def test_decisions_and_done_are_stated_once_in_common():
    common = (PLUGIN / 'charters' / '_common.md').read_text(encoding='utf-8')
    assert '## Done' in common and '| Hard to undo | act, with a `Rollback:` line | ask the owner |' in common
    days = {3: 'three'}[evidence.STALE_DAYS]
    for threshold in (f'a delta of docs, or of generated files or at most {evidence.TRIVIAL} lines off risky paths, carries', f'28-day change failure rate is over {evidence.BUDGET:.0%}'.replace('%', ' percent'),
                      f'about {evidence.MAX_LINES} changed lines', f'{days} days or more', f'at `standard`, risky or owner paths add security and a wide change (over {evidence.WIDE} lines that are not prose, or 10 code files) adds arch',
                      "a spec contract (a file under a spec's `contracts/` folder) takes arch at any tier"):
        assert threshold in ' '.join(common.split()), threshold
    for other in ('_way.md', 'planner.md'):
        text = (PLUGIN / 'charters' / other).read_text(encoding='utf-8')
        assert '| Hard to undo |' not in text and 'Docs need none' not in text, other
        assert '_common.md' in text, other
    rules = (PLUGIN / 'skills' / 'wuwei-rules' / 'SKILL.md').read_text(encoding='utf-8')
    assert '| Hard to undo |' not in rules and '_common.md' in rules


def test_a_requested_reviewer_and_staleness_are_process_fit_everywhere():
    for path in (PLUGIN / 'charters' / '_common.md', PLUGIN / 'skills' / 'wuwei-rules' / 'SKILL.md'):
        text = ' '.join(path.read_text(encoding='utf-8').split())
        done = text.split('## Done', 1)[1]
        safety = re.split(r'The rest is process fit|Process fit never blocks', done, maxsplit=1)[0]
        assert 'reviewer' not in safety and 'stale' not in safety and 'three days' not in safety, path.name


def test_the_word_door_means_a_refusal_not_a_decision():
    for path in CHARTERS + SKILLS:
        assert 'door is one-way' not in path.read_text(encoding='utf-8'), path


def test_the_arch_gate_reviews_as_an_architect():
    text = ' '.join((PLUGIN / 'charters' / 'sentinel-arch.md').read_text(encoding='utf-8').split())
    for lens in ('Conformance:', 'Dependencies and coupling:', 'Contracts:', 'Quality attributes', 'Fitness functions:',
                 'Decisions the change quietly settles', 'Breaking: no', 'ADR', 'C4 or arc42'):
        assert lens in text, lens
    assert "are the security gate's" in text


def test_an_adr_goes_where_the_repository_keeps_them_and_a_reconfirmed_one_is_amended():
    planner = ' '.join((PLUGIN / 'charters' / 'planner.md').read_text(encoding='utf-8').split())
    arch = ' '.join((PLUGIN / 'charters' / 'sentinel-arch.md').read_text(encoding='utf-8').split())
    for home in ('`docs/adr/`', '`docs/decisions/`', "the item's spec folder", 'amend that ADR'):
        assert home in planner, home
    assert "the repository's ADRs" in arch and 'docs/adr/' not in arch


def test_a_breaking_change_is_a_semver_major_of_the_declared_public_api():
    arch = ' '.join((PLUGIN / 'charters' / 'sentinel-arch.md').read_text(encoding='utf-8').split())
    rule = arch.split(' 7. ', 1)[1].split(' Trust boundaries', 1)[0]
    assert 'When unsure, say yes' not in arch and 'When unsure, ESCALATE with Breaking: yes.' in rule
    for said in ('public API declared at the base commit', 'Yes is a SemVer major', 'an input every client must now give',
                 "a documented exit code's meaning changed",
                 'a patch only when the old behaviour contradicted the documented API'):
        assert said in rule, said
    assert 'is minor' not in rule
    assert len(rule.split()) <= 79  # str.split words after the `7.` marker
    builder = ' '.join((PLUGIN / 'charters' / 'builder.md').read_text(encoding='utf-8').split())
    assert 'Only a major' in builder and 'A stricter check of a rule the docs already state is a `fix:`' in builder
    for name in ('_common.md', 'builder.md', 'sentinel-arch.md'):
        assert 'outward contract' not in (PLUGIN / 'charters' / name).read_text(encoding='utf-8'), name
    docs = PLUGIN / 'docs'
    section = (docs / 'site' / 'concepts' / 'evidence.md').read_text(encoding='utf-8').split('## Breaking changes', 1)[1]
    section = ' '.join(section.split('\n## ', 1)[0].split())
    for said in ('SemVer 2.0.0', 'public API', 'exit codes', 'config keys', 'verdict file formats', 'owner question shapes',
                 'hook input and output', '`/wuwei-run`', 'its alias ships', 'marketplace', 'agent role names',
                 '`.wuwei/goals.md`', '`.wuwei/standards.md`', 'plan file format', 'at the base commit',
                 'contradicted the documented public API', 'an input every client must now give',
                 'not by which inputs reach it', 'Before a major merges', 'with `Breaking: yes`', 'from 4.1.0'):
        assert said in section, said
    assert 'ESLint' not in section and 'refuse or report more (' not in section
    for path in (docs / 'design.md', docs / 'site' / 'reference.md', docs / 'site' / 'concepts' / 'decisions.md'):
        text = path.read_text(encoding='utf-8')
        assert 'evidence.md#breaking-changes' in text and 'outward contract' not in text, path.name
        assert 'refuse or report more is a minor' not in text, path.name


def test_each_gate_names_the_frameworks_it_stands_on():
    for role, anchor in (('sentinel-security', 'OWASP Top 10 for LLM applications'), ('sentinel-security', 'CWE'),
                         ('sentinel-quality', 'mutation testing'), ('sentinel-arch', 'fitness functions'),
                         ('lead', 'weighted shortest job first')):
        assert anchor in (PLUGIN / 'charters' / f'{role}.md').read_text(encoding='utf-8'), (role, anchor)


def test_the_security_gate_defines_its_scanner_and_reads_the_supply_chain():
    text = ' '.join((PLUGIN / 'charters' / 'sentinel-security.md').read_text(encoding='utf-8').split())
    assert 'the configured scanner' not in text
    assert "the repository's own scanner (the secret, dependency or static-analysis step" in text
    assert 'Supply chain:' in text and 'lockfile' in text


def test_the_shepherd_asks_for_an_announcement_url_that_exists_at_the_head():
    text = ' '.join((PLUGIN / 'charters' / 'shepherd.md').read_text(encoding='utf-8').split())
    assert '`Announcement: <url>`' in text and 'one http(s) URL and nothing else' in text
    assert 'must exist at the head' in text and 'the release will write later does not count' in text
    common = ' '.join((PLUGIN / 'charters' / '_common.md').read_text(encoding='utf-8').split())
    assert '`Announcement: <url>`' in common and '`Announcement: <link>`' not in common


@pytest.mark.parametrize('folder', ['agents', '.claude/agents'])
def test_a_refused_handback_is_expected_and_no_seat_reports_it_as_a_gap(folder):
    """#1222: outside auto mode the refusal is expected; a seat that lists it under Gap: is noise in every hand-back."""
    for path in sorted((PLUGIN / folder).glob('*.md')):
        text = ' '.join(path.read_text(encoding='utf-8').split())
        assert 'refused hand-back goes under `Gap:`' not in text, path
        assert 'the harness refuses SubagentHandback, as expected' in text and "its retry reminder is not WUWEI's: ignore it" in text, path


def test_the_steward_may_propose_charter_deletions():
    text = ' '.join((PLUGIN / 'charters' / 'steward.md').read_text(encoding='utf-8').split())
    assert 'Charters shrink too' in text and 'proposed for deletion' in text


def test_the_planner_numbers_its_rules_in_order():
    body = (PLUGIN / 'charters' / 'planner.md').read_text(encoding='utf-8').split('## Running the work', 1)[1]
    body = body.split('## What goes to the owner', 1)[0]
    assert [int(n) for n in re.findall(r'^(\d+)\. ', body, re.M)] == list(range(1, 11))


@pytest.mark.parametrize('path', SKILLS, ids=lambda p: p.parent.name)
def test_every_skill_description_says_when_to_use_it_and_when_not(path):
    front = path.read_text(encoding='utf-8').split('---')[1]
    description = re.search(r'^description:\s*(.+)$', front, re.M)[1]
    assert len(description) <= 1024
    assert 'Use ' in description or 'Renamed' in description
    assert 'Not for ' in description, path.parent.name


def test_the_trigger_set_covers_every_skill_with_near_misses():
    triggers = json.loads((PLUGIN / 'tests' / 'fixtures' / 'skill-triggers.json').read_text(encoding='utf-8'))
    assert sorted(triggers) == sorted(p.parent.name for p in SKILLS)
    for skill, queries in triggers.items():
        assert len(queries['should']) >= 8 and len(queries['should_not']) >= 8, skill
        assert not set(queries['should']) & set(queries['should_not']), skill
        # a near miss is another WUWEI skill's own query: the valuable negative
        others = {q for other, o in triggers.items() if other != skill for q in o['should']}
        assert len(set(queries['should_not']) & others) >= 3, skill


MODEL = r'(Fable 5\.1|Opus 5\.5|Sonnet 5\.5|Haiku 5\.5) (low|medium|high|xhigh|max)'
PATHS = 'risky, owner or contract paths'


def _models_section():
    text = (PLUGIN / 'charters' / 'planner.md').read_text(encoding='utf-8')
    assert '## Model and effort' in text
    return text.split('## Model and effort', 1)[1].split('\n## ', 1)[0]


def _model_table():
    rows = {}
    for line in _models_section().splitlines():
        if line.startswith('| ') and not line.startswith(('| ---', '| Seat ')):
            cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
            rows[cells[0].strip('`')] = cells[1]
    return rows


def _setting(row, tier, protected):
    """The (model, effort) a table row gives at a tier, on or off risky, owner or contract paths. The
    charter says the later setting holds where two apply; a 'for <case>' clause is not a tier rule."""
    chosen = None
    for clause in row.split('; '):
        match = re.fullmatch(MODEL + r'(?: at (.+))?', clause)
        if not match:
            assert re.match(MODEL + ' for ', clause), clause
            continue
        conditions = (match[3] or '').split(' or ', 1)
        if match[3] is None or tier in conditions or (protected and f'on {PATHS}' in conditions):
            chosen = (match[1], match[2])
    return chosen


def test_the_planner_table_names_a_model_and_effort_for_every_seat():
    rows = _model_table()
    for role in json.loads((PLUGIN / 'agents' / 'allowlist.json').read_text(encoding='utf-8')):
        assert role in rows, role
        assert _setting(rows[role], 'standard', False), role
    assert rows['lookups and searches'] == 'Haiku 5.5 low'


def test_the_planner_table_holds_the_promised_settings():
    rows = _model_table()
    want = {('builder', 'light', False): ('Sonnet 5.5', 'medium'), ('builder', 'standard', False): ('Opus 5.5', 'medium'),
            ('builder', 'light', True): ('Opus 5.5', 'high'), ('builder', 'full', False): ('Opus 5.5', 'high'),
            ('sentinel-security', 'standard', False): ('Opus 5.5', 'high'), ('sentinel-security', 'standard', True): ('Opus 5.5', 'xhigh'),
            ('sentinel-security', 'full', False): ('Opus 5.5', 'xhigh'), ('sentinel-arch', 'full', True): ('Opus 5.5', 'high'),
            ('sentinel-quality', 'light', False): ('Sonnet 5.5', 'high'), ('sentinel-quality', 'standard', True): ('Opus 5.5', 'high'),
            ('sentinel-quality', 'full', False): ('Opus 5.5', 'high'), ('sentinel-goal', 'full', False): ('Sonnet 5.5', 'high'),
            ('lead', 'full', False): ('Opus 5.5', 'xhigh'), ('shepherd', 'standard', False): ('Sonnet 5.5', 'medium'),
            ('steward', 'standard', False): ('Opus 5.5', 'high')}
    assert {key: _setting(rows[key[0]], key[1], key[2]) for key in want} == want
    assert 'Opus 5.5 high for a conflict where both sides changed logic' in rows['shepherd']


def test_every_head_has_a_gate_on_another_model_and_no_haiku_gate_on_a_protected_path():
    """Rule 3 and the floor computed over every tier and path the gate rule in _common.md tells apart."""
    rows, text = _model_table(), ' '.join(_models_section().split())
    assert 'at least one gate per head runs on a different model than the builder' in text
    fallback = 'the quality gate takes the other of Opus 5.5 and Sonnet 5.5, at high' in text
    floor = f'Haiku 5.5 never runs a gate on {PATHS}' in text and 'is an `exception:` for the owner' in text
    for tier in ('light', 'standard', 'full'):
        for path in (None, 'risky', 'owner', 'contract'):
            gates = ['sentinel-quality'] + (['sentinel-security'] if tier == 'standard' and path in ('risky', 'owner') else [])
            gates += ['sentinel-arch'] if path == 'contract' else []
            gates = ['sentinel-security', 'sentinel-arch', 'sentinel-quality', 'sentinel-goal'] if tier == 'full' else gates
            builder = _setting(rows['builder'], tier, path is not None)[0]
            models = {gate: _setting(rows[gate], tier, path is not None) for gate in gates}
            if fallback and all(model == builder for model, _ in models.values()):
                models['sentinel-quality'] = ({'Opus 5.5': 'Sonnet 5.5', 'Sonnet 5.5': 'Opus 5.5'}[builder], 'high')
            assert any(model != builder for model, _ in models.values()), (tier, path, builder, models)
            if path:
                assert floor and all(model != 'Haiku 5.5' for model, _ in models.values()), (tier, path)


def test_the_planner_states_the_ladder_the_brief_lines_and_the_precedence():
    text = ' '.join(_models_section().split())
    assert 'Haiku 5.5, Sonnet 5.5, Opus 5.5 medium, high, xhigh, then Fable 5.1' in text
    assert 'the top step is Opus 5.5 max' in text and 'zero data retention' in text
    assert 'only on retro evidence: 10 merged items on the lower setting with no escaped defect' in text
    assert "The brief's first line is `Model: <model> <effort> (<row>)`" in text and '`Model reason: <one line>`' in text
    order = [text.index(word) for word in ("call's `model`", '`model` frontmatter', '`CLAUDE_CODE_SUBAGENT_MODEL`', 'session model')]
    assert order == sorted(order), order
    assert '`CLAUDE_CODE_EFFORT_LEVEL` beats every effort setting' in text and 'never refused' in text
    assert "The owner's `models` rows in `.wuwei/config.toml` override any row here" in text
    assert 'set it on every call, since Opus 5.5 defaults to medium' in text
    assert 'Codex' in text and 'unmeasured' in text and 'trust path' not in text


def test_the_models_page_names_and_dates_every_source():
    page = (PLUGIN / 'docs' / 'site' / 'concepts' / 'models.md').read_text(encoding='utf-8')
    sources = [line for line in page.split('## Sources', 1)[1].splitlines() if line.startswith('- ')]
    for line in sources:
        assert re.search(r'\]\(https://[^)]+\)', line) and re.search(r'read 20\d\d-\d\d-\d\d', line), line
    for doc in ('code.claude.com/docs/en/sub-agents)', 'code.claude.com/docs/en/hooks)', 'code.claude.com/docs/en/skills)',
                'code.claude.com/docs/en/plugins/components)', 'code.claude.com/docs/en/model-config)',
                'platform.claude.com/docs/en/models/overview)', 'platform.claude.com/docs/en/build-with-claude/effort)'):
        assert sum(doc in line for line in sources) == 1, doc


def test_the_models_page_maps_each_step_to_a_codex_model_as_the_planners_unmeasured_reading():
    page = (PLUGIN / 'docs' / 'site' / 'concepts' / 'models.md').read_text(encoding='utf-8')
    codex = page.split('## On Codex', 1)[1].split('\n## ', 1)[0]
    for claude, model in (('Fable 5.1', 'gpt-6-astra'), ('Opus 5.5', 'gpt-6.1-sol'), ('Sonnet 5.5', 'gpt-6-luna'),
                          ('Haiku 5.5', 'gpt-6-luna low')):
        assert any(line.startswith(f'| {claude} |') and model in line for line in codex.splitlines()), claude
    text = ' '.join(codex.split())
    assert "the planner's reading of the Codex catalog" in text and 'not OpenAI guidance' in text
    assert 'unmeasured' in text and 'ultra' in text


def test_the_team_and_codex_pages_and_the_design_link_the_table_instead_of_models():
    for name in ('docs/site/concepts/team.md', 'docs/site/concepts/codex.md'):
        text = (PLUGIN / name).read_text(encoding='utf-8')
        assert 'MODELS' not in text and 'models.md' in text, name
    assert 'unmeasured' in (PLUGIN / 'docs' / 'site' / 'concepts' / 'codex.md').read_text(encoding='utf-8')
    team = (PLUGIN / 'docs' / 'design.md').read_text(encoding='utf-8').split('## 3. The team', 1)[1].split('\n## ', 1)[0]
    assert 'MODELS' not in team and 'concepts/models.md' in team


def test_the_steward_reads_outcomes_by_model_and_effort_and_the_watch_may_run_cheaper():
    steward = ' '.join((PLUGIN / 'charters' / 'steward.md').read_text(encoding='utf-8').split())
    assert 'by seat, model and effort' in steward and 'model table' in steward
    watch = ' '.join((PLUGIN / 'skills' / 'wuwei-watch' / 'SKILL.md').read_text(encoding='utf-8').split())
    assert 'Sonnet 5.5' in watch and '`effort: medium`' in watch and 'not a default' in watch
    assert 'mostly reads and records' not in watch


SESSION_CAP = 10000  # Claude Code saves a longer additionalContext to a file and shows a 2,000-character preview


def session_plan(root, items, newline='', pad=0, first=0):
    from conftest import write_plan
    from wuwei import ws
    write_plan(root, [{'id': f'item-{n:02d}', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'standard', 'status': 'open',
                       'score': 50 - n, 'title': f'fix(hook): item {n} keeps the long title a real plan item carries,{newline} '
                       'with its promise named in the title the way this plan writes them' + 'x' * (pad + (first if n == 0 else 0))}
                      for n in range(items)])
    ws.cache_put(root, 'board', None)


def session_context(root):
    from wuwei import hook
    return hook.handle(root, 'SessionStart', {'session_id': 's1', 'cwd': str(root)})['hookSpecificOutput']['additionalContext']


def left_out(cut):
    return f'{cut} more item{"s" if cut > 1 else ""} left out; `wuwei status` lists them all.'


@pytest.mark.parametrize('items', [0, 40])
def test_the_session_start_context_fits_the_cap_and_says_what_it_left_out(root, fake, items):
    from wuwei import ws
    if items:
        session_plan(root, items)
    for name in ('goals.md', 'standards.md') if items else ():
        (root / ws.DIR / name).write_text('- ' + 'x' * 3000 + '\n')
    text = session_context(root)
    assert len(text) < SESSION_CAP, f'{len(text)} characters: Claude Code caps additionalContext at {SESSION_CAP}'
    charters = PLUGIN / 'charters'
    assert f'WUWEI CLI: {PLUGIN / "bin" / "wuwei"}' in text and str(charters / 'planner.md') in text
    assert (charters / '_way.md').read_text(encoding='utf-8').strip() in text
    common = (charters / '_common.md').read_text(encoding='utf-8')
    for rules in ('## Decisions', '## Done'):
        assert common.split(rules, 1)[1].split('\n## ', 1)[0].strip() in text, rules
    shown, left = len(re.findall(r'^- item-', text, re.M)), re.search(r'^(\d+) more items left out', text, re.M)
    assert shown + (int(left[1]) if left else 0) == items and (left is None) == (items == 0)
    assert items == 0 or shown >= 10, 'the board keeps the top items'
    assert items == 0 or text.endswith('\n' + left_out(items - shown)), 'the left-out line is whole and last'


def session_board(root, newline, pad, first=0):
    session_plan(root, 40, newline, pad, first)
    text = session_context(root)
    return text, len(re.findall(r'^- item-', text, re.M))


@pytest.mark.parametrize('pad', range(0, 200, 10))
@pytest.mark.parametrize('newline', ['', '\n'])
@pytest.mark.parametrize('deep', [0, 120])
def test_the_board_fills_the_cap_to_the_character_at_any_title_and_path_length(root, fake, deep, newline, pad):
    from wuwei import ws
    work = root / ('r' * deep)
    if deep:
        (work / ws.DIR).mkdir(parents=True)
        ws.write_config(work, ws.raw_config(root))
    text, shown = session_board(work, newline, pad)
    assert len(text) < SESSION_CAP and shown >= 10 and text.endswith('\n' + left_out(40 - shown)), (len(text), shown)
    full, kept = session_board(work, newline, pad, SESSION_CAP - 1 - len(text))
    assert len(full) == SESSION_CAP - 1 and kept == shown, 'one character under the cap keeps every item'
    over, fewer = session_board(work, newline, pad, SESSION_CAP - len(text))
    assert len(over) < SESSION_CAP and fewer == shown - 1 and over.endswith('\n' + left_out(41 - shown)), 'at the cap one goes'


def test_an_andon_reason_that_reads_like_an_item_line_is_not_counted_or_trimmed(root, fake):
    from wuwei import board
    fragment, header = '\n- item-00, a fragment of the reason', '\nBoard (what each open item still lacks):\n'
    board.andon(root, 'acme/lib', 'base branch red' + fragment)
    room = SESSION_CAP - 20 - len(session_context(root)) + len('Board: nothing open in the plan.') - len(header + left_out(40)) + 1
    session_plan(root, 40)
    for over, size, end in ((0, SESSION_CAP - 20, left_out(40)), (40, SESSION_CAP, left_out(40)[:-20])):
        board.andon(root, 'acme/lib', 'base branch red' + 'x' * (room + over) + fragment)
        text = session_context(root)
        assert len(text) == size and text.endswith(fragment + header + end), (over, len(text))


def test_the_left_out_line_reads_one_item_in_the_singular_and_two_in_the_plural(root, fake):
    session_plan(root, 40)
    shown = len(re.findall(r'^- item-', session_context(root), re.M))
    session_plan(root, shown)
    pad = SESSION_CAP - 1 - len(session_context(root))
    session_plan(root, shown, first=pad)
    text = session_context(root)
    assert len(text) == SESSION_CAP - 1 and len(re.findall(r'^- item-', text, re.M)) == shown, 'the whole board fits to the character'
    session_plan(root, shown, first=pad + 1)
    text = session_context(root)
    assert len(re.findall(r'^- item-', text, re.M)) == shown - 1 and len(text) < SESSION_CAP
    assert text.endswith('\n1 more item left out; `wuwei status` lists them all.')
    session_plan(root, shown, first=pad + 1 + SESSION_CAP - len(text))
    text = session_context(root)
    assert len(re.findall(r'^- item-', text, re.M)) == shown - 2 and text.endswith('\n2 more items left out; `wuwei status` lists them all.')


def test_a_title_with_a_newline_still_lets_the_board_trim(root, fake):
    session_plan(root, 40, newline='\n')
    text = session_context(root)
    shown = len(re.findall(r'^- item-', text, re.M))
    assert len(text) < SESSION_CAP and shown >= 10 and text.endswith('\n' + left_out(40 - shown))


def test_the_session_start_context_holds_the_cap_when_the_board_has_no_item_line_to_drop(root):
    from wuwei import board
    for n in range(30):
        board.andon(root, f'acme/app{n}', 'base branch red: ' + 'x' * 400)
    text = session_context(root)
    assert len(text) == SESSION_CAP and text.startswith(f'WUWEI CLI: {PLUGIN / "bin" / "wuwei"}') and 'ANDON acme/app0:' in text
    common, board_at = (PLUGIN / 'charters' / '_common.md').read_text(encoding='utf-8'), text.index('ANDON acme/app0:')
    rules = [(PLUGIN / 'charters' / '_way.md').read_text(encoding='utf-8').strip()]
    rules += [common.split(heading, 1)[1].split('\n## ', 1)[0].strip() for heading in ('## Decisions', '## Done')]
    assert all(rule in text[:board_at] for rule in rules), 'the rules come whole before the untrusted board text'


def test_a_gate_puts_the_findings_its_fix_closed_under_probes():
    for path in (PLUGIN / 'charters' / '_gate.md', PLUGIN / 'agents' / 'sentinel-quality.md'):
        text = ' '.join(path.read_text(encoding='utf-8').split())
        assert 'Closed findings go under ## Probes' in text, path
        assert '`closed: <finding> at <sha7>`' in text and '## Findings holds only open findings, or none' in text, path
        assert 'refuses a wrong shape, naming the next free file: write the corrected verdict there' in text, path


def test_agents_md_states_the_mutant_rule_for_the_vendored_copy():
    text = (Path(__file__).resolve().parents[1] / "AGENTS.md").read_text()
    assert ".claude/wuwei/cli/wuwei/" in text
    assert "test_the_vendored_plugin_matches_the_tree_it_was_copied_from" in text


def test_the_gate_charter_shows_finding_lines_the_parser_accepts_and_the_shapes_it_refuses():
    from wuwei import verdict
    text = (PLUGIN / 'charters' / '_gate.md').read_text(encoding='utf-8')
    examples = re.findall(r'`(- \[(?:critical|high|medium|low)\] [^`]*)`', text)
    head = 'Verdict: FIX\nGate: quality\nItem: 1\nPR: acme/app#1\nHead: ' + 'a' * 40 + '\nConfidence: high\n\n## Findings\n'
    assert len(examples) >= 3 and any('PR-body:0' in e for e in examples), examples
    for line in examples:
        assert verdict.parse(head + line + '\n')['errors'] == [], line
    for bad in ('- [high] cli/app.py:42 blocks: yes. Failure: a blank token passes\n  - seen at line 50',
                '- [low] PR body, "Size:" line. blocks: no.', '- [medium] specs/x/plan.md:29 blocks: yes. Failure (contract, R-1)'):
        assert verdict.parse(head + bad + '\n')['errors'], bad


def test_the_planner_keeps_gates_off_codex_with_no_condition_and_a_codex_brief_bars_mcp():
    text = ' '.join((PLUGIN / 'charters' / 'planner.md').read_text(encoding='utf-8').split())
    assert 'Gates never go to Codex: a gate run as a `codex-companion` task or a Codex seat never counts' in text
    assert 'builders and fix rounds may go to Codex' in text and 'only once the workspace has recorded' not in text
    assert 'A brief for a seat on Codex tells it not to use MCP tools' in text
    docs = ' '.join((PLUGIN / 'docs' / 'site' / 'concepts' / 'codex.md').read_text(encoding='utf-8').split())
    assert 'a Codex seat never counts' in docs and 'counts only once' not in docs


def test_the_planner_finishes_before_starting_under_a_wip_limit_and_a_seat_ceiling():
    flat = lambda *parts: ' '.join((PLUGIN.joinpath(*parts)).read_text(encoding='utf-8').split())  # noqa: E731
    planner = flat('charters', 'planner.md').split('## Running the work', 1)[1].split('\n2. ', 1)[0]
    planner = ' '.join(planner.split())
    assert 'up to what the machine and the owner' not in planner
    assert 'Finish before starting' in planner and 'fewer than 4 items are in progress' in planner
    assert 'at most 8 seats running at once' in planner and 'say the cost once' in planner
    assert '`WIP limit: <n>`' in planner and '`Seat ceiling: <n>`' in planner and '`Item: <id>`' in planner
    assert 'under the WIP limit' in flat('charters', '_way.md')
    assert 'under the WIP limit' in flat('skills', 'wuwei-watch', 'SKILL.md')
    close = flat('skills', 'wuwei-close', 'SKILL.md')
    assert 'Housekeeping' in close and '`git worktree remove`' in close and 'never kill' in close
    steward = flat('charters', 'steward.md')
    assert 'peak live seats' in steward and "Little's law" in steward and 'duration_ms' in steward
    assert 'flow' in flat('docs', 'site', 'concepts', 'watch.md').lower() and 'WIP limit' in flat('docs', 'site', 'concepts', 'watch.md')
