Verdict: PASS
Gate: security
Item: free-lines
PR: taoq-ai/wuwei
Head: e0ffc73afd68b66f2648b7d5829467ed96dc77f6
Confidence: high

## Findings
- [low] scripts/build-release.py:61 blocks: no. Moved unchanged, an existing gap: if the signature check in measure() is reversed so a wrong key always passes, tests/test_release.py still passes all 4 tests. No test builds with a signing key that differs from keys/manifest-signing-key.pub and expects a refusal. A follow-up test could build with a second throwaway key and expect "manifest signature does not match the release key". My probe shows the code at this head does refuse that case.
- [low] blocks: no. Existing and unchanged: build() calls shutil.copytree with symlinks=False, so a symlink in the source tree is copied as the file it points to, and the inventory's symlink refusal applies only to the staged copy. The release workflow builds from a fresh checkout, so this behaves the same as before the move.

## Probes
- git diff origin/main...e0ffc73: inventory, write_manifest, sign and measure match the deleted cli/wuwei/integrity.py line for line. Same sha256, same EXCLUDED set, same lstat symlink refusal, same namespace wuwei-manifest, same keys/manifest-signing-key.pub, same allowed_signers principal. Only two things differ: measure() no longer has a default folder, and its unsigned message is shorter.
- .github is not in the diff. release.yml:52 still runs `python3 -P scripts/build-release.py --key "$signing_key" --output release` with the same key written from the secret and then unset. The script no longer needs sys.path, so -P is still correct.
- measure() with no argument raises TypeError (missing 'plugin'), so there is no wrong default.
- git grep at the head finds no reference to integrity or MANIFEST under cli/wuwei. setup, doctor and upgrade do not depend on the deleted module.
- The only tarfile extraction is in tests/test_release.py:42, which uses filter='data'. The script only creates the archive (make_archive). CI runs Python 3.11, 3.12 and 3.13 on ubuntu-latest, and setup-python installs a recent 3.11 that has the filter.
- I ran setup.vendor() into a scratch directory and compared it with diff -r against the committed .claude/wuwei: rc 0. integrity.py is gone from both copies.
- With ssh-keygen from the builder's unpacked binary on PATH: tests/test_release.py 4 passed, full suite 466 passed (in a copy of the tree from git archive of the head).
- probe.py, known positive: a build with a matching throwaway ed25519 key gives wuwei.tar.gz and measure() returns []. Known negatives: wrong key gives "manifest signature does not match the release key"; a signature in another namespace is refused the same way; no signature gives "unsigned"; an added file gives "changed: extra"; a planted symlink gives "symlink in plugin: evil".
- Mutants (in a copy): symlink guard reversed, test_the_inventory_refuses_a_symlink fails. Changed-file comparison reversed, test_the_measure_names_a_file_changed_after_signing fails. Signature check reversed, no test fails (see the first note). The verify-side namespace mutant was not run because the replacement did not apply. The sign-side namespace is covered by the test's own ssh-keygen verify.
- Confidence is high because the moved code is byte-identical in behaviour, the workflow is untouched, and every refusal was confirmed with a known-negative probe.

## Residual risk
Release signing is now checked only by tests/test_release.py, which skips wherever ssh-keygen is absent. CI on ubuntu-latest has ssh-keygen, so CI still covers it.
