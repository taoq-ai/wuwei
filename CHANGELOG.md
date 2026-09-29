# Changelog

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
