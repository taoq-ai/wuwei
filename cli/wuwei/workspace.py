"""Shared workspace paths and validated configuration."""

from itertools import chain
import marshal
import os
from pathlib import Path
import re
import sys

from wuwei.exits import DAMAGED


# Dicts describe tables; lists contain an item rule and optional array defaults;
# tuples are type/default/constraint.
# A '*' table entry describes user-defined register/channel names.
# A None default marks a required, nonblank field.
MERGE_SCHEMA = {
    "auto": (bool, False), "max_changed_lines": (int, 400, 0),
    "max_per_day": (int, 5, 1), "soak_minutes": (int, 30, 0),
    "soak_skip": (str, "base_fix", ("base_fix", "never")),  # #668
    "reset_epoch": (int, 0, 0), "quiet_hours": [(str, None)],
    "bot_login": (str, ""), "bot_min_score": (int, 5, 0),
    "bot_score_pattern": (str, r"Confidence Score:\s*([0-9]+)/5"),
    "fix_pattern": (str, r"(?i)\b(?:fix(?:es|ed)?|bugfix|hotfix|revert)\b"),
    "size_exclude": [(str, None)],  # #615: globs of generated files max_changed_lines skips
    "never_auto_paths": [(str, None), [
        ".github/*", "ci/*", "workflows/*", ".buildkite/*", ".travis.yml", ".gitlab-ci.yml", "Jenkinsfile", ".circleci/*", "azure-pipelines*",
        "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lock*",
        "pyproject.toml", "setup.py", "setup.cfg", "requirements*.txt", "Pipfile*", "poetry.lock", "uv.lock",
        "Cargo.toml", "Cargo.lock", "go.mod", "go.sum", "Gemfile*", "composer.*",
        "pom.xml", "build.gradle*", "*.csproj", "*.lock", "CODEOWNERS",
        "migrations/*", "schema*", "schemas/*", "deploy/*", "infra/*", "infrastructure/*",
        "*.tf", "*.tfvars", "Dockerfile*", "docker-compose*", "Pulumi.*",
    ]],
}

LEVELS = ("brief", "standard", "full")
SURFACES = ("report",)
# 5.11: what the tracker opens (classes) and what it comments (kinds).
TRACKER_CLASSES = ("items", "bugs", "triage", "follow-ups")
TRACKER_KINDS = ("decisions", "progress", "verdicts", "pr", "close")
# #799: dotted keys or tables init --upgrade always removes; each #789 deletion part adds what it retires.
# A key inside [[repos]] is named without its index: repos.tests retires repos.<n>.tests.
RETIRED = ('deploy.workflows', 'nudges', 'owner.verbosity.nudges', 'brief.lead_minutes', 'brief.style', 'pace', 'repos.tests',
           'listen', 'responder', 'control_plane', 'adapters.inbound', 'shepherd.autostart', 'owner.verbosity.dm',
           'decisions.cruise', 'grants', 'merge.default_tier', 'consolidation', 'voice', 'memory.max_notes',
           'memory.note_line_cap', 'memory.probation_days', 'memory.state_entry_cap', 'memory.digest',
           'autonomy', 'decisions', 'steward', 'owner.verbosity.digest',
           'security.posture', 'security.areas', 'guards.mode', 'guards.shadow_days', 'guards.shadow_since',
           'outbound.tiers', 'outbound.default_tier', 'outbound.learn', 'outbound.people',
           'outbound.channel_classes', 'outbound.work_channels', 'outbound.external_channels',
           'outbound.company_domains', 'outbound.sensitive_keywords', 'outbound.sensitive_patterns',
           'outbound.commitment_patterns', 'outbound.disagreement_patterns',
           'outward.modes', 'outward.classes', 'outward.draft_ttl', 'outward.patterns',
           'scanner.mcp.project_file', 'scanner.mcp.user_file', 'scanner.mcp.timeout_seconds',
           'scanner.mcp.block', 'docs', 'adapters.docs',
           'tracker.required', 'tracker.skip_tiers', 'tracker.strict_close', 'tracker.auto', 'discovery',
           'watch', 'sessions', 'worktree',  # #847
           'adapters.redactor', 'owner.verbosity.decisions', 'retro.repo',  # #848
           'adapters.calendar', 'adapters.tts', 'calendar',  # #848 review: nothing reads them
           'budget.tokens_per_day')  # #845: window budgets per runtime

SCHEMA = {
    "scanner": {"severity_threshold": (str, "high", ("critical", "high", "medium", "low")),
                # #896 P3: the morning discovery's candidate rows per repo, at or above a severity
                "discovery_threshold": (str, "low", ("critical", "high", "medium", "low")),
                "discovery_rows": (int, 50, 1),
                "mcp": {"plugins_file": (str, "~/.claude/plugins/installed_plugins.json")}},
    "security": {"required": (bool, False)},
    "owner": {"name": (str, ""), "pronouns": (str, ""), "handles": [(str, None)],
              "timezone": (str, ""),
              "verbosity": {"default": (str, "brief", LEVELS),
                            **{name: (str, "", ("", *LEVELS)) for name in SURFACES}}},
    "repos": [{"name": (str, None), "path": (str, None),
               "default_branch": (str, None), "fast_checks": [(str, "")],
               "check_timeout_seconds": (int, 300, 1),  # #724: one check run's limit in this repository
               "review_required_checks": [(str, None)],
               "merge_deploys": (bool, True), "merge": MERGE_SCHEMA,
               "merge_method": (str, "auto", ("auto", "squash", "rebase", "merge")),  # #785
               "gates": {"floor": (str, "standard", ("light", "standard", "full")),
                         "light_max_lines": (int, 100, 0),
                         "data_paths": [(str, None)],  # #657: data globs (a trailing / is a directory) that never count
                         "trust_paths": [(str, None), [
                             "guards/*", "state.py", "adapters/*", ".claude-plugin/*", ".github/*",
                             "ci/*", "workflows/*", "deploy/*", "infra/*",
                             "*auth*", "*session*", "*token*", "*permission*", "*guard*"]]},
               "identity": {"name": (str, ""), "email": (str, "")},
               "shepherd": {"reviewers": [(str, None)]}}],
    "checks": {"python": (str, ""), "bootstrap": (str, "")},  # #520
    "merge": {"owner_paths": [(str, None)]},  # #997: these and never_auto_paths keep the Owner step card
    # #528: 0 derives CAP and host.seats from the measured host; a positive value is the owner's.
    "cap": (int, 0, 0),
    # #845: input plus output tokens per runtime and usage window; 0 is no budget.
    "budget": {name: {"five_hour": (int, 0, 0), "seven_day": (int, 0, 0)} for name in ("claude", "codex")},
    "template_version": (str, ""),
    "calibrate": {"fast_check_seconds": (int, 60, 1)},
    "plan": {"max_refills": (int, 3, 0)},
    "prioritisation": {"framework": (str, "wsjf", ("wsjf", "rice"))},
    "tracker": {"backlog_filter": (str, ""),
                "states": {"in_review": (str, "In Review"), "done": (str, "Done")},
                "create": [(str, None, ("bugs", "triage", "follow-ups")),
                           ["bugs", "triage", "follow-ups"]],
                "log": [(str, None, TRACKER_KINDS), list(TRACKER_KINDS)],
                "max_per_item_per_day": (int, 10, 1),
                "project": (str, ""), "board": (str, ""),
                "auth": (str, "token", ("token", "gh"))},
    "brief": {"remote": (str, "origin"),
              "prior_branch_pattern": (str, "*{item}*"),
              "full_path_patterns": [(str, "")]},
    "host": {"free_memory_mb": (int, 1024, 0), "min_free_memory_pct": (int, 0, 0, 100), "seats": (int, 0, 0),
             "reservation_timeout_seconds": (int, 14400, 1),
             "rate_limit_wait_seconds": (int, 120, 0)},
    "memory": {"budget_tokens": (int, 6000, 1), "export_to": (str, "CLAUDE.md")},
    "metrics": {"transcripts": (str, "~/.claude/projects"), "band_margin": (float, 0.2)},
    "build": {"max_iterations": (int, 8, 1), "stuck_after": (int, 3, 1),
              "poll_interval_seconds": (int, 5, 0), "poll_timeout_seconds": (int, 3600, 1)},
    "codex": {"command": [(str, None)], "timeout_seconds": (int, 300, 1)},
    "gates": {"second_opinion": (str, "off"),
              "second_opinion_role": (str, "quality", ("arch", "quality", "security")),
              # #873: item flags that select the second opinion; empty is every standard and full item
              "second_opinion_when": [(str, None, ("trust_surface", "boundary_relevant", "agent_surface"))],
              "max_rounds": (int, 2, 1),  # #623: fix rounds per item before notes ship or a blocker parks
              "tier_max_rounds": {"light": (int, 0, 0), "standard": (int, 0, 0),
                                  "full": (int, 0, 0)},
              "polish": (str, "offer", ("never", "offer", "always"))},  # #723: one notes-only round after a pass
    "pr": {"poll_seconds": (int, 120, 1), "action_minutes": (int, 30, 1),
           "review_window": (int, 120, 1)},
    # #844: the outward duties next lists until recorded
    # G7: a duty is due while its channel is configured; on only turns one off
    "duties": {"on": [(str, None, ("ping", "shepherd", "tracker", "summary")),
                      ["ping", "shepherd", "tracker", "summary"]]},
    "shepherd": {"review_channel": (str, ""), "lead_login": (str, ""),
                 "reviewers": [(str, None)], "reviewers_exclude": [(str, None)],
                 "review_gate_check": (str, "Review Gate"),
                 "min_reviewers": (int, 1, 0),
                 "author_windows_days": [(int, None, 1), [90, 180]],
                 "tie_commits": (int, 2, 0),
                 "source_exclude": [(str, None), ["specs/*", "*.lock", "*lock.json",
                                                    "*.generated.*", "generated/*"]],
                 "authors": {"*": {"login": (str, None), "mention": (str, "")}}},
    "retro": {"charter_paths": [(str, None), [".wuwei/charters"]],
              "changelog": (str, ".wuwei/memory/CHANGELOG.md")},
    "profile": (str, "strict", ("strict", "standard")),
    "guards": {"enforce": (bool, False), "stop_max_blocks": (int, 20, 0)},  # #837: false logs what a guard would refuse
    "boundary": {"*": (str, "")},
    "environments": {"*": (str, "")},
    "deploy": {"deny": [(str, None)]},
    "outbound": {
        "code_host_orgs": [(str, None)],  # part 20 decides it with tracker label creation
        # #838: the owner's identity per surface; a write whose every destination is the owner's is local.
        "owner": {"slack": {"user": (str, ""), "dm": (str, "")}, "mail": (str, ""),
                  "code_host": (str, ""), "pages": [(str, None), []]},
        "owner_channel": (str, "session", ("session", "dm")),
    },
    "outward": {
        # #838: exact MCP tool names that may send to other people; an unlisted write is refused.
        "allow": [(str, None), []],
        "banned_characters": [(str, ""), ["emoji", "\u2014", "\u2015", "\u2e3a", "\u2e3b"]],
        "max_length": {"*": (int, 1, 1)},
        "humanize": (bool, True),
        "humanize_kinds": [(str, None, ("dm", "tracker", "docs", "pr", "review")),
                           ["dm", "tracker", "docs", "pr", "review"]],
        "humanize_strict": (bool, False),
        "tool_patterns": [{"pattern": (str, None), "channel": (str, None)}, [
            # #492: the brand anywhere in the name, so mcp__<uuid>__slack_send_message matches.
            {"pattern": r"mcp__(?=.*slack).*__.*(send|post|reply|schedule|update|add_message|add_reaction|react|chat_post|delete|edit|upload|invite|kick|archive|pin|star).*", "channel": "slack"},
            {"pattern": r"mcp__(?=.*linear).*__(?:\w*_)?(save|create|update)_(issue|comment)", "channel": "tracker"},
            {"pattern": r"mcp__(?=.*github).*__(?:\w*_)?(add|create|update)_.*comment.*", "channel": "code_host"},
            {"pattern": r"mcp__(?=.*notion).*__.*(create|update|append|patch|post|move|duplicate).*", "channel": "docs"},
            {"pattern": r"mcp__(?=.*atlassian).*__(?:\w*_)?(create|update)Confluence.*", "channel": "docs"},
        ]],
        # #492: the owner's alias of an MCP server id to its channel.
        "servers": {"*": (str, None, ("slack", "tracker", "code_host", "docs", "mail", "other", "local"))},
    },
    "telemetry": {"enabled": (bool, True),
                  "share": (str, "", ("", "off", "anonymous", "attributed")),
                  "endpoint": (str, ""), "repository": (str, "taoq-ai/wuwei"),
                  "otlp": {"endpoint": (str, ""), "headers_env": (str, "")}},
    "chat": {"identity": (str, "connector", ("connector", "custom_app"))},
    "spec": {"engine": (str, "speckit", ("speckit", "superpowers", "openspec", "none")),
             "mode": (str, "strict", ("strict", "advisory", "off")),
             "skip_tiers": [(str, None, ("light", "standard", "full")), ["light"]]},
    "adapters": {"tracker": (str, "none"), "chat": (str, "none"),
                 "review_bot": (str, "none"), "runtime": (str, "claude"),
                 "scanner": (str, "none"), "code_host": (str, "github"),
                 "vcs": (str, "git"), "host": (str, "local"),
                 "checks": (str, "local"), "transcripts": (str, "none")},
}


class ConfigError(ValueError):
    """A configuration finding, rather than an inability to read the file."""


def atomic_write(path, text, *, replace=True, mode=None, sync_dir=True):
    """Durably write text through a temporary file in the destination directory; sync_dir=False
    leaves the directory fsync to a later write in the same directory."""
    path = Path(path)
    temporary = None
    try:
        # tempfile.NamedTemporaryFile's own open (exclusive, no symlink, mode 0600) without
        # importing tempfile, which brings shutil, bz2, lzma and random to every state write.
        for _ in range(100):
            candidate = path.parent / f'tmp{os.urandom(6).hex()}'
            try:
                fd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            except FileExistsError:
                continue
            temporary = candidate
            break
        else:
            raise FileExistsError(f'no unused temporary name in {path.parent}; remove stale .tmp files in that folder, then retry')
        with open(fd, 'w', encoding='utf-8') as stream:
            if mode is not None:
                os.fchmod(stream.fileno(), mode)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
        if sync_dir:
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                try:
                    os.fsync(directory_fd)
                except OSError:
                    pass
            finally:
                os.close(directory_fd)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def find_workspace(start=None, *, use_environment=True):
    """Return the root containing .wuwei, honoring WUWEI_WORKSPACE first."""
    if use_environment and "WUWEI_WORKSPACE" in os.environ:
        override = os.environ["WUWEI_WORKSPACE"]
        root = Path(override).expanduser().resolve()
        if not override or not (root / ".wuwei").is_dir():
            raise FileNotFoundError(
                f"WUWEI_WORKSPACE={override!r} must name a root containing .wuwei/; set it to a folder that holds .wuwei/, or unset it"
            )
        if (root / '.wuwei').is_symlink():
            raise ValueError('.wuwei must not be a symlink')
        return root
    start = (Path.cwd() if start is None else Path(start)).resolve()
    for root in chain((start,), start.parents):  # #626: each parent made only when reached
        if (root / ".wuwei").is_dir():
            if (root / '.wuwei').is_symlink():
                raise ValueError('.wuwei must not be a symlink')
            return root
    # #735: a configured checkout beside the workspace, read only after the walk fails.
    roots = sorted(root for root, checkouts in _indexed().items()
                   if any(start.is_relative_to(path) for path in checkouts)
                   and (Path(root) / '.wuwei').is_dir() and not (Path(root) / '.wuwei').is_symlink())
    if len(roots) == 1:
        return Path(roots[0])
    if roots:
        raise FileNotFoundError(f'{start} is a configured repository of {len(roots)} workspaces: '
                                f'{", ".join(roots)}; pass --workspace <path> (or set '
                                'WUWEI_WORKSPACE=<path>) to pick one')
    raise FileNotFoundError(f"No .wuwei/ found from {start}; run from the workspace, set "
                            "WUWEI_WORKSPACE=<path> or pass --workspace <path> (wuwei init creates one)")


INDEX = '.config/wuwei/workspaces.json'  # #735: under the home folder; never a .wuwei/ there


def _indexed():
    """#735: the per-user index {root: [checkout]}, absolute strings; missing or damaged is empty."""
    import json
    try:
        data = json.loads((Path.home() / INDEX).read_text(encoding='utf-8'))
        return {root: list(checkouts) for root, checkouts in data.items()
                if Path(root).is_absolute() and isinstance(checkouts, list)
                and all(isinstance(path, str) and Path(path).is_absolute() for path in checkouts)}
    except (OSError, ValueError, AttributeError, TypeError):
        return {}


def index(root, config):
    """#735: record root's configured checkouts in the per-user index find_workspace reads;
    the root itself and the home folder or its parents are never indexed."""
    import json
    root, home = Path(root).resolve(), Path.home().resolve()
    checkouts = sorted({str(path) for repo in config['repos']
                        if (path := (root / Path(repo['path']).expanduser()).resolve()) != root
                        and not home.is_relative_to(path)})
    data = _indexed()
    data.pop(str(root), None)
    if checkouts:
        data[str(root)] = checkouts
    path = Path.home() / INDEX
    path.parent.mkdir(parents=True, exist_ok=True)
    # ponytail: no lock; two writers at once can drop one root's entry until its next config
    # write or init --upgrade. Lock the file if several workspaces are set up concurrently.
    atomic_write(path, json.dumps(data, indent=2, sort_keys=True) + '\n')


def owner_cli(root):
    """#735: the owner command prefix that works from any folder (the leading flag, #354)."""
    import shlex
    return f'bin/wuwei --workspace {shlex.quote(str(root))}'


def worktree_workspace(path):
    """Read the anchor worktree creation writes."""
    for parent in (path, *path.parents):
        # Explicit --git-dir targets may already name the anchored metadata directory.
        gitdir = parent if (parent / 'wuwei-workspace').is_file() else parent / '.git'
        if gitdir.is_file():
            prefix, separator, value = gitdir.read_text().strip().partition(': ')
            if prefix != 'gitdir' or not separator:
                continue
            gitdir = (parent / value).resolve()
        anchor = gitdir / 'wuwei-workspace'
        if anchor.is_file():
            value = anchor.read_text().strip()
            root = Path(value).resolve()
            if not value or not (root / '.wuwei').is_dir():
                raise ValueError(f'invalid worktree workspace anchor; {DAMAGED}')
            return root
    return None


def scope(path):
    """An environment-selected workspace is context, not proof of membership."""
    selected = None
    if 'WUWEI_WORKSPACE' in os.environ:
        try:
            selected = find_workspace(path)
        except FileNotFoundError as exc:
            raise ValueError(f'invalid WUWEI_WORKSPACE override; {DAMAGED}') from exc
    try:
        root = find_workspace(path, use_environment=False)
    except FileNotFoundError:
        root = worktree_workspace(path) or selected
        if root is None:
            return None
    config = load_config(root)
    if path.is_relative_to(root) or worktree_workspace(path) == root:
        return root, config
    repos = [(root / Path(repo['path']).expanduser()).resolve() for repo in config['repos']]
    if any(path.is_relative_to(repo) for repo in repos):
        return root, config
    # External worktrees share a configured repository's common directory.
    if any((parent / '.git').exists() for parent in (path, *path.parents)):
        from wuwei import registry
        from wuwei.registry import data
        vcs = registry.load('vcs', config)
        actual = data(vcs.repo_context(str(path), root=root))
        common = actual.get('common_dir')
        if not isinstance(common, str) or not Path(common).is_absolute():
            raise ValueError('missing worktree repository context; run it from inside a configured repository checkout; if it is one, run bin/wuwei doctor')
        if any(data(vcs.repo_context(str(repo), root=root)).get('common_dir') == common
               for repo in repos):
            return root, config
    return None


def contains_workspace(path):
    try:
        with os.scandir(path) as entries:
            return any(entry.is_dir() and os.path.isdir(os.path.join(entry.path, '.wuwei'))
                       for entry in entries)
    except PermissionError:
        return False


def guard_scope(payload):
    """Find a workspace covering cwd or a resolvable target, including Git anchors."""
    cwd = Path(payload.get('cwd') or Path.cwd()).resolve()
    paths = [cwd]
    inputs = payload.get('tool_input')
    if isinstance(inputs, dict):
        for key in ('path', 'file_path', 'repo'):
            value = inputs.get(key)
            if isinstance(value, str) and value:
                try:
                    paths.append((cwd / Path(value).expanduser()).resolve())
                except (OSError, ValueError, RuntimeError):
                    continue
    for path in paths:
        context = scope(path)
        if context is not None:
            return context[0]
    return None


def zone(config):
    """The owner's time zone, or None for this machine's zone (astimezone(None))."""
    name = config['owner']['timezone']
    if not name:
        return None
    from zoneinfo import ZoneInfo  # Local: off the hook path when unset.
    try:
        return ZoneInfo(name)
    except (KeyError, ValueError):
        raise ValueError(f'owner.timezone: unknown zone {name!r}; the owner sets an IANA zone such as Europe/Lisbon with bin/wuwei config set owner.timezone') from None


def verbosity(config, surface):
    """The owner's level for one surface: its own setting, else owner.verbosity.default."""
    levels = config['owner']['verbosity']
    return levels[surface] or levels['default']


def now():
    """Return local now, or the datetime represented by WUWEI_NOW."""
    from datetime import datetime
    if "WUWEI_NOW" not in os.environ:
        return datetime.now().astimezone()
    timestamp = os.environ["WUWEI_NOW"]
    try:
        if len(timestamp) <= 10:
            raise ValueError("time component required")
        dt = datetime.fromisoformat(timestamp)
        return dt if dt.tzinfo else dt.astimezone()
    except ValueError as exc:
        raise ValueError("WUWEI_NOW must be an ISO datetime with a time component; set it like 2026-10-03T09:00:00Z, or unset it") from exc


def day_dir(root=None):
    """Return today's day directory without creating it."""
    root = find_workspace() if root is None else Path(root)
    return root / ".wuwei/days" / now().date().isoformat()


def _unit_directory(platform):
    home = Path.home()
    if platform == "darwin":
        return home / "Library/LaunchAgents"
    return Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "systemd/user"


def watch_unit(root, platform=sys.platform, name="watch"):
    """Service label and unit file of a retired user service (watch, shepherd, listen) of this workspace; init --upgrade removes them."""
    import hashlib
    label = "wuwei-" + ("" if name == "watch" else f"{name}-") + hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()[:12]
    suffix = ".plist" if platform == "darwin" else ".service"
    return label, _unit_directory(platform) / f"{label}{suffix}"


def _key_line(raw, path):
    # ponytail: heuristic locations for ordinary TOML; use a source-aware parser
    # if multiline strings or exotic quoted keys need exact diagnostics.
    names = [part for part in path if not isinstance(part, int)]
    table = []
    assignment = []
    repo_index = -1
    requested_repo = path[1] if len(path) > 1 and path[0] == 'repos' and isinstance(path[1], int) else None
    for number, line in enumerate(raw.splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("["):
            header = line.strip("[] ")
            table = [part.strip(' \"\'') for part in header.split(".")]
            if line.startswith('[[') and table == ['repos']:
                repo_index += 1
            if requested_repo is not None and repo_index >= 0 and repo_index != requested_repo:
                continue
            if table[:len(names)] == names:
                return number
        else:
            if requested_repo is not None and repo_index >= 0 and repo_index != requested_repo:
                continue
            lhs = line.split("=", 1)[0]
            keys = [part.strip(' \"\'') for part in lhs.split(".")]
            if (table + keys)[:len(names)] == names:
                return number
            if not line.startswith("{"):
                assignment = table + keys
            if names[:len(assignment)] == assignment and re.search(
                r"[\"']?" + re.escape(str(names[-1])) + r"[\"']?\s*=", line
            ):
                return number
    return None


def _validate(value, schema, path, raw, unknown=None):
    """Validate value against schema; with an unknown list, collect unknown keys there
    instead of raising (#353)."""
    if isinstance(schema, tuple) and schema[1] is None and (
        value is None or isinstance(value, str) and not value.strip()
    ):
        line = _key_line(raw, path) or _key_line(raw, path[:-1])
        location = f' at line {line}' if line is not None else ''
        key = _dotted(path)
        raise ConfigError(f'{key}: required{location}; the owner sets it with bin/wuwei config set {key} <value>')
    expected = dict if isinstance(schema, dict) else list if isinstance(schema, list) else schema[0]
    if type(value) is not expected:
        key = _dotted(path)
        raise ConfigError(f"{key}: expected {expected.__name__}; the owner fixes it with bin/wuwei config set {key} <value>")
    if isinstance(schema, dict):
        for name in value:
            if name not in schema and "*" not in schema:
                line = _key_line(raw, (*path, name))
                location = f" at line {line}" if line is not None else ""
                import difflib  # Only for an unknown key's suggestion.
                near = difflib.get_close_matches(str(name), list(schema), n=1)
                hint = (f"did you mean {'.'.join(map(str, (*path, near[0])))}?" if near
                        else "remove it or use a documented key")
                text = f"unknown key {'.'.join(map(str, (*path, name)))}{location}; {hint}"
                if unknown is None:
                    raise ConfigError(text)
                unknown.append(text)
        if "*" in schema:
            return {name: _validate(item, schema['*'], (*path, name), raw, unknown)
                    for name, item in value.items()}
        return {name: _validate(value[name], rule, (*path, name), raw, unknown) if name in value
                else _absent(rule, (*path, name), raw)
                for name, rule in schema.items()}
    if isinstance(schema, list):
        return [_validate(item, schema[0], (*path, index), raw, unknown)
                for index, item in enumerate(value)]
    if len(schema) > 2:
        constraint = schema[2]
        if expected is int and value < constraint:
            problem = f"integer >= {constraint}"
        elif expected is int and len(schema) > 3 and value > schema[3]:
            problem = f"integer <= {schema[3]}"
        elif expected is str and value not in constraint:
            problem = ' or '.join(constraint)
        else:
            return value
        key = _dotted(path)
        raise ConfigError(f"{key}: expected {problem}; the owner fixes it with bin/wuwei config set {key} <value>")
    return value


# ponytail: SCHEMA is a constant, so an absent key's validated default is computed once per
# rule (#626) and handed out as a copy; a required key (None default) raises every time.
_ABSENT = {}


def _absent(rule, path, raw):
    kept = _ABSENT.get(id(rule))
    if kept is None or kept[0] is not rule:
        kept = _ABSENT[id(rule)] = rule, _validate(_default(rule), rule, path, raw)
    return copy_data(kept[1])


def _dotted(path):
    # #626: the dotted key only for a message; a valid node never renders it.
    return ".".join(map(str, path)) or "config"


def _default(schema):
    if isinstance(schema, dict):
        return {}
    if isinstance(schema, list):
        return copy_data(schema[1]) if len(schema) > 1 else []
    return schema[1]


def copy_data(value):
    """copy.deepcopy for parsed TOML and JSON data: dicts and lists are copied, everything
    else in them is immutable. Hooks skip importing copy and weakref (#346)."""
    # #626: a leaf is returned in place, not through a call per value.
    if isinstance(value, dict):
        return {key: copy_data(item) if isinstance(item, (dict, list)) else item
                for key, item in value.items()}
    if isinstance(value, list):
        return [copy_data(item) if isinstance(item, (dict, list)) else item for item in value]
    return value


# ponytail: per-process memo keyed on the path and the config text, cleared past
# CONFIGS_KEPT texts; adapter and path checks rerun only for a text not kept, so a process
# that alternates a few texts (a raw= check beside the file) parses each once. #626: it keeps
# the config marshalled (dicts, lists and scalars only), so each load is one C-level copy.
_CONFIGS = {}
CONFIGS_KEPT = 128
# #346: the validated config and its warnings as JSON in .wuwei/generated, so a hook skips
# tomllib (with typing and string) and the checks. A copy serves only the exact text it was
# made from, under this plugin version and this layout; any other text is parsed and the
# copy rewritten. Keyed on the text, not the file's stat: a same-size rewrite inside one
# coarse timestamp tick keeps mtime, size and inode, and the text is read anyway.
CONFIG_CACHE = 'config.cache.json'
SCRATCH = '.wuwei/scratch'  # #647: <root>/.wuwei/scratch/<item>/<role>/, one per seat
CONFIG_CACHE_VERSION = 26  # Bump when the parse, the schema, the defaults or the checks change.
# Only hook and status --line processes write the copy (__main__ turns this on): they pay the
# parse on every call. Every other command reads a current copy and writes nothing, so
# doctor and why stay read-only.
CONFIG_CACHE_WRITES = False


def __getattr__(name):
    # tomllib loads on first use, off the hook path; workspace.tomllib stays addressable.
    if name == 'tomllib':
        import tomllib
        return tomllib
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def _cache_key(raw):
    from wuwei import integrity
    return {'layout': CONFIG_CACHE_VERSION, 'plugin': integrity.version(), 'text': raw}


def _cached(directory, raw):
    """(config, warnings) from the parsed copy when it was made from raw, else None; a
    missing, stale, unreadable or symlinked copy is ignored, never an error."""
    import json
    try:
        if os.path.islink(directory):
            return None
        descriptor = os.open(directory / CONFIG_CACHE, os.O_RDONLY | os.O_NOFOLLOW)
        with open(descriptor, encoding='utf-8') as stream:
            data = json.load(stream)
        config, unknown = data['config'], data['warnings']
        if (data['key'] == _cache_key(raw) and isinstance(config, dict) and isinstance(unknown, list)
                and all(isinstance(text, str) for text in unknown)):
            return config, tuple(unknown)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def _cache(directory, raw, config, unknown):
    """Rewrite the parsed copy; a workspace that cannot take it parses on every load."""
    import json
    try:
        if not os.path.islink(directory):
            directory.mkdir(exist_ok=True)
            atomic_write(directory / CONFIG_CACHE, json.dumps(
                {'key': _cache_key(raw), 'config': config, 'warnings': list(unknown)}) + '\n')
    except OSError:
        pass


def _decode_error():
    import tomllib  # Only while an exception is being matched: a cache hit never loads it.
    return tomllib.TOMLDecodeError


def load_config(root=None, *, raw=None, warnings=None):
    """Read .wuwei/config.toml (or validate raw in its place), reject invalid fields, and
    return fresh defaults. Unknown keys never refuse (#799); their texts are appended
    to warnings when it is a list. In a hook or status line process, a
    parse of the file after its parsed copy missed rewrites the copy (#346); a hit writes
    nothing."""
    path = (find_workspace() if root is None else Path(root)) / ".wuwei/config.toml"
    stale = False
    if len(_CONFIGS) >= CONFIGS_KEPT:
        _CONFIGS.clear()
    try:
        if raw is None:
            raw = path.read_text(encoding="utf-8")
            if (path, raw) not in _CONFIGS:
                found = _cached(path.parent / 'generated', raw)
                if found:
                    _CONFIGS[path, raw] = (marshal.dumps(found[0]), found[1])
                stale = not found
        if (path, raw) in _CONFIGS:
            config, unknown = _CONFIGS[path, raw]
            if warnings is not None:
                warnings.extend(f'config.toml: {text}' for text in unknown)
            return marshal.loads(config)
        import tomllib
        parsed = tomllib.loads(raw)
        unknown = []
        try:
            config = _validate(parsed, SCHEMA, (), raw, unknown)
        except ConfigError:
            if unknown:  # A typo usually explains the error after it, as before #353.
                raise ConfigError(unknown[0]) from None
            raise
        for pattern in config['deploy']['deny']:
            program = pattern.split()[0]
            if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', program):
                raise ConfigError('deploy.deny: start each pattern with a literal executable name')
        for index, tool in enumerate(config['outward']['allow']):
            if not re.fullmatch(r'mcp__[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+', tool):
                raise ConfigError(f'outward.allow.{index}: not an MCP tool name; the owner fixes it '
                                  'with bin/wuwei config set outward.allow')
        from wuwei import registry
        second = config['gates']['second_opinion']
        found = re.fullmatch(r'([a-z]+):([A-Za-z0-9][A-Za-z0-9._-]*)', second)
        if second != 'off' and (not found or found[1] not in registry.known('runtime')
                                or found[1] in ('claude', 'none')):
            raise ConfigError('gates.second_opinion: use "off" or "<runtime>:<model>" with a polling '
                              'runtime (' + ', '.join(name for name in registry.known('runtime')
                                                      if name not in ('claude', 'none')) + ')')
        repo_names = set()
        repo_paths = set()
        for index, repo in enumerate(config['repos']):
            if repo['name'] in repo_names:
                line = _key_line(raw, ('repos', index, 'name'))
                location = f' at line {line}' if line is not None else ''
                raise ConfigError(f'repos.{index}.name: duplicate {repo["name"]!r}{location}; the owner removes the duplicate [[repos]] entry in config.toml (bin/wuwei config check validates)')
            repo_names.add(repo['name'])
            try:
                resolved = (path.parent.parent / Path(repo['path']).expanduser()).resolve()
            except (ValueError, OSError) as exc:
                raise ConfigError(f'repos.{index}.path: {exc}') from exc
            if resolved in repo_paths:
                line = _key_line(raw, ('repos', index, 'path'))
                location = f' at line {line}' if line is not None else ''
                raise ConfigError(f'repos.{index}.path: duplicate {repo["path"]!r}{location}; the owner removes the duplicate [[repos]] entry in config.toml (bin/wuwei config check validates)')
            repo_paths.add(resolved)

        for kind, name in config['adapters'].items():
            try:
                registry.validate(kind, name, for_config=True)
            except ValueError as exc:
                line = _key_line(raw, ('adapters', kind))
                location = f' at line {line}' if line is not None else ''
                raise ConfigError(f'{exc}{location}') from exc
        _CONFIGS[path, raw] = (marshal.dumps(config), tuple(unknown))
        if stale and CONFIG_CACHE_WRITES:
            _cache(path.parent / 'generated', raw, config, unknown)
        if warnings is not None:
            warnings.extend(f'config.toml: {text}' for text in unknown)
        return config  # Built fresh by _validate; the memo holds its own marshalled copy.
    except (ConfigError, UnicodeError, _decode_error()) as exc:
        hint = ''
        if "immutable namespace ('repos',)" in str(exc):  # #326: repos = [] before [[repos]]
            line = _key_line(raw, ('repos',))
            if line:
                hint = f'; repos is assigned on line {line}; delete that line before using [[repos]] tables'
        raise ConfigError(f"config.toml: {exc}{hint}; run bin/wuwei config check after the fix") from exc


def _require_gate(root):
    from wuwei import state
    if not (Path(root) / '.wuwei').is_dir():
        raise ValueError('worktree creation requires a workspace; run bin/wuwei init <path> first, or work from inside a workspace')
    if not state.read_state(root).get('gate_approved'):
        raise state.StateError('morning gate approval required before worktree creation; approve the plan at the morning gate (/wuwei:wuwei-plan) first')


def _anchor(path, root, vcs, identity):
    """The workspace anchor (<git dir>/wuwei-workspace) and the commit identity of an item
    worktree; no managed Git hooks (#847)."""
    from wuwei.registry import data
    git_dir = Path(data(vcs.repo_context(str(path), root=root))['path'])
    if not git_dir.is_absolute():
        raise ValueError(f'invalid worktree Git directory; {DAMAGED}')
    atomic_write(git_dir / 'wuwei-workspace', str(Path(root).resolve()) + '\n')
    if identity and identity['name'] and identity['email']:
        written = vcs.worktree_identity(str(path), identity['name'], identity['email'], root=root)
        if written.exit == 1:
            print(f'wuwei worktree warning: {written.reason}', file=sys.stderr)
        else:
            data(written)


def create_worktree(repo, branch, path, root, vcs, identity=None, existing=False, remote=None, base=None):
    """Create and anchor a WUWEI worktree before handing it to a seat; existing checks out
    an existing branch and records the worktree as the item's (#510)."""
    from wuwei.registry import data
    from wuwei import state

    _require_gate(root)
    if existing:
        state.record_worktree(root, Path(path).name, str(path), None, check=True)
    if existing:
        result = data(vcs.worktree_checkout(str(repo), branch, str(path), remote, root=root))
    else:
        result = data(vcs.worktree_add(str(repo), branch, str(path), remote, base, root=root))
        state.append_event('worktree.created', {'item': Path(path).name, 'worktree': str(path),
                                                'branch': result['branch'], 'base': f'{remote}/{base}',
                                                'start': result['start']}, root)
    _anchor(path, root, vcs, identity)
    if existing:
        state.record_worktree(root, Path(path).name, str(path), data(vcs.head(str(path), root=root))['sha'])
    return result


def adopt_worktree(root, item, path, vcs, dirty=False, repo=None, rebind=None):
    """Register an existing clean linked worktree of a configured repository as the item's (#510).
    #901, build reconcile: dirty registers uncommitted work as it is; repo refuses a worktree of
    another repository."""
    from wuwei import commit_push
    from wuwei.registry import data
    from wuwei import state

    _require_gate(root)
    path = Path(path).resolve()
    expected = repo
    try:
        repo, actual, _ = commit_push.context(path, {}, {}, root, identity=False)
    except ValueError as exc:
        raise state.StateError(f'{path} is not a worktree of a configured repository: {exc}') from exc
    if expected and repo['name'] != expected:
        raise state.StateError(f'{path} is a worktree of {repo["name"]}, not of {expected}, the repository '
                               f'{item} is for; pass a worktree of {expected}')
    if actual['path'] == actual['common_dir']:
        raise state.StateError(f'{path} is the main checkout; run bin/wuwei worktree add {item} --branch <branch> '
                               f'--repo {repo["name"]} to check the branch out in its own worktree')
    from wuwei import brief
    rows = brief.read(vcs.worktrees, str(path), root=root)
    tops = [Path(row['path']).resolve() for row in rows if isinstance(row, dict) and isinstance(row.get('path'), str)] \
        if isinstance(rows, list) else []
    if path not in tops:
        top = max((top for top in tops if path.is_relative_to(top)), key=lambda top: len(top.parts), default=None)
        raise state.StateError(f'{path} is not a worktree root; rerun bin/wuwei worktree adopt '
                               f'{top or "<worktree root>"} --item {item}')
    changes = [row['path'] for row in brief.status(vcs, str(path), root)]
    if changes and not dirty:
        raise state.StateError(
            'worktree has unrecorded changes: ' + ', '.join(changes)
            + f'; commit them, or run git -C {path} stash push --include-untracked, then rerun '
            f'bin/wuwei worktree adopt {path} --item {item}. To register the work as it is, run '
            f'bin/wuwei build reconcile {item} --worktree {path}')
    previous = state.read_state(root)
    recorded = previous['items'].get(item, {}).get('worktree')
    replace = rebind and recorded and (root / recorded).resolve() != path
    head = data(vcs.head(str(path), root=root))['sha']
    state.record_worktree(root, item, path, None, check=True, replace=previous if replace else None)
    if replace:
        import hashlib
        import json
        from wuwei import sessions
        from wuwei.commands.build import _running
        _running(previous, item)
        old = (root / recorded).resolve()
        old_head = 'missing'
        if old.exists():
            old_context = data(vcs.repo_context(str(old), root=root))
            if Path(old_context['common_dir']).resolve() != Path(actual['common_dir']).resolve():
                raise state.StateError(f'{old} and {path} belong to different repositories; '
                                       f'admit the requested work as its own item with bin/wuwei plan add <item> --repo {repo["name"]}')
            old_head = data(vcs.head(str(old), root=root))['sha']
        token = hashlib.sha256(json.dumps([previous['items'][item], previous.get('builds', {}).get(item),
                                          str(path), old_head, head, changes], sort_keys=True).encode()).hexdigest()
        detail = (f'Rebind {item} from {old} at HEAD {old_head} to {path} at HEAD {head}. '
                  'Discard the old build evidence and run checks and gates on the selected work.')
        if reason := sessions.needs_owner(root, rebind, detail, token):
            raise state.StateError(reason)
    _anchor(path, root, vcs, repo['identity'])
    if replace and (head != data(vcs.head(str(path), root=root))['sha']
                    or old_head != (data(vcs.head(str(old), root=root))['sha'] if old.exists() else 'missing')):
        raise state.StateError('worktree HEAD changed during rebind; rerun build reconcile')
    if state.read_state(root)['items'][item].get('worktree') != str(path):  # #901: a rerun records nothing
        state.record_worktree(root, item, path, head, replace=previous if replace else None)
    return {'item': item, 'path': str(path), 'head': head}


def branch_worktree(vcs, repo, branch, root):
    """The path of the repository's worktree on branch, else None."""
    from wuwei import brief
    rows = brief.read(vcs.worktrees, str(repo), root=root)
    if not isinstance(rows, list):
        raise ValueError(f'invalid worktree listing; {DAMAGED}')
    return next((row['path'] for row in rows if isinstance(row, dict) and row.get('branch') == branch), None)
