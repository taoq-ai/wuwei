Verdict: PASS
Gate: goal
Item: 1068
PR: taoq-ai/wuwei
Head: ee252d7f974a2b80b927f5497e651ba85a3a3c4b
Confidence: high

## Findings
- [low] cli/wuwei/guards.py:244 blocks: no. Claude Code's default commit shape `git commit -m "$(cat <<'EOF' ... EOF\n)" && git push origin <branch>` is now refused as unreadable when the message has an odd number of `"` (for example `fix: the 3" pipe`). bash runs it fine. On main the guard returned [] and passed it. This is what the promise designs (it cannot be tokenized and it names git push), and the refusal gives the reason. But the hint ("close the quote, or pass a PR body by --body-file") does not tell a committer to use `git commit -F`. A message with an apostrophe, or an even number of `"`, still passes.
- [low] cli/wuwei/guards.py:244 blocks: no. If an unquoted heredoc body (`<<EOF`) contains backticks and an apostrophe, and the command also has gh pr create or git push, it is refused as unreadable, and the hint names --body-file even when --body-file is already in use. Quoting the delimiter (`<<'EOF'`), which is what planners write, is unaffected. Fails closed. Note for the hint text.
- [low] specs/1068-guards-multiline/spec.md blocks: no. The spec puts `cat <<EOF | sh` out of scope, which the plan's Outside list does not name. `cat <<'EOF' | sh\ngit push --force origin x\nEOF` passes on both main and the branch, as does `echo "git push --force" | sh`. This is a gap that already existed (piping into a shell), not the newline or quote defect the issue reports. Candidate follow-up item.

## Probes
- Read the item with `wuwei plan show 1068` and the issue with `gh api repos/taoq-ai/wuwei/issues/1068`. The builder's explain-back in specs/1068-guards-multiline/spec.md matches the promise and all 8 acceptance scenarios. No requirement is missing. The extra claims (backtick as a separator, the hook.py post_tool regex, the line-budget refactors in once/leak/_default/pre_tool) serve the promise or its 3,000-line budget.
- Incident replay, in a scratch copy at ee252d7 using the suite's FakeGh, with plan item I-1 at tier standard and no attested gates. Six shapes: `cd /home/user/wuwei && cat > body.md <<'EOF'` with a PR body containing apostrophes, `"`, backticks, $HOME and WUWEI-Item, then `EOF\ngh pr create --title ... --body-file body.md --base main`. Variants: /tmp/body.md with --repo/--head, `<< 'EOF'`, `<<"EOF"`, unquoted `<<EOF` with `it's`, and `gh pr create --body "$(cat <<'EOF' ... EOF\n)"`. All six were refused with "acme/app i-1-change opens as a PR once its gates pass at the branch head ...: gates missing at head aaaaaaa: quality, security".
- The same six shapes after attest(quality) and attest(security): all pass (None, or the pr-standard note). The door opens once the gates count.
- Baseline: the same probe file on origin/main 7f8a0d7. Five of the six incident shapes pass the create door there (the bug is reproduced). The `--body "$(cat ...)"` shape was already caught on main.
- Through the real hook entry, hook.handle(root, 'PreToolUse', ...), the incident command returns permissionDecision deny with the gates-missing reason.
- Everyday flows when no door applies, 14 shapes, all None. They cover: a heredoc PR body followed by `gh pr edit --body-file`; `gh pr comment --body-file - <<'EOF'`; a `python3 - <<'EOF'` script containing apostrophes and `subprocess.run(['gh','pr',...])`; multi-line `python3 -c "..."`; `python3 -I - <<'PY'`; `git add -A && git commit -m "$(cat <<'EOF' ... It's ... EOF\n)" && git push -u origin claude/...`; the same with `"quoted"` and backticks in the message; `git commit -F - <<'EOF'` followed by a push; multi-line git/gh read commands; `gh api .../comments -f body="It's fixed"`; for/if blocks containing a feature-branch push; a trailing `# it's pushed` comment.
- Edge probes (scratch script): `echo 'oops\ngh pr merge 5` is refused with "cannot read this command (No closing quotation) ...". A heredoc body followed by `git push origin main` is refused as a push to the default branch. A python heredoc that mentions git push passes. The odd-`"` commit message: passes alone, refused when followed by `&& git push` (see findings).
- Full suite at ee252d7: 285 passed. Runtime `cat cli/wuwei/*.py | wc -l` gives 3000 (main also gives 3000). The test_setup.py size test passes.
- Commit ee252d7 is authored by Leone <leone.lage@gmail.com>.
- Confidence is high because the reported shape is reproduced on main, refused on the branch with a usable reason, and opens once gates attest. The fake gh stands in for GitHub I/O. A shape outside these probes is what would lower it.

## Residual risk
The refusal of unreadable commands is broad (a raw-text regex). Rare valid shapes, such as an odd `"` inside a `"$(cat <<'EOF')"` commit message followed by a push, now fail closed, and the hint does not name the fix. Piping into a shell (`cat <<EOF | sh`) remains an open bypass that predates this item.
