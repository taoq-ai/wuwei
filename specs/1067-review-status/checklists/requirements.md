# Requirements checklist: 1067 review status

- [x] Every acceptance scenario of item 1067 maps to a test
- [x] No config key added (five keys)
- [x] Runtime at 3,000 lines or fewer
- [x] Lines freed only in cli/wuwei/evidence.py and cli/wuwei/gh.py
- [x] A failed host read never turns a status into a pass
- [x] No Actions call when the head has no unsettled commit status
- [x] Docs updated: design section 6 and the evidence concept page
- [x] No emojis, no em dashes
