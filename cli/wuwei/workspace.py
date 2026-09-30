"""Shared workspace paths and validated configuration."""

from copy import deepcopy
from datetime import datetime
import os
from pathlib import Path
import re
import sys
import tempfile
import tomllib


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

SCHEMA = {
    "scanner": {"severity_threshold": (str, "high", ("critical", "high", "medium", "low")),
                "mcp": {"project_file": (str, ".mcp.json"),
                        "plugins_file": (str, "~/.claude/plugins/installed_plugins.json"),
                        "user_file": (str, "~/.claude.json")}},
    "security": {"required": (bool, False)},
    "owner": {"name": (str, ""), "pronouns": (str, ""), "handles": [(str, None)]},
    "repos": [{"name": (str, None), "path": (str, None),
               "default_branch": (str, None), "fast_checks": [(str, "")],
               "review_required_checks": [(str, None)],
               "merge_deploys": (bool, True), "merge": MERGE_SCHEMA,
               "identity": {"name": (str, ""), "email": (str, "")}}],
    "cap": (int, 1, 1),
    "prioritisation": {"framework": (str, "wsjf", ("wsjf", "rice"))},
    "discovery": {"min_queue": (int, 2, 1),
                  "autostart": (str, "strict", ("off", "strict", "goal"))},
    "tracker": {"backlog_filter": (str, ""),
                "states": {"in_review": (str, "In Review"), "done": (str, "Done")}},
    "calendar": {"url": (str, "")},
    "brief": {"lead_minutes": (int, 30, 1),
              "style": {"length": (str, "standard", ("concise", "standard")),
                        "speed": (int, 180, 120, 240)},
              "remote": (str, "origin"),
              "prior_branch_pattern": (str, "*{item}*"),
              "full_path_patterns": [(str, "")]},
    "host": {"free_memory_mb": (int, 1024, 0), "seats": (int, 4, 1),
             "reservation_timeout_seconds": (int, 14400, 1)},
    "consolidation": {"archive_after_days": (int, 30, 0),
                      "similarity_threshold": (float, 0.85)},
    "memory": {"max_notes": (int, 60, 1), "note_line_cap": (int, 80, 1),
               "probation_days": (int, 10, 0), "state_entry_cap": (int, 3, 1)},
    "metrics": {"transcripts": (str, "~/.claude/projects")},
    "voice": {"sources": {"*": [(str, None)]}, "review_prs": [(str, None)]},
    "build": {"max_iterations": (int, 8, 1), "stuck_after": (int, 3, 1),
              "poll_interval_seconds": (int, 5, 0), "poll_timeout_seconds": (int, 3600, 1)},
    "codex": {"command": [(str, None)], "timeout_seconds": (int, 300, 1)},
    "watch": {"clock_seconds": (int, 600, 1), "dead_seconds": (int, 1200, 1),
              "stale_seconds": (int, 900, 1), "sweep_seconds": (int, 7200, 1)},
    "steward": {"every_tool_calls": (int, 50, 1)},
    "pr": {"poll_seconds": (int, 120, 1), "action_minutes": (int, 30, 1),
           "review_window": (int, 120, 1)},
    "shepherd": {"review_channel": (str, ""), "lead_login": (str, ""),
                 "review_gate_check": (str, "Review Gate"),
                 "min_reviewers": (int, 1, 0),
                 "author_windows_days": [(int, None, 1), [90, 180]],
                 "tie_commits": (int, 2, 0),
                 "source_exclude": [(str, None), ["specs/*", "*.lock", "*lock.json",
                                                    "*.generated.*", "generated/*"]],
                 "authors": {"*": {"login": (str, None), "mention": (str, None)}}},
    "retro": {"repo": (str, "."),
              "charter_paths": [(str, None), [".wuwei/charters"]],
              "changelog": (str, ".wuwei/memory/CHANGELOG.md")},
    "profile": (str, "strict", ("strict", "standard")),
    "boundary": {"*": (str, "")},
    "environments": {"*": (str, "")},
    "deploy": {"workflows": [(str, None)], "deny": [(str, None)]},
    "outbound": {
        "work_channels": [(str, None)], "external_channels": [(str, None)],
        "company_domains": [(str, None)], "code_host_orgs": [(str, None)],
        "people": {"*": {"email": (str, ""), "org": (str, "")}},
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
    },
    "outward": {
        "patterns": [(str, ""), [
            r"\bdrafts?\b.*\b(?:pending|owner|approval)\b",
            r"\bpending\s+drafts?\b", r"\bqueues?\b",
            r"\b(?:the\s+)?agents?\b", r"\bsentinel\b", r"\bseats?\b",
            r"\b(?:claude|codex|subagents?|steward|gate\s+verdicts?)\b",
            r"\bwuwei\b", r"\bqueued\b", r"\bthe\s+owner\b",
        ]],
        "banned_characters": [(str, ""), ["emoji", "\u2014", "\u2015", "\u2e3a", "\u2e3b"]],
        "max_length": {"*": (int, 1, 1)},
        "tool_patterns": [{"pattern": (str, None), "channel": (str, None)}, [
            {"pattern": r"mcp__.*slack.*__.*(send|post|reply|schedule|update).*", "channel": "slack"},
            {"pattern": r"mcp__.*linear.*__(save|create|update)_(issue|comment)", "channel": "tracker"},
            {"pattern": r"mcp__.*github.*__(add|create|update)_.*comment.*", "channel": "code_host"},
        ]],
    },
    "chat": {"identity": (str, "connector", ("connector", "custom_app"))},
    "control_plane": {"content": (str, "summary", ("summary", "none"))},
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


def atomic_write(path, text, *, replace=True, mode=None):
    """Durably write text through a temporary file in the destination directory."""
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            if mode is not None:
                os.fchmod(stream.fileno(), mode)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
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
                f"WUWEI_WORKSPACE={override!r} must name a root containing .wuwei/"
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
    raise FileNotFoundError(f"No .wuwei/ found from {start}; run wuwei init")


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
                raise ValueError('invalid worktree workspace anchor')
            return root
    return None


def scope(path):
    """An environment-selected workspace is context, not proof of membership."""
    from wuwei import registry
    from wuwei.registry import data

    selected = None
    if 'WUWEI_WORKSPACE' in os.environ:
        try:
            selected = find_workspace(path)
        except FileNotFoundError as exc:
            raise ValueError('invalid WUWEI_WORKSPACE override') from exc
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
        vcs = registry.load('vcs', config)
        actual = data(vcs.repo_context(str(path), root=root))
        common = actual.get('common_dir')
        if not isinstance(common, str) or not Path(common).is_absolute():
            raise ValueError('missing worktree repository context')
        if any(data(vcs.repo_context(str(repo), root=root)).get('common_dir') == common
               for repo in repos):
            return root, config
    return None


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


def now():
    """Return local now, or the datetime represented by WUWEI_NOW."""
    if "WUWEI_NOW" not in os.environ:
        return datetime.now().astimezone()
    timestamp = os.environ["WUWEI_NOW"]
    try:
        if len(timestamp) <= 10:
            raise ValueError("time component required")
        dt = datetime.fromisoformat(timestamp)
        return dt if dt.tzinfo else dt.astimezone()
    except ValueError as exc:
        raise ValueError("WUWEI_NOW must be an ISO datetime with a time component") from exc


def day_dir(root=None):
    """Return today's day directory without creating it."""
    root = find_workspace() if root is None else Path(root)
    return root / ".wuwei/days" / now().date().isoformat()


def watch_unit(root, platform=sys.platform):
    """Service label and the unit file `watch install` writes for this workspace."""
    import hashlib
    label = "wuwei-" + hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()[:12]
    home = Path.home()
    if platform == "darwin":
        return label, home / "Library/LaunchAgents" / f"{label}.plist"
    return label, Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "systemd/user" / f"{label}.service"


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


def _validate(value, schema, path, raw):
    key = ".".join(map(str, path)) or "config"
    if isinstance(schema, tuple) and schema[1] is None and (
        value is None or isinstance(value, str) and not value.strip()
    ):
        line = _key_line(raw, path) or _key_line(raw, path[:-1])
        location = f' at line {line}' if line is not None else ''
        raise ConfigError(f'{key}: required{location}')
    expected = dict if isinstance(schema, dict) else list if isinstance(schema, list) else schema[0]
    if type(value) is not expected:
        raise ConfigError(f"{key}: expected {expected.__name__}")
    if isinstance(schema, dict):
        for name in value:
            if name not in schema and "*" not in schema:
                unknown = (*path, name)
                line = _key_line(raw, unknown)
                location = f" at line {line}" if line is not None else ""
                raise ConfigError(
                    f"unknown key {'.'.join(map(str, unknown))}{location}; "
                    "remove it or use a documented key"
                )
        if "*" in schema:
            return {name: _validate(item, schema['*'], (*path, name), raw)
                    for name, item in value.items()}
        return {name: _validate(value.get(name, _default(rule)), rule, (*path, name), raw)
                for name, rule in schema.items()}
    if isinstance(schema, list):
        return [_validate(item, schema[0], (*path, index), raw)
                for index, item in enumerate(value)]
    if len(schema) > 2:
        constraint = schema[2]
        if expected is int and value < constraint:
            raise ConfigError(f"{key}: expected integer >= {constraint}")
        if expected is int and len(schema) > 3 and value > schema[3]:
            raise ConfigError(f"{key}: expected integer <= {schema[3]}")
        if expected is str and value not in constraint:
            raise ConfigError(f"{key}: expected {' or '.join(constraint)}")
    return value


def _default(schema):
    if isinstance(schema, dict):
        return {}
    if isinstance(schema, list):
        return deepcopy(schema[1]) if len(schema) > 1 else []
    return schema[1]


# ponytail: per-process memo keyed on the config text; adapter and path checks rerun only
# when the text changes.
_CONFIGS = {}


def load_config(root=None):
    """Read .wuwei/config.toml, reject invalid fields, and return fresh defaults."""
    path = (find_workspace() if root is None else Path(root)) / ".wuwei/config.toml"
    try:
        raw = path.read_text(encoding="utf-8")
        if _CONFIGS.get(path, (None,))[0] == raw:
            return deepcopy(_CONFIGS[path][1])
        parsed = tomllib.loads(raw)
        config = _validate(parsed, SCHEMA, (), raw)
        for pattern in config['deploy']['deny']:
            program = pattern.split()[0]
            if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', program):
                raise ConfigError('deploy.deny: start each pattern with a literal executable name')
        repo_names = set()
        repo_paths = set()
        for index, repo in enumerate(config['repos']):
            if repo['name'] in repo_names:
                line = _key_line(raw, ('repos', index, 'name'))
                location = f' at line {line}' if line is not None else ''
                raise ConfigError(f'repos.{index}.name: duplicate {repo["name"]!r}{location}')
            repo_names.add(repo['name'])
            try:
                resolved = (path.parent.parent / Path(repo['path']).expanduser()).resolve()
            except (ValueError, OSError) as exc:
                raise ConfigError(f'repos.{index}.path: {exc}') from exc
            if resolved in repo_paths:
                line = _key_line(raw, ('repos', index, 'path'))
                location = f' at line {line}' if line is not None else ''
                raise ConfigError(f'repos.{index}.path: duplicate {repo["path"]!r}{location}')
            repo_paths.add(resolved)
        from wuwei import registry

        for kind, name in config['adapters'].items():
            try:
                registry.validate(kind, name, for_config=True)
            except ValueError as exc:
                line = _key_line(raw, ('adapters', kind))
                location = f' at line {line}' if line is not None else ''
                raise ConfigError(f'{exc}{location}') from exc
        _CONFIGS[path] = (raw, config)
        return deepcopy(config)
    except (ConfigError, tomllib.TOMLDecodeError, UnicodeError) as exc:
        raise ConfigError(f"config.toml: {exc}") from exc


def create_worktree(repo, branch, path, root, vcs, identity=None):
    """Create and anchor a WUWEI worktree before handing it to a seat."""
    from wuwei.commands.git_hook import install
    from wuwei.registry import data
    from wuwei import state

    if not (Path(root) / '.wuwei').is_dir():
        raise ValueError('worktree creation requires a workspace')
    if not state.read_state(root).get('gate_approved'):
        raise state.StateError('morning gate approval required before worktree creation')
    result = data(vcs.worktree_add(str(repo), branch, str(path), root=root))
    install(path, root, vcs)
    if identity and identity['name'] and identity['email']:
        data(vcs.worktree_identity(str(path), identity['name'], identity['email'], root=root))
    return result
