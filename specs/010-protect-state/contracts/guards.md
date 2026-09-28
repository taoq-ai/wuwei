# State and workspace guard contract

`cli/wuwei/guards/protect_state.py` registers two PreToolUse guards:

- `Write|Edit|MultiEdit|NotebookEdit`: check `tool_input.file_path` (or `notebook_path`
  for NotebookEdit) relative to absolute payload `cwd`.
- `Bash`: normalize `tool_input.command`, inspect output targets and protected operands,
  and contain persistent cd/pushd/popd directory changes within `find_workspace(cwd)`.

Both checks return `(0, '')` for safe actions, `(1, reason)` for known violations,
and `(2, reason)` for invalid payloads, relevant parse failures or unresolved paths. State
refusals direct callers to the CLI. Directory refusals recommend `git -C` or a
subshell. The existing hook dispatcher translates both nonzero states to a deny
response and exit 2.

`Command.writes` extends the shell contract with a defaulted tuple of literal output
redirection paths. Existing argv, subshell and env fields are unchanged. A command
containing only redirections has empty argv. Wrapper redirections attach to the
first normalized command, and subshell trailing redirections retain their targets.
Input redirections and numeric descriptor duplication do not appear as writes.

The normalizer rejects dynamic writer/cd arguments and command names, input-driven
writers even through nested wrappers, and unsupported environment mutation. The state guard treats interpreter
mentions of protected names in snippets or arguments as opaque. The safe
`python3 -P -m wuwei` entry point remains supported.

Path checks retain possible directories across flattened shell control flow. This can
conservatively reject a safe conditional or nested command. CDPATH searches and unknown directory stacks fail closed. Tilde cd targets use HOME.
The final pipeline stage is persistent under zsh. Protected operands default to refusal
unless the command is a known reader or source-only cp/dd/rsync operation.
Casefold resolved names, and compare multiply linked files with protected workspace
files using samefile. General script analysis remains outside this contract.

## Guard convention notes

- Protect resolved `.wuwei/days/*/state.json`, `.wuwei/days/*/events.jsonl`, and archive
  paths regardless of cwd or workspace override. Scan hard links only with a known root.
  Only directory containment requires cwd inside the workspace.
- NonliteralPathError is a ParseError subclass for nonliteral redirections and file or
  directory arguments. Parse failures block on state mentions, `\.w[\w*?\[]`, or
  scoped cd/pushd/popd words. Nonliteral paths and dynamic write constructs also block
  from protected state containers with a known workspace. Ordinary opaque commands
  elsewhere pass per F11's explicit examples; see the assumption and residual in spec.md.
- Expand parsed glob arguments for ln/install/rsync/rm/cp/mv/tee/truncate/sed and dd
  output values relative to cwd before checking protected paths. Quoted glob strings
  are conservatively checked too.
- Refuse rm/mv sources naming `.wuwei`, day containers, workspace roots or ancestors.
  Check chmod/chown operands in directories mode. Refuse git apply at or inside a
  workspace, resolving git -C; patch destinations from elsewhere remain a residual.
- The CLI independently leaves state and events at mode 0444. State gets this mode on
  its temporary file before rename. Events retain O_APPEND and the existing lock scope,
  with temporary chmod to open the descriptor and 0444 restored before the append.
