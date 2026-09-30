# Tasks: Remote operation runbook

Each test task is written, run and seen failing for the stated reason before its
implementation task. Test command: `python -m pytest -q` from the repository root.

## Phase 1: The page is part of the site [US1]

- [X] T001 [US1] In tests/test_docs.py, `test_site_pages_and_links`: add `'remote'` to
  `pages`. Run `python -m pytest -q tests/test_docs.py -k site_pages_and_links`. Expected
  failure: `docs/site/remote.md` is not a file.
- [X] T002 [US1] Add `docs/site/remote.md` with the front matter, `# Remote operation`, the
  home link, the intro and the eight headings of FR-001 (bodies follow in Phase 2), and the
  `Remote operation` bullet in docs/site/index.md after "Daily path". T001 passes.

## Phase 2: The page matches the code [US1]

- [X] T003 [US1] In tests/test_docs.py, add `test_remote_runbook_matches_the_code` with the
  eleven checks in plan.md section 4. Run
  `python -m pytest -q tests/test_docs.py -k remote_runbook`. Expected failure:
  `(remote.html)` is not in daily.md (then, once that line exists, the first missing
  section content, such as `chat.postMessage` or the one-liner).
- [X] T004 [US1] In docs/site/daily.md, add the one-sentence link at the end of section 5's
  Remote Control paragraph (plan.md section 3).
- [X] T005 [US1] In docs/site/remote.md, write sections 1 to 4 (Remote Control, the Slack
  app, the identity pin, the second factor) as plan.md section 1 specifies, verifying each
  claim against the sources plan.md lists.
- [X] T006 [US1] In docs/site/remote.md, write sections 5 to 8 (listener install and kill
  switches, command exchanges with the code's literal replies, decisions on the phone,
  limits). Before writing each example reply, read the string in cli/wuwei/remote.py or
  cli/wuwei/control_plane.py and copy it. T003 passes.

## Phase 3: Verify

- [X] T007 Run the page's steps that need no Slack against a scratch workspace outside the
  repository: `bin/wuwei init <scratch>`, set `adapters.inbound = "slack"` and
  `adapters.chat = "slack"`, run `bin/wuwei config check` (the Slack lines read `missing`,
  exit 1) and `bin/wuwei listen install --dry-run` (prints the unit with the `listen`
  command and the `wuwei-listen-` label), and `bin/wuwei status --line` to confirm the
  status reply shape used in section 6. Change nothing on the host.
- [X] T008 Run `python -m pytest -q`; everything passes. Check every changed file for
  em-dashes, emojis, absolute local paths and real tokens or ids, and confirm
  `git status --short` shows only docs/site/remote.md, docs/site/index.md,
  docs/site/daily.md, tests/test_docs.py and specs/055-remote-docs/.
