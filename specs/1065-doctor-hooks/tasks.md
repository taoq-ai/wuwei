# Tasks: doctor hooks check (#1065)

- [x] T001 Write the failing test in tests/test_setup.py: another clone's row, attest and sent give warn; a refused row gives ok; a later init gives warn; a prompt row gives ok
- [x] T002 Run it red (fails at `assert hooks() == 'ok'` after the refused row)
- [x] T003 Add HOOK_ROWS and the since-init scan of this clone's ledger file to doctor in cli/wuwei/setup.py
- [x] T004 Read ws.config once in doctor; move the cloud hook entries into merge_settings
- [x] T005 Run the full suite green, runtime at 3,000 lines
