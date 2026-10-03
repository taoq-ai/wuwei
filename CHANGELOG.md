# Changelog

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
