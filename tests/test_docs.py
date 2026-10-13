"""Keep the public docs aligned with the shipped entry points and config."""

from argparse import Namespace
import os
from pathlib import Path
import posixpath
import re
import runpy
import subprocess
import sys
import tarfile
import tomllib

from wuwei import integrity, registry


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'docs/site'
TABLE = re.compile(r'^\s*#?\s*\[\[?([\w.]+)\]\]?\s*$')


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


def test_reference_lists_owner_completed_plan_command():
    page = (SITE / 'reference.md').read_text()
    assert '`plan done`' in page.split('## init')[0]
    assert '| `done <item> --reason <text>` |' in page.split('## plan')[1].split('### Goals')[0]


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


def test_reference_lists_every_cli_command(tmp_path):
    result = subprocess.run([sys.executable, '-P', '-m', 'wuwei', '--help'], capture_output=True,
                            text=True, cwd=tmp_path, env={**os.environ, 'PYTHONPATH': str(ROOT / 'cli')})
    assert result.returncode == 0, result.stderr
    commands = set(re.findall(r'^    ([a-z-]+)\s', result.stdout, re.M))
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


def test_skills_use_the_recorded_executable_directly():
    # #348: a session reads the pointer once and runs the absolute path as a plain command.
    for name in ('wuwei-plan', 'wuwei-report', 'wuwei-retro'):
        text = (ROOT / 'skills' / name / 'SKILL.md').read_text()
        assert '$(' not in text and 'executable recorded in' not in text, name
        for phrase in ('read `.wuwei/executable` once with the Read tool', 'first word of a plain command'):
            assert phrase in text, (name, phrase)
