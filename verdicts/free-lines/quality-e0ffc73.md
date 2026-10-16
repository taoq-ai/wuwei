Verdict: PASS
Gate: quality
Item: free-lines
PR: taoq-ai/wuwei
Head: e0ffc73afd68b66f2648b7d5829467ed96dc77f6
Confidence: medium
Breaking: no

## Findings
- [medium] blocks: no. The signature-verify branch of measure is untested: with `problems = [] if True` the suite still passes, so a release signed with a key that does not match keys/manifest-signing-key.pub would pass build()'s self-check. The test only uses a matching key. The branch moved verbatim and the acceptance does not require it. A test that signs with a second throwaway key would kill it.
- [low] blocks: no. Mutants that survived and are equivalent or unreachable from the test input: the `.pyc` skip (the fixture strips pyc on copy), the `.in_use` directory prune (no such dir in the fixture), sign ignoring a nonzero exit (a missing .sig then fails measure as unsigned), and build() ignoring measure problems (nothing changes between sign and measure).
- [low] scripts/build-release.py:49 blocks: no. The move is not strictly word for word, as follows. The `PLUGIN` constant is gone. `measure` has no default argument. The unsigned message lost its "(a development checkout)" suffix, and the docstring says "staged" instead of "installed". All of these follow from the move and the one caller passes the stage.

## Probes
- Diffed the moved functions against origin/main:cli/wuwei/integrity.py. inventory, write_manifest and sign are byte-identical. measure differs only in the message and docstring above, and in the default argument.
- Ran the full suite in a scratch copy at e0ffc73 with ssh-keygen on PATH: 466 passed. Without ssh-keygen the two signing tests skip and the symlink and no-import tests pass.
- Counted runtime lines with `cat cli/wuwei/*.py | wc -l`: 2939.
- Ran setup.vendor() into an empty directory and ran diff -r against the tracked .claude/wuwei, .claude/agents and .claude/skills: identical, and integrity.py is absent in both. `git grep integrity` finds no runtime reference.
- `bin/wuwei agents check` printed "agents match the charters".
- Mutants run in a scratch copy, each against tests/test_release.py.
  - Killed: symlink guard off (test_the_inventory_refuses_a_symlink), the EXCLUDED filter off, the manifest dropping its last file, the wrong sign namespace, the changed-file check off (test_the_measure_names_a_file_changed_after_signing).
  - Survived: the cases in the findings above, plus the unsigned guard off. Without that guard a missing .sig raises FileNotFoundError at read_bytes anyway.
- Release workflow runs `python3 -P scripts/build-release.py`. The script no longer needs sys.path, since it imports nothing from wuwei. tests.yml runs pytest on a runner that has ssh-keygen. I did not run that CI.
- Simplicity: none. Dropping `PLUGIN` and the default argument already trimmed the move, and nothing else is a trust-boundary-free deletion.

## Residual risk
Signing and verification are covered only on the happy path, and only where ssh-keygen exists. The wrong-key case is unprotected by tests, but the logic is unchanged from before.
