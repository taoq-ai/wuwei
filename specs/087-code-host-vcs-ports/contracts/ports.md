# Port contracts

All functions return registry.Result(exit, data, reason) and have a trailing root=None. Failures print a diagnostic and return (2, None, reason). Successful calls return (0, plain data, ''). No operation has admin or approval arguments.

## code_host

References: owner/repo#number or a github.com pull request URL. Repositories: owner/repo. SHA: full hexadecimal commit ID. Draft: repo, base, head, title, body; optional draft boolean.

- pr(ref): {repo, number, url, author, state, draft, head, base, base_sha, branch, mergeable, merge_state, additions, deletions, changed_files, updated_at, node_id}.
- checks(ref, sha): list of {name, state, conclusion, sha, url}; both check runs and commit statuses at exactly sha.
- reviews(ref): list of {id, author, state, body, sha, submitted_at}.
- threads(ref): {comments: [{id, author, body, created_at, updated_at}], threads: [{id, resolved, outdated, comments: [{id, author, body, created_at}]}]}. PR conversation comments and inline threads are included; review bodies are in reviews.
- protection(repo, branch): {required_checks: [{name, app_id}], strict, approvals, dismiss_stale_reviews, require_code_owner_reviews, require_last_push_approval, enforce_admins, conversation_resolution}. Missing optional protection rules normalize to disabled; malformed rules fail closed.
- create_pr(draft): {number, url}.
- request_reviewers(ref, logins): {requested: [login]}.
- comment(ref, text, thread): {id, url}; thread=None posts an issue comment, otherwise thread is the numeric root inline comment ID to reply to.
- merge(ref, sha): {accepted: true, sha}; uses gh pr merge URL --squash --match-head-commit sha. This reports command acceptance; merge queues may finish later.
- revert_pr(ref): {number, url}, creating a revert PR through GraphQL.

## vcs

Repo and worktree paths accept path-like objects. Revisions and branch names cannot start with a dash. Each invocation uses git -C repo.

- identity(repo): {name, email, author: {name, email}, committer: {name, email}}. Config is read in the repository's config context, including normal inheritance; effective identities come from git var.
- head(repo), merge_base(repo, ref): {sha}.
- status(repo): list of {path, index, worktree, original_path}; original_path is null unless renamed/copied. Porcelain v1 NUL output preserves unusual filenames.
- diff_stat(repo, base, head): list of {path, additions, deletions}; binary counts are null. Disable rename detection so every NUL record has the same shape.
- log_since(repo, sha): list of {sha, author, email, committer, committer_email, committed_at, subject}; machine-readable NUL fields, newest first.
- worktree_add(repo, branch, path): {branch, path}; create a new branch and worktree from current HEAD.

## Test doubles

Recording fakes have these operation signatures and return copies of normalized cassette results. Every call is recorded with its positional inputs and context. An unconfigured operation returns exit 2 instead of fabricated clean data. The same cassettes drive PATH subprocess replay for adapter tests.
