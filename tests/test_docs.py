"""Keep the public docs aligned with the shipped entry points and config."""

import json
from pathlib import Path
import re
import tomllib
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'docs/site'


def test_readme_install_and_hero():
    readme = (ROOT / 'README.md').read_text()
    for phrase in ('prefers-color-scheme: dark', 'docs/assets/hero-light.svg',
                   'docs/assets/hero-dark.svg', '#00C9A7', '无为',
                   'What WUWEI is and is not', '/plugin marketplace add taoq-ai/wuwei',
                   '/plugin install wuwei@wuwei', 'wuwei init', '/wuwei plan'):
        assert phrase in readme
    for variant in ('light', 'dark'):
        art = ROOT / f'docs/assets/hero-{variant}.svg'
        svg = ElementTree.parse(art).getroot()
        assert svg.tag == '{http://www.w3.org/2000/svg}svg'
        assert '#00C9A7' in art.read_text()
        assert all(word in art.read_text() for word in ('Plan', 'Build', 'Review', 'Close'))


def test_site_pages_and_links():
    pages = ('index', 'concepts', 'configuration', 'adapters', 'charter-overrides', 'security', 'reference')
    index = (SITE / 'index.md').read_text()
    assert index.startswith('---\nlayout: default\n---\n')
    for page in pages[1:]:
        assert (SITE / f'{page}.md').is_file()
        assert (SITE / f'{page}.md').read_text().startswith('---\nlayout: default\n---\n')
        assert f'({page}.html)' in index
    assert (SITE / '_config.yml').is_file()
    assert '9.1' in (SITE / 'security.md').read_text()
    assert (ROOT / 'skills/wuwei-plan/SKILL.md').is_file()
    assert 'docs/site' in (ROOT / '.github/workflows/docs.yml').read_text()


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
        table = re.match(r'^\s*#?\s*\[\[?([\w.]+)\]\]?\s*$', line)
        if table:
            section = table.group(1)
            continue
        assignment = re.match(r'^\s*#?\s*([A-Za-z_][\w]*)\s*=', line)
        if assignment:
            keys.add(f'{section}.{assignment.group(1)}' if section else assignment.group(1))
    missing = sorted(key for key in keys if f'`{key}`' not in page)
    assert not missing, f'Undocumented config keys: {missing}'
    tomllib.loads(template)


def test_entry_guides_install_signed_release_and_explain_development_checkout():
    integrity = (ROOT / 'docs/integrity.md').read_text()
    assert 'source checkouts are unsigned and report a page' not in integrity
    assert 'clean commit' in integrity and 'HEAD' in integrity
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
                'tie_commits', 'source_exclude', 'min_reviewers'):
        assert key in settings
        assert f'`shepherd.{key}`' in page
    assert settings['min_reviewers'] == 1


def test_reference_verdict_example_and_phase_table():
    from wuwei import state, verdict
    reference = (SITE / 'reference.md').read_text()
    example = re.search(r'## Gate verdict layout\n.*?```text\n(.*?)```', reference, re.S)[1]
    assert verdict.lint(example, quality=True, class_sweep=True)[0] == 0
    for phase, following in state.PHASES.items():
        assert f'| `{phase}` | {", ".join(following) or "none"} |' in reference
    for phrase in ('worktree add', 'stdin', 'sentinel-arch'):
        assert phrase in reference
    configuration = (SITE / 'configuration.md').read_text()
    assert '--dry-run' in configuration and 'watch dead' in configuration
    assert 'wuwei worktree add' in (ROOT / 'skills/wuwei-plan/SKILL.md').read_text()
