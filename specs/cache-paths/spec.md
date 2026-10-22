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
name. Every caller is covered without a change at the caller.

The acceptance scenarios, restated:

1. `.wuwei/cache` linked to another folder: a prune deletes no file in that folder.
2. A Stop payload whose `session_id` holds `../`: no `stop-` entry is written outside
   `.wuwei/cache`.
3. A cache entry linked to a file outside the cache reads as absent.

## Requirements

- FR-001: every cache read, write and prune goes through `ws._cached`.
- FR-002: no POSIX-only call is added (no `O_NOFOLLOW`, no `dir_fd`); `Path.resolve`,
  `Path.is_symlink` and `Path.is_file` work on Windows, macOS and Linux.
- FR-003: runtime grows by 12 lines at most.

## Assumptions

- A name that would leave the folder is refused, not rewritten: the Stop hook with such a
  `session_id` reminds each time instead of once. Overturned if a real harness sends ids with `/`.
- A linked `.wuwei` disables the cache (reads absent, writes skipped). Overturned if an owner
  links `.wuwei` on purpose.
- A planted link at an entry blocks that entry (read absent, never replaced). Fail closed.
- The check and the open are separate calls: a writer racing the check between them is out of
  scope; whoever can do that already writes the workspace.
