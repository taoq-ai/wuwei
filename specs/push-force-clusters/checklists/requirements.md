# Requirements checklist: push-force-clusters

- [x] Every acceptance scenario of item push-force-clusters maps to a test
- [x] `-4f`, `-f4`, `-6f`, `-qf6`, `-4vf` with the refspec `main` move a diverged main under real git, and guards.bash refuses each with the force text
- [x] `-4`, `-6`, `-q`, `-v`, `-u` alone keep main's verdict: the default-branch text on main, a pass on a feature branch
- [x] The same clusters on a feature branch are refused with the force text, before the remote and after the refspec
- [x] `-fo=x` and `-fo.x` (f before `-o`, whose value is the rest of the word) are refused; `-o fix`, `--follow-tags` and `--signed=if-asked` pass
- [x] The new pattern matches every word main's pattern matched (no refusal loosens): probe newly passed 0, no main route moves
- [x] The route corpus is read through main's and the head's guards, with its sha256 at both, and each moved row listed
- [x] The generated probe runs under real bash with a stub git and reports generated, ran and holes, at the head and at main
- [x] Mutants of the pattern, applied to both guards.py copies one at a time, each fail a behavioural test
- [x] Vendored copy matches; drift test passes
- [x] Runtime lines stated against the item's budget
- [x] No emojis, no em dashes
