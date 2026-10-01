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


def test_readme_compares_with_other_tools():
    readme = (ROOT / 'README.md').read_text()
    assert '## How WUWEI compares' in readme
    assert (readme.index('## What WUWEI is and is not') < readme.index('## How WUWEI compares')
            < readme.index('## Install'))
    section = readme.split('## How WUWEI compares', 1)[1].split('\n## ', 1)[0]
    assert re.search(r'As of [A-Z][a-z]+ \d{4}', section)
    for phrase in ('Spec Kit', 'OpenSpec', 'superpowers', 'BMAD Method', 'Kiro', 'Claude Code',
                   'github.com/github/spec-kit', 'github.com/Fission-AI/OpenSpec',
                   'github.com/obra/superpowers', 'github.com/bmad-code-org/BMAD-METHOD',
                   'kiro.dev', 'code.claude.com/docs', '### How they compose'):
        assert phrase in section
    assert '### Where WUWEI is worse' in section
    worse = ' '.join(section.split('### Where WUWEI is worse', 1)[1].split())
    for phrase in ('only in Claude Code', 'one owner per workspace', '40 to 100 ms',
                   'not an isolation boundary', 'proven only by', 'live rehearsal'):
        assert phrase in worse
    assert len(section.splitlines()) < 70
    assert '\N{EM DASH}' not in section


def test_hero_variants_share_geometry_and_motion():
    dark, light = ((ROOT / f'docs/assets/hero-{v}.svg').read_text() for v in ('dark', 'light'))
    mask = lambda text: re.sub(r'#[0-9A-Fa-f]{3,8}', '#', text)
    assert mask(dark) == mask(light)
    assert 'prefers-reduced-motion' in dark and 'animateMotion' in dark


def test_site_pages_and_links():
    pages = ('index', 'daily', 'recovery', 'concepts', 'configuration', 'adapters', 'charter-overrides',
             'security', 'reference', 'rehearsal', 'remote')
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
                        'drafts approve', 'watch uninstall', 'listen uninstall', 'config promote'):
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


def test_calibration_is_documented_between_configure_and_plan():
    daily = (SITE / 'daily.md').read_text()
    for phrase in ('bin/wuwei calibrate', 'bin/wuwei config promote', 'calibration.md'):
        assert phrase in daily, phrase
    assert daily.index('bin/wuwei calibrate') < daily.index('/wuwei plan')
    configuration = (SITE / 'configuration.md').read_text()
    section = configuration.split('\n## Calibration\n', 1)[1].split('\n## ', 1)[0]
    for phrase in ('.wuwei/calibration.json', 'calibration.drift', 'config promote',
                   'instruction-like', 'edit by hand'):
        assert phrase in section, phrase



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
    skill = (ROOT / 'skills/wuwei-plan/SKILL.md').read_text()
    for phrase in ('calibrate --questions', 'calibrate --answer', '.wuwei/charters/planner.md'):
        assert phrase in skill, phrase

RECOVERY = ('state transition', 'runtime dispatch', 'runtime continue', 'integrity reconfirm')


def test_daily_path_and_recovery_pages():
    daily = (SITE / 'daily.md').read_text()
    for phrase in ('/wuwei plan', 'wuwei.tar.gz', 'plan approve', 'build next', 'dispatch next',
                   'pr raise', 'pr state', 'decision outcome', 'close',
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
    assert '(remote.html)' in (SITE / 'daily.md').read_text()
    headings = ['## 1. Remote Control, no setup', '## 2. The Slack app', '## 3. Pin your identity',
                '## 4. The second factor', '## 5. Install the listener', '## 6. Commands from the DM',
                '## 7. Decisions on the phone', '## 8. Limits']
    positions = [page.index(f'\n{heading}\n') for heading in headings]
    assert positions == sorted(positions)
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
                 'Recorded D-3 option B. Confirm it on the host.', 'decision.replied', 'decision outcome',
                 'drafts approve', 'listen install', 'listen uninstall', 'listen dead',
                 'responder.enabled = false', 'stop all', 'loginctl enable-linger', 'resets at midnight',
                 'otpauth://totp/', 'algorithm=SHA1&digits=6&period=30', 'App Home', 'Messages Tab',
                 'Allow users to send Slash commands and messages from the messages tab',
                 'OAuth & Permissions', 'Bot Token Scopes', 'Agent tools are refused these commands',
                 'answered from the phone', remote.ANSWERED.format(identifier='D-3', option='B'),
                 'WUWEI_TOTP_SECRET: set', 'status --line` shows `listen dead`', 'phone answers 1',
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
                 'exit 0', 'exit 1', 'exit 2', 'design 4.5', '9.1'):
        assert text in section, text

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
