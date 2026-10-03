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
    rows = [line for line in section.splitlines() if line.startswith('|')]
    for header in ('Who plans the day', 'Who reviews the work', 'What stops a bad merge',
                   'What is learned afterwards', 'Where it runs'):
        assert header in rows[0], header
    assert rows[0].count('|') <= 7
    assert 'WUWEI' in rows[2].split('|')[1]
    assert 'Where WUWEI is worse' not in readme
    for word in ('professional', 'enterprise', 'best-in-class'):
        assert word not in readme.lower(), word
    assert len(section.splitlines()) < 70
    assert '\N{EM DASH}' not in section


def test_readme_lead_and_limits():
    readme = (ROOT / 'README.md').read_text()
    lead = readme.split('Apache 2.0</a></p>', 1)[1].split('## What WUWEI is and is not', 1)[0]
    for phrase in ('careful engineering team', 'ranked', 'did not write', 'retro'):
        assert phrase in lead, phrase
    alt = re.search(r'alt="([^"]+)"', readme)[1]
    intro = (SITE / 'index.md').read_text().split('# WUWEI documentation', 1)[1].strip().split('\n\n', 1)[0]
    for word in ('ranked', 'retro'):
        assert word in alt and word in intro, word
    assert (readme.index('## Quick start') < readme.index('## Limits')
            < readme.index('## Development installs'))
    section = readme.split('## Limits', 1)[1].split('\n## ', 1)[0]
    flat = ' '.join(section.split()).lower()
    for phrase in ('needs claude code', 'one owner per workspace', '40 to 100 ms', 'its author',
                   'live rehearsal', 'docs/site/reference.md#hook-latency-budget',
                   'docs/site/rehearsal.md', 'docs/site/security.md', 'setup --shadow', 'observe'):
        assert phrase in flat, phrase


def test_hero_variants_share_geometry_and_motion():
    dark, light = ((ROOT / f'docs/assets/hero-{v}.svg').read_text() for v in ('dark', 'light'))
    mask = lambda text: re.sub(r'#[0-9A-Fa-f]{3,8}', '#', text)
    assert mask(dark) == mask(light)
    assert 'prefers-reduced-motion' in dark and 'animateMotion' in dark


def test_site_pages_and_links():
    pages = sorted(p.stem for p in SITE.glob('*.md') if p.stem != 'index')
    index = (SITE / 'index.md').read_text()
    assert index.startswith('---\nlayout: default\n---\n')
    for page in pages:
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
    assert not re.search(r'^\s*mode\s*=', template, re.MULTILINE)
    assert 'mode' not in tomllib.loads(template)['guards']
    block = template.split('\n[security]\n', 1)[1].splitlines()
    first = next(i for i, line in enumerate(block) if line.strip() and not line.startswith('#'))
    assert block[first].startswith('posture =')
    for profile in ('observe', 'guarded', 'strict'):
        assert sum(line.startswith(f'# {profile}:') for line in block[:first]) == 1


def test_docs_retire_guards_mode():
    rows = {line.split('|')[1].strip(): line for line in (SITE / 'configuration.md').read_text().splitlines()
            if line.startswith('| `')}
    assert 'doctor --fix' in rows['`guards.mode`'] and 'init --upgrade' in rows['`guards.mode`']
    assert '--shadow' in rows['`security.posture`'] and 'guards.shadow_days' in rows['`security.posture`']
    page = (SITE / 'security.md').read_text()
    assert 'setup --shadow' in page
    assert '`guards.mode = "shadow"` (`init --shadow`) counts as `observe`' not in page


def test_entry_guides_install_signed_release_and_explain_development_checkout():
    integrity = (ROOT / 'docs/integrity.md').read_text()
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
                'tie_commits', 'source_exclude', 'min_reviewers', 'autostart'):
        assert key in settings
        assert f'`shepherd.{key}`' in page
    assert settings['min_reviewers'] == 1
    assert settings['autostart'] is False
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
                        'drafts approve', 'watch uninstall', 'listen uninstall', 'config promote',
                        'config set', 'config add-repo', 'setup'):
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
    skill = (ROOT / 'skills/wuwei-plan/SKILL.md').read_text()
    for phrase in ('calibrate --questions', 'calibrate --answer', '.wuwei/charters/planner.md'):
        assert phrase in skill, phrase


def test_pr_flow_is_documented():
    assert 'wuwei doctor --section pr-flow' in (ROOT / 'skills/wuwei-plan/SKILL.md').read_text()
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
                 'exit 0', 'exit 1', 'exit 2', 'design 4.5', '9.1', 'classic protection',
                 'none visible (404: unprotected or no admin)', 'required now', 'review_gate_check'):
        assert text in section, text
    assert 'currently reads as missing' not in page

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
    result = subprocess.run([sys.executable, '-P', '-m', 'wuwei', '--help'], capture_output=True,
                            text=True, cwd=tmp_path, env={**os.environ, 'PYTHONPATH': str(ROOT / 'cli')})
    assert result.returncode == 0, result.stderr
    commands = set(re.search(r'\{([a-z,-]+)\}', result.stdout)[1].split(','))
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
            < readme.index('## How WUWEI compares'))
    ships = readme.split('\n## What ships today\n', 1)[1].split('\n## ', 1)[0]
    for link in ('docs/site/daily.md', 'docs/site/security.md', 'docs/site/concepts.md#review-tiers',
                 'docs/site/remote.md', 'docs/site/concepts.md#cockpit-and-board',
                 'docs/site/configuration.md#calibration', 'docs/site/reference.md#heartbeat',
                 'docs/specs/2026-09-24-wuwei-design.md', 'docs/site/daily.md#2-configure',
                 'docs/site/reference.md#doctor', 'docs/site/security.md#security-posture'):
        assert f'({link})' in ships, link


def test_cruise_mode_is_designed_not_built():
    readme = (ROOT / 'README.md').read_text()
    for path in [ROOT / 'README.md', *SITE.glob('*.md')]:
        for paragraph in re.split(r'\n\s*\n', path.read_text()):
            if re.search('cruise', paragraph, re.I) and not paragraph.startswith('#'):
                assert 'not built' in ' '.join(paragraph.split()), (path.name, paragraph)
    assert 'cruise' in readme.split('\n## What ships today\n', 1)[1].split('\n## ', 1)[0]
    assert all('cruise' in (SITE / f'{page}.md').read_text() for page in ('concepts', 'configuration'))


def test_concepts_and_daily_cover_shipped_mechanisms():
    concepts = (SITE / 'concepts.md').read_text()
    for heading in ('Review tiers', 'Decision classes and cruise levels', 'Sessions', 'Listener',
                    'Heartbeat', 'Cockpit and board'):
        assert f'\n## {heading}\n' in concepts, heading
    daily = (SITE / 'daily.md').read_text()
    assert '`tier`' in daily.split('3. Gates:', 1)[1].split('4. Fix round:', 1)[0]
    assert 'phone answers' in daily.split('\n## 5. ', 1)[1].split('\n## ', 1)[0]


def test_security_integrity_and_cross_links():
    for path in (SITE / 'security.md', ROOT / 'docs/integrity.md'):
        text = path.read_text()
        assert 'plugin.json' in text and 'mcp check' in text, path.name
    assert '(rehearsal.html)' in (SITE / 'recovery.md').read_text()
    assert '(recovery.html)' in (SITE / 'rehearsal.md').read_text()


def test_shipped_things_are_not_called_planned():
    for path, stale in ((SITE / 'configuration.md', 'MCP scanning (#35)'),
                        (SITE / 'configuration.md', 'Planned planner rotation'),
                        (SITE / 'reference.md', 'will set `remote`'),
                        (SITE / 'reference.md', 'nothing sets `remote`'),
                        (ROOT / 'README.md', 'with three parallel review gates'),
                        (SITE / 'charter-overrides.md', '**Planned:**'),
                        (ROOT / 'README.md', 'interactive day planner')):
        assert stale not in path.read_text(), (path.name, stale)


def test_hero_shows_the_current_day():
    readme = (ROOT / 'README.md').read_text()
    alt = re.search(r'alt="([^"]+)"', readme)[1].lower()
    for variant in ('light', 'dark'):
        art = ROOT / f'docs/assets/hero-{variant}.svg'
        text = art.read_text()
        assert len(art.read_bytes()) < 20000, variant
        for word in ('Calibrate', 'interview', 'tier', 'Phone', 'DM', 'heartbeat'):
            assert word in text, (variant, word)
        desc = re.search(r'<desc[^>]*>(.*?)</desc>', text, re.S)[1].lower()
        for word in ('calibrat', 'tier', 'phone', 'heartbeat'):
            assert word in desc and word in alt, (variant, word)
        reduced = re.search(r'@media \(prefers-reduced-motion:\s*reduce\)\s*\{(.*?)\}\s*\}', text, re.S)[1]
        classes = {name for attr in re.findall(r'class="([^"]+)"', text) for name in attr.split()}
        for name in classes - {'slow'}:
            assert f'.{name}' in reduced, (variant, name)


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
                   'scripts/build-hero.py', 'SECURITY.md', 'stdlib'):
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
                 'MCP Apps', 'release-please', 'ZIRAN', 'WSJF', 'RICE', 'two-way door'):
        assert name.lower() in notice.lower(), name


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
    page = (SITE / 'agent.md').read_text()
    assert page.startswith('---\nlayout: default\n---\n') and len(page.splitlines()) <= 100
    for phrase in ('wuwei next', '/wuwei:wuwei-plan', '/wuwei:wuwei-report', '.wuwei/executable',
                   '-P', 'host terminal', 'posture:', 'planner', 'lead', 'builder', 'sentinel',
                   'shepherd', 'steward'):
        assert phrase in page, phrase
    assert '\N{EM DASH}' not in page and not any(ord(c) >= 0x1F000 for c in page)
    for name in ('index.md', 'daily.md'):
        assert '(agent.html)' in (SITE / name).read_text(), name
    readme = (ROOT / 'README.md').read_text()
    assert 'orients itself' in readme.split('\n## Quick start\n', 1)[1].split('\n## ', 1)[0]
    for skill in sorted(ROOT.glob('skills/*/SKILL.md')):
        body = skill.read_text().split('\n# ', 1)[1].split('\n\n', 2)[1]
        assert '`wuwei next`' in body, skill.parent.name


def test_owner_questions_use_widgets_or_the_dm():
    for path in (ROOT / 'skills').glob('*/SKILL.md'):
        text = path.read_text()
        for phrase in ('AskUserQuestion', 'decision route', '--widget', 'Seats never ask the owner'):
            assert phrase in text, (path.parent.name, phrase)
        assert 'Decided-by: owner' not in text and 'Outcome: proceed' not in text, path.parent.name
    plan = (ROOT / 'skills/wuwei-plan/SKILL.md').read_text()
    for phrase in ('wuwei mcp check --widget', 'record', 'calibrate --answer', 'wuwei_board'):
        assert phrase in plan, phrase
    decisions = (SITE / 'daily.md').read_text().split('\n## 5. Owner decisions\n', 1)[1].split('\n## ', 1)[0]
    answer = decisions.split('\n### How you answer\n', 1)[1].split('\n#', 1)[0]
    for phrase in ('question card', 'DM', 'host terminal'):
        assert phrase in answer, phrase
def test_unparsed_commands_are_documented():
    # #347: the security page names the unparsed class and the cd rule's subshell form.
    security = ' '.join((SITE / 'security.md').read_text().split())
    for phrase in ('unparsed', '(cd <dir> && <command>)', 'blocks only under `strict`'):
        assert phrase in security, phrase


def test_close_carry_skill_and_docs():
    report = (ROOT / 'skills/wuwei-report/SKILL.md').read_text()
    step = next(line for line in report.splitlines() if line.startswith('1. '))
    for phrase in ('wuwei close', 'wuwei close --widget', 'record', 'steward_launch', 'plan carry'):
        assert phrase in step, phrase
    assert 'Outcome: carried' not in report and 'Outcome: parked' not in report
    retro = (ROOT / 'skills/wuwei-retro/SKILL.md').read_text()
    step = next(line for line in retro.splitlines() if line.startswith('1. '))
    assert all(phrase in step for phrase in ('wuwei close', 'steward_launch', 'open item'))
    concepts = (SITE / 'concepts.md').read_text()
    assert 'bin/wuwei plan carry' in concepts and 'bin/wuwei plan park' in concepts
    assert 'Outcome: carried ITEM' not in concepts
