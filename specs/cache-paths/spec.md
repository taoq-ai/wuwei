# Feature Specification: a cache entry or name never reads, writes or deletes outside .wuwei/cache

**Feature branch**: `leone/cache-paths`
**Item**: cache-paths, tier standard, goal G-2
**Input**: security verdict `.wuwei/verdicts/free-lines-6/security-17a9553.md` on #1229 (2026-10-22),
pre-existing on main: `ws.cache_get` follows an entry linked outside the cache; cache names built
from payload fields (`stop-<session_id>` in hook.py, `notes-<session>` in guards.py) can hold `../`
unchecked; when `.wuwei/cache` is itself a link, `ws.cache_prune` deletes files in its target.

## The promise in my words

The three cache helpers in `cli/wuwei/ws.py` (`cache_get`, `cache_put`, `cache_prune`) built the
entry path as `.wuwei/cache/<name>.json` and used it as given. A name with a separator walked out
of the folder, a link at the entry was followed, and a linked cache folder (or a linked `.wuwei`)
sent every read, write and delete to the link's target.

After this change one helper, `ws._cached(root, name)`, gives the entry path only when:

1. the name stays one file name directly in the cache folder (no `/`, and on Windows no `\` or
   drive prefix: the path's parent must be the cache folder itself);
2. the cache folder resolves to `<root>/.wuwei/cache` and is not itself a link (a linked `.wuwei`,
   a linked `cache`, a link loop or a Windows junction all fail this);
3. the entry is not a link.

Otherwise it gives None: `cache_get` reads it as absent, `cache_put` writes nothing and still
returns the value, and `cache_prune` deletes only a regular file that is the entry for its own
name. `ws.clone` and `hook._confirm`, which used the cache path directly, go through the same
check (FR-001).

The acceptance scenarios, restated:

1. `.wuwei/cache` linked to another folder: a prune deletes no file in that folder.
2. A Stop payload whose `session_id` holds `../`: no `stop-` entry is written outside
   `.wuwei/cache`.
3. A cache entry linked to a file outside the cache reads as absent.

## Requirements

- FR-001: every cache read, write and prune goes through `ws._cached`: `cache_get`, `cache_put`,
  `cache_prune`, `ws.clone` (the file keeps its name `clone`, so existing ids and ledger files stay)
  and `hook._confirm`, which skips any globbed answer entry that is not `ws._cached(root, path.stem)`.
  `ws.clone` raises an OSError naming the link when the cache folder or its clone entry is a link,
  and replaces an id that is not a plain alphanumeric token, since the id names the ledger file.
  `git grep -n "'cache'" -- cli/` at the head lists every direct use of the cache path:
  - `guards.py:34` and `guards.py:41`: names in guard tables, no file access;
  - `hook.py:344`: the `_confirm` glob, each hit checked by `ws._cached` before it is read or deleted;
  - `replay.py:37`: removes the cache of a replay copy, never the live workspace;
  - `sync.py:17`: the name in the never-synced list, no file access;
  - `ws.py:219`, `ws.py:222`, `ws.py:244`: `_cached` itself and the `cache_prune` glob, each hit checked.
- FR-002: no POSIX-only call is added (no `O_NOFOLLOW`, no `dir_fd`); `Path.resolve`,
  `Path.is_symlink` and `Path.is_file` work on Windows, macOS and Linux.
- FR-003: runtime grows by 18 lines at most (12 in the first round).

## Assumptions

- A name that would leave the folder is refused, not rewritten: the Stop hook with such a
  `session_id` reminds each time instead of once. Overturned if a real harness sends ids with `/`.
- A linked `.wuwei` disables the cache (reads absent, writes skipped). Overturned if an owner
  links `.wuwei` on purpose.
- A planted link at an entry blocks that entry (read absent, never replaced). Fail closed.
- A linked cache folder or clone entry makes `ws.record` raise: a hook records nothing there,
  and a call naming a door is denied with the error, which names the link. Overturned if an
  owner needs a linked cache to keep working.
- The check and the open are separate calls: a writer racing the check between them is out of
  scope; whoever can do that already writes the workspace.
