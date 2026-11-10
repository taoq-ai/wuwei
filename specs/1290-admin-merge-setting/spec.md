# Spec: an owner setting allows admin-bypass merges (#1290)

## In my words

A repository whose ruleset blocks every update to main needs an admin bypass for each merge. Today
the guard refuses `gh pr merge --admin` outright, and the evidence adds the gap "GitHub reports the
merge blocked for a reason WUWEI cannot name" to every such PR, so no merge goes through WUWEI there.
The owner patched both out of the installed plugin, and each plugin update undid the patch.

After this change the owner writes `allow = ["admin-merge"]` in `.wuwei/config.toml`, a file a
plugin update never touches. With it, `gh pr merge <n> --admin` meets the merge door like any other
merge, and the unnamed merge-block gap is not raised. Every gap WUWEI can name (CI, gates, owner
review, threads, ...) still holds the merge. Without the key both stay as today. `allow` is the
seventh config key and a plain list, so item 1291 can add `auto-approve` to it. A seat can neither
set the key (`wuwei config allow ...`) nor edit the file: the config door already refuses both.

## Acceptance scenarios

1. `allow = ["admin-merge"]`, a PR with no safety gap that GitHub reports blocked: `gh pr merge <n>
   --admin` passes the merge door and records `merge.checked`.
2. `allow = ["admin-merge"]`, a PR with a safety gap (CI failing, owner review): the merge door
   refuses and names the gap.
3. No `allow` key: `--admin` is refused as today; a blocked PR still shows the unnamed gap.
4. A seat running `wuwei config allow admin-merge`, or writing `.wuwei/config.toml` by Edit, Write or
   a redirect, is refused.

## How this fails

- A non-list `allow` (a bare string) read by `in` would match by substring: the config reader keeps
  only a list of strings.
- An owner's existing harness deny `Bash(gh pr merge --admin:*)` still refuses the flag-first
  spelling. With admin-merge, init stops adding it and doctor stops asking for it; neither removes it.
- A ruleset hold that is not a bypass the owner takes (a required review GitHub names) is no longer
  surfaced as a gap when `admin-merge` is on; GitHub's own merge then bypasses it with `--admin`.

## Assumptions

- The owner's request for an owner setting approves the seventh key (constitution 3.6.0). Overturn
  if a key should be retired instead.
- `allow` is omitted from config.toml when empty, as `models` is, so existing files do not change.
- The key name `allow` keeps constitution VII ("never a parallel allow list"): it narrows WUWEI's
  own deny and grants no harness access. `wuwei config allow X` replaces the list, so 1291's docs
  set both names.
- `allow` is workspace-wide: it applies to every repository in `repos`.
