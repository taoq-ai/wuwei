Verdict: PASS
Gate: arch
Item: free-lines
PR: taoq-ai/wuwei
Head: e0ffc73afd68b66f2648b7d5829467ed96dc77f6
Confidence: high
Breaking: no

## Findings
- [low] scripts/build-release.py:59 blocks: no. Reversing the signature check in measure (`[] if True else`) survives tests/test_release.py: no test signs with a key whose public half differs from keys/manifest-signing-key.pub. The code is moved verbatim and main had no such test either, so this is an existing gap. A test that swaps keys/ for a second throwaway key and expects 'manifest signature does not match the release key' would close it.
- [low] scripts/build-release.py:44 blocks: no. Reversing the sign() returncode check survives, but the mutant is equivalent in effect: with no .sig file, measure returns 'unsigned: ...' and build still raises, so no bad archive ships.
- [low] SECURITY.md:12 blocks: no. "the signed manifest or the integrity check" names an integrity check that has had no runtime home since #1024 (1.0). This change does not make it more stale. Worth a wording fix in a later docs item; the line-51 claim (release ships a signed MANIFEST.sha256) still holds.
- [low] blocks: no. .github/workflows/release.yml:42 still sets PYTHONPATH: cli. The script no longer reads it, so it is harmless and stays out of scope as the promise says (the workflow file is listed as Outside).

## Probes
- `git grep -n -i integrity <head>` across cli, .claude/wuwei, scripts, tests, docs, docs/site, charters, skills, agents, hooks, bin, .github, SECURITY.md and design.md: no remaining import of wuwei.integrity. The only hits are CHANGELOG history, "ledger integrity" wording in design.md:171 and metrics.md:18 (unrelated), SECURITY.md:12 and :51, and the new test.
- `git log -S integrity origin/main -- cli/wuwei/doctor.py cli/wuwei/cli.py docs README.md`: the doctor's manifest measure was removed in #1024. No CLI subcommand, doctor, upgrade or hook path verifies a manifest on install, and no doc tells a user to call wuwei.integrity, so the module was never a published contract. That is why Breaking: no.
- Contracts that stay the same: MANIFEST.sha256 format (two-space separator, sorted, same EXCLUDED set), the namespace 'wuwei-manifest', the key path, `--key/--output` flags, exit 2 with 'release unmeasured', and the workflow invocation `python3 -P scripts/build-release.py`.
- compare.sh: built a release from origin/main and from the head the way the workflow does (`PYTHONPATH=cli python3 -P`), using one throwaway ed25519 key and ssh-keygen 9.6p1 unpacked into scratch. Both exit 0. The manifest diff and the archive listing diff are exactly one line each: cli/wuwei/integrity.py. Tampering README.md after signing makes measure return ['changed: README.md'].
- tests/test_release.py with ssh-keygen on PATH: 4 passed. Without ssh-keygen (the cloud image): 2 passed, 2 skipped, as the spec states.
- Full suite at the head (`uv run --with pytest python -m pytest -q`): 464 passed, 2 skipped, vendored-drift test included. `cat cli/wuwei/*.py | wc -l` gives 2939.
- mutants.sh: symlink guard reversed, test_the_inventory_refuses_a_symlink fails. Changed-file guard reversed, test_the_measure_names_a_file_changed_after_signing fails. Signature check and sign returncode reversed: both survive (see findings).
- How this fails 1 to 3 probed: the -P invocation works with no cli import; the manifest is unchanged byte for byte apart from the dropped file; whether CI runs the signing tests is unmeasured here because the PR has not opened, and that rests on the recorded ubuntu-latest assumption.

## Residual risk
Whether CI actually runs the two signing tests or skips them is unmeasured until the PR's tests job reports. An older installed plugin is unaffected because no runtime path ever imported the module after 1.0.
