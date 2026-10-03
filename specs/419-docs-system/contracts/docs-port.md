# Contract: the `docs` port

Two operations, every adapter, keyword `root=None` last (the registry contract test checks the
signature): `read(ref, *, root=None)` and `write(draft, *, root=None)`. Each returns
`registry.Result(exit, data, reason)`: exit 0 with data, 1 a finding (markdown: no page), 2 could
not run. A reason never holds provider text or a credential (`_http.operation` already reduces
exceptions to their type or a `Failure` message).

## Shapes

- `read(ref)` data: `{"id": str, "title": str, "link": str, "updated": str}`.
- `draft`: `{"kind": "page"|"report"|"retro", "item": str, "title": str, "body": str (Markdown),
  "parent": str, "ref": str}`. `ref == ""` creates a page titled `title` under `parent` with
  `body`; otherwise `body` is appended to `ref` (the caller has already put a dated `##` heading
  first). `title` is ignored on append.
- `write(draft)` data: `{"id": str, "link": str}`.
- `notion.write`, `confluence.write` and `none.write` are wrapped by
  `registry.outward_operation('docs')` over `_http.operation(...)`, so a call returns
  `Result(1, None, '<APPROVAL_REQUIRED>; stored draft <id>; wuwei drafts approve <id>')` without
  any HTTP when the kind is not in `docs.auto`; `drafts.approve` calls `write.__wrapped__`.
  `markdown.write` is not wrapped.

## Notion (`adapters/docs/notion.py`)

Credential `NOTION_TOKEN`. Base `https://api.notion.com/v1`; headers `Authorization: Bearer
<token>`, `Notion-Version: 2022-06-28`, `Content-Type: application/json`. A page id is the last
32 hex digits of `ref` with dashes removed (a bare id or a `notion.so`/`notion.site` link);
anything else is `Failure('invalid Notion page')`.

| Call | HTTP | Data |
| --- | --- | --- |
| `read(ref)` | `GET /pages/<id>` | `id`, `url` as `link`, `last_edited_time` as `updated`, `title` = joined `plain_text` of the property whose `type` is `title` |
| `write`, create | `POST /pages` `{"parent": {"page_id": <parent id>}, "properties": {"title": {"title": [{"text": {"content": title}}]}}, "children": <blocks>}` | `id`, `url` as `link` |
| `write`, append | `PATCH /blocks/<id>/children` `{"children": <blocks>}` | `id` = ref id, `link` = `https://www.notion.so/<id without dashes>` |

An `{"object": "error"}` body, a missing `id`/`url`, or a non-2xx status is exit 2.

## Confluence (`adapters/docs/confluence.py`)

Credentials `CONFLUENCE_EMAIL` and `CONFLUENCE_API_TOKEN`; header `Authorization: Basic
base64(email:token)`. A `ref` or `parent` link `https://<site>.atlassian.net/wiki/.../pages/<n>/...`
gives the base `https://<site>.atlassian.net/wiki` and the id `<n>`; a bare numeric id takes the
base from `docs.space` (`workspace.load_config(workspace.find_workspace(root))`).

| Call | HTTP | Data |
| --- | --- | --- |
| `read(ref)` | `GET <base>/api/v2/pages/<id>` | `id`, `title`, `link` = base + `_links.webui`, `updated` = `version.createdAt` |
| `write`, create | `GET <base>/api/v2/pages/<parent>` (its `spaceId`), then `POST <base>/api/v2/pages` `{"spaceId", "status": "current", "title", "parentId", "body": {"representation": "storage", "value": <storage>}}` | `id`, `link` |
| `write`, append | `GET <base>/api/v2/pages/<id>?body-format=storage`, then `PUT <base>/api/v2/pages/<id>` `{"id", "status": "current", "title": <current title>, "body": {"representation": "storage", "value": <current> + <storage>}, "version": {"number": <current + 1>}}` | `id`, `link` |

Storage format: `html.escape`d text; `#`..`###` to `<h1>`..`<h3>`, consecutive `- ` lines to one
`<ul><li>..</li></ul>`, other non-empty lines to `<p>`.

## Markdown (`adapters/docs/markdown.py`)

No credential, no network. `ref` and `parent` are absolute paths inside the item's worktree,
built by `docs.py`. `read`: a missing file or a symlink is exit 1. `write`: target `ref` or
`<parent>/<item>.md`; a symlink target or one outside `parent` is exit 2; create writes
`# <title>\n\n<body>`, append writes the current text plus `\n<body>`; both through
`workspace.atomic_write`.

## None (`adapters/docs/none.py`)

`read` records `adapter: none` with reason `unmeasured`; `write` records it with reason `no
adapter configured`; both exit 2 with no data (the shared `test_none_call` covers both once
`CALLS` lists them).

## Recorded fixtures

`tests/fixtures/docs/recordings.json`: `{"notion": {"read": ..., "create": ..., "append": ...,
"error": ...}, "confluence": {"read": ..., "parent": ..., "create": ..., "current": ...,
"update": ..., "error": ...}}`, neutral ids and a `https://example.atlassian.net/wiki` base, no
real names. The contract test asserts the method, URL and JSON body of each recorded call and the
returned shape.
