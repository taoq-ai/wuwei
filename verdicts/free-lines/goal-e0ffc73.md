Verdict: PASS
Gate: goal
Item: free-lines
PR: taoq-ai/wuwei
Head: e0ffc73afd68b66f2648b7d5829467ed96dc77f6
Confidence: high

## Findings
- [low] scripts/build-release.py:55 blocks: no. The unsigned message drops "(a development checkout)" and measure loses its default argument; the spec records both, and build() never reaches that branch because it signs first. No runtime caller is left, so no client sees the change.
- [low] blocks: no. Where ssh-keygen is absent, tests/test_release.py skips the two signing tests (shown with PATH=/usr/bin:/bin: 2 passed, 2 skipped). CI runs on ubuntu-latest, which ships OpenSSH, so the build is exercised there. A skip report in the CI log would overturn this.

## Probes
- Read the promise and acceptance with `wuwei plan show free-lines`. The builder's explain-back in specs/free-lines/spec.md matches all four scenarios and the out-of-scope list. Read the diff with `git diff origin/main...e0ffc73`: the workflow, keys and manifest format are untouched, and integrity.py is deleted in both cli/ and .claude/wuwei/.
- Real entry point (`python3 -P scripts/build-release.py --key <throwaway ed25519> --output ...`, run from /, ssh-keygen from the scratch unpack): A = base script on the base tree, B = head script on the head tree, C = head script on the base tree. All three exit 0.
- A vs C (same tree and key, old vs new script): MANIFEST.sha256 is identical, MANIFEST.sha256.sig is byte-identical, and the unpacked archives are identical under `diff -r`. Behaviour is unchanged.
- A vs B: the manifests differ only by the removed line for cli/wuwei/integrity.py. B's signature verifies with `ssh-keygen -Y verify` ("Good wuwei-manifest signature"). The listed files equal the files in the archive (55), and `sha256sum -c` passes.
- `cat cli/wuwei/*.py | wc -l`: 2939 at the head, 2999 at the base, which meets acceptance 4. `diff -r cli/wuwei .claude/wuwei/cli/wuwei` shows no difference. `git grep integrity` at the head finds no code reference outside tests/test_release.py.
- Full suite in a scratch copy of the head with ssh-keygen on PATH: 466 passed. tests/test_release.py: 4 passed (verify, changed: README.md, symlink refusal, no runtime import).
- Confidence is high because the old and new scripts produce byte-identical outputs for the same tree and key.

## Residual risk
- The signing tests depend on the CI runner keeping OpenSSH; the release job shares that dependency.
