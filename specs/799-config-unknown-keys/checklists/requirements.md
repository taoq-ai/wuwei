# Requirements Checklist: 799-config-unknown-keys

Purpose: check the requirements are complete, clear and testable before `implement`.

- [x] CHK001 Is the posture behaviour of an unknown key stated for every posture? [Completeness, FR-001]
- [x] CHK002 Is the kept `outbound.tiers` refusal named, with why it stays? [Clarity, FR-002, plan units table]
- [x] CHK003 Is the exact output line given for both `--upgrade` and `--dry-run`? [Clarity, FR-003]
- [x] CHK004 Is "parsed remainder equals the old config minus the removed keys" measurable? [Measurability, FR-004, T007]
- [x] CHK005 Is the failure path for an unsafe layout defined (exit code, no writes, message)? [Coverage, FR-004, US2 scenario 4]
- [x] CHK006 Is the newer-template case defined and tested? [Coverage, FR-006, T009]
- [x] CHK007 Are typos treated explicitly, with the reason? [Ambiguity, Assumption 1]
- [x] CHK008 Does every removed unit carry its (a) or (b) class? [Consistency, plan units table]
- [x] CHK009 Does every test change either follow a behaviour change or delete a test with its code, with none loosened? [Consistency, plan items 5 to 8]
- [x] CHK010 Are all files the change touches named, including docs and tests outside the obvious two? [Completeness, plan Files to edit, Verified fallout]
- [x] CHK011 No emojis, no em-dashes, no absolute local paths, no names in the artifacts. [Style]
