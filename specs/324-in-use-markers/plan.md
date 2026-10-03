# Implementation Plan: Claude Code in-use process markers are not a tamper finding

**Branch**: `324-in-use-markers` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

Both walks of the installed plugin (`inventory` and `fresh`) keep their own copy of the
prune list, and neither knows about Claude Code's `.in_use/<pid>` markers. Replace the two
copies with one helper, `_prune`, that also drops the root `.in_use` directory after
checking that every entry in it is a regular file named by digits. Everything else
(`measure`, the fingerprint, `check`, `cached`, `reconfirm`, `write_manifest`) already goes
through `inventory`, so the fix lands in one spot. One docs paragraph names the
exclusion.

## Technical Context

Python 3.11+ stdlib runtime, pytest for tests. Reuse in `cli/wuwei/integrity.py`: the
existing prune list, `re` (already imported), `os.scandir`, and the existing error
mapping (`measure` turns `ValueError` into exit 1 `page: plugin integrity: ...`, `OSError`
into exit 2 unmeasured). Test helpers in `tests/test_integrity.py`: `core`, `plugin`,
`workspace_root`, `ssh`, the `fresh_plugin` fixture, the hook payload shape of
`pre_tool_use`, and the release build pattern of
`test_release_package_covers_every_shipped_file`. The PATH shim pattern (a `python3`
symlink to `sys.executable`) is in the `launcher` fixture of `tests/test_heartbeat.py`.
No new dependency, module, port, config key, state key or event kind.

## Constitution Check

Stdlib only. Exits stay 0/1/2: an unexpected entry is a finding (exit 1) in `measure`, an
unreadable `.in_use` is unmeasured (exit 2), and nothing becomes clean when unmeasured.
The exclusion is narrow and checked, so it is not a new hiding place (Principle VII). One
behaviour, one function: the prune rule lives only in `_prune`. Test first. Passes.

## Design

### 1. One prune helper (`cli/wuwei/integrity.py`)

Add next to `_name`:

```python
MARKERS = '.in_use'  # Claude Code's per-process markers (<pid> files) for its plugin cache cleanup


def _prune(plugin, directory, dirs):
    dirs[:] = sorted(d for d in dirs if d not in ('.git', '__pycache__'))
    markers = Path(directory) / MARKERS
    if Path(directory) != Path(plugin) or MARKERS not in dirs or markers.is_symlink():
        return
    for entry in os.scandir(markers):
        if not (re.fullmatch(r'[0-9]+', entry.name) and entry.is_file(follow_symlinks=False)):
            raise ValueError(f'not a Claude Code process marker: {_name(MARKERS + "/" + entry.name)}')
    dirs.remove(MARKERS)
```

- `re.fullmatch(r'[0-9]+', ...)`, not `str.isdigit`: `isdigit` accepts non-ASCII digits.
- `entry.is_file(follow_symlinks=False)` rejects symlinks, directories, fifos and sockets.
- `_name(...)` keeps the reason one printable line: a name with a control character
  raises `invalid inventory path` instead, which is also a finding.
- `os.scandir` without a `with` block is fine for a short loop, but the builder may use
  `with os.scandir(markers) as entries:` if the suite warns about unclosed iterators.
- A symlinked `.in_use` stays in `dirs`, so `inventory`'s existing loop raises
  `symlink in installed plugin: .in_use`. A nested `.in_use` is never at the root, so it
  is walked and measured as before.

### 2. Use it in both walks

- `inventory`, line 39: `dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__')]`
  becomes `_prune(plugin, directory, dirs)`. The following `for name in dirs + names`
  loop is unchanged.
- `fresh`, line 213: `dirs[:] = sorted(d for d in dirs if d not in ('.git', '__pycache__'))`
  becomes `_prune(PLUGIN, directory, dirs)`. `_prune` sorts, so walk order is unchanged.
  Its `ValueError` is caught by the existing `except` and returned as exit 2 with the
  reason text (spec Assumptions).

Nothing else in `integrity.py` changes. The fingerprint (`measure`, lines 101-107) hashes
`actual` from `inventory`, so it excludes markers by construction (FR-004), and `check`,
`cached`, `reconfirm` and `write_manifest` inherit that.

### 3. Docs (`docs/integrity.md`)

After "Git metadata and generated Python bytecode are not shipped or measured." add, in
plain words: Claude Code writes one marker file per running Claude process into
`.in_use/` at the install root, named by the process id, so its plugin cache cleanup
skips versions in use. These markers change whenever a process starts or exits, so they
are not measured and do not change the confirmed fingerprint. Anything else under that
`.in_use/` (another name, a directory, a symlink), a symlinked `.in_use`, or an `.in_use`
deeper in the plugin is still a finding. Keep every phrase `tests/test_docs.py` already
requires of this file (`clean commit`, `HEAD`).

## What must not change

- `measure`, `check`, `cached`, `reconfirm`, `initialize`, `workspace_check`, the guards
  in `cli/wuwei/guards/integrity.py`, and `scripts/build-release.py`.
- The symlink refusal, the `.pyc` skip, `EXCLUDED`, the checkout path, exit codes and
  every existing reason string.
- The PreToolUse gate never walks the plugin; hook latency is unchanged.
- `scripts/headless_e2e.py` and the release workflow.

## Test notes for the builder

- Markers are created after `write_manifest` and the faked signature, as Claude Code does
  after install. Compare fingerprints (`result.data`) with and without markers.
- For `fresh`, set the marker mtime later than `verdict.json` with `os.utime`, as
  `test_fresh_names_a_file_changed_after_the_verdict` does.
- The smoke (T008) must sign for real because the subprocess launcher cannot be
  monkeypatched: build the stage in-process with the faked signer (as
  `test_release_package_covers_every_shipped_file`), then replace
  `<stage>/keys/manifest-signing-key.pub` with a throwaway ed25519 public key, unlink
  `MANIFEST.sha256.sig`, call `api.write_manifest(stage)`, and sign with `ssh().sign`
  (the real adapter; take it from `registry.load` directly, not from the monkeypatched
  `api.signature_adapter`). Skip when `ssh-keygen` is absent, like
  `test_real_ssh_release_roundtrip_and_wrong_key`.
- Drive `<stage>/bin/wuwei` with a PATH whose first entry holds a `python3` symlink to
  `sys.executable`, `HOME` pointed at a temp directory, and `WUWEI_WORKSPACE` removed from
  the environment. Never write an absolute local path into a file in the repository.
