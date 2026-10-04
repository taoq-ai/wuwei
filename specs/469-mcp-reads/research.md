# Research: recorded MCP tool names and the default-rule review (#469)

The builder copies these lists into `tests/test_outward.py` as `RECORDED`. They are the
public tool names of each server (spec A7). Server segments in the tests: `slack`,
`linear`, `github`. Each outcome below was checked with a dry run of plan Design 1 and 5
against the defaults (`pass` = read, `draft` = a built-in rule matches, `line` = a write no
rule matches, refused with the config line). No recorded name is `unknown`.

## Slack, noun-first server (korotovsky slack-mcp-server)

| tool | outcome |
|---|---|
| `conversations_history` | pass |
| `conversations_replies` | pass |
| `conversations_search_messages` | pass |
| `channels_list` | pass |
| `conversations_add_message` | draft (`add_message`, new) |

## Slack, reference server (modelcontextprotocol/servers, archived)

| tool | outcome |
|---|---|
| `slack_list_channels` | pass |
| `slack_get_channel_history` | pass |
| `slack_get_thread_replies` | pass |
| `slack_get_users` | pass |
| `slack_get_user_profile` | pass |
| `slack_post_message` | draft |
| `slack_reply_to_thread` | draft |
| `slack_add_reaction` | draft (`add_reaction`, new; main matched nothing) |

The claude.ai Slack connector names already in `tests/test_outward.py`
(`slack_search_public`, `slack_read_channel`, `slack_read_thread`,
`slack_list_user_channels`, `slack_send_message`, `slack_schedule_message`) keep their rows.

## Linear MCP server

Reads, all `pass`: `list_comments`, `list_cycles`, `get_document`, `list_documents`,
`get_issue`, `get_issue_git_branch_name`, `list_issues`, `list_issue_statuses`,
`get_issue_status`, `list_my_issues`, `list_issue_labels`, `list_projects`, `get_project`,
`list_project_labels`, `list_teams`, `get_team`, `list_users`, `get_user`,
`search_documentation`.

Writes: `create_comment`, `create_issue`, `update_issue` are `draft` (tracker);
`create_project`, `update_project`, `create_issue_label` are `line`.

Review: the default `(save|create|update)_(issue|comment)` stays. Widening it to projects
and labels would send them through the tracker policy, which drafts them, but no CLI port
can queue a project or label draft, so the seat is refused either way; the config line at
least names the owner's choice. The claude.ai connector's `save_issue` and `save_comment`
rows stay `draft`.

## GitHub MCP server (github/github-mcp-server, plus the archived reference server)

Reads, all `pass`: `get_me`, `get_issue`, `get_issue_comments`, `list_issues`,
`search_issues`, `get_pull_request`, `list_pull_requests`, `get_pull_request_files`,
`get_pull_request_status`, `get_pull_request_comments`, `get_pull_request_reviews`,
`get_pull_request_diff`, `get_file_contents`, `list_commits`, `get_commit`,
`list_branches`, `search_code`, `search_repositories`, `search_users`, `list_tags`,
`get_tag`, `list_notifications`, `get_notification_details`, `list_code_scanning_alerts`,
`get_code_scanning_alert`, `list_secret_scanning_alerts`, `get_secret_scanning_alert`,
`list_workflows`, `list_workflow_runs`, `get_workflow_run`, `get_job_logs`.

Writes `draft` (code_host): `add_issue_comment`,
`add_pull_request_review_comment_to_pending_review`.

Writes `line`: `create_issue`, `update_issue`, `create_pull_request`,
`update_pull_request`, `merge_pull_request`, `update_pull_request_branch`,
`create_pull_request_review`, `create_pending_pull_request_review`,
`submit_pending_pull_request_review`, `delete_pending_pull_request_review`,
`create_and_submit_pull_request_review`, `request_copilot_review`,
`assign_copilot_to_issue`, `create_branch`, `create_or_update_file`, `delete_file`,
`push_files`, `create_repository`, `fork_repository`, `dismiss_notification`,
`mark_all_notifications_read`, `manage_notification_subscription`,
`manage_repository_notification_subscription`, `run_workflow`, `rerun_workflow_run`,
`cancel_workflow_run`.

Review: the default `(add|create|update)_.*comment.*` stays; the other writes are not
outward text the approval tier can classify, and main refuses them too.

## Write verbs added beyond the issue's list

Each is needed by a recorded write or an existing test row; without it that name would be
`unknown` and pass under guarded, where main refuses it.

| verb | needed by |
|---|---|
| `save` | `mcp__unknown__save_issue` (existing row) |
| `notify` | `mcp__unknown__notify`, `mcp__x__notify` (existing rows) |
| `draft` | `mcp__gmail__draft_email` (existing row) |
| `respond` | `mcp__unknown__respond_to_event` (existing row) |
| `push` | `push_files` |
| `fork` | `fork_repository` |
| `request` | `request_copilot_review` |
| `dismiss` | `dismiss_notification` |
| `mark` | `mark_all_notifications_read` (it also holds the read word `read`) |
| `manage` | `manage_notification_subscription` |
| `run` | `run_workflow` (also covers `rerun_workflow_run` and `cancel_workflow_run`) |

`rerun` and `cancel` are not added: `run` already covers the recorded names.

## Names checked against the issue's write words

No recorded read holds a write word except through the leading-read test: none does in
these lists, but `get_message` (Gmail and similar) would, which is why main's leading test
runs first (spec A1). Plural nouns (`messages`, `comments`, `runs`) are not write words.
