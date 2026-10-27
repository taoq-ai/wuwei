# Plan

Use stdlib Python and the existing timestamped report files. Add focused tests through hook.handle
for latest selection, historical body reuse, notified latest versions, and session isolation.
Change retention to compare only the latest retained version. Deliver pending versions newest first,
archive superseded files, and retain the existing notification matching and atomic rename.
Read pending names before archived names, sort both by timestamp, and let archived versions
suppress older pending files after a claim or a temporary archival failure.
Synchronize the vendored hook. Run focused hook/setup checks and route differentials against the
parent source fa46883c and original main 3feedf5c. Record the corpus hash and every moved route.

Constitution check: stdlib only, test first, isolated worktree, runtime growth at most nine lines.
No public API change, new store, command parser change, or trust-boundary change.
