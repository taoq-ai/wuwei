# Tasks: an owner setting allows admin-bypass merges (#1290)

- [x] T001 Write the failing tests: tests/test_ledger.py (allow read as a list of names, seven keys), tests/test_evidence.py (admin-merge drops the unnamed block, CI and owner review still hold), tests/test_guards.py (--admin meets the merge door only with admin-merge; `wuwei config allow admin-merge` in the seat corpus)
- [x] T002 Run them red: 5 failed (ValueError: unknown key allow)
- [x] T003 Add `allow` to ws.DEFAULTS and the config reader; gate the --admin deny in guards.gh_command and the unnamed gap in evidence.gaps on it; mirror to .claude/wuwei/
- [x] T004 Docs: constitution 3.6.0 seven keys, design, reference, philosophy, README, SECURITY, charters/_way.md, CLI help, upgrade message; agents build
- [x] T005 Run the touched test files green and the route corpus differential at main and head
