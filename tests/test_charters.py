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
    for threshold in (f'at most {evidence.TRIVIAL} lines off risky paths', f'28-day change failure rate is over {evidence.BUDGET:.0%}'.replace('%', ' percent'),
                      f'about {evidence.MAX_LINES} changed lines', f'{days} days or more', f'at `standard`, risky or owner paths add security and a wide change (over {evidence.WIDE} lines of code and specs, or 10 code files) adds arch',
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
