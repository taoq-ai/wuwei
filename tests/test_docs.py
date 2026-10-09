"""Keep the public docs aligned with the shipped entry points and config."""

from argparse import Namespace
import json
import os
from pathlib import Path
import posixpath
import re
import runpy
import subprocess
import sys
import tarfile
import tomllib
from xml.etree import ElementTree

from wuwei import calibrate, integrity, registry


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'docs/site'
TABLE = re.compile(r'^\s*#?\s*\[\[?([\w.]+)\]\]?\s*$')
# Issue #366: the glossary terms in concepts.md order, each with the word forms that count as a use.
GLOSSARY = (('Seat', r'seats?'), ('Gate', r'gates?'), ('Sentinel', r'sentinels?'),
            ('Shepherd', r'shepherds?'), ('Steward', r'stewards?'), ('CAP', r'cap'),
            ('Seats per goal', r'seats per goal'),
            ('Envelope', r'envelopes?'), ('Tier', r'tiers?'), ('Pace', r'paces?'), ('Soak', r'soak'),
            ('Delta', r'deltas?'), ('Park', r'park(?:s|ed|ing)?'),
            ('Carry', r'carr(?:y|ies|ied|ying)'), ('Nudge', r'nudges?'), ('Page', r'pages?'),
            ('Digest', r'digests?'), ('Unmeasured', r'unmeasured'), ('Mandate', r'mandates?'),
            ('Novel', r'novel'),
            ('Trust surface', r'trust surfaces?'), ('Host terminal', r'host terminals?'),
            ('Humanizer', r'humanizer'), ('Spec engine', r'spec engines?'), ('Strict mode', r'strict mode'),
            ('Docs system', r'docs systems?'), ('Docs obligation', r'docs obligations?'),
            ('Ticket', r'tickets?'), ('Tracker hygiene', r'tracker hygiene'), ('Fold', r'fold(?:s|ed)?'),
            ('Adopted', r'adopted'), ('Lens', r'lens(?:es)?'))


def _prose(text):
    """text with fenced and inline code, HTML tags and link targets blanked; offsets kept."""
    return re.sub(r'```.*?```|`[^`\n]*`|<[^>]+>|(?<=\])\([^)]*\)',
                  lambda m: ' ' * len(m[0]), text, flags=re.S)


def test_interview_options_lead_with_plain_words():
    from wuwei import interview
    words = [pattern for _, pattern in GLOSSARY] + [re.escape(word) for word in (
        'floor', 'control plane', 'control-plane', 'deploy.deny', 'one-way')]
    for row in interview.QUESTIONS:
        # Design 5.10 fixes the spec question's wording, glossary term included.
        question = () if row['id'] == 'spec' else (row['question'],)
        for text in (row['header'], *question, *(d for _, d, _ in row['choices'])):
            lead = text.split('(', 1)[0]
            for word in words:
                assert not re.search(rf'\b{word}\b', lead, re.I), (row['id'], word, text)
    gates = {label: description for label, description, _ in interview.question('gates')['choices']}
    assert gates['Light'].startswith('Small low-risk changes get one reviewer agent')
    assert all('three reviewer agents' in gates[label] for label in ('Standard', 'Full'))


def test_concepts_opens_with_the_glossary():
    section = (SITE / 'concepts.md').read_text().split('\n## ', 2)[1]
    assert section.startswith('Glossary\n')
    entries = re.findall(r'^### (.+)\n\n((?:.+\n)+)', section, re.M)
    assert [title for title, _ in entries] == [term for term, _ in GLOSSARY]
    for title, body in entries:
        assert len(body.splitlines()) <= 2, title


def test_decision_lenses_documented():
    """#475: the lens config row, the index entry and the record shape in concepts."""
    configuration = (SITE / 'configuration.md').read_text()
    assert '| `decisions.lenses` |' in configuration and '`[decisions.lenses]`' in configuration
    concepts = (SITE / 'concepts.md').read_text()
    for word in ('Title', 'Rationale', 'Consequence', 'Reasoning', '`design`', '`boundary`', '`refactor`'):
        assert word in concepts, word


def test_glossary_words_link_at_first_use():
    for path in (ROOT / 'README.md', SITE / 'index.md', SITE / 'daily.md'):
        text = path.read_text()
        prose = _prose(text)
        links = [(m.start(), m.end(), m[2]) for m in re.finditer(r'\[([^\]]*)\]\(([^)]*)\)', text)]
        for term, pattern in GLOSSARY:
            found = re.search(rf'\b{pattern}\b', prose, re.I)
            if not found:
                continue
            anchor = term.lower().replace(' ', '-')
            assert any(start <= found.start() < end
                       and re.search(rf'concepts\.(?:html|md)#{anchor}$', target)
                       for start, end, target in links), (
                path.name, term, text[max(found.start() - 20, 0):found.end() + 20])


def test_daily_shows_a_clean_first_day():
    daily = (SITE / 'daily.md').read_text()
    for number, markers in (('2', ('plugin integrity: clean', 'code host login:', 'Interview answers:',
                                   '- review_bot: None -> adapters.review_bot = "none"',
                                   '- reviewers: Owner only -> shepherd.min_reviewers = 0',
                                   'Test runner found: acme/widget: python3 -m pytest -q',
                                   'Applied the setup and recorded .wuwei/calibration.json',
                                   'Status line: added to .claude/settings.json',
                                   'Optional: bin/wuwei promote; 2 more in bin/wuwei doctor\n'
                                   'Ready: run /wuwei:wuwei-plan\n',
                                   '  warn       watch: not installed',
                                   'doctor: 1 fail, 1 warn, 0 unmeasured')),
                            ('3', ('goals: 1 goal saved (G-1)', 'planned 1/1', 'planned item(s) can'))):
        section = daily.split(f'\n## {number}. ', 1)[1].split('\n## ', 1)[0]
        blocks = re.findall(r'```text\n(.*?)```', section, re.S)
        for marker in markers:
            assert any(marker in block for block in blocks), (number, marker)
    assert 'Still owed' not in daily and 'Next: /wuwei plan' not in daily
    source = '\n'.join(path.read_text() for path in ROOT.glob('cli/wuwei/**/*.py'))
    for marker in ('plugin integrity: clean', 'code host login:', 'Interview answers:', 'and recorded .wuwei/calibration.json',
                   'Test runner found: ', 'Status line: added to .claude/settings.json', 'more in bin/wuwei doctor',
                   "'Optional: '", 'Ready: run /wuwei:wuwei-plan', "'not installed'", 'planned item(s) can'):
        assert marker in source, marker


def test_readme_install_and_hero():
    readme = (ROOT / 'README.md').read_text()
    for phrase in ('prefers-color-scheme: dark', 'docs/site/assets/hero-light.svg',
                   'docs/site/assets/hero-dark.svg', '无为',
                   'What WUWEI is and is not', '/plugin marketplace add taoq-ai/wuwei',
                   '/plugin install wuwei@wuwei', 'wuwei init', '/wuwei plan'):
        assert phrase in readme
    # #561: the brand accent belongs to the art and the design spec, not the README text.
    assert '#00C9A7' not in readme and 'brand accent' not in readme.lower()
    assert 'deploy' not in readme.split('## What WUWEI is and is not', 1)[1].split('\n## ', 1)[0]
    index = (SITE / 'index.md').read_text()
    for variant in ('light', 'dark'):
        art = SITE / f'assets/hero-{variant}.svg'
        svg = ElementTree.parse(art).getroot()
        assert svg.tag == '{http://www.w3.org/2000/svg}svg'
        assert '#00C9A7' in art.read_text()
        assert all(word in art.read_text() for word in ('Specs and plan', 'Agent team', 'Gates', 'Pull requests',
                                                        'Review and merge'))
        assert f'<img src="assets/hero-{variant}.svg#only-{variant}"' in index, variant


# #561: the nine principles in order, each as (phrases in the item, link in the item).
PRINCIPLES = (
    (('model walks it', 'wuwei next', 'judgement'), '(docs/site/agent.md'),
    (('observe', 'guarded', 'warning or a card', 'floor', 'records', 'strict'),
     '(docs/site/security.md#security-posture)'),
    (('moment of action', 'invariant', 'code host'), '(docs/site/concepts.md#guards)'),
    (('mit cisr', 'routine', 'mandate', 'strategic', 'one-way', 'card'),
     '(docs/site/concepts.md#decision-classes-and-cruise-levels)'),
    (('ledger', 'ceiling', 'novel', 'undo', 'error budget', 'brier', 'shadow'),
     '(docs/site/daily.md#cruise-answers)'),
    (('records', 'card', 'confirmation', 'host terminal'), '(docs/site/concepts.md#drafts-and-cards)'),
    (('unmeasured', 'ci is the gate', 'live source'), '(docs/site/concepts.md#unmeasured)'),
    (('ziran', 'signed', 'posture', 'deploy', 'approve', 'admin'), '(docs/site/security.md)'),
    (('stdlib', 'delet'), '(https://github.com/taoq-ai/wuwei/blob/main/.specify/memory/constitution.md)'),
)


def _principles(readme):
    section = readme.split('\n## Principles\n', 1)[1].split('\n## ', 1)[0]
    return [line for line in section.splitlines() if line.strip()]


def test_readme_states_the_principles():
    readme = (ROOT / 'README.md').read_text()
    for gone in ('## How WUWEI compares', '### How they compose', '## Philosophy', 'BMAD',
                 'kiro.dev', 'Who plans the day'):
        assert gone not in readme, gone
    items = _principles(readme)
    assert [re.match(r'^(\d)\. ', item).group(1) for item in items] == [str(n) for n in range(1, 10)]
    for item, (phrases, link) in zip(items, PRINCIPLES, strict=True):
        for phrase in phrases:
            assert phrase in item.lower(), (phrase, item[:40])
        assert link in item, link
        assert len(re.sub(r'\]\([^)]*\)', ']', item).split()) <= 110, item[:40]
        assert '\N{EM DASH}' not in item
    for n in range(556, 561):
        assert f'https://github.com/taoq-ai/wuwei/issues/{n})' in items[4], n
    for word in ('professional', 'enterprise', 'best-in-class'):
        assert word not in readme.lower(), word


def test_readme_landing_marks_follow_main():
    # #561: "landing" names only issues whose feature has not landed (no specs/<n>-* yet),
    # so the word has to go once the feature reaches main.
    readme = (ROOT / 'README.md').read_text()
    shipped = lambda n: any(ROOT.glob(f'specs/{n}-*'))
    sentences = [s for line in readme.splitlines() for s in re.split(r'(?<=[.!?])\s+', line)
                 if re.search(r'\blanding\b', s, re.I)]
    landing = set()  # #586: no landing mark is left once every marked issue shipped
    for sentence in sentences:
        issues = {int(n) for n in re.findall(r'taoq-ai/wuwei/issues/(\d+)\)', sentence)}
        assert issues, sentence
        landing |= issues
    assert not [n for n in landing if shipped(n)], landing
    principle = _principles(readme)[4]
    for n in range(556, 561):
        marked = any(f'issues/{n})' in s for s in re.split(r'(?<=[.!?])\s+', principle)
                     if re.search(r'\blanding\b', s, re.I))
        assert marked != shipped(n), n


def test_readme_lead_and_limits():
    readme = (ROOT / 'README.md').read_text()
    lead = readme.split('Apache 2.0</a></p>', 1)[1].split('## What WUWEI is and is not', 1)[0]
    for phrase in ('careful engineering team', 'ranked', 'did not write', 'retro'):
        assert phrase in lead, phrase
    intro = (SITE / 'index.md').read_text().split('# WUWEI documentation', 1)[1].strip().split('\n\n', 1)[0]
    for word in ('ranked', 'retro'):
        assert word in intro, word
    assert (readme.index('## Quick start') < readme.index('## Limits')
            < readme.index('## Development installs'))
    section = readme.split('## Limits', 1)[1].split('\n## ', 1)[0]
    flat = ' '.join(section.split()).lower()
    for phrase in ('needs claude code', 'one owner per workspace', '40 to 100 ms', 'its author',
                   'live rehearsal', 'docs/site/reference.md#hook-latency-budget',
                   'docs/site/rehearsal.md', 'docs/site/security.md', 'setup --shadow', 'observe'):
        assert phrase in flat, phrase


def test_readme_tells_the_day_in_superpowers_shape():
    from wuwei.__main__ import GROUPS
    readme = _plain('README.md')
    assert len(readme.splitlines()) <= 300
    new = ('## How it works', '## The basic workflow', '## When something goes wrong',
           '## What is inside', '## Principles', '## Installation')
    order = [readme.index(f'\n{h}\n') for h in ('## What ships today', *new, '## Quick start')]
    assert order == sorted(order)
    section = lambda h: readme.split(f'\n{h}\n', 1)[1].split('\n## ', 1)[0]
    flat = lambda h: ' '.join(section(h).split()).lower()
    story = section('## How it works')
    paragraphs = [p for p in re.split(r'\n\s*\n', story) if p.strip()]
    assert len(paragraphs) == 4
    for paragraph in paragraphs:
        assert re.search(r'\byou\b', paragraph, re.I) and len(paragraph.strip().splitlines()) <= 5, paragraph
    for phrase in ('/wuwei:wuwei-plan', 'retro', 'status line', 'DM', 'safe path'):
        assert phrase in ' '.join(story.split()), phrase
    workflow = section('## The basic workflow')
    blocks = re.findall(r'^```mermaid\n(.*?)^```$', workflow, re.M | re.S)
    assert len(blocks) == 1 and blocks[0].startswith('flowchart LR')
    chart = blocks[0]
    stages = [chart.index(f'["{name}') for name in (
        'Setup and calibration', 'Plan and the morning gate', 'Build', 'Review by tier',
        'Shepherd to merge', 'Close and retro')]
    assert stages == sorted(stages)
    assert re.search(r'close -- "memory into tomorrow[^"]*" --> plan', chart)
    assert re.search(r'you\b.*-\.-> plan & review$', chart, re.M)
    assert re.search(r'hooks\(\["hooks check every action"\]\) -\.-> build$', chart, re.M)
    assert workflow.index('```mermaid') > workflow.index('In words:')
    assert 'not built' not in flat('## The basic workflow')
    assert len(workflow.strip().splitlines()) < 25
    wrong = section('## When something goes wrong')
    assert len(re.findall(r'^- ', wrong, re.M)) == 5
    for phrase in ('why last refusal', 'doctor --fix', 'wuwei next', 'shadow report', '.wuwei/days/'):
        assert phrase in wrong, phrase
    inside = section('## What is inside')
    for path in (ROOT / 'skills').glob('*/SKILL.md'):
        assert f'(skills/{path.parent.name}/SKILL.md)' in inside, path.parent.name
    for path in (ROOT / 'charters').glob('[!_]*.md'):
        assert f'(charters/{path.name})' in inside, path.name
    for event in json.loads((ROOT / 'hooks/hooks.json').read_text())['hooks']:
        assert event in inside, event
    assert '(docs/site/index.md)' in inside and '(docs/site/adapters.md)' in inside
    rows = {port: {name.strip('`') for name in names.strip().split(', ')}
            for port, names in re.findall(r'^\| `?([a-z_]+)`? \| ([^|]+) \|', inside, re.M)}
    assert rows == {port: set(registry.known(port)) for port in registry.INTERFACES}
    planned = next(line for line in inside.splitlines() if line.startswith('Planned:'))
    installed = {name for port in registry.INTERFACES for name in registry.known(port)}
    assert not {word.lower() for word in re.findall(r'\b[A-Z]\w+', planned)} & installed, planned
    install =section('## Installation')
    parts = install.split('\n### ')
    assert [part.split('\n', 1)[0] for part in parts[1:]] == [
        'Claude Code', 'Codex', 'Other harnesses (planned)']
    claude, codex, others = parts[1:]
    assert claude.index('wuwei.tar.gz') < claude.index('/plugin marketplace add ../wuwei-plugin')
    assert '/plugin marketplace add taoq-ai/wuwei' in claude and '(#development-installs)' in claude
    for phrase in ('adapters.runtime', 'codex.command', '(docs/specs/2026-09-30-codex-plugin-spike.md)'):
        assert phrase in codex, phrase
    if not (ROOT / '.codex-plugin/plugin.json').exists():
        assert 'planned' in codex
    assert 'https://github.com/taoq-ai/wuwei/issues/441' in others and '```' not in others
    assert 'planned' in others and 'measured' in others
    text = '\n'.join(section(h) for h in new)
    assert all((ROOT / 'skills' / name).is_dir() for name in re.findall(r'/wuwei:([a-z-]+)', text))
    commands = ' '.join(words for _, words in GROUPS).split()
    for span in re.findall(r'`([^`\n]+)`', text):
        for command in re.findall(r'\bwuwei ([a-z][a-z-]*)', span):
            assert command in commands, span


def test_docs_index_mirrors_the_readme_sections():
    readme = (ROOT / 'README.md').read_text()
    pairs = (('How it works', 'daily'), ('The basic workflow', 'concepts'),
             ('When something goes wrong', 'recovery'), ('What is inside', 'adapters'),
             ('Principles', 'security'), ('Installation', 'integrity'))
    for heading, page in pairs:
        assert f'(docs/site/{page}.md' in readme.split(f'\n## {heading}\n', 1)[1].split('\n## ', 1)[0], page
    index = (SITE / 'index.md').read_text().split('\n## Start here\n', 1)[0]
    pages = '\n'.join(line for line in index.splitlines() if line.startswith('- ['))
    positions = [pages.index(f'({page}.md)') for _, page in pairs]
    assert positions == sorted(positions)


def test_hero_variants_share_geometry_and_motion():
    dark, light = ((SITE / f'assets/hero-{v}.svg').read_text() for v in ('dark', 'light'))
    mask = lambda text: re.sub(r'#[0-9A-Fa-f]{3,8}', '#', text)
    assert mask(dark) == mask(light)
    assert 'prefers-reduced-motion' in dark and 'animateMotion' in dark


def test_site_pages_are_plain_markdown():
    for path in SITE.rglob('*.md'):
        text = path.read_text()
        assert not text.startswith('---') and '[Home](index' not in text, path.name
        for target in re.findall(r'\]\(([^)\s]+)\)', text):
            if ':' in target or target.startswith('#'):
                continue
            file = target.split('#', 1)[0]
            assert not file.endswith('.html') and (path.parent / file).is_file(), (path.name, target)
    assert '9.1' in (SITE / 'security.md').read_text()
    assert (ROOT / 'skills/wuwei-plan/SKILL.md').is_file()


def test_mkdocs_nav_covers_every_page():
    config = (ROOT / 'mkdocs.yml').read_text()
    for phrase in ('site_name: WUWEI', 'site_url: https://taoq-ai.github.io/wuwei/',
                   'repo_url: https://github.com/taoq-ai/wuwei', 'docs_dir: docs/site',
                   'name: material', 'scheme: slate', 'scheme: default', 'primary: indigo',
                   'accent: cyan', 'navigation.tabs', 'content.code.copy', 'permalink: true',
                   'omitted_files: warn', 'anchors: warn', 'unrecognized_links: warn'):
        assert phrase in config, phrase
    nav = set(re.findall(r'^\s*- (?:[^:\n]+: )?([\w./-]+\.md)\s*$', config, re.M))
    pages = {path.relative_to(SITE).as_posix() for path in SITE.rglob('*.md')}
    assert nav == pages, (sorted(pages - nav), sorted(nav - pages))
    index = (SITE / 'index.md').read_text()
    for page in sorted(pages - {'index.md'}):
        assert f'({page})' in index, page


def test_docs_workflow_deploys_mkdocs():
    workflow = (ROOT / '.github/workflows/docs.yml').read_text()
    for phrase in ('docs/site/**', 'mkdocs.yml', 'contents: write', 'astral-sh/setup-uv',
                   'uvx --with mkdocs-material mkdocs gh-deploy --force --strict'):
        assert phrase in workflow, phrase
    assert 'jekyll' not in workflow and 'pages: write' not in workflow
    assert not (SITE / '_config.yml').exists()
    ignore = (ROOT / '.gitignore').read_text().split()
    assert '/site/' in ignore and 'site/' not in ignore  # unanchored would also ignore docs/site


def test_release_rehearsal_page_is_runnable_alone():
    page = (SITE / 'rehearsal.md').read_text()
    for phrase in ('python3 scripts/headless_e2e.py --rehearsal', 'WUWEI_REHEARSAL_REPO', 'GH_TOKEN',
                   'ANTHROPIC_API_KEY', '--local-login', 'decision outcome', 'unmeasured',
                   'exit 2', 'before a release'):
        assert phrase in page
    assert 'credential skip' not in (ROOT / 'docs/headless-e2e.md').read_text()


def test_operator_reference_covers_schema_and_companion():
    page = (SITE / 'reference.md').read_text()
    for name in ('plan template', 'rank template', 'decision template', 'WSJF', 'RICE',
                 'trust_surface', 'boundary_relevant', 'agent_surface', 'envelope',
                 'Blocked:', 'Gap:', 'Change:', '[retro]', 'merge.auto', 'task',
                 'status', 'result', 'cancel', '--json', 'jobId', 'workspaceRoot',
                 'storedJob.result.rawOutput'):
        assert name in page


def test_retro_and_merge_examples_are_in_shipped_config():
    template = (ROOT / 'templates/workspace/config.toml').read_text()
    page = (SITE / 'configuration.md').read_text()
    for phrase in ('[retro]', 'repo = "."', 'charter_paths', 'changelog', '[repos.merge]', 'auto = false'):
        assert phrase in template
    for key in ('retro.repo', 'retro.charter_paths', 'retro.changelog', 'repos.merge.auto'):
        assert f'`{key}`' in page


def test_every_template_config_key_is_documented():
    template = (ROOT / 'templates/workspace/config.toml').read_text()
    page = (SITE / 'configuration.md').read_text()
    section = ''
    keys = set()
    for line in template.splitlines():
        table = TABLE.match(line)
        if table:
            section = table.group(1)
            continue
        assignment = re.match(r'^\s*#?\s*([A-Za-z_][\w]*)\s*=', line)
        if assignment:
            keys.add(f'{section}.{assignment.group(1)}' if section else assignment.group(1))
    missing = sorted(key for key in keys if f'`{key}`' not in page)
    assert not missing, f'Undocumented config keys: {missing}'
    tomllib.loads(template)


def test_template_security_starts_with_posture_and_has_no_guards_mode():
    template = (ROOT / 'templates/workspace/config.toml').read_text()
    assert 'guards.mode' not in template
    # [spec] has its own mode key (5.10); no other table may.
    assert not re.search(r'^\s*mode\s*=', template.replace('\nmode = "strict"\n', '\n', 1), re.MULTILINE)
    assert 'mode' not in tomllib.loads(template)['guards']
    block = template.split('\n[security]\n', 1)[1].splitlines()
    first = next(i for i, line in enumerate(block) if line.strip() and not line.startswith('#'))
    assert block[first].startswith('posture =')
    for profile in ('observe', 'guarded', 'strict'):
        assert sum(line.startswith(f'# {profile}:') for line in block[:first]) == 1


def test_worktree_git_hooks_is_documented():
    rows = {line.split('|')[1].strip(): line for line in (SITE / 'configuration.md').read_text().splitlines()
            if line.startswith('| `')}
    row = rows['`worktree.git_hooks`']
    for word in ('`chain`', '`skip`', '`replace`', 'worktree.hooks_skipped', 'strict', 'PreToolUse'):
        assert word in row, word


def test_docs_retire_guards_mode():
    rows = {line.split('|')[1].strip(): line for line in (SITE / 'configuration.md').read_text().splitlines()
            if line.startswith('| `')}
    assert 'doctor --fix' in rows['`guards.mode`'] and 'init --upgrade' in rows['`guards.mode`']
    assert '--shadow' in rows['`security.posture`'] and 'guards.shadow_days' in rows['`security.posture`']
    page = (SITE / 'security.md').read_text()
    assert 'setup --shadow' in page
    assert '`guards.mode = "shadow"` (`init --shadow`) counts as `observe`' not in page


def test_entry_guides_install_signed_release_and_explain_development_checkout():
    integrity = (SITE / 'integrity.md').read_text()
    assert 'source checkouts are unsigned and report a page' not in integrity
    assert 'clean commit' in integrity and 'HEAD' in integrity and '.in_use' in integrity
    for path in (ROOT / 'README.md', SITE / 'index.md'):
        text = path.read_text()
        for phrase in ('releases/latest/download/wuwei.tar.gz', 'curl -fL', 'tar -xzf',
                       'bin/wuwei init', 'integrity reconfirm', 'clean', 'HEAD', '/wuwei plan'):
            assert phrase in text, (path.name, phrase)
        assert text.index('wuwei.tar.gz') < text.index('/plugin marketplace add')
        for stale in ('git clone', 'skill is not present', 'not shipped in this version',
                      'interactive day planner is planned'):
            assert stale not in text, (path.name, stale)
    marketplace = json.loads((ROOT / '.claude-plugin/marketplace.json').read_text())
    entry = next(plugin for plugin in marketplace['plugins'] if plugin['name'] == 'wuwei')
    assert entry['source'] == './'
    assert 'development source' in entry['description'].lower()


def test_shepherd_settings_are_visible_in_template_and_site():
    template = (ROOT / 'templates/workspace/config.toml').read_text()
    page = (SITE / 'configuration.md').read_text()
    settings = tomllib.loads(template)['shepherd']
    for key in ('lead_login', 'authors', 'review_channel', 'review_gate_check',
                'tie_commits', 'source_exclude', 'min_reviewers', 'autostart', 'reviewers',
                'reviewers_exclude'):
        assert key in settings
        assert f'`shepherd.{key}`' in page
    assert settings['min_reviewers'] == 1
    assert settings['reviewers'] == settings['reviewers_exclude'] == []
    assert '`repos.shepherd.reviewers`' in page and '`[repos.shepherd]`' in page
    assert '# [repos.shepherd]' in template
    assert settings['autostart'] is True
    row = next(line for line in page.splitlines() if line.startswith('| `shepherd.min_reviewers`'))
    assert '`0`' in row.split('|')[3]


def _hero():
    import importlib.util
    spec = importlib.util.spec_from_file_location('build_hero', ROOT / 'scripts/build-hero.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hero_files_match_their_generator():
    module = _hero()
    for name, palette in module.PAL.items():
        assert (SITE / f'assets/hero-{name}.svg').read_text() == module.svg(palette), name


def test_reference_verdict_example_and_phase_table():
    from wuwei import state, verdict
    reference = (SITE / 'reference.md').read_text()
    example = re.search(r'## Gate verdict layout\n.*?```text\n(.*?)```', reference, re.S)[1]
    assert verdict.lint(example, quality=True, class_sweep=True)[0] == 0
    for phase, following in state.PHASES.items():
        assert f'| `{phase}` | {", ".join(following) or "none"} |' in reference
    for phrase in ('worktree add', 'stdin', 'sentinel-arch', 'watch off', 'watch dead'):
        assert phrase in reference
    configuration = (SITE / 'configuration.md').read_text()
    assert all(phrase in configuration for phrase in ('--dry-run', 'watch off', 'watch dead',
                                                      'refuses `watch uninstall`'))
    clears = 'clears at the next clock line, or after `watch uninstall` when no clock line was written today'
    assert clears in ' '.join(configuration.split()) and clears in ' '.join(reference.split())
    assert 'wuwei worktree add' in (ROOT / 'cli/wuwei/dispatch.py').read_text()  # #551: the start entry


def test_host_terminal_actions_and_morning_references():
    reference = (SITE / 'reference.md').read_text()
    concepts = (SITE / 'concepts.md').read_text()
    for text in (reference, concepts):
        assert 'Host terminal actions' in text
        for command in ('decision outcome', 'decide', 'state recover', 'integrity reconfirm', 'mcp decide',
                        'drafts approve', 'watch uninstall', 'listen uninstall', 'config promote',
                        'config set', 'config add-repo', 'setup', 'memory forget'):
            assert command in text
    for phrase in ('run it in a host terminal', 'no plan yet', 'proposal.json', 'pr raise',
                   '--base', '--title', '--body-file', '--item'):
        assert phrase in reference


def test_reference_states_hook_latency_budget():
    reference = ' '.join((SITE / 'reference.md').read_text().split())
    workflow = (ROOT / '.github/workflows/tests.yml').read_text()
    for phrase in ('Hook latency budget', '50 ms CPU p95 on developer hardware (M-series class)',
                   'about 2x on 2-CPU CI runners', '100 ms wall p95', 'python3 -I -c pass',
                   'a trend line, not a gate', 'continue-on-error', 'WUWEI_BENCH=1',
                   'startup floor'):
        assert phrase in reference, phrase
    command = 'python -m pytest -q tests/test_hooks.py -k latency'
    assert command in reference and command in workflow
    assert 'continue-on-error: true' in workflow
    assert 'latency budget' in (SITE / 'index.md').read_text()


def test_guard_boundaries_are_stated_once():
    flat = lambda text: ' '.join(text.split())
    spec = (ROOT / 'docs/specs/2026-09-24-wuwei-design.md').read_text()
    section = lambda number: flat(re.search(rf'^### {number} .*?(?=^##)', spec, re.S | re.M)[0])
    matching, threat = section(r'4\.5'), section(r'9\.1')
    testing = flat(re.search(r'^## 10\. .*?(?=^## )', spec, re.S | re.M)[0])
    security = flat((SITE / 'security.md').read_text())
    constitution = flat((ROOT / '.specify/memory/constitution.md').read_text())
    for phrase in ('the parser is the only local check',
                   'the guarantee comes from the code host and the credential layout',
                   'no token in seat environments that can approve, release or deploy',
                   '`wuwei config check` verifies',
                   'further local checks, not boundaries',
                   'narrow argv allowlist may be used for privileged publish actions only',
                   'allowing an interpreter or the test runner allows arbitrary code'):
        assert phrase in matching, phrase
    for text in (threat, security):
        for phrase in ('cooperative mistake prevention', 'isolation boundary',
                       'protected refs, required checks, required reviews',
                       'publication credentials kept out of seat environments'):
            assert phrase in text, phrase
    assert 'none of them is a boundary' in threat
    assert ('no seat holds a token that can approve, release or deploy, and a merge lands only '
            "through the protected ref's required checks and reviews") in threat
    assert 'push and merge are guaranteed by the host rules' in security
    assert not re.search(r'second anchor|local anchors', spec, re.I)
    for phrase in ('What a real day must prove', 'live rehearsal', 'unmeasured, never a pass'):
        assert phrase in testing, phrase
    assert 'design reconsideration recorded in its spec' in constitution and '#222' in constitution


def test_calibration_is_documented_between_configure_and_plan():
    daily = (SITE / 'daily.md').read_text()
    for phrase in ('bin/wuwei calibrate', 'bin/wuwei config promote', 'calibration.md'):
        assert phrase in daily, phrase
    assert daily.index('bin/wuwei calibrate') < daily.index('/wuwei plan')
    configuration = (SITE / 'configuration.md').read_text()
    section = configuration.split('\n## Calibration\n', 1)[1].split('\n## ', 1)[0]
    for phrase in ('.wuwei/calibration.json', 'calibration.drift', 'config promote',
                   'instruction-like', 'edit by hand', '--measure', 'calibrate.fast_check_seconds',
                   'CI only', 'repos.fast_checks'):
        assert phrase in section, phrase
    row = next(line for line in (SITE / 'reference.md').read_text().splitlines()
               if line.startswith('| `bin/wuwei calibrate`'))
    assert '--measure' in row



def test_owner_interview_is_documented_next_to_calibration():
    daily = (SITE / 'daily.md').read_text()
    interview = daily.index('bin/wuwei calibrate --interview')
    assert daily.index('bin/wuwei calibrate') < interview < daily.index('/wuwei plan')
    configuration = (SITE / 'configuration.md').read_text()
    assert configuration.split('\n## Calibration\n', 1)[1].split('\n## ', 1)[1].startswith('Owner interview\n')
    section = configuration.split('\n## Owner interview\n', 1)[1].split('\n## ', 1)[0]
    for phrase in ('calibrate --interview', '--questions', '--answer', 'interview.json', 'config promote',
                   'wuwei promote', '--interview merge'):
        assert phrase in section, phrase
    from wuwei import guide
    assert '.wuwei/charters/planner.md' in (ROOT / 'skills/wuwei-plan/SKILL.md').read_text()
    for phrase in ('calibrate --questions', 'calibrate --answer'):  # #551: next asks, the guide records
        assert phrase in guide.text(), phrase


def test_pr_flow_is_documented():
    assert 'wuwei doctor --section pr-flow' in (ROOT / 'cli/wuwei/commands/next.py').read_text()
    doctor = (SITE / 'reference.md').read_text().split('\n## Doctor\n', 1)[1].split('\n## ', 1)[0]
    assert 'PR flow' in doctor and '--section pr-flow' in doctor
    configuration = (SITE / 'configuration.md').read_text()
    section = configuration.split('\n## Owner interview\n', 1)[1].split('\n## ', 1)[0]
    for phrase in ('`tracker`', '`chat`', '`review_bot`'):
        assert phrase in section, phrase
    daily = (SITE / 'daily.md').read_text()
    assert 'shepherd.lead_login' in daily and 'shepherd.authors' in daily


def test_calibration_profiles_are_documented_after_the_interview():
    configuration = (SITE / 'configuration.md').read_text()
    assert configuration.split('\n## Owner interview\n', 1)[1].split('\n## ', 1)[1].startswith(
        'Calibration profiles\n')
    section = configuration.split('\n## Calibration profiles\n', 1)[1].split('\n## ', 1)[0]
    for phrase in ('calibrate export', 'calibrate import', '--skip', 'profile.json', 'templates/profiles/',
                   'python-library', 'cli-tool', 'merge.auto', 'gates.floor', 'shepherd.autostart',
                   'decisions.cruise', 'adapters', 'calendar.url', 'watch.ping_url', 'codex.command'):
        assert phrase in section, phrase
    row = next(line for line in (SITE / 'reference.md').read_text().splitlines()
               if line.startswith('| `bin/wuwei calibrate`'))
    assert 'export' in row and 'import' in row


RECOVERY = ('state transition', 'runtime dispatch', 'runtime continue', 'integrity reconfirm')


def test_daily_path_and_recovery_pages():
    daily = (SITE / 'daily.md').read_text()
    for phrase in ('/wuwei plan', 'wuwei.tar.gz', 'plan approve', 'build next', 'dispatch next',
                   'pr raise', 'pr state', 'wuwei decide', 'close',
                   'Remote Control', 'Push when actions required'):
        assert phrase in daily, phrase
    for command in RECOVERY:
        assert command not in daily, command
    recovery = (SITE / 'recovery.md').read_text()
    for command in RECOVERY:
        section = recovery.split(command, 1)[1].split('\n## ', 1)[0]
        assert 'recovery' in section.lower(), command


def test_remote_runbook_matches_the_code():
    import base64
    import contextlib
    import io
    from wuwei import control_plane, env, remote, workspace
    from wuwei.commands.config import PIN_MISSING
    from wuwei.commands.event import EVENT_PRODUCERS
    page = (SITE / 'remote.md').read_text()
    flat = ' '.join(page.split())
    assert '(remote.md)' in (SITE / 'daily.md').read_text()
    headings = ['## Connect Slack in one command', '## 1. Remote Control, no setup', '## 2. The Slack app', '## 3. Pin your identity',
                '## 4. The second factor', '## 5. Install the listener', '## 6. Commands from the DM',
                '## 7. Decisions on the phone', '## 8. Limits']
    positions = [page.index(f'\n{heading}\n') for heading in headings]
    assert positions == sorted(positions)
    assert 'bin/wuwei setup slack' in page[positions[0]:positions[1]]
    for name in ('remote.md', 'daily.md'):
        assert 'A phone answer is not yet your outcome' not in (SITE / name).read_text(), name
    slack = (ROOT / 'adapters/chat/slack.py').read_text()
    for method in ('conversations.history', 'chat.postMessage'):
        assert method in slack and f'`{method}`' in page, method
    for scope in ('channels:history', 'groups:history', 'im:history', 'chat:write'):
        assert f'`{scope}`' in page, scope
    for key in ('SLACK_BOT_TOKEN', 'SLACK_USER_TOKEN', 'SLACK_OWNER_DM_CHANNEL', 'WUWEI_TOTP_SECRET',
                'SLACK_API_BASE'):
        assert key in env.CREDENTIALS and key in page, key
    pin = page[page.index('## 3. Pin'):page.index('## 4. ')]
    listener = ' '.join(page[page.index('## 5. '):page.index('## 6. ')].split())
    assert 'owner.name: not set' in page and '`owner.name`' in pin
    assert 'listen --once' in listener and 'exit 0' in listener and 'exit 2' in listener
    for section, key in re.findall(r'`([a-z_]+)\.([a-z_]+)(?: = [^`]*)?`', page):
        assert (key in workspace.SCHEMA.get(section, {}) or f'{section}.{key}' in EVENT_PRODUCERS
                or f'{section}.{key}' in ('conversations.history', 'config.toml')), f'{section}.{key}'
    for command in re.findall(r'bin/wuwei ([a-z_]+)', page):
        assert (ROOT / f'cli/wuwei/commands/{command}.py').is_file(), command
    for text in (remote.VOCABULARY, remote.CONFIRM, remote.CHANGED, remote.NOTHING, remote.UNAVAILABLE,
                 control_plane.HELP, 'Push when actions required', 'organisation Owner',
                 remote.RECORDED.format(identifier='D-3', option='B'),
                 remote.NOTED.format(identifier='D-3', option='B'), 'decision.replied', 'wuwei decide',
                 'drafts approve', 'listen install', 'listen uninstall', 'listen dead',
                 'responder.enabled = false', 'stop all', 'loginctl enable-linger', 'resets at midnight',
                 'otpauth://totp/', 'algorithm=SHA1&digits=6&period=30', 'App Home', 'Messages Tab',
                 'Allow users to send Slash commands and messages from the messages tab',
                 'OAuth & Permissions', 'Bot Token Scopes', 'Agent tools are refused these commands',
                 'answered from the phone', remote.ANSWERED.format(identifier='D-3', option='B'),
                 'WUWEI_TOTP_SECRET: set', '`wuwei status` shows `listen dead`', 'phone answers 1',
                 'bin/wuwei remote ack', 'remote.acknowledged'):
        assert text in flat, text
    section = ' '.join(pin.split())
    assert PIN_MISSING in section and 'stays paged until the day ends' not in section
    decisions = ' '.join(page[page.index('## 7. '):page.index('## 8. ')].split())
    assert 'for decisions a `plan` session raises' not in decisions
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exec(re.search(r'python3 -c "([^"]+)"', page)[1], {})
    assert len(base64.b32decode(output.getvalue().strip())) == 20
    assert not re.search(r'xox[a-z]-', page)
    ids = {found for found in re.findall(r'\b[CDTUW][A-Z0-9]{6,}\b', page) if re.search(r'\d', found)}
    assert ids <= {'T0123ABC', 'U0123ABC', 'D0123ABC'}, ids
    assert '\N{EM DASH}' not in page


def test_implemented_protections_are_not_planned():
    for path in [*SITE.glob('*.md'), ROOT / 'README.md', *(ROOT / 'docs').glob('*.md')]:
        for line in path.read_text().splitlines():
            if re.search(r'\bplanned\b', line, re.I):
                assert not re.search('manifest|canar|honeytoken', line, re.I), (path.name, line)
    assert 'Planned:' not in (SITE / 'concepts.md').read_text()
    skill = (ROOT / 'skills/wuwei-plan/SKILL.md').read_text()
    assert 'transition the item to `fix`' not in skill
    assert '`seats`' in skill and '`receive`' in skill
    adapters = (SITE / 'adapters.md').read_text()
    assert 'including control planes' not in adapters and '[control_plane]' in adapters

def test_config_check_host_and_credential_layout_are_documented():
    page = (SITE / 'configuration.md').read_text()
    section = page[page.index('### Host protections and seat credentials'):]
    for text in ('Host protections', 'Seat credentials', '`ok`', '`missing`', '`unmeasured`',
                 'exit 0', 'exit 1', 'exit 2', 'design 4.5', '9.1', 'classic protection',
                 'none visible (404: unprotected or no admin)', 'required now', 'review_gate_check'):
        assert text in section, text
    assert 'currently reads as missing' not in page

def test_github_tracker_gh_auth_and_credential_diagnostics_are_documented():
    # #602: the opt-in, its trade-off and how seats reach it; the malformed and HTTP status lines.
    adapters = (SITE / 'adapters.md').read_text()
    adapters = ' '.join(adapters.split())
    section = adapters[adapters.index('### GitHub tracker through your gh login'):]
    for text in ('`tracker.auth = "gh"`', 'gh api graphql', 'GITHUB_TRACKER_TOKEN', 'is used first',
                 'only through `bin/wuwei`', 'least privilege', 'gh auth refresh -s project', 'strict',
                 'security.md', '`GH_TOKEN`'):
        assert text in section, text
    for text in ('malformed (contains whitespace)', 'looks like a path', 'HTTP 401', 'HTTP 403', 'HTTP 404'):
        assert text in adapters, text
    page = (SITE / 'configuration.md').read_text()
    assert '| `tracker.auth` | `"token"` |' in page and 'malformed' in page


def test_loop_robustness_is_documented():
    # #617: one steward on the newest brief; a failing tracker lookup is named and per ticket.
    page = ' '.join((SITE / 'configuration.md').read_text().split())
    assert 'newest steward brief' in page and 'while a steward seat runs' in page
    reference = ' '.join((SITE / 'reference.md').read_text().split())
    assert '`lead_time.unmeasured`' in reference and 'while a steward seat runs' in reference
    adapters = ' '.join((SITE / 'adapters.md').read_text().split())
    assert 'GitHub error response for <owner>/<repo>#<n>' in adapters


def test_release_asset_ships_every_linked_doc(tmp_path, monkeypatch):
    signed = []
    def sign(manifest, key):
        signed.append(Path(manifest))
        Path(str(manifest) + '.sig').write_text('signature')
        return registry.Result(0)
    monkeypatch.setattr(integrity, 'signature_adapter', lambda: Namespace(
        sign=sign, verify=lambda *a: registry.Result(0)))
    build = runpy.run_path(str(ROOT / 'scripts/build-release.py'))['build']
    archive = build(ROOT, tmp_path / 'release', tmp_path / 'key')
    stage = tmp_path / 'release/wuwei'
    listed = {line[66:] for line in (stage / integrity.MANIFEST).read_text().splitlines()}
    assert {'LICENSE', 'NOTICE', 'SECURITY.md'} <= listed
    resolved, missing = set(), []
    for path in [ROOT / 'README.md', *sorted((ROOT / 'skills').rglob('*.md')),
                 *sorted((ROOT / 'agents').rglob('*.md'))]:
        name = path.relative_to(ROOT).as_posix()
        for match in re.finditer(r'\]\(([^)\s]+)\)|(?:src|srcset|href)="([^"]+)"', path.read_text()):
            target = match.group(1) or match.group(2)
            if ':' in target or target.startswith('#'):
                continue
            link = posixpath.normpath(posixpath.join(posixpath.dirname(name), target.split('#')[0]))
            resolved.add(link)
            if link not in listed:
                missing.append(f'{name} -> {target}')
    assert 'docs/site/index.md' in resolved
    assert not missing, missing
    expected = {p.relative_to(ROOT).as_posix() for p in
                [*SITE.glob('*.md'), *(SITE / 'assets').glob('*.svg')]}
    with tarfile.open(archive) as tar:
        archived = {n.removeprefix('wuwei/') for n in tar.getnames()}
    assert expected <= listed and expected <= archived
    assert signed == [stage / integrity.MANIFEST]
    assert integrity.measure(stage).exit == 0


def test_repository_gate_keys_are_documented():
    from wuwei import workspace
    page = (SITE / 'configuration.md').read_text()
    assert all(f'`repos.gates.{key}`' in page for key in workspace.SCHEMA['repos'][0]['gates'])
    assert '`tier`' in (SITE / 'reference.md').read_text()


def test_daily_long_sessions_section():
    page = (SITE / 'daily.md').read_text()
    assert '## Long sessions' in page and page.index('## Long sessions') < page.index('## 6. Close')
    section = page[page.index('## Long sessions'):page.index('## 6. Close')]
    for phrase in ('sessions.rotate_after', '--take-over', 'Active constraints', 'Quality by band',
                   'owner.timezone', 'metrics.band_margin'):
        assert phrase in section, phrase
    template = (ROOT / 'templates/workspace/config.toml').read_text()
    assert all(key in template for key in ('timezone', 'band_margin', 'rotate_after'))


def test_heartbeat_is_documented():
    from wuwei import heartbeat
    reference = (SITE / 'reference.md').read_text()
    section = reference.split('## Heartbeat\n', 1)[1].split('\n## ', 1)[0]
    for name, _ in heartbeat.PROBES:
        assert f'`{name}`' in section, name
    for phrase in ('heartbeat: clock', 'health degraded', 'behaviour drift', 'watch.ping_url'):
        assert phrase in section, phrase
    assert '`watch.ping_url`' in (SITE / 'configuration.md').read_text()
    assert 'no external dead-man ping' not in (SITE / 'remote.md').read_text()


def test_reference_lists_every_cli_command(tmp_path):
    result = subprocess.run([sys.executable, '-P', '-m', 'wuwei', '--help', '--all'], capture_output=True,
                            text=True, cwd=tmp_path, env={**os.environ, 'PYTHONPATH': str(ROOT / 'cli')})
    assert result.returncode == 0, result.stderr
    commands = set(re.findall(r'^  ([a-z-]+) ', result.stdout, re.M))
    section = (SITE / 'reference.md').read_text().split('\n## Commands\n', 1)[1].split('\n## ', 1)[0]
    listed = set(re.findall(r'^\| `bin/wuwei ([a-z-]+)`', section, re.M))
    assert listed == commands, (sorted(commands - listed), sorted(listed - commands))


def test_configuration_names_every_config_section():
    from wuwei import workspace
    template = (ROOT / 'templates/workspace/config.toml').read_text()
    sections = {match[1] for line in template.splitlines() if (match := TABLE.match(line))}
    sections |= {name for name, rule in workspace.SCHEMA.items() if isinstance(rule, (dict, list))}
    page = (SITE / 'configuration.md').read_text()
    page = page.split('\n## Sections\n', 1)[1].split('\n## ', 1)[0]
    missing = sorted(name for name in sections if f'`[{name}]`' not in page and f'`[[{name}]]`' not in page)
    assert not missing, missing


def test_readme_first_day_and_shipped_areas():
    readme = (ROOT / 'README.md').read_text()
    index = (SITE / 'index.md').read_text()
    for text, heading in ((readme, '## Quick start'), (index, '## Start here')):
        section = text.split(f'\n{heading}\n', 1)[1].split('\n## ', 1)[0]
        steps = [section.index(step) for step in ('setup --shadow', 'bin/wuwei doctor', '/wuwei plan')]
        assert steps == sorted(steps), heading
        assert 'config set' in section, heading
    assert (readme.index('## What WUWEI is and is not') < readme.index('## What ships today')
            < readme.index('## Principles'))
    ships = readme.split('\n## What ships today\n', 1)[1].split('\n## ', 1)[0]
    for link in ('docs/site/daily.md', 'docs/site/security.md', 'docs/site/concepts.md#review-tiers',
                 'docs/site/remote.md', 'docs/site/concepts.md#cockpit-and-board',
                 'docs/site/configuration.md#calibration', 'docs/site/reference.md#heartbeat',
                 'docs/specs/2026-09-24-wuwei-design.md', 'docs/site/daily.md#2-configure',
                 'docs/site/reference.md#doctor', 'docs/site/security.md#security-posture',
                 'docs/site/agent.md'):
        assert f'({link})' in ships, link


def test_cruise_mode_ships():
    # #283: cruise mode is built; no page calls it designed or not built.
    readme = (ROOT / 'README.md').read_text()
    for path in [ROOT / 'README.md', *SITE.glob('*.md')]:
        for paragraph in re.split(r'\n\s*\n', path.read_text()):
            if re.search('cruise', paragraph, re.I):
                assert 'not built' not in ' '.join(paragraph.split()), (path.name, paragraph)
    assert 'cruise' in readme.split('\n## What ships today\n', 1)[1].split('\n## ', 1)[0]
    configuration = (SITE / 'configuration.md').read_text()
    for key in ('margin', 'max_per_day', 'undo_minutes', 'promote_agreements', 'promote_days',
                'budget_share', 'budget_window_days', 'burn_warn'):
        assert f'`decisions.cruise.{key}`' in configuration, key
    daily = (SITE / 'daily.md').read_text()
    assert 'decision undo' in daily and 'cruise off' in daily
    assert '`undo D-<n>`' in (SITE / 'reference.md').read_text()
    assert 'cruise' in (SITE / 'concepts.md').read_text()


def test_concepts_and_daily_cover_shipped_mechanisms():
    concepts = (SITE / 'concepts.md').read_text()
    for heading in ('Review tiers', 'Decision classes and cruise levels', 'Sessions', 'Listener',
                    'Heartbeat', 'Cockpit and board'):
        assert f'\n## {heading}\n' in concepts, heading
    daily = (SITE / 'daily.md').read_text()
    assert '`tier`' in daily.split('3. Gates:', 1)[1].split('4. Fix round:', 1)[0]
    assert 'phone answers' in daily.split('\n## 5. ', 1)[1].split('\n## ', 1)[0]


def test_security_integrity_and_cross_links():
    for path in (SITE / 'security.md', SITE / 'integrity.md'):
        text = path.read_text()
        assert 'plugin.json' in text and 'mcp check' in text, path.name
    assert '(rehearsal.md)' in (SITE / 'recovery.md').read_text()
    assert '(recovery.md)' in (SITE / 'rehearsal.md').read_text()


def test_shipped_things_are_not_called_planned():
    for path, stale in ((SITE / 'configuration.md', 'MCP scanning (#35)'),
                        (SITE / 'configuration.md', 'Planned planner rotation'),
                        (SITE / 'reference.md', 'will set `remote`'),
                        (SITE / 'reference.md', 'nothing sets `remote`'),
                        (ROOT / 'README.md', 'with three parallel review gates'),
                        (SITE / 'charter-overrides.md', '**Planned:**'),
                        (ROOT / 'README.md', 'interactive day planner')):
        assert stale not in path.read_text(), (path.name, stale)


def _smil(text):
    """(tag, attributes, ancestor classes) for every SMIL element in an SVG text."""
    root = ElementTree.fromstring(text)
    parents = {child: parent for parent in root.iter() for child in parent}
    found = []
    for el in root.iter():
        tag = el.tag.split('}')[1]
        if tag.startswith('animate'):
            up, classes = el, set()
            while up in parents:
                up = parents[up]
                classes |= set(up.get('class', '').split())
            found.append((tag, el.attrib, classes))
    return found


def _value_at(attrs, k):
    """Linear lookup of a numeric SMIL value at key time k."""
    times = [float(t) for t in attrs['keyTimes'].split(';')]
    values = [float(v) for v in attrs['values'].split(';')]
    for (t0, v0), (t1, v1) in zip(zip(times, values), zip(times[1:], values[1:])):
        if t0 <= k <= t1 and t1 > t0:
            return v0 + (v1 - v0) * (k - t0) / (t1 - t0)
    return values[-1]


def _hero_parts(text):
    """(static, still, live) slices of a hero SVG: drawn first, the reduced-motion frame, the animation."""
    static, rest = text.split('<g class="still"', 1)
    still, live = rest.split('<g class="live"', 1)
    return static, still, live


def _timing(text, ident):
    """Attributes of the <animate> that is the first child of the element with this id."""
    attrs = re.search(rf'id="{ident}"[^>]*>\s*<animate ([^>]*)', text)[1]
    return dict(re.findall(r'(\w[\w-]*)="([^"]*)"', attrs))


def _popped(stops):
    return max(k for k, p in stops if p == 'off')


def _place(stops, k):
    return [p for at, p in stops if at <= k][-1]


def test_hero_shows_the_system():
    hero = _hero()
    readme = (ROOT / 'README.md').read_text()
    alts = re.findall(r'<img src="assets/hero-[^>]*alt="([^"]+)"', (SITE / 'index.md').read_text())
    assert alts == [hero.ALT, hero.ALT] and re.search(r'alt="([^"]+)"', readme)[1] == hero.ALT
    assert hero.ALT.count('. ') == 0 and hero.ALT.endswith('.') and 'treadmill' not in hero.ALT.lower()
    for part in ('queue', 'agent team', 'gates', 'pull requests', 'card', 'under the hood'):
        assert part in hero.ALT.lower(), part
    names = [name for name, *_ in hero.STAGES]
    smalls = [small for _, small, *_ in hero.STAGES]
    assert len(names) == 5 and [x for *_, x in hero.STAGES] == sorted(x for *_, x in hero.STAGES)
    assert all(len(n.split()) <= 3 for n in names) and all(len(s.split()) <= 6 for s in smalls)
    assert hero.STAGES[0][2] == hero.STAGES[-1][2], 'you at both ends'
    for variant in ('light', 'dark'):
        art = SITE / f'assets/hero-{variant}.svg'
        text = art.read_text()
        static, still, live = _hero_parts(text)
        assert len(art.read_bytes()) < 40000, variant
        assert re.search(r'<desc[^>]*>(.*?)</desc>', text, re.S)[1] == hero.ALT
        labels = re.findall(r'<text[^>]*>([^<]+)<', static)
        for row in (names, smalls):
            at = [labels.index(word) for word in row]
            assert at == sorted(at), (variant, row)
        for i in range(5):
            assert re.search(rf'<path id="icon-{i}"[^>]*fill="none"', static), (variant, i)
        for panel in ('queue', 'lanes', 'prs', 'cards', 'band'):
            assert f'id="panel-{panel}"' in static, (variant, panel)
        for phrase in ('build ⟲ check', 'raise PR', 'sweep', 'overnight: sweeps, never merges',
                       *hero.LOOPS, hero.DAY, *hero.INDICATORS):
            assert f'>{phrase}<' in static, (variant, phrase)
        for i, name in enumerate(hero.QUEUE, 1):
            pill = re.search(rf'<g>(<animate [^>]*/>)<rect [^>]*/><text [^>]*>{i} · {name}</text></g>', live)
            attrs = dict(re.findall(r'(\w[\w-]*)="([^"]*)"', pill[1]))
            assert _value_at(attrs, 0) == 1, (variant, name)
        for lane in range(3):
            assert f'id="build-{lane}"' in static, (variant, lane)
            for n in range(3):
                assert f'id="gate-{lane}-{n}"' in static, (variant, lane, n)
        assert 'fix ×1 → delta' in text and 'id="fix-loop"' in live and 'id="sweep"' in static
        for loop in ('ask-loop', 'answer-loop'):
            assert re.search(rf'id="{loop}"[^>]*stroke-dasharray', static), (variant, loop)
        assert 'id="day-loop"' in static
        for phrase in (*[label for label, _, _ in hero.PRS], *[d[3] for d in hero.DECISIONS],
                       *[d[2] for d in hero.DECISIONS if d[2]], 'Approved · 3 seats',
                       'answers a card now and then', f'{hero.clock(hero.CLOSE)} close: report written, retro done',
                       '09:00', '18:00'):
            assert phrase in text, (variant, phrase)
        for brand in ('Linear', 'Jira', 'GitHub', 'Claude', 'Codex', 'Slack', 'Notion', 'Confluence',
                      'Discord', 'PagerDuty', 'Grafana', 'Sentry', 'Datadog', 'ZIRAN', 'pytest',
                      'spec-kit', 'treadmill'):
            assert brand not in text, (variant, brand)
        assert all(h.startswith('#') for h in re.findall(r'href="([^"]*)"', text)) and 'url(http' not in text
        smil = _smil(text)
        assert smil and all('live' in classes for _, _, classes in smil), variant
        for tag, attrs, _ in smil:
            if 'keyTimes' in attrs:
                times = [float(t) for t in attrs['keyTimes'].split(';')]
                assert times[0] == 0 and times[-1] == 1 and times == sorted(times), (tag, attrs)
                assert len(times) == len(attrs['values'].split(';')), (tag, attrs)
        reduced = re.search(r'@media \(prefers-reduced-motion:\s*reduce\)\s*\{(.*?)\}\s*\}', text, re.S)[1]
        classes = {name for attr in re.findall(r'class="([^"]+)"', text) for name in attr.split()}
        assert classes == {'live', 'still', 'spin', 'beat'}, classes
        for name in classes:
            assert f'.{name}' in reduced, (variant, name)
    assert len((ROOT / 'scripts/build-hero.py').read_text().splitlines()) < 320


def test_hero_only_moves_forward():
    hero = _hero()
    for name, _, stops in hero.ITEMS:
        xs = [hero.PLACES[place] for _, place in stops]
        assert xs == sorted(xs), name
        assert [k for k, _ in stops] == sorted(k for k, _ in stops), name
    name, on, off = hero.FIX
    stops = next(s for n, _, s in hero.ITEMS if n == name)
    assert any(a <= on and off <= b and p == q == 'gates' for (a, p), (b, q) in zip(stops, stops[1:])), stops
    for variant in ('light', 'dark'):
        text = (SITE / f'assets/hero-{variant}.svg').read_text()
        motions = [attrs for tag, attrs, _ in _smil(text) if tag == 'animateMotion']
        assert len(motions) == len(hero.ITEMS), variant
        for attrs in motions:
            xs = [float(pair.split(',')[0]) for pair in attrs['values'].split(';')]
            assert xs == sorted(xs), attrs['values']
        fix = _timing(text, 'fix-loop')
        assert _value_at(fix, (on + off) / 2) > 0.5, variant
        assert _value_at(fix, on - .02) < 0.5 and _value_at(fix, off + .02) < 0.5, variant


def test_hero_queue_lanes_and_cards():
    hero = _hero()
    order = sorted(hero.ITEMS, key=lambda i: _popped(i[2]))
    assert [name for name, *_ in order] == hero.QUEUE
    for lane in range(len(hero.LANE_Y)):
        spans = [(_popped(s), s[-1][0]) for _, l, s in order if l == lane]
        assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:])), lane
    for name, lane, stops in order[len(hero.LANE_Y):]:
        before = max((s for n, l, s in order if l == lane and _popped(s) < _popped(stops)), key=_popped)
        assert _popped(stops) == before[-1][0], name

    def waiting(k):
        busy = {l for _, l, s in hero.ITEMS if _popped(s) <= k < s[-1][0]}
        return len(busy) == len(hero.LANE_Y) and any(_popped(s) > k for _, _, s in hero.ITEMS)
    ks = [step / 1000 for step in range(1001) if waiting(step / 1000)]
    assert ks
    last = {name: s[-1] for name, _, s in hero.ITEMS}
    for label, raised, merged in hero.PRS:
        assert last[label.split(' ', 1)[1]] == (raised, 'PR'), label
    merges = [m for *_, m in hero.PRS]
    assert merges == sorted(merges)
    carried = sum(1 for k, p in last.values() if p != 'PR')
    phone = [d for d in hero.DECISIONS if d[4]]
    assert all(any(a <= d[0] and d[1] <= b and c == 'warm' for a, b, c in hero.PHONE) for d in phone)
    first, close = min(_popped(s) for _, _, s in hero.ITEMS), hero.CLOSE
    for variant in ('light', 'dark'):
        text = (SITE / f'assets/hero-{variant}.svg').read_text()
        _, still, live = _hero_parts(text)
        waits = _timing(text, 'waits')
        assert _value_at(waits, (ks[0] + ks[-1]) / 2) > 0.5 and _value_at(waits, .1) < .5 and _value_at(waits, .9) < .5
        for n in range(len(hero.PRS) + 1):
            assert f'>shipped today: {n}<' in live, (variant, n)
        assert f'carried to tomorrow: {carried}' in text
        assert f'asked today: {len(phone)} of {len(hero.DECISIONS)}' in text
        ask, answer = _timing(text, 'ask-loop-lit'), _timing(text, 'answer-loop-lit')
        for asked, answered, *_ in hero.DECISIONS:
            assert _value_at(ask, asked + .015) > .5 and _value_at(answer, answered + .015) > .5, (variant, asked)
        lead, day = _timing(text, 'lead'), _timing(text, 'day-loop-lit')
        last_pop = max(_popped(s) for _, _, s in hero.ITEMS)
        assert _value_at(lead, last_pop + .03) > .5 and _value_at(lead, .5) < .5, variant
        assert _value_at(day, close + .03) > .5 and _value_at(day, .5) < .5, variant
        assert '<animate' not in still and hero.clock(hero.STILL_K) in still, variant
        assert first < hero.STILL_K and 'waits: CAP 3 seats' in still and 'fix ×1 → delta' in still
        for i, (name, lane, stops) in enumerate(order, 1):
            queued, in_lane = _popped(stops) > hero.STILL_K, _popped(stops) <= hero.STILL_K < stops[-1][0]
            assert (f'{i} · {name}<' in still) == queued, (variant, name)
            if in_lane:
                x, y = hero.at(_place(stops, hero.STILL_K), lane)
                assert f'x="{x}" y="{y + 5}" text-anchor="middle">{name}<' in still, (variant, name)
        for asked, answered, opened, closed, _ in hero.DECISIONS:
            if opened and asked <= hero.STILL_K < answered:
                assert opened in still and closed not in still, (variant, opened)
            elif answered <= hero.STILL_K:
                assert closed in still, (variant, closed)


def test_pr_events_are_documented():
    configuration = (SITE / 'configuration.md').read_text()
    row = next(line for line in configuration.splitlines() if line.startswith('| `pr.poll_seconds`'))
    assert '30 s' in row
    daily = ' '.join((SITE / 'daily.md').read_text().split())
    for text in ('prs <n> changed', 'next turn', 'PR monitor'):
        assert text in daily, text
    remote = ' '.join((SITE / 'remote.md').read_text().split())
    for text in ('If-None-Match', '`shepherd.autostart`', 'details are on the host', 'no webhooks'):
        assert text in remote, text


def test_owner_verbosity_and_voice_are_documented():
    from wuwei import remote, workspace
    configuration = (SITE / 'configuration.md').read_text()
    for key in ('default', *workspace.SURFACES):
        assert f'`owner.verbosity.{key}`' in configuration, key
    assert '`verbosity`' in configuration
    for name in ('daily.md', 'reference.md'):
        page = (SITE / name).read_text()
        assert 'decision show' in page and '--full' in page, name
    page = (SITE / 'remote.md').read_text()
    assert remote.VOCABULARY in ' '.join(page.split()) and 'more D-n' in page
    concepts = (SITE / 'concepts.md').read_text()
    assert all(word in concepts for word in ('humanizer', '3.1.0', 'MIT', '`ai_tells`', '`style`'))


def test_outward_humanize_is_documented():
    configuration = (SITE / 'configuration.md').read_text()
    for key in ('humanize', 'humanize_kinds', 'humanize_strict'):
        assert f'`outward.{key}`' in configuration, key
    concepts = (SITE / 'concepts.md').read_text()
    assert '`outward.ai_tells`' in concepts and 'humanize_strict' in concepts
    assert 'a tell never blocks a send' not in concepts
    row = next(line for line in (SITE / 'reference.md').read_text().splitlines()
               if line.startswith('| `bin/wuwei drafts approve <id>` |'))
    assert 'humanize' in row


def test_owner_channel_in_skills():
    # #495: the owner's own DM is where the planner posts when owner_channel = "dm".
    from wuwei import guide
    plan = guide.text()  # #551: the guide holds the rule, next names the DM on the report row
    for word in ('outbound.owner_channel', 'outbound.owner.slack.dm', 'outbound learn --tool', '--owner <file>'):
        assert word in plan, word
    assert 'config set outbound.owner' not in plan  # Learned on the card, never typed (#492).
    assert 'owner_channel' in (ROOT / 'cli/wuwei/commands/next.py').read_text()
    configuration = (SITE / 'configuration.md').read_text()
    assert '`outbound.owner`' in configuration and '`outbound.owner_channel`' in configuration
    security = (SITE / 'security.md').read_text()
    assert 'outward.to_owner' in security and 'unknown DM recipient' in security


def test_mandate_waits_and_loops_are_documented():
    configuration = (SITE / 'configuration.md').read_text()
    for key in ('decisions.wait_hours', 'decisions.cruise.enabled', 'decisions.cruise.levels',
                'steward.loop_window_hours', 'steward.loop_threshold'):
        assert f'`{key}`' in configuration, key
    concepts = (SITE / 'concepts.md').read_text()
    for phrase in ('mandate block', 'Assumptions:', '--external', 'negotiation.loop'):
        assert phrase in concepts, phrase
    assert 'loops N' in (SITE / 'daily.md').read_text()
    reference = (SITE / 'reference.md').read_text()
    assert 'decision route D-n --external' in reference and '`Assumption:`' in reference


def _plain(name):
    text = (ROOT / name).read_text()
    assert '\N{EM DASH}' not in text and not any(ord(c) >= 0x1F000 for c in text), name
    return text


def test_security_policy_scope_and_channel():
    text = ' '.join(_plain('SECURITY.md').split())
    for phrase in ('cooperative mistake prevention', 'isolation boundary',
                   "a determined process running as the owner's user with a shell",
                   'private vulnerability reporting', 'latest release', 'docs/site/security.md',
                   'injected instruction', 'forge', 'manifest', 'credential'):
        assert phrase in text, phrase
    assert re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', text) is None


def test_contributing_points_at_the_rules():
    text = _plain('CONTRIBUTING.md')
    for phrase in ('AGENTS.md', '.specify/memory/constitution.md', 'python3 -m pytest -q',
                   'scripts/build-hero.py', 'SECURITY.md', 'stdlib',
                   'uvx --with mkdocs-material mkdocs serve', 'gh-pages'):
        assert phrase in text, phrase
    assert 'test first' in text.lower()
    assert calibrate.instruction_like(text) == []


def test_notice_credits_match_readme_acknowledgements():
    notice, readme = _plain('NOTICE'), (ROOT / 'README.md').read_text()
    assert '\n## Acknowledgements\n' in readme
    section = readme.split('\n## Acknowledgements\n', 1)[1]
    assert '\n## ' not in section
    urls = re.findall(r'https://[^\s)]+', notice)
    missing = [u for u in urls if u not in section]
    assert urls and not missing, missing
    spec_kit = _plain('.specify/LICENSE')
    assert 'Copyright GitHub, Inc.' in spec_kit and 'Permission is hereby granted' in spec_kit
    for text in ('.specify/', '.agents/skills/speckit-', '.specify/LICENSE'):
        assert text in notice, text
    for name in ('Spec Kit', 'autoharness', 'ralph-starter', 'humanizer', 'Model Context Protocol',
                 'MCP Apps', 'release-please', 'ZIRAN', 'WSJF', 'RICE', 'two-way door', 'Simple Icons',
                 'superpowers', 'OpenSpec', 'CISR', 'vGOAL', 'error budget', 'Brier'):
        assert name.lower() in notice.lower(), name
    assert '16.33.0' in notice and 'CC0' in notice
    superpowers = notice.split('\nsuperpowers\n', 1)[1].split('\n\n', 1)[0]
    assert 'README' in superpowers and 'MIT' in superpowers


def test_doctor_is_the_first_stop():
    from wuwei.commands import doctor
    for page in ('recovery.md', 'daily.md'):
        assert 'bin/wuwei doctor' in (SITE / page).read_text(), page
    section = (SITE / 'reference.md').read_text().split('\n## Doctor\n', 1)[1].split('\n## ', 1)[0]
    for name, (command, _, _) in doctor.FIXES.items():
        assert f'`{name}`' in section and command in section, name
    assert '/dev/tty' in section and 'doctor.fixed' in section
    daily = (SITE / 'daily.md').read_text()
    first = daily.split('\n## 1. ', 1)[1].split('\n## ', 1)[0]
    assert first.index('setup --shadow') < first.index('bin/wuwei doctor')
    flat = ' '.join(daily.split())
    for key in ('security.posture', 'guards.shadow_days', 'owner.timezone', 'metrics.band_margin',
                'sessions.rotate_after'):
        assert f'bin/wuwei config set {key}' in flat, key
    assert '"guarded"` in `config.toml`' not in flat
    intro = (SITE / 'configuration.md').read_text().split('\n## Sections\n', 1)[0]
    assert 'bin/wuwei config set' in intro and 'bin/wuwei config add-repo' in intro


TROUBLESHOOTING = (  # the 0.11.0 trial findings B1 to B9, in order
    ('.in_use', 'bin/wuwei integrity check'),
    ('not attached (unapproved)', 'bin/wuwei mcp decide proceed-unmeasured'),
    ('does not load', 'bin/wuwei config check'),
    ('delete that line before using [[repos]] tables', 'bin/wuwei init --upgrade'),
    ('by hand', 'bin/wuwei config set'),
    ('fast_checks = []', 'bin/wuwei config promote'),
    ('CI only', 'bin/wuwei calibrate --measure'),
    ('none visible (404: unprotected or no admin)', 'bin/wuwei config check'),
    ('read-only', 'bin/wuwei why last refusal'),
)


def test_troubleshooting_covers_the_first_run_findings():
    section = (SITE / 'recovery.md').read_text().split('\n## Troubleshooting\n', 1)[1].split('\n## ', 1)[0]
    assert re.search(r'bin/wuwei [a-z-]+', section)[0] == 'bin/wuwei doctor'
    entries = [' '.join(entry.split()) for entry in section.split('\n### ')[1:]]
    assert len(entries) == len(TROUBLESHOOTING)
    for entry, (symptom, command) in zip(entries, TROUBLESHOOTING):
        assert symptom in entry and command in entry, (symptom, command)
    assert integrity.MARKERS == '.in_use'


def test_security_posture_table_matches_the_code():
    from wuwei import workspace
    page = (SITE / 'security.md').read_text()
    section = page.split('\n## Security posture\n', 1)[1].split('\n## ', 1)[0]
    rows = [[cell.strip() for cell in line.strip().strip('|').split('|')]
            for line in section.splitlines() if line.startswith('|')]
    default = workspace.SCHEMA['security']['posture'][1]
    names = [cell.removesuffix(' (default)') for cell in rows[0][2:]]
    assert names == list(workspace.POSTURES) and f'{default} (default)' in rows[0]
    table = {row[0].strip('`'): row[2:] for row in rows[2:]}
    assert table == {area: [workspace.POSTURES[name][area] for name in names] for area in workspace.AREAS}
    flat = ' '.join(section.split())
    for area, level in workspace.FLOORS.items():
        assert f'`{area}` always {level}s' in flat, area
    assert workspace.SCHEMA['scanner']['mcp']['block'][1] == []  # #351: the posture decides
    assert '`scanner.mcp.block`, which is unset by default: no severity under `guarded`' in flat
    assert '`critical`, `high` and `unmeasured` under `strict`' in flat
    ziran = ' '.join(page.split('\n## ZIRAN integration\n', 1)[1].split('\n## ', 1)[0].split())
    for phrase in ('Under `observe` and `guarded` (the default) every finding warns',
                   'never starts an unapproved project server', '`uvx`, `npx` or `pipx run`'):
        assert phrase in ziran, phrase


def test_agent_guide_ships_and_is_linked():
    from wuwei import guide
    page = (SITE / 'agent.md').read_text()
    assert len(page.splitlines()) <= 100
    # #476: the reference between the markers is the printed `wuwei guide`, one source.
    assert page.count(guide.START) == 1 and page.split(guide.START, 1)[1].split(guide.END, 1)[0] == (
        '\n' + guide.text())
    for phrase in ('wuwei next', '/wuwei:wuwei-plan', '/wuwei:wuwei-report', '.wuwei/executable',
                   '-P', 'host terminal', 'posture:', 'planner', 'lead', 'builder', 'sentinel',
                   'shepherd', 'steward', 'first word of a plain command', 'wuwei guide'):
        assert phrase in page, phrase
    daily = (SITE / 'daily.md').read_text().split('\n## 1. ', 1)[1].split('\n## ', 1)[0]
    assert 'open Claude Code in the workspace and say what you want; the session knows the rest' in daily
    row = next(line for line in (SITE / 'configuration.md').read_text().splitlines()
               if line.startswith('| `memory.export_to`'))
    assert 'guide block' in row
    assert '--start' in (ROOT / 'docs/headless-e2e.md').read_text()
    assert '\N{EM DASH}' not in page and not any(ord(c) >= 0x1F000 for c in page)
    for name in ('index.md', 'daily.md'):
        assert '(agent.md)' in (SITE / name).read_text(), name
    readme = (ROOT / 'README.md').read_text()
    assert 'orients itself' in readme.split('\n## Quick start\n', 1)[1].split('\n## ', 1)[0]
    for skill in sorted(ROOT.glob('skills/*/SKILL.md')):
        body = skill.read_text().split('\n# ', 1)[1].split('\n\n', 2)[1]
        assert '`wuwei next`' in body, skill.parent.name


def test_skills_use_the_recorded_executable_directly():
    # #348: a session reads the pointer once and runs the absolute path as a plain command.
    for name in ('wuwei-plan', 'wuwei-report', 'wuwei-retro', 'wuwei-consolidate'):
        text = (ROOT / 'skills' / name / 'SKILL.md').read_text()
        assert '$(' not in text and 'executable recorded in' not in text, name
        for phrase in ('read `.wuwei/executable` once with the Read tool', 'first word of a plain command'):
            assert phrase in text, (name, phrase)


def test_owner_questions_use_widgets_or_the_dm():
    for path in (ROOT / 'skills').glob('*/SKILL.md'):
        text = path.read_text()
        for phrase in ('AskUserQuestion', 'decision route', '--widget', 'Seats never ask the owner'):
            assert phrase in text, (path.parent.name, phrase)
        assert 'Decided-by: owner' not in text and 'Outcome: proceed' not in text, path.parent.name
    from wuwei import guide
    plan = (ROOT / 'skills/wuwei-plan/SKILL.md').read_text()
    for phrase in ('record', 'wuwei_board'):
        assert phrase in plan, phrase
    for phrase in ('wuwei mcp check --widget', 'calibrate --answer'):
        assert phrase in guide.text(), phrase
    decisions = (SITE / 'daily.md').read_text().split('\n## 5. Owner decisions\n', 1)[1].split('\n## ', 1)[0]
    answer = decisions.split('\n### How you answer\n', 1)[1].split('\n#', 1)[0]
    for phrase in ('question card', 'DM', 'host terminal'):
        assert phrase in answer, phrase
def test_unparsed_commands_are_documented():
    # #347: the security page names the unparsed class and the cd rule's subshell form.
    security = ' '.join((SITE / 'security.md').read_text().split())
    for phrase in ('unparsed', '(cd <dir> && <command>)', 'blocks only under `strict`',
                   'read-only subcommands', '--help', 'unknown git subcommand', '`echo`'):
        assert phrase in security, phrase


def test_close_carry_skill_and_docs():
    from wuwei import guide
    from wuwei.commands import close
    report = (ROOT / 'skills/wuwei-report/SKILL.md').read_text()
    # #551: next returns the close, its card and the steward launch; the card records the carry.
    assert 'wuwei close --widget' in report and 'record' in report and 'wuwei close --widget' in guide.text()
    assert 'bin/wuwei plan <label>' in (ROOT / 'cli/wuwei/commands/close.py').read_text() and close.widget
    assert 'Outcome: carried' not in report and 'Outcome: parked' not in report
    retro = (ROOT / 'skills/wuwei-retro/SKILL.md').read_text()
    step = next(line for line in retro.splitlines() if line.startswith('1. '))
    assert all(phrase in step for phrase in ('wuwei close', 'steward_launch', 'open item'))
    concepts = (SITE / 'concepts.md').read_text()
    assert 'bin/wuwei plan carry' in concepts and 'bin/wuwei plan park' in concepts
    assert 'Outcome: carried ITEM' not in concepts


def test_one_gate_question():
    # #365: the morning gate is one approval; the separate questions come only on Change something.
    # #551: next returns the gate card (plan gate's widget) and its then line; the charter keeps the rule.
    from wuwei.commands import next as next_command
    assert "'wuwei plan gate'" in (ROOT / 'cli/wuwei/commands/next.py').read_text()
    assert 'Change something ask the owner what to change' in next_command.THEN['gate']
    charter = (ROOT / 'charters/planner.md').read_text()
    assert "Approve today's plan as proposed?" in charter and 'Change something' in charter
    after = charter.split('on `Change something`', 1)[1]
    for phrase in ('goals', 'queue', 'seat policy', 'CAP', 'envelope', 'carry-over'):
        assert phrase in after, phrase
    daily = (SITE / 'daily.md').read_text().split('\n## 3. Plan and the morning gate\n', 1)[1].split('\n## ', 1)[0]
    assert "Approve today's plan as proposed?" in daily and 'Change something' in daily
    assert 'question per decision' not in daily
    configuration = (SITE / 'configuration.md').read_text()
    assert '`[]`' in configuration.split('\n## Owner interview\n', 1)[1].split('\n## ', 1)[0]
    prompt = ROOT / 'evals/wuwei-plan-positive-06/prompt.md'
    assert 'once' in prompt.read_text().split('---', 2)[2]


def test_scanner_none_turns_the_gate_off():
    # #424: the docs say what scanner "none" turns off and what still blocks.
    security = ' '.join((SITE / 'security.md').read_text().split())
    configuration = ' '.join((SITE / 'configuration.md').read_text().split())
    assert 'the registry gate is off' in security
    assert 'mcp: not measured (no scanner configured; set adapters.scanner = "ziran" to measure)' in security
    assert 'cannot start (not on PATH, wrong version) is a check that could not run' in security
    assert 'The `none` scanner reports unmeasured rather than clean' not in security
    assert 'turns the registry gate off' in configuration and 'tool drift or poisoning' in configuration
    assert 'the `none` adapter are unmeasured' not in configuration


def test_pages_address_the_reader():
    # #362: the pages speak to their reader ("you"); agent.md speaks to the agent, the
    # charter page and the glossary entry define the role.
    found = []
    for path in sorted(SITE.glob('*.md')):
        if path.name in ('agent.md', 'charter-overrides.md'):
            continue
        text = path.read_text()
        if path.name == 'concepts.md':
            text = re.sub(r'\n## Glossary\n.*?(?=\n## )', '\n', text, flags=re.S)
        found += [f'{path.name}: {line}' for line in text.splitlines() if re.search(r'\bthe owner\b', line, re.I)]
    assert not found, f'{len(found)} lines:\n' + '\n'.join(found)


def test_memory_tiers_are_documented():
    configuration = (SITE / 'configuration.md').read_text()
    for phrase in ('memory.digest', 'memory.budget_tokens', 'memory.export_to', 'archive/<year>/'):
        assert phrase in configuration, phrase
    concepts = (SITE / 'concepts.md').read_text()
    memory = concepts[concepts.index('## Memory'):concepts.index('## Day flow')]
    for phrase in ('digest', '30 days', 'wuwei memory forget', 'CLAUDE.md'):
        assert phrase in memory, phrase
    reference = (SITE / 'reference.md').read_text()
    for phrase in ('memory show', 'memory status', 'memory export', 'memory forget', 'consolidate --widget'):
        assert phrase in reference, phrase
    doctor = reference[reference.index('## Doctor'):]
    assert 'memory tiers' in doctor[:doctor.index('\n## ', 5)]
    skill = (ROOT / 'skills/wuwei-consolidate/SKILL.md').read_text()
    for phrase in ('consolidate --widget', 'memory forget', 'memory show'):
        assert phrase in skill, phrase


def test_charters_carry_the_spec_mode():
    builder = (ROOT / 'charters/builder.md').read_text()
    assert 'Spec:' in builder and 'plan set' in builder
    assert 'skip_tiers' in (ROOT / 'charters/lead.md').read_text()
    assert 'spec=skipped' in (ROOT / 'charters/planner.md').read_text()
    assert 'spec engine' in (SITE / 'daily.md').read_text().lower()


def test_telemetry_is_documented():
    # #422: the plan skill presents proposals after the gate; the security page says what leaves.
    from wuwei import guide
    assert 'wuwei telemetry proposals --widget' in guide.text()  # #551: next returns the card
    security = (SITE / 'security.md').read_text()
    for phrase in ('IP address', 'your login', 'wuwei telemetry off', '`telemetry.share`'):
        assert phrase in security, phrase
    reference = (SITE / 'reference.md').read_text()
    for phrase in ('metrics --week', '`ms`', 'telemetry send'):
        assert phrase in reference, phrase
    assert 'telemetry send' in (SITE / 'concepts.md').read_text()
    assert 'OpenTelemetry' in (SITE / 'configuration.md').read_text()


def test_docs_system_is_documented():
    from wuwei import workspace
    configuration = (SITE / 'configuration.md').read_text()
    assert '`[docs]`' in configuration.split('\n## Sections\n', 1)[1].split('\n## ', 1)[0]
    for key in workspace.SCHEMA['docs']:
        assert f'`docs.{key}`' in configuration, key
    commands = (SITE / 'reference.md').read_text().split('\n## Commands\n', 1)[1].split('\n## ', 1)[0]
    for row in ('| `bin/wuwei docs page', '| `bin/wuwei docs publish', '| `bin/wuwei plan set <item> docs='):
        assert row in commands, row
    assert re.search(r'docs obligation', (SITE / 'daily.md').read_text(), re.I)
    adapters = (SITE / 'adapters.md').read_text()
    for name in ('NOTION_TOKEN', 'CONFLUENCE_EMAIL', 'CONFLUENCE_API_TOKEN'):
        assert name in adapters, name


def test_lead_goals_are_blocks_while_proposing():
    """#471: the lead writes proposed goals as blocks; the question lint sits in outward."""
    from wuwei.commands import next as next_command
    for rel in ('charters/lead.md', 'agents/lead.md'):
        assert 'never an id alone' in (ROOT / rel).read_text(), rel
    assert 'never an id alone' in next_command.LEAD_BODY  # #551: the lead brief next returns
    for path in (SITE / 'security.md', ROOT / 'docs/specs/2026-09-24-wuwei-design.md'):
        row, = [line for line in path.read_text().splitlines() if line.startswith('| `outward` |')]
        assert '`decision.check_question`' in row, path


def test_draft_card_is_documented():
    # #493: a draft names its rule, the card is how the owner decides, and the allowance is one call.
    concepts = (SITE / 'concepts.md').read_text()
    for phrase in ('allowance', 'card', 'bin/wuwei drafts show <id> --widget'):
        assert phrase in concepts, phrase
    assert 'one card away from being sent' in (SITE / 'daily.md').read_text()
    security = (SITE / 'security.md').read_text()
    assert 'You decide, on the card' in security and 'asks for a draft you send yourself' not in security
    assert any(line.startswith('| `outward.draft_ttl` | `3600` |')
               for line in (SITE / 'configuration.md').read_text().splitlines())


def test_grants_are_documented():
    # #478: the owner decides an owner-only action on a card; a grant is how they decide once.
    assert '`grants.standing`' in (SITE / 'configuration.md').read_text()
    concepts = (SITE / 'concepts.md').read_text()
    for phrase in ('Allow once', 'Allow today', 'Always allow', 'bin/wuwei grants revoke'):
        assert phrase in concepts, phrase
    security = (SITE / 'security.md').read_text()
    assert 'grant' in security and 'bin/wuwei grants revoke' in security
    assert 'Ask when it happens' in (SITE / 'daily.md').read_text()
    assert '`bin/wuwei grants revoke <n>`' in (SITE / 'reference.md').read_text()
    skill = (ROOT / 'skills/wuwei-plan/SKILL.md').read_text()
    assert 'decision show D-n --widget' in skill and 'prints a list' in skill


def test_outbound_tiers_docs():
    # #496: the tier table, the audience classes and the commands are documented.
    concepts = (SITE / 'concepts.md').read_text()
    section = concepts.split('## Outbound tiers\n', 1)[1].split('\n## ', 1)[0]
    for word in ('`send`', '`ask`', '`block`', '`owner`', '`team`', '`company`', '`client`', '`public`',
                 'client channel'):
        assert word in section, word
    configuration = (SITE / 'configuration.md').read_text()
    for key in ('`outbound.tiers`', '`outbound.channel_classes`', '`outward.classes`', '`outbound.people`'):
        assert key in configuration, key
    assert '`class`' in configuration
    security = (SITE / 'security.md').read_text()
    assert 'a `send` row never reaches a client or public audience' in security
    assert 'a seat never writes the table' in security
    reference = (SITE / 'reference.md').read_text()
    assert 'outbound tiers' in reference and 'outbound explain' in reference
    template = (ROOT / 'templates/workspace/config.toml').read_text()
    assert '# tiers = [' in template and '# [outbound.channel_classes]' in template


def test_thread_reply_docs():
    # #526: the planner learns a thread's participants; the thread row and the draft posture line.
    from wuwei import guide
    skill = guide.text()  # #551: the learn step lives in the guide
    assert 'outbound learn --tool <tool>' in skill and '--thread <file>' in skill and 'thread_ts' in skill
    assert 'a draft is one card away' in (SITE / 'reference.md').read_text()
    assert 'topic = "thread"' in (SITE / 'concepts.md').read_text()
    assert '--thread <file>' in (SITE / 'security.md').read_text()
    assert '`thread`' in (SITE / 'configuration.md').read_text().split('| `outbound.tiers` |', 1)[1].split('\n', 1)[0]


def test_gradual_adoption_is_documented():
    daily = (SITE / 'daily.md').read_text()
    section = daily.split('## Starting with work in progress', 1)[1].split('\n## ', 1)[0]
    for phrase in ('pr claim', 'worktree adopt', 'worktree add <item> --branch'):
        assert phrase in section
    assert '### Adopted' in (SITE / 'concepts.md').read_text()
    reference = (SITE / 'reference.md').read_text()
    assert 'worktree adopt' in reference and '--branch' in reference


def test_card_answer_writes_the_config_documented():
    """#529: the owner's card answer is the confirmation of a config write outside strict."""
    design = (ROOT / 'docs/specs/2026-09-24-wuwei-design.md').read_text()
    records = design[design.index('Records (owner, 2026-10-03, #357)'):design.index('Availability (owner')]
    assert '#529' in records and '--from-card' in records
    skill = (ROOT / 'skills/wuwei-plan/SKILL.md').read_text()
    assert 'wuwei calibrate --questions cap seats' in skill and '--from-card' in skill
    assert '`config set` on guard settings is refused' not in skill
    security = (SITE / 'security.md').read_text()
    assert 'never change from an agent tool' not in security and '--from-card' in security
    for name in ('concepts.md', 'configuration.md'):
        assert '--from-card' in (SITE / name).read_text(), name


def test_plan_and_report_skills_are_the_loop():
    # #551: the CLI owns the path; each skill is the loop plus the Agent and AskUserQuestion mechanics.
    from wuwei import guide
    from wuwei.commands import next as next_command
    for name in ('wuwei-plan', 'wuwei-report'):
        text = (ROOT / 'skills' / name / 'SKILL.md').read_text()
        assert len(text.splitlines()) < 25, name
        for phrase in ('`launch`', '`continue`', '`resume`', '`subagent_type`', 'in one message',
                       'AskUserQuestion', '`record`', 'wuwei next --json'):
            assert phrase in text, (name, phrase)
        assert not re.search(r'^\d+\. ', text, re.M), name  # no step list for a model to interpret
    text = guide.text()
    for phrase in (next_command.LOOP, 'outbound.owner_channel', 'outbound.owner.slack.dm',
                   'outbound learn --tool', '--owner <file>'):
        assert phrase in text, phrase
    assert 'config set outbound.owner' not in text
    # Each rule removed from the plan skill lives in the guide or in a next row (#551 review).
    rows = Path(next_command.__file__).read_text()
    for phrase in ('--import-yesterday', 'publish:', 'Keep owner-only', 'continue the seat',
                   'assume-and-record', 'negotiation.loop', '<item>-question-<agent>'):
        assert phrase in text or phrase in rows, phrase


def test_register_section_and_who():
    # #552: one section explains the register; each modeled key points at it.
    page = (SITE / 'configuration.md').read_text()
    section = page.split('\n## People, channels and tools\n', 1)[1].split('\n## ', 1)[0]
    assert 'bin/wuwei who' in section and 'bin/wuwei init --upgrade' in section and '.wuwei/graph.json' in section
    for key in ('owner.handles', 'shepherd.authors', 'voice.sources', 'outward.servers', 'outward.modes',
                'outward.classes', 'outbound.work_channels', 'outbound.external_channels',
                'outbound.channel_classes', 'outbound.people', 'outbound.owner'):
        rows = [line for line in page.replace(section, '').splitlines() if line.startswith((f'| `{key}`', f'| `{key}.'))]
        assert rows and all('#people-channels-and-tools' in line for line in rows), key
    reference = (SITE / 'reference.md').read_text()
    assert '| `bin/wuwei who` |' in reference and 'edge: ' in reference.split('\n## Why\n', 1)[1]


def test_merge_grant_documented():
    # #524: merge is a grant like deploy; merge.default_tier decides what happens with no grant.
    rows = {line.split('|')[1].strip(): line for line in (SITE / 'configuration.md').read_text().splitlines()
            if line.startswith('| `')}
    for word in ('`ask`', '`owner_only`', '`strict`'):
        assert word in rows['`merge.default_tier`'], word
    assert '`merge`' in rows['`grants.standing`']
    grants = (SITE / 'concepts.md').read_text().split('\n## Grants\n', 1)[1].split('\n## ', 1)[0]
    for phrase in ('merge', 'merge.default_tier', 'no grant lifts', 'bin/wuwei merge'):
        assert phrase in grants, phrase
    spec = (ROOT / 'docs/specs/2026-09-24-wuwei-design.md').read_text()
    assert spec.count('(owner, 2026-10-05, #524)') >= 2


def test_design_records_the_headless_shepherd():
    """#511: 4.2.1 names the overnight sweep."""
    design = (Path(__file__).resolve().parents[1] / 'docs/specs/2026-09-24-wuwei-design.md').read_text()
    section = design.split('#### 4.2.1', 1)[1].split('\n### ', 1)[0]
    assert '#511' in section and 'sweep obligations --headless' in section


def test_dora_keys_documented():
    # #586: the command row, the concepts section, design 5.6 and 5.13, and the README bullet.
    from wuwei import metrics, telemetry
    assert '| `bin/wuwei dora' in (SITE / 'reference.md').read_text()
    concepts = (SITE / 'concepts.md').read_text().split('\n## DORA keys\n', 1)[1].split('\n## ', 1)[0]
    for _, label, _ in metrics.DORA:
        assert label.lower() in ' '.join(concepts.lower().split()), label
    assert 'unmeasured' in concepts
    design = (ROOT / 'docs/specs/2026-09-24-wuwei-design.md').read_text()
    assert 'wuwei dora' in design.split('### 5.6 ', 1)[1].split('### 5.7 ', 1)[0]
    table = design.split('### 5.13 ', 1)[1].split('### 5.14 ', 1)[0]
    for key in telemetry.METRICS:
        assert f'`{key}`' in table, key
    assert '(docs/site/concepts.md#dora-keys)' in (ROOT / 'README.md').read_text()
