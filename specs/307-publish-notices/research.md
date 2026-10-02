# Research: licence and source of each credited item

Checked 2026-10-02 against each project's own repository or publisher, and re-checked by the builder the same day (T007): every row confirmed; MCP Apps corrected from Apache-2.0 alone to the MCP licence split its LICENSE file states. The builder re-checks
every row before writing NOTICE, and the PR body lists the "checked at" URL per row
(acceptance: "the PR body lists the URL checked for each licence").

## Projects

| Entry | Source URL (goes in NOTICE and README) | Licence and copyright line | Checked at | What WUWEI took |
|---|---|---|---|---|
| GitHub Spec Kit | https://github.com/github/spec-kit | MIT, `Copyright GitHub, Inc.` | https://github.com/github/spec-kit/blob/main/LICENSE | Vendored code: `.specify/` templates and scripts (spec-kit 1.0.13.dev0) and `.agents/skills/speckit-*`. Licence text copied to `.specify/LICENSE`. |
| autoharness | https://github.com/tigerless-labs/autoharness | MIT, `Copyright (c) 2026 ryan` | https://github.com/tigerless-labs/autoharness/blob/main/LICENSE | Ideas only: propose then promote, the ledger, the adherence lifecycle (design spec 6.8). |
| ralph-starter | https://github.com/rubenmarcus/ralph-starter | MIT, `Copyright (c) 2026 Ruben Marcus` | https://github.com/rubenmarcus/ralph-starter/blob/main/LICENSE | Idea only: the builder loop with backpressure and stuck detection (design spec 5.3). The project site https://ralphstarter.ai/ names `multivmlabs/ralph-starter`; GitHub serves `rubenmarcus/ralph-starter`. Re-checked 2026-10-02: `multivmlabs/ralph-starter` redirects (301) to `rubenmarcus/ralph-starter`. |
| humanizer | https://github.com/blader/humanizer | MIT, `Copyright (c) 2025 Siqi Chen` | https://github.com/blader/humanizer/blob/main/LICENSE (also the plugin's own `LICENSE` and `plugin.json`, version 3.1.0) | The ten-line writing checklist in `charters/_common-authoring.md` is condensed from it; the charters call the skill when installed. |
| Wikipedia: Signs of AI writing | https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing | Credit only (humanizer is based on it; WUWEI copies no text) | the page itself | Indirect source of the checklist. |
| Model Context Protocol | https://modelcontextprotocol.io | Apache-2.0 for new code, MIT for legacy contributions, CC-BY-4.0 for documentation; `Copyright (c) 2024-2025 Model Context Protocol a Series of LF Projects, LLC.` | https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/LICENSE | Protocol implemented by the board server (`cli/wuwei/commands/board.py`); no code copied. |
| MCP Apps | https://github.com/modelcontextprotocol/ext-apps | Same as MCP: Apache-2.0 for new code, MIT for legacy contributions, CC-BY-4.0 for documentation; `Copyright (c) 2024-2025 Model Context Protocol a Series of LF Projects, LLC.` | https://github.com/modelcontextprotocol/ext-apps/blob/main/LICENSE | The `ui://` resource convention the board serves (`ui://wuwei/board.html`); no code copied. |
| release-please | https://github.com/googleapis/release-please | Apache-2.0 | https://github.com/googleapis/release-please/blob/main/LICENSE | Used as a CI tool through `googleapis/release-please-action` (`.github/workflows/release.yml`). |
| ZIRAN | https://github.com/taoq-ai/ziran | Apache-2.0 | https://github.com/taoq-ai/ziran | Used as a CI tool for the role-grant audit (`ziran-audit` job, `agents/ziran-baseline.json`). |

## Concepts (credited by author and source, no licence)

| Entry | Source URL | Author | Where WUWEI uses it |
|---|---|---|---|
| WSJF | https://framework.scaledagile.com/wsjf | Donald Reinertsen, The Principles of Product Development Flow (2009), as popularised by SAFe | `wsjf` ranking, design spec 5.7 |
| RICE | https://www.intercom.com/blog/rice-simple-prioritization-for-product-managers/ | Sean McBride, Intercom | `rice` ranking, design spec 5.7 |
| One-way and two-way doors | https://s2.q4cdn.com/299287126/files/doc_financials/annual/2015-Letter-to-Shareholders.PDF | Jeff Bezos, Amazon 2015 letter to shareholders (Type 1 and Type 2 decisions) | Decision framework, design spec 5.8 and 5.3 |

## Decisions

- Spec-kit is the only vendored code, so it is the only licence text reproduced. Decision:
  `.specify/LICENSE` with the upstream text verbatim. Alternative rejected: a copy in each
  of the ten `.agents/skills/speckit-*` directories (ten identical files, same legal effect
  as the NOTICE pointer).
- NOTICE lists one Source URL per entry and no licence-file URLs, so the README check can
  require every NOTICE URL in the README without dragging licence links into the README.
  The licence-file URLs live here and in the PR body.
