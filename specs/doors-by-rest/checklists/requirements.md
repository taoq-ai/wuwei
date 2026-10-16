# Requirements checklist: doors-by-rest

- [x] Every acceptance scenario of item doors-by-rest maps to a test
- [x] Each `gh api` spelling the reader claims was checked against gh 2.89.0 through a logging proxy
- [x] One route table replaces the merge regex and GUARDED_API
- [x] REST create meets create_door with head, base and body from the fields or the --input file
- [x] REST merge and auto-merge meet merge_door in every spelling tested
- [x] REST branch writes and repository delete refused; protection writes still refused
- [x] GraphQL door mutations refused with a pointer to gh pr merge or create; thread routes pass
- [x] gh pr new reads as gh pr create
- [x] MCP push_files, create_or_update_file and delete_file in guards.DOORS and refused on the default branch or with no branch
- [x] charters/shepherd.md names a create route the door checks; agents/ rebuilt
- [x] SECURITY.md says what the reader covers and what it does not
- [x] Every recorded corpus route reads as recorded; 15 routes added with sources
- [x] Main-versus-head comparison shows only the promised moves
- [x] .claude/ re-vendored at the head
- [x] Runtime at 3,000 lines or fewer
- [x] No config key, no new door, no emojis, no em dashes
