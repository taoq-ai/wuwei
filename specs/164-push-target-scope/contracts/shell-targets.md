# Shell target metadata

Existing hook, guard, VCS and state contracts remain unchanged.

`wuwei.shell.normalize` still returns `Command` records and raises `ParseError`
with its plain-command hint for unsupported syntax. It adds:

- `Command.scope`: a tuple identifying a shell scope and its ancestors. Commands
  within a scope share directory changes; subshells and shell wrappers inherit
  then isolate them. Literal eval uses the calling scope.
- `Command.separator`: the following shell separator. A directory change followed
  by `&&` must succeed for the following command to run. Other separators require
  retaining both directory possibilities.
- Optional `words`: a caller-owned list collecting literal words observed during
  normalization, including words before a parse failure. These are scope hints,
  never proof that a rejected command is safe or executable.

No parser-level guard policy is introduced. Callers establish relevance before
normalization and own their scoped failure behavior. The commit/push guard treats
unresolved repository selectors as unmeasured and refuses with the parser hint.
