# Changelog

## [0.18.1](https://github.com/taoq-ai/wuwei/compare/v0.18.0...v0.18.1) (2026-10-05)


### Bug Fixes

* **outward:** the owner's own identity is recorded without a card: outbound learn --owner writes outbound.owner.slack directly outside strict, so a self-DM is never a draft the owner has to approve ([#539](https://github.com/taoq-ai/wuwei/issues/539)) ([a3422b9](https://github.com/taoq-ai/wuwei/commit/a3422b9232d6dc83297c50b29a0b0b3aefe9535e)), closes [#537](https://github.com/taoq-ai/wuwei/issues/537)
* **outward:** the umbrella covers docs and tracker writes made through a connector; docs.auto and tracker.auto apply only to WUWEI's own adapter writes ([#536](https://github.com/taoq-ai/wuwei/issues/536)) ([34ce63b](https://github.com/taoq-ai/wuwei/commit/34ce63b59ad82418a05c5ff963bf280da7956bb1)), closes [#535](https://github.com/taoq-ai/wuwei/issues/535)

## [0.18.0](https://github.com/taoq-ai/wuwei/compare/v0.17.1...v0.18.0) (2026-10-05)


### Features

* **outward:** outbound.default_tier is the umbrella for outward messages, send out of the box: the broad commitment, disagreement and company rows drop out and only client, public and sensitive text ask; ask keeps the old rules ([#531](https://github.com/taoq-ai/wuwei/issues/531)) ([6d5a9ef](https://github.com/taoq-ai/wuwei/commit/6d5a9ef12d1de51e0dfd3ec9b347c3838148fc58)), closes [#527](https://github.com/taoq-ai/wuwei/issues/527)

## [0.17.1](https://github.com/taoq-ai/wuwei/compare/v0.17.0...v0.17.1) (2026-10-05)


### Bug Fixes

* **close:** a parked or carried item never blocks the close through a measurement (missing worktree, branch without commits), the retro launches once every item has a disposition, worktree records are repaired by doctor --fix, and close --why names what is missing per item ([#525](https://github.com/taoq-ai/wuwei/issues/525)) ([47be5bb](https://github.com/taoq-ai/wuwei/commit/47be5bb89a17c19b88810e8d955044b50bcfab94)), closes [#517](https://github.com/taoq-ai/wuwei/issues/517)
* **plan:** plan propose accepts every owner action the lead charter can name (message, merge, secret-set, deploy, release, publish) with a target shape per action, and an unknown owner action is a warning on the plan, never an exit 2 before the gate ([#519](https://github.com/taoq-ai/wuwei/issues/519)) ([1716e20](https://github.com/taoq-ai/wuwei/commit/1716e208b7441ed6a8c102185408787c95d82d02)), closes [#518](https://github.com/taoq-ai/wuwei/issues/518)

## [0.17.0](https://github.com/taoq-ai/wuwei/compare/v0.16.1...v0.17.0) (2026-10-04)


### Features

* **outward:** outward control is one owner-configured tier table (send, ask, block) matched by tool, person, channel, audience class and topic, with audience classes on people and channels learned on the card and client-facing defaults ([#512](https://github.com/taoq-ai/wuwei/issues/512)) ([7347b4d](https://github.com/taoq-ai/wuwei/commit/7347b4dfa3995af750e01b2e9a2ca759a7eaed82)), closes [#496](https://github.com/taoq-ai/wuwei/issues/496)


### Bug Fixes

* **outward:** a message to the owner's own DM or user id is never a draft: the owner's identity per channel is learned on the first card and the send passes under every posture ([#503](https://github.com/taoq-ai/wuwei/issues/503)) ([e6c65d6](https://github.com/taoq-ai/wuwei/commit/e6c65d695d92fe011baa05e63d6fcd22d97f59c9)), closes [#495](https://github.com/taoq-ai/wuwei/issues/495)
* **outward:** no default tier row blocks: public and client commitment or disagreement rows ask, and only an owner row refuses ([#515](https://github.com/taoq-ai/wuwei/issues/515)) ([0dc24be](https://github.com/taoq-ai/wuwei/commit/0dc24be86051ee705be314c05b5ec88a50e97446)), closes [#496](https://github.com/taoq-ai/wuwei/issues/496)
* **outward:** the outward lint reads text and destinations from any connector payload shape (nested rich text, Jira comment, Notion children, GitHub body) instead of failing closed on unknown fields ([#505](https://github.com/taoq-ai/wuwei/issues/505)) ([07fd33c](https://github.com/taoq-ai/wuwei/commit/07fd33ce247ea4955e732753ac16e57dbc000b6d)), closes [#501](https://github.com/taoq-ai/wuwei/issues/501)
* **publish:** an owner-only action asks the owner instead of blocking (keep owner-only, once, today, always) and records the answer as a decision; standing grants in config with revoke; the gate question pre-approves planned deploys; the reason names the action and target ([#506](https://github.com/taoq-ai/wuwei/issues/506)) ([42deb75](https://github.com/taoq-ai/wuwei/commit/42deb75d01c4a82e42df3c5d47018e1178a31d73)), closes [#478](https://github.com/taoq-ai/wuwei/issues/478)

## [0.16.1](https://github.com/taoq-ai/wuwei/compare/v0.16.0...v0.16.1) (2026-10-04)


### Bug Fixes

* **config:** config set writes list and table keys correctly in any config.toml layout (subtables after the section, inline tables, arrays of tables, missing section) and round-trips the rest of the file ([#499](https://github.com/taoq-ai/wuwei/issues/499)) ([a843ace](https://github.com/taoq-ai/wuwei/commit/a843ace5679739c5b2a560e6b7183520573f4f4d)), closes [#494](https://github.com/taoq-ai/wuwei/issues/494)
* **outward:** a draft names the rule that forced it and its id, the owner approves it on a card, and the approved draft goes out through the same MCP tool the seat called; drafts approve keeps the adapter path for configured adapters ([#500](https://github.com/taoq-ai/wuwei/issues/500)) ([edc10e7](https://github.com/taoq-ai/wuwei/commit/edc10e719dfa6ed0a6c7ac4b94dcb70a4c21f6d4)), closes [#493](https://github.com/taoq-ai/wuwei/issues/493)
* **outward:** any connector name resolves its channel (alias, pattern anywhere in the name, vocabulary), config lists keep their defaults, unknown connectors, work channels and people are learned from the connector and confirmed on one card, and no reason tells a seat to edit the guard's config ([#502](https://github.com/taoq-ai/wuwei/issues/502)) ([6168be8](https://github.com/taoq-ai/wuwei/commit/6168be874b8be0b8cd2269e075b9569a48e48d9e)), closes [#492](https://github.com/taoq-ai/wuwei/issues/492)
* **plan:** the owner's session is never blocked by work: seats and long commands run in the background, the planner stays available, and a test rejects blocking instructions in skills and charters ([#497](https://github.com/taoq-ai/wuwei/issues/497)) ([e207c8f](https://github.com/taoq-ai/wuwei/commit/e207c8feeef87bd04d317418bc7919cf5fa236dd)), closes [#477](https://github.com/taoq-ai/wuwei/issues/477)

## [0.16.0](https://github.com/taoq-ai/wuwei/compare/v0.15.0...v0.16.0) (2026-10-04)


### Features

* **decisions:** every option carries a title, rationale and consequence, the recommendation carries its reasoning, the Ask card shows all of it, and a configurable lens per decision class (SOLID, twelve-factor, YAGNI, ponytail for engineering) is applied and recorded ([#485](https://github.com/taoq-ai/wuwei/issues/485)) ([b400d60](https://github.com/taoq-ai/wuwei/commit/b400d607fce98b6c7923500c9e0a2a4168268f96)), closes [#475](https://github.com/taoq-ai/wuwei/issues/475)
* **dispatch:** the day starts in parallel: CAP from the calibrated host, seats per goal in the plan and the gate question, every dispatchable item launched up to CAP in one turn, and an item's gate sentinels run together ([#487](https://github.com/taoq-ai/wuwei/issues/487)) ([0e22fac](https://github.com/taoq-ai/wuwei/commit/0e22facfd4db5829fac9410bda20f1d467604e25)), closes [#474](https://github.com/taoq-ai/wuwei/issues/474)
* **session:** the plugin reference is exported once per version into the managed CLAUDE.md block, SessionStart injects only the day's steps, wuwei guide prints the reference, and a conformance test proves a fresh session reaches dispatch without a refusal ([#490](https://github.com/taoq-ai/wuwei/issues/490)) ([58becfc](https://github.com/taoq-ai/wuwei/commit/58becfca9e19916e55247a1cce0719c9483bb0b9)), closes [#476](https://github.com/taoq-ai/wuwei/issues/476)


### Bug Fixes

* **guards:** a quoted mention of an owner command is data, rank and propose take the lead's goals in either shape without sending the owner to a terminal, and the gate-citation lint on AskUserQuestion warns outside strict ([#482](https://github.com/taoq-ai/wuwei/issues/482)) ([7f85e79](https://github.com/taoq-ai/wuwei/commit/7f85e794f1089bf514b8f9b0b39988caf003f87d)), closes [#471](https://github.com/taoq-ai/wuwei/issues/471)
* **guards:** every read-only git subcommand is known, unknown git subcommands warn under observe and guarded, and a read with a variable or loop target never hits the records floor ([#491](https://github.com/taoq-ai/wuwei/issues/491)) ([fd19372](https://github.com/taoq-ai/wuwei/commit/fd19372ea343afa07be30a5ea9e7bc2f1719b04a)), closes [#470](https://github.com/taoq-ai/wuwei/issues/470)
* **outward:** read-only MCP tools are recognised by any word of their name, unknown tools warn under observe and guarded with the exact config line, and the built-in Slack write pattern covers add_message and friends ([#479](https://github.com/taoq-ai/wuwei/issues/479)) ([88359c8](https://github.com/taoq-ai/wuwei/commit/88359c86757d35158a562452c117605accf8ea59)), closes [#469](https://github.com/taoq-ai/wuwei/issues/469)
* **plan:** plan add admits an owner-named item with --goal during the day, the reason names the form, and the plan skill says how an item joins an approved plan ([#483](https://github.com/taoq-ai/wuwei/issues/483)) ([d4c3663](https://github.com/taoq-ai/wuwei/commit/d4c36633b2ac81861f6940140a190494207135ae)), closes [#481](https://github.com/taoq-ai/wuwei/issues/481)
* **seats:** a hand-back without last_assistant_message is read from the transcript and never leaves a seat running, traces redact only secrets, and a failed span records a gap event ([#488](https://github.com/taoq-ai/wuwei/issues/488)) ([e68db69](https://github.com/taoq-ai/wuwei/commit/e68db6922c1e7afa5f5d666fa8a98d42428bc830)), closes [#473](https://github.com/taoq-ai/wuwei/issues/473)
* **worktree:** worktree add chains WUWEI's git hooks with a repository's own core.hooksPath instead of refusing, and skips with a warning when it cannot chain ([#484](https://github.com/taoq-ai/wuwei/issues/484)) ([b98797e](https://github.com/taoq-ai/wuwei/commit/b98797e3eb3320d5ec53e2b66d6a90c41c5a402d)), closes [#472](https://github.com/taoq-ai/wuwei/issues/472)

## [0.15.0](https://github.com/taoq-ai/wuwei/compare/v0.14.0...v0.15.0) (2026-10-03)


### Features

* **docs:** documentation system: [docs] system and obligation per tier, docs page from the item's record, report and retro publishing, Notion by default with Confluence and repository Markdown adapters ([#467](https://github.com/taoq-ai/wuwei/issues/467)) ([163f0ee](https://github.com/taoq-ai/wuwei/commit/163f0eec37ec9c4a2b3f397b28dba2751109ecec)), closes [#419](https://github.com/taoq-ai/wuwei/issues/419)
* **memory:** memory tiers over time: raw days archived after a window, a rolling week and month digest that sessions load, promoted rules only in charters, and forgetting proposed by the retro with evidence ([#458](https://github.com/taoq-ai/wuwei/issues/458)) ([ae475ef](https://github.com/taoq-ai/wuwei/commit/ae475ef30ce8356a0697f84c7093c68e9f4ffb7c)), closes [#443](https://github.com/taoq-ai/wuwei/issues/443)
* **spec:** specification mode: [spec] engine and mode, hooks that enforce the engine's steps per item, trivial tiers skipped, setup and doctor detect the engine ([#462](https://github.com/taoq-ai/wuwei/issues/462)) ([ab4d0c6](https://github.com/taoq-ai/wuwei/commit/ab4d0c68016701a5fbb6a562e17283e97401606d)), closes [#412](https://github.com/taoq-ai/wuwei/issues/412)
* **telemetry:** signal set with a versioned vocabulary, weekly aggregation off the hook path, metrics on the board with proposals, and anonymous sharing the owner approves or turns off ([#466](https://github.com/taoq-ai/wuwei/issues/466)) ([56709f8](https://github.com/taoq-ai/wuwei/commit/56709f82568a32a77f1cfbcaf485db0651d26228)), closes [#422](https://github.com/taoq-ai/wuwei/issues/422)
* **tracker:** tracker hygiene: required tickets per item, mid-item bug and triage tickets, decisions, progress and verdicts as comments, Linear by default with Jira and GitHub Projects adapters ([#468](https://github.com/taoq-ai/wuwei/issues/468)) ([df55a85](https://github.com/taoq-ai/wuwei/commit/df55a857c1229fae8e4569963e1edfe29835416c)), closes [#417](https://github.com/taoq-ai/wuwei/issues/417)


### Bug Fixes

* **reasons:** the next-step test also collects `x or 'literal'` fallbacks, and the two branch-protection fallbacks get a next step ([#463](https://github.com/taoq-ai/wuwei/issues/463)) ([10f01ed](https://github.com/taoq-ai/wuwei/commit/10f01ed66a250b66d6e42198eddee079faefebae)), closes [#456](https://github.com/taoq-ai/wuwei/issues/456)

## [0.14.0](https://github.com/taoq-ai/wuwei/compare/v0.13.0...v0.14.0) (2026-10-03)


### Features

* **cli:** every refusal says what happened, why, and the one command to run, with real values and one reason per refusal ([#455](https://github.com/taoq-ai/wuwei/issues/455)) ([d911002](https://github.com/taoq-ai/wuwei/commit/d9110027b3d4770966d97ed8b1580754d2897ef0)), closes [#362](https://github.com/taoq-ai/wuwei/issues/362)
* **outward:** every external write goes through the humanizer pass by default (configurable): tracker comments, docs pages, DM, PR comments and review pings ([#434](https://github.com/taoq-ai/wuwei/issues/434)) ([23dff23](https://github.com/taoq-ai/wuwei/commit/23dff23829b2873c4b108d56958ef21b5740d254)), closes [#420](https://github.com/taoq-ai/wuwei/issues/420)
* **plan:** one approval at the morning gate, and no second interview on the first day ([#430](https://github.com/taoq-ai/wuwei/issues/430)) ([6f9d48b](https://github.com/taoq-ai/wuwei/commit/6f9d48bd9cff96950f4b08dc3e86093404ea71c5)), closes [#365](https://github.com/taoq-ai/wuwei/issues/365)
* **remote:** phone answers to two-way decisions are outcomes, and `wuwei setup slack` connects the DM in one command ([#447](https://github.com/taoq-ai/wuwei/issues/447)) ([6e9908c](https://github.com/taoq-ai/wuwei/commit/6e9908cd5ff7bf64b89b301c6d7d36e27efddbea)), closes [#364](https://github.com/taoq-ai/wuwei/issues/364)


### Bug Fixes

* **mcp:** adapters.scanner = none turns the MCP gate off with one nudge line instead of an unmeasured exit 2 from init, mcp check and the launch gate ([#448](https://github.com/taoq-ai/wuwei/issues/448)) ([f627198](https://github.com/taoq-ai/wuwei/commit/f627198a7a50ed1195674a7bc655f28c6b221ea6)), closes [#424](https://github.com/taoq-ai/wuwei/issues/424)
* **shepherd:** reviewers come from who touched the changed code with no configuration, the owner can override them, and a solo owner raises PRs with none ([#446](https://github.com/taoq-ai/wuwei/issues/446)) ([b57b457](https://github.com/taoq-ai/wuwei/commit/b57b4578a3c7d0c7d45887b8796de8bbd77054e4)), closes [#369](https://github.com/taoq-ai/wuwei/issues/369)


### Performance Improvements

* **hooks:** fourth round: a parsed-config cache keyed on the config text, security.load from the validated config, SessionStart guards run together and the day decoded once ([#426](https://github.com/taoq-ai/wuwei/issues/426)) ([54513f3](https://github.com/taoq-ai/wuwei/commit/54513f3337d7dffe221a3d27db87b66a2adf4d9c)), closes [#346](https://github.com/taoq-ai/wuwei/issues/346)

## [0.13.0](https://github.com/taoq-ai/wuwei/compare/v0.12.0...v0.13.0) (2026-10-03)


### Features

* **close:** close offers carry or park for each open item and records the decision itself ([#408](https://github.com/taoq-ai/wuwei/issues/408)) ([8083971](https://github.com/taoq-ai/wuwei/commit/8083971b820fa54b859e4e45dc858dde638df91b)), closes [#363](https://github.com/taoq-ai/wuwei/issues/363)
* **owner:** every owner question is an AskUserQuestion widget in the session, with its recording command printed next to it, and the DM when no widget exists ([#385](https://github.com/taoq-ai/wuwei/issues/385)) ([f98fedc](https://github.com/taoq-ai/wuwei/commit/f98fedc086dbad3612065821253511047bb84468)), closes [#359](https://github.com/taoq-ai/wuwei/issues/359)
* **owner:** owner confirmations are a yes or no at the terminal or a question in the session, never a typed digest, and a decision is one command ([#414](https://github.com/taoq-ai/wuwei/issues/414)) ([9434cc0](https://github.com/taoq-ai/wuwei/commit/9434cc0327a8125b188caa0cfcd96ed2dc376982)), closes [#354](https://github.com/taoq-ai/wuwei/issues/354)
* **plan:** the workflow writes its own records: lead-proposed goals run the first plan, the planner records them on gate approval, and no step asks the owner to edit a file by hand ([#391](https://github.com/taoq-ai/wuwei/issues/391)) ([701b1ce](https://github.com/taoq-ai/wuwei/commit/701b1ce295a0359a576210d37274c93a6299a37a)), closes [#357](https://github.com/taoq-ai/wuwei/issues/357)
* **security:** MCP findings warn by default under guarded, block only under strict, and the owner accepts a baseline in one command ([#373](https://github.com/taoq-ai/wuwei/issues/373)) ([bd89809](https://github.com/taoq-ai/wuwei/commit/bd89809948ba8cd8a104d3ce39840d16fbfa50e0)), closes [#351](https://github.com/taoq-ai/wuwei/issues/351)
* **session:** wuwei next names the next step from the day's state, SessionStart orients the session with it, and the plugin ships an agent-facing guide to the whole flow ([#382](https://github.com/taoq-ai/wuwei/issues/382)) ([05b4a8b](https://github.com/taoq-ai/wuwei/commit/05b4a8b374bafe0339dd64f7d8a709292c3a0aae)), closes [#358](https://github.com/taoq-ai/wuwei/issues/358)
* **setup:** setup fills the owner's code-host identity and bot authors, the interview chooses the adapters, and doctor warns on every empty setting that would block the PR flow ([#395](https://github.com/taoq-ai/wuwei/issues/395)) ([957b43c](https://github.com/taoq-ai/wuwei/commit/957b43c58647d6401b7b2fe8ebb3b41733f696be)), closes [#356](https://github.com/taoq-ai/wuwei/issues/356)


### Bug Fixes

* **brief:** item worktrees use their repository's default branch, and plan propose reads the scanner findings list ([#383](https://github.com/taoq-ai/wuwei/issues/383)) ([e1927cb](https://github.com/taoq-ai/wuwei/commit/e1927cbb928297dc5bbe378bfd51c3cbedbe844e)), closes [#361](https://github.com/taoq-ai/wuwei/issues/361)
* **cli:** readable nudges, grouped help and a short session-start block ([#400](https://github.com/taoq-ai/wuwei/issues/400)) ([8700ec2](https://github.com/taoq-ai/wuwei/commit/8700ec2ea1a9ffe0bd1dccd9212914dbb3980d81)), closes [#367](https://github.com/taoq-ai/wuwei/issues/367)
* **config:** keys from a newer template warn instead of refusing, and setup and doctor tell the owner to restart Claude Code after an upgrade so one plugin version runs ([#390](https://github.com/taoq-ai/wuwei/issues/390)) ([87269d7](https://github.com/taoq-ai/wuwei/commit/87269d7aae749759356f5662cf76805a9df10b5e)), closes [#353](https://github.com/taoq-ai/wuwei/issues/353)
* **guards:** a command the parser cannot read warns instead of falling to the publish floor, and read-only commands are never opaque ([#389](https://github.com/taoq-ai/wuwei/issues/389)) ([cc9ccbf](https://github.com/taoq-ai/wuwei/commit/cc9ccbf59be110ed3fc68129848ba88a48718bf6)), closes [#347](https://github.com/taoq-ai/wuwei/issues/347)
* **guards:** protect_state blocks writes to records and config, never reads of them ([#409](https://github.com/taoq-ai/wuwei/issues/409)) ([e0c32d1](https://github.com/taoq-ai/wuwei/commit/e0c32d1741b4a36214f56b8a17439c4184f7e758)), closes [#349](https://github.com/taoq-ai/wuwei/issues/349)
* **guards:** the plugin's own CLI is a known command: absolute path, recorded executable or wuwei on PATH, with read-only subcommands and --help passing in every posture ([#397](https://github.com/taoq-ai/wuwei/issues/397)) ([a3dbd7f](https://github.com/taoq-ai/wuwei/commit/a3dbd7f9263dc9638b2f938eedd71c55fc8ae427)), closes [#348](https://github.com/taoq-ai/wuwei/issues/348)
* **mcp:** mcp check writes one report per server per check, the decision summarises the findings, and mcp decide records the outcome without hand edits ([#393](https://github.com/taoq-ai/wuwei/issues/393)) ([89b577e](https://github.com/taoq-ai/wuwei/commit/89b577e47f7def01dfdad5e19f327f0dca0d1449)), closes [#350](https://github.com/taoq-ai/wuwei/issues/350)
* **setup:** --shadow means posture observe: setup, init and init --upgrade write security.posture = "observe" and retire guards.mode = "shadow" ([#394](https://github.com/taoq-ai/wuwei/issues/394)) ([685470e](https://github.com/taoq-ai/wuwei/commit/685470e3bf9bdbb0f2004114e1ae12ab8ab0f9ce)), closes [#355](https://github.com/taoq-ai/wuwei/issues/355)
* **setup:** the first day works on defaults: default branch from git, scanner off unless asked, tests measured once, solo owner asked, one ready line ([#406](https://github.com/taoq-ai/wuwei/issues/406)) ([b2a4557](https://github.com/taoq-ai/wuwei/commit/b2a4557f125629082ac0049578cdb1cbcbca5f29)), closes [#360](https://github.com/taoq-ai/wuwei/issues/360)
* **traces:** tool-sequence decisions apply to item seats only, once per session per day, and never to the planner or lead session ([#368](https://github.com/taoq-ai/wuwei/issues/368)) ([92077ef](https://github.com/taoq-ai/wuwei/commit/92077efd78ec38d26777be54881befaa968912da)), closes [#352](https://github.com/taoq-ai/wuwei/issues/352)


### Performance Improvements

* **hooks:** bring the hook, status line and heartbeat under their latency budgets on the CI runner without touching the budgets ([#396](https://github.com/taoq-ai/wuwei/issues/396)) ([e19aa66](https://github.com/taoq-ai/wuwei/commit/e19aa669cae43372f2ea5c542603874a5215ec17)), closes [#346](https://github.com/taoq-ai/wuwei/issues/346)
* **hooks:** third round: python3 -I -P -S, hooks and the status line exit without interpreter teardown, no copy import, prefix-tree scan ([#405](https://github.com/taoq-ai/wuwei/issues/405)) ([0c528f6](https://github.com/taoq-ai/wuwei/commit/0c528f6245f7ad45fb2faa47664f2d80de3a8288))

## [0.12.0](https://github.com/taoq-ai/wuwei/compare/v0.11.0...v0.12.0) (2026-10-03)


### Features

* **cli:** wuwei doctor: find every problem in the install, host, workspace, gates, day and guards, and fix the deterministic ones in one confirmed batch ([#342](https://github.com/taoq-ai/wuwei/issues/342)) ([5d4da83](https://github.com/taoq-ai/wuwei/commit/5d4da83026ea73ab5192efe9ea3b33f002643127)), closes [#339](https://github.com/taoq-ai/wuwei/issues/339)
* **security:** posture profiles: what warns and what blocks is configurable by where the plugin runs and for what purpose ([#345](https://github.com/taoq-ai/wuwei/issues/345)) ([9568967](https://github.com/taoq-ai/wuwei/commit/956896737977275d8dab17b49310c69650768ea8))
* **setup:** wuwei setup: discover the repositories and the host, write the configuration, calibrate and interview, promote once, and check, in one command ([#343](https://github.com/taoq-ai/wuwei/issues/343)) ([39d9961](https://github.com/taoq-ai/wuwei/commit/39d99613801e141292c02ebc1c56a1c75faa2bf4)), closes [#327](https://github.com/taoq-ai/wuwei/issues/327)


### Bug Fixes

* **calibrate:** fill an explicit empty fast_checks, and propose only genuinely fast checks ([#333](https://github.com/taoq-ai/wuwei/issues/333)) ([aa68937](https://github.com/taoq-ai/wuwei/commit/aa68937610a38bd062af669050ffc771c03ab645)), closes [#328](https://github.com/taoq-ai/wuwei/issues/328)
* **code_host:** branch protection read falls back to rulesets on a classic 404 and reports each source ([#334](https://github.com/taoq-ai/wuwei/issues/334)) ([e5e2070](https://github.com/taoq-ai/wuwei/commit/e5e2070d27fd92a2c59958bb745c4b13869f9dcc)), closes [#329](https://github.com/taoq-ai/wuwei/issues/329)
* **config:** a broken config.toml can be read and fixed from the session, the template cannot produce the most likely TOML error, and config check names it ([#335](https://github.com/taoq-ai/wuwei/issues/335)) ([c3681bb](https://github.com/taoq-ai/wuwei/commit/c3681bb3efc9a7d3a5f1e2cd43cea6d119872310)), closes [#326](https://github.com/taoq-ai/wuwei/issues/326)
* **guards:** outside a WUWEI workspace every hook does nothing, including when a command cannot be parsed ([#341](https://github.com/taoq-ai/wuwei/issues/341)) ([a90cde8](https://github.com/taoq-ai/wuwei/commit/a90cde850967af3b85578cd766be4c98155e038b)), closes [#323](https://github.com/taoq-ai/wuwei/issues/323)
* **guards:** read-only shell forms are not refused for being uninspectable, and shadow mode records them ([#338](https://github.com/taoq-ai/wuwei/issues/338)) ([22771ed](https://github.com/taoq-ai/wuwei/commit/22771ed1b0213cb3661cc5d1080513a75828a506)), closes [#330](https://github.com/taoq-ai/wuwei/issues/330)
* **integrity:** Claude Code's .in_use process markers in the plugin cache are not a tamper finding ([#332](https://github.com/taoq-ai/wuwei/issues/332)) ([e634ce1](https://github.com/taoq-ai/wuwei/commit/e634ce1c7e6abc56d52369fff9de2bbcb9359a41)), closes [#324](https://github.com/taoq-ai/wuwei/issues/324)
* **mcp:** the registry gate warns by default, scans only servers that attach, one server at a time, and never launches unpinned third-party code ([#336](https://github.com/taoq-ai/wuwei/issues/336)) ([4a384c5](https://github.com/taoq-ai/wuwei/commit/4a384c5aec226905c69bb5e17d6f3cf69f776f8c)), closes [#325](https://github.com/taoq-ai/wuwei/issues/325)

## [0.11.0](https://github.com/taoq-ai/wuwei/compare/v0.10.0...v0.11.0) (2026-10-02)


### Features

* **calibrate:** shareable calibration profiles: export a promoted calibration and interview, import as a proposal ([#322](https://github.com/taoq-ai/wuwei/issues/322)) ([7a3a081](https://github.com/taoq-ai/wuwei/commit/7a3a0817305d8cadaba9b8ccc9154572ddb98687)), closes [#313](https://github.com/taoq-ai/wuwei/issues/313)
* **cli:** wuwei why: reconstruct from events why an item, decision or refusal happened ([#321](https://github.com/taoq-ai/wuwei/issues/321)) ([62ca7db](https://github.com/taoq-ai/wuwei/commit/62ca7db7d6e64db1a0133fdb5061328e2d9d7fde)), closes [#312](https://github.com/taoq-ai/wuwei/issues/312)
* **gates:** a second-opinion gate on a different model for STANDARD and FULL items ([#320](https://github.com/taoq-ai/wuwei/issues/320)) ([d6385b2](https://github.com/taoq-ai/wuwei/commit/d6385b2d72814072fe3930a5ee343d52176b3435)), closes [#311](https://github.com/taoq-ai/wuwei/issues/311)
* **guards:** shadow mode: hooks record what they would refuse, for a first week on a project ([#317](https://github.com/taoq-ai/wuwei/issues/317)) ([6e55d81](https://github.com/taoq-ai/wuwei/commit/6e55d813e6985c222d523fd02d237b6a52960fc7)), closes [#308](https://github.com/taoq-ai/wuwei/issues/308)

## [0.10.0](https://github.com/taoq-ai/wuwei/compare/v0.9.0...v0.10.0) (2026-10-01)


### Features

* **listener:** GitHub events reach the planner and the owner without the owner relaying them: faster PR polling, precise wakes, headless shepherd on change, DM nudges ([#299](https://github.com/taoq-ai/wuwei/issues/299)) ([56e9107](https://github.com/taoq-ai/wuwei/commit/56e9107368c34c430804140daa91b78b29dfb05c)), closes [#297](https://github.com/taoq-ai/wuwei/issues/297)
* **owner:** verbosity levels for everything the owner reads, and humanizer-checked text from seats and the CLI ([#305](https://github.com/taoq-ai/wuwei/issues/305)) ([cb459ce](https://github.com/taoq-ai/wuwei/commit/cb459ce7a4c59f5e1a7d415605f14ed526390c23)), closes [#303](https://github.com/taoq-ai/wuwei/issues/303)
* **team:** mandate block in briefs, assume-and-record, time-boxed external waits, ask metrics, and a negotiation-loop nudge per work item ([#306](https://github.com/taoq-ai/wuwei/issues/306)) ([671f32a](https://github.com/taoq-ai/wuwei/commit/671f32a6202ec5c0e6534968711d017dd8d9643b)), closes [#302](https://github.com/taoq-ai/wuwei/issues/302)

## [0.9.0](https://github.com/taoq-ai/wuwei/compare/v0.8.0...v0.9.0) (2026-10-01)


### Features

* **calibrate:** an owner interview that turns personal preferences into configuration and charter overrides ([#292](https://github.com/taoq-ai/wuwei/issues/292)) ([7a23b2d](https://github.com/taoq-ai/wuwei/commit/7a23b2d7b9425ceb59f40dd188ab07b899e27bac)), closes [#279](https://github.com/taoq-ai/wuwei/issues/279)
* **calibrate:** profile the project and host and propose the workspace configuration ([#285](https://github.com/taoq-ai/wuwei/issues/285)) ([2a63396](https://github.com/taoq-ai/wuwei/commit/2a6339628d23cdbaed98501a9583a6e74aa9f698)), closes [#278](https://github.com/taoq-ai/wuwei/issues/278)
* **cockpit:** the day board as an inline widget in the Claude Code conversation through a plugin MCP server ([#290](https://github.com/taoq-ai/wuwei/issues/290)) ([8084fe9](https://github.com/taoq-ai/wuwei/commit/8084fe99c7c390382cadd784c4856ded1db288e3)), closes [#281](https://github.com/taoq-ai/wuwei/issues/281)
* **gates:** risk-tiered gates computed from the diff, with per-repository floors and escaped-defect measurement ([#284](https://github.com/taoq-ai/wuwei/issues/284)) ([e4b3da0](https://github.com/taoq-ai/wuwei/commit/e4b3da051495b8dfae3509aa5647042c487e0fd9)), closes [#280](https://github.com/taoq-ai/wuwei/issues/280)
* **metrics:** quality by hour and by session age, and planned planner-session rotation ([#293](https://github.com/taoq-ai/wuwei/issues/293)) ([89a7f65](https://github.com/taoq-ai/wuwei/commit/89a7f65037058846cd110da8cdecc9c84c15130e)), closes [#288](https://github.com/taoq-ai/wuwei/issues/288)
* **ops:** heartbeat: the watch proves the system is alive and behaving, not only running ([#295](https://github.com/taoq-ai/wuwei/issues/295)) ([ddc9495](https://github.com/taoq-ai/wuwei/commit/ddc94958af661ba18f0bb4ad49d176afb5f92faa)), closes [#287](https://github.com/taoq-ai/wuwei/issues/287)


### Bug Fixes

* **mcp:** the registry gate measures servers declared inline in a plugin's plugin.json, not only .mcp.json files ([#296](https://github.com/taoq-ai/wuwei/issues/296)) ([eec27a6](https://github.com/taoq-ai/wuwei/commit/eec27a60704ea6811ce3b7da094a9a16b9cd6bca)), closes [#291](https://github.com/taoq-ai/wuwei/issues/291)

## [0.8.0](https://github.com/taoq-ai/wuwei/compare/v0.7.0...v0.8.0) (2026-09-30)


### Features

* **adapters:** Slack inbound by polling mentions and DMs ([#268](https://github.com/taoq-ai/wuwei/issues/268)) ([e8800e5](https://github.com/taoq-ai/wuwei/commit/e8800e55128f882480db810bbfa04394da3efb79)), closes [#50](https://github.com/taoq-ai/wuwei/issues/50)
* **control-plane:** command vocabulary and session-per-thread over headless Claude Code ([#269](https://github.com/taoq-ai/wuwei/issues/269)) ([f614b5b](https://github.com/taoq-ai/wuwei/commit/f614b5bf2c951a1ec74b1b9696e40095a220958f)), closes [#65](https://github.com/taoq-ai/wuwei/issues/65)
* **guards:** remote-command guards (pinned safety number, second factor, stop all) ([#270](https://github.com/taoq-ai/wuwei/issues/270)) ([5ca6e51](https://github.com/taoq-ai/wuwei/commit/5ca6e51d05b6c3425ac19b32ed0feb047aa0d6ad)), closes [#66](https://github.com/taoq-ai/wuwei/issues/66)
* **listener:** `wuwei listen` process, inbox and service templates ([#266](https://github.com/taoq-ai/wuwei/issues/266)) ([493716a](https://github.com/taoq-ai/wuwei/commit/493716ac697d65f2908ee0a9176a7198b91e288b)), closes [#49](https://github.com/taoq-ai/wuwei/issues/49)


### Bug Fixes

* **remote:** decisions and health are visible on both ends ([#275](https://github.com/taoq-ai/wuwei/issues/275)) ([80f3573](https://github.com/taoq-ai/wuwei/commit/80f35739521141b9e41a639acaa19b60477701a5)), closes [#273](https://github.com/taoq-ai/wuwei/issues/273)
* **remote:** phone answers as one status segment, an ack for a refused-sender page, and the section 3 quote ([#277](https://github.com/taoq-ai/wuwei/issues/277)) ([61e6704](https://github.com/taoq-ai/wuwei/commit/61e6704dd2143d9a84775c02042d82f606a03eac)), closes [#276](https://github.com/taoq-ai/wuwei/issues/276)
* **remote:** the DM path works from the runbook alone ([#274](https://github.com/taoq-ai/wuwei/issues/274)) ([58f4889](https://github.com/taoq-ai/wuwei/commit/58f488973d44d187b853618320b35c5cbded9db3)), closes [#272](https://github.com/taoq-ai/wuwei/issues/272)

## [0.7.0](https://github.com/taoq-ai/wuwei/compare/v0.6.1...v0.7.0) (2026-09-30)


### Features

* **adapters:** inbound adapter interface and redactor adapter ([#263](https://github.com/taoq-ai/wuwei/issues/263)) ([ce6c7cf](https://github.com/taoq-ai/wuwei/commit/ce6c7cf8e1b1bcbc854c4ce14e5f0921fa2a5f46)), closes [#48](https://github.com/taoq-ai/wuwei/issues/48)
* **config:** config check verifies the host protections and seat credential layout that spec 4.5 and 9.1 now rely on ([#254](https://github.com/taoq-ai/wuwei/issues/254)) ([4b765ae](https://github.com/taoq-ai/wuwei/commit/4b765ae554eb4bf5fa57a2e69f10f0dd8a80db8f)), closes [#243](https://github.com/taoq-ai/wuwei/issues/243)
* **control-plane:** control-plane interface with Remote Control and push as default ([#264](https://github.com/taoq-ai/wuwei/issues/264)) ([16ab360](https://github.com/taoq-ai/wuwei/commit/16ab36071a80af72f0eaf831fad132c271672fe1)), closes [#57](https://github.com/taoq-ai/wuwei/issues/57)
* **team:** session registry: several Claude Code sessions in one workspace, with one planner ([#265](https://github.com/taoq-ai/wuwei/issues/265)) ([0fbe37e](https://github.com/taoq-ai/wuwei/commit/0fbe37e3f28daec989351bb18087eb5b04f9a5d8)), closes [#260](https://github.com/taoq-ai/wuwei/issues/260)


### Bug Fixes

* **cli:** operator records and owner-action consistency after the fourth dry run ([#256](https://github.com/taoq-ai/wuwei/issues/256)) ([3804c2b](https://github.com/taoq-ai/wuwei/commit/3804c2b7c7e417a6f30049ce48026bd9cb23ac58)), closes [#247](https://github.com/taoq-ai/wuwei/issues/247)
* **release:** the asset ships the operator docs it links to ([#257](https://github.com/taoq-ai/wuwei/issues/257)) ([6806cbb](https://github.com/taoq-ai/wuwei/commit/6806cbbe797242ef26daa987ffd82162b18e2cc8)), closes [#245](https://github.com/taoq-ai/wuwei/issues/245)
* **team:** seats can commit in a WUWEI worktree without setting git identity by hand ([#253](https://github.com/taoq-ai/wuwei/issues/253)) ([190ad8c](https://github.com/taoq-ai/wuwei/commit/190ad8c4acafaef142ed3a8df3a8730739a3766d)), closes [#246](https://github.com/taoq-ai/wuwei/issues/246)
* **team:** the daily path runs without operator repairs and is documented as one path ([#249](https://github.com/taoq-ai/wuwei/issues/249)) ([527d384](https://github.com/taoq-ai/wuwei/commit/527d384c587f3696ac3a01cdf96a661bff4115f4)), closes [#238](https://github.com/taoq-ai/wuwei/issues/238)


### Performance Improvements

* **hooks:** import only the guards an event needs, after profiling on the owner's hardware ([#244](https://github.com/taoq-ai/wuwei/issues/244)) ([dccbe61](https://github.com/taoq-ai/wuwei/commit/dccbe61a11e6cb76b365eb9f4df0500b9dab8f89)), closes [#240](https://github.com/taoq-ai/wuwei/issues/240)

## [0.6.1](https://github.com/taoq-ai/wuwei/compare/v0.6.0...v0.6.1) (2026-09-30)


### Bug Fixes

* **cli:** the morning before the first plan, owner actions on a terminal, and operator records ([#233](https://github.com/taoq-ai/wuwei/issues/233)) ([45775cb](https://github.com/taoq-ai/wuwei/commit/45775cb3ea6500c911497320fc8c75876387efc8)), closes [#227](https://github.com/taoq-ai/wuwei/issues/227)
* **guards:** indirect owner-action forms share one rule with the direct ones ([#235](https://github.com/taoq-ai/wuwei/issues/235)) ([7c2bb20](https://github.com/taoq-ai/wuwei/commit/7c2bb20db5f4736e1f4d24f06aecde0b5734d7e1)), closes [#222](https://github.com/taoq-ai/wuwei/issues/222)
* **guards:** ordinary seat command forms pass the commit, deploy and PR guards ([#234](https://github.com/taoq-ai/wuwei/issues/234)) ([c42df62](https://github.com/taoq-ai/wuwei/commit/c42df6216770d835910984d9847d54585aa67238)), closes [#226](https://github.com/taoq-ai/wuwei/issues/226)
* **security:** a workspace is usable right after init ([#229](https://github.com/taoq-ai/wuwei/issues/229)) ([81ca75b](https://github.com/taoq-ai/wuwei/commit/81ca75b13ebd21905464b20349eb680507ac525d)), closes [#228](https://github.com/taoq-ai/wuwei/issues/228)
* **team:** the loop's remaining joints: continue, gate role names, phases after raise and merge, decisions from pr act ([#241](https://github.com/taoq-ai/wuwei/issues/241)) ([e9e7fd9](https://github.com/taoq-ai/wuwei/commit/e9e7fd9762b1dc6e8b01522c00cf61da2a702862)), closes [#225](https://github.com/taoq-ai/wuwei/issues/225)

## [0.6.0](https://github.com/taoq-ai/wuwei/compare/v0.5.0...v0.6.0) (2026-09-30)


### Features

* **team:** worktree command, watch install safety and operator docs ([#216](https://github.com/taoq-ai/wuwei/issues/216)) ([01959e1](https://github.com/taoq-ai/wuwei/commit/01959e1b8a6408e60265f5ed2483af65e1c28d25)), closes [#210](https://github.com/taoq-ai/wuwei/issues/210)


### Bug Fixes

* **core:** hook latency budget and recovery from a corrupt state file ([#221](https://github.com/taoq-ai/wuwei/issues/221)) ([e212b9d](https://github.com/taoq-ai/wuwei/commit/e212b9dd4649c9dd157168da68fbb0a76d5f3fe9)), closes [#211](https://github.com/taoq-ai/wuwei/issues/211)
* **guards:** the plugin's own launcher and irrelevant scripts are never refused as opaque ([#213](https://github.com/taoq-ai/wuwei/issues/213)) ([31a36cc](https://github.com/taoq-ai/wuwei/commit/31a36cc44c60994e6612a87e766551288e20adf0)), closes [#205](https://github.com/taoq-ai/wuwei/issues/205)
* **team:** a solo owner can raise, push and close without reviewers or chat ([#218](https://github.com/taoq-ai/wuwei/issues/218)) ([e40e332](https://github.com/taoq-ai/wuwei/commit/e40e3320b035a03202fc6cb6dc2e07b5f8fb8741)), closes [#207](https://github.com/taoq-ai/wuwei/issues/207)
* **team:** an answered owner decision clears close, and the Stop hook never traps the session ([#214](https://github.com/taoq-ai/wuwei/issues/214)) ([7b35aad](https://github.com/taoq-ai/wuwei/commit/7b35aade9b316615e56efd8459e472d5d0aee4d1)), closes [#206](https://github.com/taoq-ai/wuwei/issues/206)
* **team:** records the operator reads are correct ([#219](https://github.com/taoq-ai/wuwei/issues/219)) ([55d9133](https://github.com/taoq-ai/wuwei/commit/55d913312e3a015c0e96a326afce04fbe99ad831)), closes [#209](https://github.com/taoq-ai/wuwei/issues/209)
* **team:** the loop's joints between build, gates, delta and push ([#217](https://github.com/taoq-ai/wuwei/issues/217)) ([11921c5](https://github.com/taoq-ai/wuwei/commit/11921c5565af004720ec821423c7f53db2276c59)), closes [#208](https://github.com/taoq-ai/wuwei/issues/208)

## [0.5.0](https://github.com/taoq-ai/wuwei/compare/v0.4.0...v0.5.0) (2026-09-29)


### Features

* **cockpit:** live PR rows, briefing path and status producers ([#203](https://github.com/taoq-ai/wuwei/issues/203)) ([d3f525f](https://github.com/taoq-ai/wuwei/commit/d3f525f61b032d7e0743924895c685f9549588cc)), closes [#178](https://github.com/taoq-ai/wuwei/issues/178)
* **team:** decision outcomes, reversal metric and the two-way digest ([#202](https://github.com/taoq-ai/wuwei/issues/202)) ([b9f5b2e](https://github.com/taoq-ai/wuwei/commit/b9f5b2e74baabb89e20b5cdfac101f9ac1b994da)), closes [#175](https://github.com/taoq-ai/wuwei/issues/175)
* **team:** intraday intake and autostart ([#198](https://github.com/taoq-ai/wuwei/issues/198)) ([0e694b3](https://github.com/taoq-ai/wuwei/commit/0e694b38347a7b3518bb85b993147630365191b0)), closes [#176](https://github.com/taoq-ai/wuwei/issues/176)
* **team:** owner draft queue for outward replies ([#201](https://github.com/taoq-ai/wuwei/issues/201)) ([a9c761f](https://github.com/taoq-ai/wuwei/commit/a9c761fb493dfc6b62a939fe171c34985832b5bf)), closes [#174](https://github.com/taoq-ai/wuwei/issues/174)
* **team:** shepherd actions for conflicted, red, changes requested and unanswered PRs ([#199](https://github.com/taoq-ai/wuwei/issues/199)) ([2b9c527](https://github.com/taoq-ai/wuwei/commit/2b9c527d95f217a2a3587aebc5a5685c46c9db91)), closes [#177](https://github.com/taoq-ai/wuwei/issues/177)


### Bug Fixes

* **cli:** the shipped goals guide parses and nudges lists nothing on an empty day ([#196](https://github.com/taoq-ai/wuwei/issues/196)) ([72b3e1c](https://github.com/taoq-ai/wuwei/commit/72b3e1caffb915d8d235529e849d4d631e3acb9f))

## [0.4.0](https://github.com/taoq-ai/wuwei/compare/v0.3.0...v0.4.0) (2026-09-29)


### Features

* **adapters:** credentials from a workspace env file and a configuration check that names them ([#195](https://github.com/taoq-ai/wuwei/issues/195)) ([d9cedd5](https://github.com/taoq-ai/wuwei/commit/d9cedd5066dc03464b0026861930b79d5d969584)), closes [#170](https://github.com/taoq-ai/wuwei/issues/170)
* **adapters:** Linear backlog discovery and tracker transitions in the loop ([#191](https://github.com/taoq-ai/wuwei/issues/191)) ([f0e174a](https://github.com/taoq-ai/wuwei/commit/f0e174a3a22fa3269ad87513775fd8300c6c6ca7)), closes [#172](https://github.com/taoq-ai/wuwei/issues/172)
* **memory:** owner edits to goals and voice satisfy workspace integrity ([#194](https://github.com/taoq-ai/wuwei/issues/194)) ([987ddc9](https://github.com/taoq-ai/wuwei/commit/987ddc9314bbfc3c4ecf0aa9de0622697db2ca35)), closes [#169](https://github.com/taoq-ai/wuwei/issues/169)


### Bug Fixes

* **cli:** documented schemas, valid templates and actionable errors ([#193](https://github.com/taoq-ai/wuwei/issues/193)) ([bfefcc8](https://github.com/taoq-ai/wuwei/commit/bfefcc8e3da7e69ba27aaaf026a69ede2d86514e)), closes [#171](https://github.com/taoq-ai/wuwei/issues/171)
* **sweeps:** quiet defaults, a nudge list and a watch installer ([#189](https://github.com/taoq-ai/wuwei/issues/189)) ([64b08ad](https://github.com/taoq-ai/wuwei/commit/64b08ad128ab7eb219e46c8f5e10cf8a7cfadcd8)), closes [#168](https://github.com/taoq-ai/wuwei/issues/168)
* **team:** build loop distinguishes environment failures and reports seat usage ([#192](https://github.com/taoq-ai/wuwei/issues/192)) ([97a0f9c](https://github.com/taoq-ai/wuwei/commit/97a0f9cbbc250f663a107f05d74917f0eab313c5)), closes [#173](https://github.com/taoq-ai/wuwei/issues/173)

## [0.3.0](https://github.com/taoq-ai/wuwei/compare/v0.2.0...v0.3.0) (2026-09-29)


### Features

* **team:** item-to-PR link and PR claiming ([#183](https://github.com/taoq-ai/wuwei/issues/183)) ([e57f536](https://github.com/taoq-ai/wuwei/commit/e57f536bab445c0432eeb2cd05e54d88b9b87720)), closes [#162](https://github.com/taoq-ai/wuwei/issues/162)
* **team:** step-wise build loop for Claude Code subagent seats ([#187](https://github.com/taoq-ai/wuwei/issues/187)) ([d35dbd1](https://github.com/taoq-ai/wuwei/commit/d35dbd152e5dc03d57dca40cf4fdb310a9027f0d)), closes [#161](https://github.com/taoq-ai/wuwei/issues/161)


### Bug Fixes

* **guards:** commit and push guards act on the target repository, not only the cwd ([#184](https://github.com/taoq-ai/wuwei/issues/184)) ([895c5e0](https://github.com/taoq-ai/wuwei/commit/895c5e02b49e46d72d0b1658d7c39a48f6baffd6)), closes [#164](https://github.com/taoq-ai/wuwei/issues/164)
* **guards:** day close refuses while work is unresolved ([#188](https://github.com/taoq-ai/wuwei/issues/188)) ([26a98ed](https://github.com/taoq-ai/wuwei/commit/26a98edcb0495650b3c5a107b27ead1f39aa8561)), closes [#167](https://github.com/taoq-ai/wuwei/issues/167)
* **guards:** SubagentStop verdict lint checks only the stopping seat's own verdict ([#182](https://github.com/taoq-ai/wuwei/issues/182)) ([0b6a06c](https://github.com/taoq-ai/wuwei/commit/0b6a06c3211371f2a58b977124461b4e38cc9c76)), closes [#166](https://github.com/taoq-ai/wuwei/issues/166)
* **security:** plugin installs from the marketplace or a source checkout do not lock the workspace ([#185](https://github.com/taoq-ai/wuwei/issues/185)) ([201ad0a](https://github.com/taoq-ai/wuwei/commit/201ad0a5cebb8845d73402891147dc14f41416ca)), closes [#165](https://github.com/taoq-ai/wuwei/issues/165)
* **team:** PR raise works for a solo owner and reads the item worktree ([#186](https://github.com/taoq-ai/wuwei/issues/186)) ([9a16758](https://github.com/taoq-ai/wuwei/commit/9a16758de36ec7aa0b334339335dd7eb67e67248)), closes [#163](https://github.com/taoq-ai/wuwei/issues/163)
* **team:** seat launch prompts carry the brief reference the launch guard requires ([#180](https://github.com/taoq-ai/wuwei/issues/180)) ([b4304db](https://github.com/taoq-ai/wuwei/commit/b4304dba3cb1e28bd4689ed1c252c90ab27414f9)), closes [#160](https://github.com/taoq-ai/wuwei/issues/160)

## [0.2.0](https://github.com/taoq-ai/wuwei/compare/v0.1.0...v0.2.0) (2026-09-29)


### Features

* **security:** MCP audit and drift watch at init and each morning (S3) ([#158](https://github.com/taoq-ai/wuwei/issues/158)) ([4a326ca](https://github.com/taoq-ai/wuwei/commit/4a326ca9a178017aaa9647765f254166a767b37d)), closes [#35](https://github.com/taoq-ai/wuwei/issues/35)
* **security:** ZIRAN over live session traces at each sweep (S2) ([#156](https://github.com/taoq-ai/wuwei/issues/156)) ([d1ea031](https://github.com/taoq-ai/wuwei/commit/d1ea031d0ca40c7390f63a20097dff1047b55a7c)), closes [#34](https://github.com/taoq-ai/wuwei/issues/34)

## 0.1.0 (2026-09-29)


### Features

* **adapters:** adapter interfaces and registry with `none` defaults ([#82](https://github.com/taoq-ai/wuwei/issues/82)) ([40fbfc7](https://github.com/taoq-ai/wuwei/commit/40fbfc7c0ec8dd99bb84be870b30349e6fdf1149)), closes [#5](https://github.com/taoq-ai/wuwei/issues/5)
* **adapters:** code_host and vcs ports with GitHub and git adapters ([#99](https://github.com/taoq-ai/wuwei/issues/99)) ([4101118](https://github.com/taoq-ai/wuwei/commit/4101118bc6b226fcfd674562f0ff6fbd16c9f869)), closes [#87](https://github.com/taoq-ai/wuwei/issues/87)
* **adapters:** Linear tracker, Slack chat and Greptile review-bot adapters ([#121](https://github.com/taoq-ai/wuwei/issues/121)) ([f539fc3](https://github.com/taoq-ai/wuwei/commit/f539fc3d1bd13c0763178ee9102659300c12bf79)), closes [#27](https://github.com/taoq-ai/wuwei/issues/27)
* **adapters:** runtime adapter for Claude agents and Codex ([#126](https://github.com/taoq-ai/wuwei/issues/126)) ([2d2b340](https://github.com/taoq-ai/wuwei/commit/2d2b3403e0f0c6b6841b417844249226bbdba732)), closes [#26](https://github.com/taoq-ai/wuwei/issues/26)
* **cli:** `wuwei` entry point with the three-state exit contract ([#69](https://github.com/taoq-ai/wuwei/issues/69)) ([8048281](https://github.com/taoq-ai/wuwei/commit/80482812aacc4404ddb5df45a27c7124f40db440)), closes [#2](https://github.com/taoq-ai/wuwei/issues/2)
* **cockpit:** optional SwiftBar menu-bar indicator ([#128](https://github.com/taoq-ai/wuwei/issues/128)) ([f5aa243](https://github.com/taoq-ai/wuwei/commit/f5aa243e6f04664a02e83452e07eae8e7ac2f2ff)), closes [#94](https://github.com/taoq-ai/wuwei/issues/94)
* **cockpit:** signal classification and `wuwei status` for the status line ([#113](https://github.com/taoq-ai/wuwei/issues/113)) ([ab95aff](https://github.com/taoq-ai/wuwei/commit/ab95affc2fdabfa7b86c3170a0ecbaf1584ae53d)), closes [#92](https://github.com/taoq-ai/wuwei/issues/92)
* **cockpit:** Work, Decisions and People lanes with CLI-backed approvals ([#130](https://github.com/taoq-ai/wuwei/issues/130)) ([36f0993](https://github.com/taoq-ai/wuwei/commit/36f0993e539d58a3a7fb4804776fc3e751fa7dc8)), closes [#93](https://github.com/taoq-ai/wuwei/issues/93)
* **core:** versioned charters and `wuwei init --upgrade` ([#116](https://github.com/taoq-ai/wuwei/issues/116)) ([2a22238](https://github.com/taoq-ai/wuwei/commit/2a2223890a4a733ce8967e386247379e60616b89)), closes [#40](https://github.com/taoq-ai/wuwei/issues/40)
* **guards:** `strict` and `standard` profiles ([#131](https://github.com/taoq-ai/wuwei/issues/131)) ([c00e9fe](https://github.com/taoq-ai/wuwei/commit/c00e9fe52459f6b329c7c9ef0d3ed5356cf5b15a)), closes [#17](https://github.com/taoq-ai/wuwei/issues/17)
* **guards:** `wuwei brief` and the agent-launch guard ([92f7e84](https://github.com/taoq-ai/wuwei/commit/92f7e84a1e2b9ee9289d160aa741c2c7d43ba804))
* **guards:** commit and push guard (identity, force, default branch, fast checks) ([8c4d639](https://github.com/taoq-ai/wuwei/commit/8c4d6396ada6239a7b56ebe28fd66693a37731e3))
* **guards:** day-close Stop guard ([#136](https://github.com/taoq-ai/wuwei/issues/136)) ([48ec931](https://github.com/taoq-ai/wuwei/commit/48ec9315395bf285606e2b00009b51c43b4f07b3)), closes [#16](https://github.com/taoq-ai/wuwei/issues/16)
* **guards:** decision records, decision lint and the question guard ([#123](https://github.com/taoq-ai/wuwei/issues/123)) ([d2d700e](https://github.com/taoq-ai/wuwei/commit/d2d700e587e54da6593484deba8b29710e474ae0)), closes [#78](https://github.com/taoq-ai/wuwei/issues/78)
* **guards:** deployment ban ([d73ceb7](https://github.com/taoq-ai/wuwei/commit/d73ceb70edd579257a4b6f08c6f8a3af2ae4452e))
* **guards:** merge policy, `wuwei merge` and the post-merge circuit breaker ([#137](https://github.com/taoq-ai/wuwei/issues/137)) ([00d9426](https://github.com/taoq-ai/wuwei/commit/00d942659ed11bcf4b684040ab3b009af7413190)), closes [#77](https://github.com/taoq-ai/wuwei/issues/77)
* **guards:** outbound approval tiers ([#122](https://github.com/taoq-ai/wuwei/issues/122)) ([9ecf2bc](https://github.com/taoq-ai/wuwei/commit/9ecf2bc975c2503d2df1c8337fe9b2f4bb1cdad3)), closes [#95](https://github.com/taoq-ai/wuwei/issues/95)
* **guards:** outward-text lint and approved-draft rule for chat and tracker calls ([#107](https://github.com/taoq-ai/wuwei/issues/107)) ([31aa223](https://github.com/taoq-ai/wuwei/commit/31aa223ec620973dc0dde76c899625d5ec4f34c5)), closes [#11](https://github.com/taoq-ai/wuwei/issues/11)
* **guards:** PR create, merge and approve guards ([#117](https://github.com/taoq-ai/wuwei/issues/117)) ([64b5169](https://github.com/taoq-ai/wuwei/commit/64b51698cc5300f2c17bcc4ccad85eeefb9e80ab)), closes [#9](https://github.com/taoq-ai/wuwei/issues/9)
* **guards:** protect state files and the workspace root ([#106](https://github.com/taoq-ai/wuwei/issues/106)) ([ea32d9d](https://github.com/taoq-ai/wuwei/commit/ea32d9d11c98dd2877118bd6775debe154fef5c6)), closes [#10](https://github.com/taoq-ai/wuwei/issues/10)
* **guards:** record every tool call to `traces.jsonl` in OTel JSONL ([#108](https://github.com/taoq-ai/wuwei/issues/108)) ([2ba7db1](https://github.com/taoq-ai/wuwei/commit/2ba7db1c3a1cd10185a0f0957a0beba29e3dae4b)), closes [#12](https://github.com/taoq-ai/wuwei/issues/12)
* **guards:** verdict lint and retro-note capture ([#102](https://github.com/taoq-ai/wuwei/issues/102)) ([f139af0](https://github.com/taoq-ai/wuwei/commit/f139af0f1516a9b0c160cdaf0115cc2914b90617)), closes [#13](https://github.com/taoq-ai/wuwei/issues/13)
* **hooks:** hook shims and recorded-payload test harness ([#98](https://github.com/taoq-ai/wuwei/issues/98)) ([b9db726](https://github.com/taoq-ai/wuwei/commit/b9db726b79fffb5b6084081e88e5d1c6f6da141d))
* **memory:** daily fold and weekly `/wuwei consolidate` ([#153](https://github.com/taoq-ai/wuwei/issues/153)) ([8787f3b](https://github.com/taoq-ai/wuwei/commit/8787f3b4319803e05624e5c0e0927fff58641b8d)), closes [#32](https://github.com/taoq-ai/wuwei/issues/32)
* **memory:** generated index and session payload ([#89](https://github.com/taoq-ai/wuwei/issues/89)) ([4e73b33](https://github.com/taoq-ai/wuwei/commit/4e73b335d2c6c14f66d7e2c1b7eb8c53d95977a6)), closes [#30](https://github.com/taoq-ai/wuwei/issues/30)
* **memory:** memory lint ([#124](https://github.com/taoq-ai/wuwei/issues/124)) ([d4666b0](https://github.com/taoq-ai/wuwei/commit/d4666b015e5eae59d51614c92161de70e422d6fb)), closes [#31](https://github.com/taoq-ai/wuwei/issues/31)
* **memory:** notes with frontmatter contract and `wuwei note` ([#83](https://github.com/taoq-ai/wuwei/issues/83)) ([a9fcd3c](https://github.com/taoq-ai/wuwei/commit/a9fcd3c55efc2ce3ef26035a111cb1fe7b53a8cd)), closes [#29](https://github.com/taoq-ai/wuwei/issues/29)
* **memory:** proposals, `wuwei promote` and the ledger ([#118](https://github.com/taoq-ai/wuwei/issues/118)) ([42ad4b6](https://github.com/taoq-ai/wuwei/commit/42ad4b6cf471f7b809e8f41e661b08a8195ee9bb)), closes [#81](https://github.com/taoq-ai/wuwei/issues/81)
* **security:** prompt canary and honeytoken ([#135](https://github.com/taoq-ai/wuwei/issues/135)) ([35d211c](https://github.com/taoq-ai/wuwei/commit/35d211ccf819c0e623f278213a35e93260e251bd)), closes [#105](https://github.com/taoq-ai/wuwei/issues/105)
* **security:** signed integrity manifest and workspace integrity ([#143](https://github.com/taoq-ai/wuwei/issues/143)) ([0b65100](https://github.com/taoq-ai/wuwei/commit/0b651006710a73d518a944644e0c88895f4ae5e9)), closes [#104](https://github.com/taoq-ai/wuwei/issues/104)
* **security:** ZIRAN scanner adapter and agent-surface gate (S4) ([#145](https://github.com/taoq-ai/wuwei/issues/145)) ([93125f1](https://github.com/taoq-ai/wuwei/commit/93125f1dd16114cb1241ee5a4b182c9075dde90e)), closes [#33](https://github.com/taoq-ai/wuwei/issues/33)
* **state:** single writer for `state.json` and append-only `events.jsonl` ([#74](https://github.com/taoq-ai/wuwei/issues/74)) ([a353d75](https://github.com/taoq-ai/wuwei/commit/a353d75b59e28d93a37367e7aa5fdc33365d39e2)), closes [#4](https://github.com/taoq-ai/wuwei/issues/4)
* **sweeps:** reply and visibility obligations over open PRs ([#115](https://github.com/taoq-ai/wuwei/issues/115)) ([7c4d68a](https://github.com/taoq-ai/wuwei/commit/7c4d68a3703eb0e4e8b9815ef259e8b9976855b1)), closes [#14](https://github.com/taoq-ai/wuwei/issues/14)
* **sweeps:** watch process, session payload and compaction flush ([#134](https://github.com/taoq-ai/wuwei/issues/134)) ([aba0b01](https://github.com/taoq-ai/wuwei/commit/aba0b017b30364a42a77e30573660d500eaaa599)), closes [#15](https://github.com/taoq-ai/wuwei/issues/15)
* **team:** `/wuwei plan` skill, lead discovery and the morning gate ([#129](https://github.com/taoq-ai/wuwei/issues/129)) ([e8d7fbb](https://github.com/taoq-ai/wuwei/commit/e8d7fbb2e275fde5d0e7227b954c09ea283e38a3)), closes [#21](https://github.com/taoq-ai/wuwei/issues/21)
* **team:** `/wuwei report` and the steward retro ([#149](https://github.com/taoq-ai/wuwei/issues/149)) ([52ec8c2](https://github.com/taoq-ai/wuwei/commit/52ec8c2da8f282f41dfe29c1db90da203f4abf9b)), closes [#25](https://github.com/taoq-ai/wuwei/issues/25)
* **team:** `wuwei metrics` outcome metrics against the owner's baseline ([#152](https://github.com/taoq-ai/wuwei/issues/152)) ([1878555](https://github.com/taoq-ai/wuwei/commit/18785559a771c5038e0a1c081ae756b051ec3597)), closes [#80](https://github.com/taoq-ai/wuwei/issues/80)
* **team:** briefing pack with audio, meeting card and defend drill ([#154](https://github.com/taoq-ai/wuwei/issues/154)) ([4d9c919](https://github.com/taoq-ai/wuwei/commit/4d9c91915b87f3075a5406bb2df6b885d26e8d0c)), closes [#96](https://github.com/taoq-ai/wuwei/issues/96)
* **team:** generate agent files from charters with tool allowlists ([#125](https://github.com/taoq-ai/wuwei/issues/125)) ([a71ebc7](https://github.com/taoq-ai/wuwei/commit/a71ebc7e829679d4dad0f959538de5899c7aed21)), closes [#20](https://github.com/taoq-ai/wuwei/issues/20)
* **team:** generic charter set for nine roles ([#88](https://github.com/taoq-ai/wuwei/issues/88)) ([fa9e5e0](https://github.com/taoq-ai/wuwei/commit/fa9e5e0395c23380cf20f177c07997252f64c85c)), closes [#19](https://github.com/taoq-ai/wuwei/issues/19)
* **team:** goals, all-day discovery and `wuwei rank` (WSJF or RICE) ([#141](https://github.com/taoq-ai/wuwei/issues/141)) ([9025a30](https://github.com/taoq-ai/wuwei/commit/9025a300732ba5c8364a73f541bf407b04457b45)), closes [#79](https://github.com/taoq-ai/wuwei/issues/79)
* **team:** owner voice profile and voice lint ([#133](https://github.com/taoq-ai/wuwei/issues/133)) ([8ac9e3e](https://github.com/taoq-ai/wuwei/commit/8ac9e3e46abd9ad16089e96dfce42b353dcee0f3)), closes [#85](https://github.com/taoq-ai/wuwei/issues/85)
* **team:** passive dashboard over state and events ([#90](https://github.com/taoq-ai/wuwei/issues/90)) ([0a0bc7c](https://github.com/taoq-ai/wuwei/commit/0a0bc7c1f2fdc9d11bda009686a2c3053abcd7e0)), closes [#28](https://github.com/taoq-ai/wuwei/issues/28)
* **team:** planner dispatch and receive flow with parallel pre-PR gates ([#142](https://github.com/taoq-ai/wuwei/issues/142)) ([729ef6a](https://github.com/taoq-ai/wuwei/commit/729ef6ae6cc204e84c040becd2eb22c83aedd6bf)), closes [#22](https://github.com/taoq-ai/wuwei/issues/22)
* **team:** PR ownership loop (state, actions, wake, turn-end anchor) ([#144](https://github.com/taoq-ai/wuwei/issues/144)) ([ea7006f](https://github.com/taoq-ai/wuwei/commit/ea7006f26576ee99e073abe44e6eaa06053263c8)), closes [#120](https://github.com/taoq-ai/wuwei/issues/120)
* **team:** shepherd flow (raise, reviewer selection, ping gate, replies) ([#148](https://github.com/taoq-ai/wuwei/issues/148)) ([55a9b7b](https://github.com/taoq-ai/wuwei/commit/55a9b7b35dbd1b806e6db6e575414d9eebf7f65d)), closes [#23](https://github.com/taoq-ai/wuwei/issues/23)
* **team:** steward seat, metrics and decision pre-triage ([#147](https://github.com/taoq-ai/wuwei/issues/147)) ([2533538](https://github.com/taoq-ai/wuwei/commit/2533538b05820b557b20092ebe71f443ff21c513)), closes [#24](https://github.com/taoq-ai/wuwei/issues/24)
* **workspace:** `.wuwei/` layout, `config.toml` schema and `wuwei init` ([#71](https://github.com/taoq-ai/wuwei/issues/71)) ([62da4d9](https://github.com/taoq-ai/wuwei/commit/62da4d9022e19b6bee0f9cbf0e352ee877e1fce1)), closes [#3](https://github.com/taoq-ai/wuwei/issues/3)


### Bug Fixes

* **cli:** run the shim in isolated mode ([#100](https://github.com/taoq-ai/wuwei/issues/100)) ([2eb6319](https://github.com/taoq-ai/wuwei/commit/2eb6319c1405f2ea09ab2eef2c4301f9db23e369))
* **guards:** PreToolUse no longer hangs on rm -rf / outside a workspace ([#139](https://github.com/taoq-ai/wuwei/issues/139)) ([65e7231](https://github.com/taoq-ai/wuwei/commit/65e723186b080d4b67d7eb33e7383d8af6df9639))
* **release:** bump minor, not major, before 1.0 ([#72](https://github.com/taoq-ai/wuwei/issues/72)) ([b772c29](https://github.com/taoq-ai/wuwei/commit/b772c29c2ae155dff6a5145fb4f697c99700e38b))
* **release:** first release is 0.1.0, not the 1.0.0 default ([#73](https://github.com/taoq-ai/wuwei/issues/73)) ([1dc8cf2](https://github.com/taoq-ai/wuwei/commit/1dc8cf26e0cb7d8a52d1f23a95e61531f53aea0b))
* **state:** generic state set and event write only an allowlist ([#138](https://github.com/taoq-ai/wuwei/issues/138)) ([004f190](https://github.com/taoq-ai/wuwei/commit/004f190c20eb33fff37b1779ea1dce5b3c9ae4e6)), closes [#114](https://github.com/taoq-ai/wuwei/issues/114)
