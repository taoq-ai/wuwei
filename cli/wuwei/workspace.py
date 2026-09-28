"""Shared workspace paths and validated configuration."""

from copy import deepcopy
from datetime import datetime
import os
from pathlib import Path
import re
import tempfile
import tomllib


# Dicts describe tables; lists contain an item rule and optional array defaults;
# tuples are type/default/constraint.
# A '*' table entry describes user-defined register/channel names.
# A None default marks a required, nonblank field.
SCHEMA = {
    "owner": {"name": (str, ""), "pronouns": (str, ""), "handles": [(str, None)]},
    "repos": [{"name": (str, None), "path": (str, None),
               "default_branch": (str, "main"), "fast_checks": [(str, "")]}],
    "cap": (int, 1, 1),
    "brief": {"remote": (str, "origin"),
              "prior_branch_pattern": (str, "*{item}*"),
              "full_path_patterns": [(str, "")]},
    "host": {"free_memory_mb": (int, 1024, 0), "seats": (int, 1, 1),
             "reservation_timeout_seconds": (int, 14400, 1)},
    "memory": {"max_notes": (int, 60, 1)},
    "profile": (str, "strict", ("strict", "standard")),
    "boundary": {"*": (str, "")},
    "environments": {"*": (str, "")},
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
    "adapters": {"tracker": (str, "none"), "chat": (str, "none"),
                 "review_bot": (str, "none"), "runtime": (str, "claude"),
                 "scanner": (str, "none"), "code_host": (str, "github"),
                 "vcs": (str, "git"), "host": (str, "local")},
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


def find_workspace(start=None):
    """Return the root containing .wuwei, honoring WUWEI_WORKSPACE first."""
    if "WUWEI_WORKSPACE" in os.environ:
        override = os.environ["WUWEI_WORKSPACE"]
        root = Path(override).expanduser().resolve()
        if not override or not (root / ".wuwei").is_dir():
            raise FileNotFoundError(
                f"WUWEI_WORKSPACE={override!r} must name a root containing .wuwei/"
            )
        return root
    start = (Path.cwd() if start is None else Path(start)).resolve()
    for root in (start, *start.parents):
        if (root / ".wuwei").is_dir():
            return root
    raise FileNotFoundError(f"No .wuwei/ found from {start}; run wuwei init")


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
        if expected is str and value not in constraint:
            raise ConfigError(f"{key}: expected {' or '.join(constraint)}")
    return value


def _default(schema):
    if isinstance(schema, dict):
        return {}
    if isinstance(schema, list):
        return deepcopy(schema[1]) if len(schema) > 1 else []
    return schema[1]


def load_config(root=None):
    """Read .wuwei/config.toml, reject invalid fields, and return fresh defaults."""
    path = (find_workspace() if root is None else Path(root)) / ".wuwei/config.toml"
    try:
        raw = path.read_text(encoding="utf-8")
        parsed = tomllib.loads(raw)
        config = _validate(parsed, SCHEMA, (), raw)
        repo_names = set()
        repo_paths = set()
        for index, repo in enumerate(config['repos']):
            if repo['name'] in repo_names:
                line = _key_line(raw, ('repos', index, 'name'))
                location = f' at line {line}' if line is not None else ''
                raise ConfigError(f'repos.{index}.name: duplicate {repo["name"]!r}{location}')
            repo_names.add(repo['name'])
            resolved = (path.parent.parent / Path(repo['path']).expanduser()).resolve()
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
        return config
    except (ConfigError, tomllib.TOMLDecodeError, UnicodeError) as exc:
        raise ConfigError(f"{path}: {exc}") from exc
