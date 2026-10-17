# Requirements checklist: scratch-remotes

- [x] Every acceptance scenario of item scratch-remotes maps to a test or a recorded probe run
- [x] Acceptance 1 is proven through `guards.bash` at the head with real local repositories and no push; the live run waits for the planner after merge
- [x] Acceptance 2: the working repository's .git, a remote on a symlink to the working repository and origin on GitHub are refused
- [x] The generated probe reports 0 holes at the head, with truth from real bash and git's own url resolution
- [x] Every false refusal is a shape outside the one plain command, listed
- [x] Force pushes to a scratch remote stay refused
- [x] An unreadable git config keeps the door
- [x] Every older routes.json row keeps its verdict on head
- [x] Nothing that passed on main is refused at the head, so no breaking change
- [x] Vendored copy rewritten; drift test passes
- [x] Runtime within 3,000 lines; the overrun of the item's budget is named in the spec and the PR
- [x] No emojis, no em dashes
