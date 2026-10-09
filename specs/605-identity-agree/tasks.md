# Tasks: 605-identity-agree

- [X] T001 Test: `tests/test_commit_push.py`, an empty `repos.0.identity` makes the guard exit 2 with `commit_push.unset_identity`'s reason and fix for index 0.
- [X] T002 Implement: `unset_identity` and `configured_identity` in `cli/wuwei/guards/commit_push.py`; the guard and `git_hook.py` call it before the identity check.
- [X] T003 Test: `tests/test_doctor.py`, an empty identity fails doctor's row with the same reason; with a resolved git identity the fix names it, without one the fix equals the guard's.
- [X] T004 Implement: doctor's identity row calls `commit_push.unset_identity`.
- [X] T005 Test: `tests/test_invariants.py` I25, doctor's row and the guard agree on a set and an empty identity; design 9.2 row I25.
- [X] T006 Implement: `doctor.identity_row`, the row I25 and doctor share.
- [X] T007 Test (review F1): a malformed identity (`name = "<name>"`) fails the guard, the native hook, doctor's row and I25 with the reason `repos.0.identity is empty or malformed`.
- [X] T008 Implement: `unset_identity` uses `_identity`'s own check.
- [X] T009 Test (review F2): the guard's and the native hook's fix name the commit context's author, with no new `identity` call; I25 compares doctor and the guard word for word with a resolved git identity and restores the fake's `identity` result.
- [X] T010 Implement: `configured_identity(repo, root, actual.get('author'))` in the guard and `git_hook.py`.
