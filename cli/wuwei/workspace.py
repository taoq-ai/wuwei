"""Shared workspace paths and validated configuration."""

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
    "reset_epoch": (int, 0, 0), "quiet_hours": [(str, None)],
    "bot_login": (str, ""), "bot_min_score": (int, 5, 0),
    "bot_score_pattern": (str, r"Confidence Score:\s*([0-9]+)/5"),
    "fix_pattern": (str, r"(?i)\b(?:fix(?:es|ed)?|bugfix|hotfix|revert)\b"),
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
SURFACES = ("decisions", "digest", "nudges", "dm", "report")
# #331: what warns and what blocks, per area, by where the plugin runs.
AREAS = ('integrity', 'mcp', 'publish', 'records', 'outward', 'seats')
AREA_LEVELS = ('off', 'warn', 'block')
POSTURES = {
    'observe': {**{area: 'warn' for area in AREAS}, 'records': 'block'},
    'guarded': {'integrity': 'block', 'mcp': 'warn', 'publish': 'block', 'records': 'block',
                'outward': 'warn', 'seats': 'warn'},
    'strict': {area: 'block' for area in AREAS},
}
# Floors no posture or override lowers; a lower override is a config finding.
FLOORS = {'records': 'block'}

# 5.11: what the tracker opens (classes) and what it comments (kinds).
AUDIENCES = ('owner', 'team', 'company', 'client', 'public')  # #496: outbound audience classes.
TOPICS = ('sensitive', 'commitment', 'disagreement', 'thread')
TRACKER_CLASSES = ("items", "bugs", "triage", "follow-ups")
TRACKER_KINDS = ("decisions", "progress", "verdicts", "pr", "close")

SCHEMA = {
    "scanner": {"severity_threshold": (str, "high", ("critical", "high", "medium", "low")),
                "mcp": {"project_file": (str, ".mcp.json"),
                        "plugins_file": (str, "~/.claude/plugins/installed_plugins.json"),
                        "user_file": (str, "~/.claude.json"),
                        "timeout_seconds": (int, 60, 1),
                        "block": [(str, None, ("critical", "high", "medium", "low", "unmeasured")), []]}},
    "security": {"required": (bool, False), "posture": (str, "guarded", tuple(POSTURES)),
                 "areas": {area: (str, "", ("", *AREA_LEVELS)) for area in AREAS}},
    "owner": {"name": (str, ""), "pronouns": (str, ""), "handles": [(str, None)],
              "timezone": (str, ""),
              "verbosity": {"default": (str, "brief", LEVELS),
                            **{name: (str, "", ("", *LEVELS)) for name in SURFACES}}},
    "repos": [{"name": (str, None), "path": (str, None),
               "default_branch": (str, None), "fast_checks": [(str, "")],
               "review_required_checks": [(str, None)],
               "merge_deploys": (bool, True), "merge": MERGE_SCHEMA,
               "gates": {"floor": (str, "standard", ("light", "standard", "full")),
                         "light_max_lines": (int, 100, 0),
                         "trust_paths": [(str, None), [
                             "guards/*", "state.py", "adapters/*", ".claude-plugin/*", ".github/*",
                             "ci/*", "workflows/*", "deploy/*", "infra/*"]]},
               "identity": {"name": (str, ""), "email": (str, "")},
               "shepherd": {"reviewers": [(str, None)]}}],
    "worktree": {"git_hooks": (str, "chain", ("chain", "skip", "replace"))},
    "checks": {"python": (str, ""), "bootstrap": (str, "")},  # #520
    # #524: with no grant, a merge asks on a card or names the host-terminal command; "" follows the posture.
    "merge": {"default_tier": (str, "", ("", "ask", "owner_only"))},
    # #478: standing grants, written by the owner's Always allow answer; ignored under strict.
    "grants": {"standing": [{"action": (str, None, ("deploy", "release", "publish", "merge")),
                             "target": (str, None), "scope": (str, "always", ("always",)),
                             "decision": (str, None), "date": (str, None)}]},
    # #528: 0 derives CAP and host.seats from the measured host; a positive value is the owner's.
    "cap": (int, 0, 0),
    "budget": {"tokens_per_day": (int, 0, 0)},
    "template_version": (str, ""),
    "calibrate": {"fast_check_seconds": (int, 60, 1)},
    "prioritisation": {"framework": (str, "wsjf", ("wsjf", "rice"))},
    "discovery": {"min_queue": (int, 2, 1),
                  "autostart": (str, "strict", ("off", "strict", "goal"))},
    "tracker": {"backlog_filter": (str, ""),
                "states": {"in_review": (str, "In Review"), "done": (str, "Done")},
                "required": (bool, True),
                "skip_tiers": [(str, None, ("light", "standard", "full")), []],
                "strict_close": (bool, True),
                "create": [(str, None, ("bugs", "triage", "follow-ups")),
                           ["bugs", "triage", "follow-ups"]],
                "log": [(str, None, TRACKER_KINDS), list(TRACKER_KINDS)],
                "auto": [(str, None, (*TRACKER_CLASSES, *TRACKER_KINDS)), ["progress", "pr", "close"]],
                "max_per_item_per_day": (int, 10, 1),
                "project": (str, ""), "board": (str, "")},
    "docs": {"system": (str, "none"),
             "required_tiers": [(str, None, ("light", "standard", "full")), ["standard", "full"]],
             "space": (str, ""), "root": (str, "docs"),
             "publish": [(str, None, ("report", "retro")), ["report", "retro"]],
             "auto": [(str, None, ("page", "report", "retro")), []],
             "strict_close": (bool, True)},
    "calendar": {"url": (str, "")},
    "brief": {"lead_minutes": (int, 30, 1),
              "style": {"length": (str, "standard", ("concise", "standard")),
                        "speed": (int, 180, 120, 240)},
              "remote": (str, "origin"),
              "prior_branch_pattern": (str, "*{item}*"),
              "full_path_patterns": [(str, "")]},
    "host": {"free_memory_mb": (int, 1024, 0), "seats": (int, 0, 0),
             "reservation_timeout_seconds": (int, 14400, 1)},
    "consolidation": {"archive_after_days": (int, 30, 0),
                      "similarity_threshold": (float, 0.85)},
    "memory": {"max_notes": (int, 60, 1), "note_line_cap": (int, 80, 1),
               "probation_days": (int, 10, 0), "state_entry_cap": (int, 3, 1),
               "digest": (str, "week", ("week", "off")), "budget_tokens": (int, 6000, 1),
               "export_to": (str, "CLAUDE.md")},
    "metrics": {"transcripts": (str, "~/.claude/projects"), "band_margin": (float, 0.2)},
    "voice": {"sources": {"*": [(str, None)]}, "review_prs": [(str, None)]},
    "build": {"max_iterations": (int, 8, 1), "stuck_after": (int, 3, 1),
              "poll_interval_seconds": (int, 5, 0), "poll_timeout_seconds": (int, 3600, 1)},
    "codex": {"command": [(str, None)], "timeout_seconds": (int, 300, 1)},
    "gates": {"second_opinion": (str, "off"),
              "second_opinion_role": (str, "quality", ("arch", "quality", "security"))},
    "watch": {"clock_seconds": (int, 600, 1), "dead_seconds": (int, 1200, 1),
              "stale_seconds": (int, 900, 1), "sweep_seconds": (int, 7200, 1),
              "ping_url": (str, "")},
    "sessions": {"stale_seconds": (int, 3600, 1),
                 "rotate_after": {"turns": (int, 0, 0), "compactions": (int, 0, 0),
                                  "clock": (str, "")}},
    "listen": {"poll_seconds": (int, 60, 1), "dead_seconds": (int, 300, 1)},
    "responder": {"enabled": (bool, True)},
    "steward": {"every_tool_calls": (int, 50, 1), "loop_window_hours": (int, 4, 1),
                "loop_threshold": (int, 9, 1)},
    "autonomy": {"mode": (str, "autonomous", ("autonomous", "supervised"))},
    "decisions": {"wait_hours": (int, 24, 1),
                  "cruise": {"enabled": (bool, True), "margin": (float, 0.2),
                             "max_per_day": (int, 20, 0), "undo_minutes": (int, 60, 1),
                             "promote_agreements": (int, 10, 1), "promote_days": (int, 14, 1),
                             "levels": {"*": (int, None, 0, 3)}},
                  "lenses": {"*": (str, "")}},
    "pr": {"poll_seconds": (int, 120, 1), "action_minutes": (int, 30, 1),
           "review_window": (int, 120, 1)},
    "shepherd": {"review_channel": (str, ""), "lead_login": (str, ""),
                 "reviewers": [(str, None)], "reviewers_exclude": [(str, None)],
                 "review_gate_check": (str, "Review Gate"),
                 "min_reviewers": (int, 1, 0),
                 "author_windows_days": [(int, None, 1), [90, 180]],
                 "tie_commits": (int, 2, 0), "autostart": (bool, True),
                 "source_exclude": [(str, None), ["specs/*", "*.lock", "*lock.json",
                                                    "*.generated.*", "generated/*"]],
                 "authors": {"*": {"login": (str, None), "mention": (str, "")}}},
    "retro": {"repo": (str, "."),
              "charter_paths": [(str, None), [".wuwei/charters"]],
              "changelog": (str, ".wuwei/memory/CHANGELOG.md")},
    "profile": (str, "strict", ("strict", "standard")),
    "guards": {"mode": (str, "enforce", ("enforce", "shadow")), "shadow_days": (int, 7, 1),
               "shadow_since": (str, "")},
    "boundary": {"*": (str, "")},
    "environments": {"*": (str, "")},
    "deploy": {"workflows": [(str, None)], "deny": [(str, None)]},
    "outbound": {
        "work_channels": [(str, None)], "external_channels": [(str, None)],
        "company_domains": [(str, None)], "code_host_orgs": [(str, None)],
        "people": {"*": {"email": (str, ""), "org": (str, ""), "class": (str, "", ("", *AUDIENCES))}},
        # #496: any class for a channel id, over work_channels (team) and external_channels (client).
        "channel_classes": {"*": (str, None, AUDIENCES)},
        # #496: the owner's tier rows, before the defaults; the first match wins.
        "tiers": [{"tool": (str, ""), "person": (str, ""), "channel": (str, ""),
                   "audience": (str, "", ("", *AUDIENCES)), "topic": (str, "", ("", *TOPICS)),
                   "tier": (str, None, ("send", "ask", "block"))}, []],
        "owner": {"slack": {"user": (str, ""), "dm": (str, "")}, "mail": (str, ""),
                  "code_host": (str, "")},
        "owner_channel": (str, "session", ("session", "dm")),
        "sensitive_keywords": [(str, None), [
            "performance", "feedback", "compensation", "salary", "pay", "bonus",
            "hiring", "interview", "firing", "personal", "health", "medical",
            "conflict", "legal", "hr", "harassment", "promotion", "illness",
        ]],
        "sensitive_patterns": [(str, None), [r"\bmental\s+health\b"]],
        "commitment_patterns": [(str, None), [
            r"\b(?:i|we)\s*(?:['\u2019]ll|will|shall|can|promise|commit)\b",
            r"\b(?:by|before|after)\s+(?:\w+day|tomorrow|noon|\d)",
            r"\b(?:follow[ -]?up|deadline|out of scope|next (?:week|sprint))\b",
        ]],
        "disagreement_patterns": [(str, None), [
            r"\bdisagree\b", r"\b(?:you|that)\s*(?:are|['\u2019]re|is)\s+wrong\b",
            r"\b(?:i|we)\s+(?:object|oppose)\b",
        ]],
        # #492: card asks the owner, auto writes under observe and guarded, off never learns.
        "learn": (str, "card", ("card", "auto", "off")),
        # #527: the umbrella. What no narrower row holds gets this tier (chat, code host, mail,
        # other); docs and tracker writes keep docs.auto and tracker.auto. With send, the broad
        # default rows (commitment, disagreement, company) drop out and the owner's rows narrow.
        "default_tier": (str, "send", ("send", "ask", "block")),
    },
    "outward": {
        # #533 (owner, 2026-10-05): no built-in internal-state words; real messages say "agents" and
        # "phase". An owner who wants the old list adds it; the matched word is named in the reason.
        "patterns": [(str, ""), []],
        "banned_characters": [(str, ""), ["emoji", "\u2014", "\u2015", "\u2e3a", "\u2e3b"]],
        "max_length": {"*": (int, 1, 1)},
        "humanize": (bool, True),
        "humanize_kinds": [(str, None, ("dm", "tracker", "docs", "pr", "review")),
                           ["dm", "tracker", "docs", "pr", "review"]],
        "humanize_strict": (bool, False),
        "draft_ttl": (int, 3600, 60),
        "tool_patterns": [{"pattern": (str, None), "channel": (str, None)}, [
            # #492: the brand anywhere in the name, so mcp__<uuid>__slack_send_message matches.
            {"pattern": r"mcp__(?=.*slack).*__.*(send|post|reply|schedule|update|add_message|add_reaction|react|chat_post|delete|edit|upload|invite|kick|archive|pin|star).*", "channel": "slack"},
            {"pattern": r"mcp__(?=.*linear).*__(?:\w*_)?(save|create|update)_(issue|comment)", "channel": "tracker"},
            {"pattern": r"mcp__(?=.*github).*__(?:\w*_)?(add|create|update)_.*comment.*", "channel": "code_host"},
            {"pattern": r"mcp__(?=.*notion).*__.*(create|update|append|patch|post|move|duplicate).*", "channel": "docs"},
            {"pattern": r"mcp__(?=.*atlassian).*__(?:\w*_)?(create|update)Confluence.*", "channel": "docs"},
        ]],
        # #492: the owner's alias of an MCP server id to its channel.
        "servers": {"*": (str, None, ("slack", "tracker", "code_host", "docs", "mail", "other"))},
        # #492: the owner's approval mode of an MCP server id; absent is the class default.
        "modes": {"*": (str, None, ("send", "draft", "refuse"))},
        # #496: a connector's default audience class for what it has not seen, by server id.
        "classes": {"*": (str, None, AUDIENCES)},
    },
    "telemetry": {"enabled": (bool, True),
                  "share": (str, "", ("", "off", "anonymous", "attributed")),
                  "endpoint": (str, ""), "repository": (str, "taoq-ai/wuwei"),
                  "otlp": {"endpoint": (str, ""), "headers_env": (str, "")}},
    "chat": {"identity": (str, "connector", ("connector", "custom_app"))},
    "control_plane": {"content": (str, "summary", ("summary", "none")), "owner": (str, "")},
    "spec": {"engine": (str, "speckit", ("speckit", "superpowers", "openspec", "none")),
             "mode": (str, "strict", ("strict", "advisory", "off")),
             "skip_tiers": [(str, None, ("light", "standard", "full")), ["light"]]},
    "adapters": {"tracker": (str, "none"), "chat": (str, "none"),
                 "review_bot": (str, "none"), "runtime": (str, "claude"),
                 "scanner": (str, "none"), "code_host": (str, "github"),
                 "vcs": (str, "git"), "host": (str, "local"),
                 "checks": (str, "local"), "tts": (str, "say" if sys.platform == "darwin" else "none"),
                 "calendar": (str, "none"), "transcripts": (str, "none"),
                 "inbound": (str, "none"), "redactor": (str, "builtin")},
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
    for root in (start, *start.parents):
        if (root / ".wuwei").is_dir():
            if (root / '.wuwei').is_symlink():
                raise ValueError('.wuwei must not be a symlink')
            return root
    raise FileNotFoundError(f"No .wuwei/ found from {start}; run from the workspace, set "
                            "WUWEI_WORKSPACE=<path> or pass --workspace <path> (wuwei init creates one)")


def worktree_workspace(path):
    """Read the local anchor installed by wuwei git-hook in managed worktrees."""
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
        raise ValueError(f'owner.timezone: unknown zone {name!r}; the owner sets an IANA zone such as Europe/Lisbon with bin/wuwei config set owner.timezone in a host terminal') from None


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
    """Service label and the unit file `<name> install` writes for this workspace."""
    import hashlib
    label = "wuwei-" + ("" if name == "watch" else f"{name}-") + hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()[:12]
    suffix = ".plist" if platform == "darwin" else ".service"
    return label, _unit_directory(platform) / f"{label}{suffix}"


def unit_installed(root, name="watch"):
    """watch_unit(root, name=name)[1].exists(); with no WUWEI unit installed at all (the
    common case) it lists the directory instead of loading hashlib for the label."""
    try:
        if not any(entry.startswith("wuwei-") for entry in os.listdir(_unit_directory(sys.platform))):
            return False
    except (FileNotFoundError, NotADirectoryError):
        return False
    except OSError:
        pass  # An unlistable directory: check the unit file itself, as before.
    return watch_unit(root, name=name)[1].exists()


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
    key = ".".join(map(str, path)) or "config"
    if isinstance(schema, tuple) and schema[1] is None and (
        value is None or isinstance(value, str) and not value.strip()
    ):
        line = _key_line(raw, path) or _key_line(raw, path[:-1])
        location = f' at line {line}' if line is not None else ''
        raise ConfigError(f'{key}: required{location}; the owner sets it with bin/wuwei config set {key} <value> in a host terminal')
    expected = dict if isinstance(schema, dict) else list if isinstance(schema, list) else schema[0]
    if type(value) is not expected:
        raise ConfigError(f"{key}: expected {expected.__name__}; the owner fixes it with bin/wuwei config set {key} <value> in a host terminal")
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
        return {name: _validate(value.get(name, _default(rule)), rule, (*path, name), raw, unknown)
                for name, rule in schema.items()}
    if isinstance(schema, list):
        return [_validate(item, schema[0], (*path, index), raw, unknown)
                for index, item in enumerate(value)]
    if len(schema) > 2:
        constraint = schema[2]
        if expected is int and value < constraint:
            raise ConfigError(f"{key}: expected integer >= {constraint}; the owner fixes it with bin/wuwei config set {key} <value> in a host terminal")
        if expected is int and len(schema) > 3 and value > schema[3]:
            raise ConfigError(f"{key}: expected integer <= {schema[3]}; the owner fixes it with bin/wuwei config set {key} <value> in a host terminal")
        if expected is str and value not in constraint:
            raise ConfigError(f"{key}: expected {' or '.join(constraint)}; the owner fixes it with bin/wuwei config set {key} <value> in a host terminal")
    return value


def _default(schema):
    if isinstance(schema, dict):
        return {}
    if isinstance(schema, list):
        return copy_data(schema[1]) if len(schema) > 1 else []
    return schema[1]


def copy_data(value):
    """copy.deepcopy for parsed TOML and JSON data: dicts and lists are copied, everything
    else in them is immutable. Hooks skip importing copy and weakref (#346)."""
    if isinstance(value, dict):
        return {key: copy_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [copy_data(item) for item in value]
    return value


# ponytail: per-process memo keyed on the config text; adapter and path checks rerun only
# when the text changes.
_CONFIGS = {}
# #346: the validated config and its warnings as JSON in .wuwei/generated, so a hook skips
# tomllib (with typing and string) and the checks. A copy serves only the exact text it was
# made from, under this plugin version and this layout; any other text is parsed and the
# copy rewritten. Keyed on the text, not the file's stat: a same-size rewrite inside one
# coarse timestamp tick keeps mtime, size and inode, and the text is read anyway.
CONFIG_CACHE = 'config.cache.json'
CONFIG_CACHE_VERSION = 14  # Bump when the parse, the schema, the defaults or the checks change.
# Only hook and status --line processes write the copy (__main__ turns this on): they pay the
# parse on every call. Every other command reads a current copy and writes nothing, so
# doctor, why and the board stay read-only.
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
    return fresh defaults. Unknown keys refuse only under strict (#353); otherwise their
    texts are appended to warnings when it is a list. In a hook or status line process, a
    parse of the file after its parsed copy missed rewrites the copy (#346); a hit writes
    nothing."""
    path = (find_workspace() if root is None else Path(root)) / ".wuwei/config.toml"
    generated = path.parent / 'generated'
    stale = False
    try:
        if raw is None:
            raw = path.read_text(encoding="utf-8")
            if _CONFIGS.get(path, (None,))[0] != raw:
                found = _cached(generated, raw)
                if found:
                    _CONFIGS[path] = (raw, *found)
                stale = not found
        if _CONFIGS.get(path, (None,))[0] == raw:
            if warnings is not None:
                warnings.extend(f'config.toml: {text}' for text in _CONFIGS[path][2])
            return copy_data(_CONFIGS[path][1])
        from datetime import date
        import tomllib
        parsed = tomllib.loads(raw)
        unknown = []
        try:
            config = _validate(parsed, SCHEMA, (), raw, unknown)
        except ConfigError:
            if unknown:  # A typo usually explains the error after it, as before #353.
                raise ConfigError(unknown[0]) from None
            raise
        config['adapters']['docs'] = config['docs']['system']  # #419: the registry reads adapters.
        for pattern in config['deploy']['deny']:
            program = pattern.split()[0]
            if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', program):
                raise ConfigError('deploy.deny: start each pattern with a literal executable name')
        if bad := next((text for text in unknown if text.startswith('unknown key outbound.tiers.')), None):
            raise ConfigError(bad)  # #496: a typo would widen the row to match everything.
        for index, row in enumerate(config['outbound']['tiers']):
            try:
                re.compile(row['tool'])
            except re.error:
                raise ConfigError(f'outbound.tiers.{index}.tool: not a regular expression; the owner fixes it '
                                  'with bin/wuwei config set in a host terminal') from None
        since = config['guards']['shadow_since']
        if since:
            try:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', since):
                    raise ValueError
                date.fromisoformat(since)
            except ValueError:
                raise ConfigError('guards.shadow_since: expected YYYY-MM-DD or ""; the owner fixes it with bin/wuwei config set guards.shadow_since in a host terminal') from None
        for area, floor in FLOORS.items():
            value = config['security']['areas'][area]
            if value and AREA_LEVELS.index(value) < AREA_LEVELS.index(floor):
                raise ConfigError(f'security.areas.{area}: "{value}" is below its floor "{floor}"; '
                                  f'{area} always blocks, remove the override')
        if not 0 < config['decisions']['cruise']['margin'] <= 1:
            raise ConfigError('decisions.cruise.margin: expected a number above 0 and at most 1; the owner fixes it with bin/wuwei config set decisions.cruise.margin <value> in a host terminal')
        for name, value in config['decisions']['cruise']['levels'].items():
            from wuwei.decision import CLASSES
            if name not in CLASSES:
                raise ConfigError(f'decisions.cruise.levels.{name}: unknown class; use one of '
                                  + ', '.join(CLASSES))
            if value > CLASSES[name][1]:
                raise ConfigError(f'decisions.cruise.levels.{name}: above its ceiling L{CLASSES[name][1]}; the owner lowers it with bin/wuwei config set in a host terminal')
        for name in config['decisions']['lenses']:
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', name):
                raise ConfigError(f'decisions.lenses.{name}: use letters, digits, dash or underscore, starting with a letter; the owner fixes it with bin/wuwei config set in a host terminal')
        for index, line in enumerate(config['grants']['standing']):
            if not (re.fullmatch(r'repo:[A-Za-z0-9_.*?-]+/[A-Za-z0-9_.*?-]+', line['target'])
                    and re.fullmatch(r'D-[1-9][0-9]*', line['decision'])
                    and re.fullmatch(r'\d{4}-\d{2}-\d{2}', line['date'])):
                raise ConfigError(f'grants.standing.{index}: expected target repo:<org>/<name>, decision '
                                  f'D-n and date YYYY-MM-DD; the owner fixes it with bin/wuwei grants '
                                  f'revoke {index + 1} in a host terminal')
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
                raise ConfigError(f'repos.{index}.name: duplicate {repo["name"]!r}{location}; the owner removes the duplicate [[repos]] entry in a host terminal (bin/wuwei config check validates)')
            repo_names.add(repo['name'])
            try:
                resolved = (path.parent.parent / Path(repo['path']).expanduser()).resolve()
            except (ValueError, OSError) as exc:
                raise ConfigError(f'repos.{index}.path: {exc}') from exc
            if resolved in repo_paths:
                line = _key_line(raw, ('repos', index, 'path'))
                location = f' at line {line}' if line is not None else ''
                raise ConfigError(f'repos.{index}.path: duplicate {repo["path"]!r}{location}; the owner removes the duplicate [[repos]] entry in a host terminal (bin/wuwei config check validates)')
            repo_paths.add(resolved)

        for kind, name in config['adapters'].items():
            try:
                registry.validate(kind, name, for_config=True)
            except ValueError as exc:
                key = ('docs', 'system') if kind == 'docs' else ('adapters', kind)
                line = _key_line(raw, key)
                location = f' at line {line}' if line is not None else ''
                text = str(exc).replace('adapters.docs:', 'docs.system:')
                raise ConfigError(f'{text}{location}') from exc
        if unknown and posture(config)[0] == 'strict':
            from wuwei import integrity  # A newer plugin's keys are unknown to me, not errors.
            if not integrity.newer_template(config):
                raise ConfigError(unknown[0])
        _CONFIGS[path] = (raw, config, tuple(unknown))
        if stale and CONFIG_CACHE_WRITES:
            _cache(generated, raw, config, unknown)
        if warnings is not None:
            warnings.extend(f'config.toml: {text}' for text in unknown)
        return copy_data(config)
    except (ConfigError, UnicodeError, _decode_error()) as exc:
        hint = ''
        if "immutable namespace ('repos',)" in str(exc):  # #326: repos = [] before [[repos]]
            line = _key_line(raw, ('repos',))
            if line:
                hint = f'; repos is assigned on line {line}; delete that line before using [[repos]] tables'
        raise ConfigError(f"config.toml: {exc}{hint}; run bin/wuwei config check after the fix") from exc


def posture(config):
    """The posture name and each area's level (#331); guards.mode = "shadow" (#308,
    deprecated) is observe."""
    name = 'observe' if config['guards']['mode'] == 'shadow' else config['security']['posture']
    return name, {area: config['security']['areas'][area] or level
                  for area, level in POSTURES[name].items()}


def posture_source(config):
    """The key the effective posture comes from (#355); guards.mode is retired."""
    return ('guards.mode = "shadow", deprecated; run doctor --fix'
            if config['guards']['mode'] == 'shadow' else 'security.posture')


def _require_gate(root):
    from wuwei import state
    if not (Path(root) / '.wuwei').is_dir():
        raise ValueError('worktree creation requires a workspace; run bin/wuwei init <path> first, or work from inside a workspace')
    if not state.read_state(root).get('gate_approved'):
        raise state.StateError('morning gate approval required before worktree creation; approve the plan at the morning gate (/wuwei:wuwei-plan) first')


def _anchor(path, root, vcs, identity):
    """Hooks (chained, #472), the pre-push anchor and the commit identity of an item worktree."""
    from wuwei.commands.git_hook import install
    from wuwei.registry import data
    install(path, root, vcs)
    if identity and identity['name'] and identity['email']:
        written = vcs.worktree_identity(str(path), identity['name'], identity['email'], root=root)
        if written.exit == 1:
            print(f'wuwei worktree warning: {written.reason}', file=sys.stderr)
        else:
            data(written)


def create_worktree(repo, branch, path, root, vcs, identity=None, existing=False):
    """Create and anchor a WUWEI worktree before handing it to a seat; existing checks out
    an existing branch and records the worktree as the item's (#510)."""
    from wuwei.registry import data
    from wuwei import sessions, state

    _require_gate(root)
    if existing:
        state.record_worktree(root, Path(path).name, str(path), None, check=True)
    sessions.claim_item(Path(root), Path(path).name)
    add = vcs.worktree_checkout if existing else vcs.worktree_add
    result = data(add(str(repo), branch, str(path), root=root))
    _anchor(path, root, vcs, identity)
    if existing:
        state.record_worktree(root, Path(path).name, str(path), data(vcs.head(str(path), root=root))['sha'])
    return result


def adopt_worktree(root, item, path, vcs):
    """Register an existing clean linked worktree of a configured repository as the item's (#510)."""
    from wuwei.guards import commit_push
    from wuwei.registry import data
    from wuwei import sessions, state

    _require_gate(root)
    path = Path(path).resolve()
    try:
        repo, actual, _ = commit_push.context(path, {}, {}, root, identity=False)
    except ValueError as exc:
        raise state.StateError(f'{path} is not a worktree of a configured repository: {exc}') from exc
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
    changes = brief.status(vcs, str(path), root)
    if changes:
        raise state.StateError(
            'worktree has unrecorded changes: ' + ', '.join(row['path'] for row in changes)
            + f'; commit them, or run git -C {path} stash push --include-untracked, then rerun '
            f'bin/wuwei worktree adopt {path} --item {item}')
    state.record_worktree(root, item, path, None, check=True)
    sessions.claim_item(Path(root), item)
    _anchor(path, root, vcs, repo['identity'])
    head = data(vcs.head(str(path), root=root))['sha']
    state.record_worktree(root, item, path, head)
    return {'item': item, 'path': str(path), 'head': head}


def branch_worktree(vcs, repo, branch, root):
    """The path of the repository's worktree on branch, else None."""
    from wuwei import brief
    rows = brief.read(vcs.worktrees, str(repo), root=root)
    if not isinstance(rows, list):
        raise ValueError(f'invalid worktree listing; {DAMAGED}')
    return next((row['path'] for row in rows if isinstance(row, dict) and row.get('branch') == branch), None)
