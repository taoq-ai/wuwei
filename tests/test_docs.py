"""Keep the public docs aligned with the shipped entry points and config."""

from argparse import Namespace
import json
from pathlib import Path
import posixpath
import re
import runpy
import tarfile
import tomllib
from xml.etree import ElementTree

from wuwei import integrity, registry


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


def test_hero_variants_share_geometry_and_motion():
    dark, light = ((ROOT / f'docs/assets/hero-{v}.svg').read_text() for v in ('dark', 'light'))
    mask = lambda text: re.sub(r'#[0-9A-Fa-f]{3,8}', '#', text)
    assert mask(dark) == mask(light)
    assert 'prefers-reduced-motion' in dark and 'animateMotion' in dark


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
    row = next(line for line in page.splitlines() if line.startswith('| `shepherd.min_reviewers`'))
    assert '`0`' in row.split('|')[3]


def test_hero_files_match_their_generator():
    import importlib.util
    spec = importlib.util.spec_from_file_location('build_hero', ROOT / 'scripts/build-hero.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, palette in module.PAL.items():
        assert (ROOT / f'docs/assets/hero-{name}.svg').read_text() == module.svg(palette), name


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
    assert 'wuwei worktree add' in (ROOT / 'skills/wuwei-plan/SKILL.md').read_text()


def test_host_terminal_actions_and_morning_references():
    reference = (SITE / 'reference.md').read_text()
    concepts = (SITE / 'concepts.md').read_text()
    for text in (reference, concepts):
        assert 'Host terminal actions' in text
        for command in ('decision outcome', 'state recover', 'integrity reconfirm', 'mcp decide',
                        'drafts approve', 'watch uninstall'):
            assert command in text
    for phrase in ('run it in a host terminal', 'no plan yet', 'proposal.json', 'pr raise',
                   '--base', '--title', '--body-file', '--item'):
        assert phrase in reference
    assert 'wuwei rank .wuwei/days/' in (ROOT / 'skills/wuwei-plan/SKILL.md').read_text()


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
                [*SITE.glob('*.md'), *(ROOT / 'docs/assets').glob('*.svg')]}
    with tarfile.open(archive) as tar:
        archived = {n.removeprefix('wuwei/') for n in tar.getnames()}
    assert expected <= listed and expected <= archived
    assert signed == [stage / integrity.MANIFEST]
    assert integrity.measure(stage).exit == 0
