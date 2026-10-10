"""Static shell tables: no command in this file is executed."""

import pytest


@pytest.mark.parametrize('script,expected', [
    ('', []), ('  # comment\n', []),
    ('git status', [(['git', 'status'], False)]),
    ('git status; gh pr list && git push || echo failed | cat\npwd',
     [(['git', 'status'], False), (['gh', 'pr', 'list'], False),
      (['git', 'push'], False), (['echo', 'failed'], True), (['cat'], False), (['pwd'], False)]),
    ('''echo 'a;b' "x&&y" '|' '(' ')' "" a"b c"d''',
     [(['echo', 'a;b', 'x&&y', '|', '(', ')', '', 'ab cd'], False)]),
    (r'echo a\;b \( \) \|', [(['echo', 'a;b', '(', ')', '|'], False)]),
    ('git \\\npush', [(['git', 'push'], False)]),
    ('echo foo#bar', [(['echo', 'foo#bar'], False)]),
    ('git -C /repo -c user.name=Owner push',
     [(['git', '-C', '/repo', '-c', 'user.name=Owner', 'push'], False)]),
    ('(cd /tmp && git status); cd /workspace',
     [(['cd', '/tmp'], True), (['git', 'status'], True), (['cd', '/workspace'], False)]),
    ('( (git status) ); pwd', [(['git', 'status'], True), (['pwd'], False)]),
    ('''bash -c 'cd /tmp; sh -c "git push"'; pwd''',
     [(['cd', '/tmp'], True), (['git', 'push'], True), (['pwd'], False)]),
    ('''/bin/zsh -lc 'gh pr merge 1' ''', [(['gh', 'pr', 'merge', '1'], True)]),
    ('env VAR=x GIT_DIR=/repo command exec nohup time git push', [(['git', 'push'], False)]),
    ('VAR=x git push', [(['git', 'push'], False)]),
    ('env -i -u VAR -- VAR=x command -p -- exec -a alias git push', [(['git', 'push'], False)]),
    ('time -p nohup -- git push', [(['git', 'push'], False)]),
    ('VAR=x', []), ('xargs', [(['echo'], True)]),
])
def test_normalize(script, expected):
    from wuwei.shell import normalize
    assert [(item.argv, item.subshell) for item in normalize(script)] == expected


@pytest.mark.parametrize('script', [
    "git 'push", 'echo "unterminated', 'git push\\', '(git push', 'git push)',
    'git push &&', '| git push', 'git push ;; pwd', 'bash -c', 'bash -c "git \'push"',
    'env -u', 'env --unknown git push', 'xargs --unknown git push',
    'exec -a', 'time -o log git push', 'sh script.sh',
    'echo $(git push)', 'echo `git push`', '$CMD push',
    'if true; then git push; fi', '\x00',
])
def test_parse_error(script):
    from wuwei.shell import ParseError, normalize
    with pytest.raises(ParseError):
        normalize(script)


@pytest.mark.parametrize('script,opaque', [
    ('''python -c 'import os; os.system("git push")' ''', True),
    ('''python3 -c 'run("gh pr merge 1")' ''', True),
    ('''python3 -c 'print("gh pr merge 1")' ''', True),  # #671: a gh word keeps #643's reader opaque
    ('''/usr/bin/python3 -I -c 'run("git push")' ''', True),
    ('''node -e 'run("git push")' ''', True),
    ('''perl -e 'system("gh pr merge")' ''', True),
    ('''ruby -e 'system("git push")' ''', True),
    ('''env X=y bash -c 'python3 -c "run(\\\"git push\\\")"' ''', True),
    ('''python -c 'print("legit text")' ''', False),
    ('''python3 -c 'print("github")' ''', False),
    ('''echo 'python -c git push' ''', False),  # #671: an echo argument is text
    ('git push', False),
])
def test_opaque_interpreter(script, opaque):
    from wuwei.shell import ParseError, is_opaque, normalize
    if opaque:
        with pytest.raises(ParseError):
            normalize(script)
    else:
        assert not any(is_opaque(item.argv) for item in normalize(script))


@pytest.mark.parametrize('argv', [
    ['python3', '-cimport os; os.system("git push")'],
    ['python3', '-Ic', 'run("gh pr merge")'],
    ['node', '--eval', 'run("git push")'],
    ['node', '-e', 'safe()', '-e', 'run("git push")'],
    ['perl', '-we', 'system("git push")'],
    ['ruby', '-esystem("gh pr merge")'],
])
def test_opaque_attached_combined_and_repeated_options(argv):
    from wuwei.shell import is_opaque
    assert is_opaque(argv)


@pytest.mark.parametrize('script', [
    '''X='; git push'; bash -c "echo $X"''',
    '''env X='; git push' bash -c "echo ${X}"''',
    '''env X=value command bash -c 'echo '"$X"''',
    '''xargs -I{} bash -c "$SCRIPT"''',
])
def test_expanding_nested_script_fails_closed(script):
    from wuwei.shell import ParseError, normalize
    with pytest.raises(ParseError):
        normalize(script)


def test_single_quotes_inside_outer_double_quotes_still_expand():
    from wuwei.shell import ParseError, normalize
    with pytest.raises(ParseError):
        normalize('''bash -c "echo '$X'"''')


@pytest.mark.parametrize('script', [
    "sh -c -e 'git push -f'", "sh -c -- 'git push -f'",
])
def test_shell_script_after_options(script):
    from wuwei.shell import normalize
    assert [item.argv for item in normalize(script)] == [['git', 'push', '-f']]


@pytest.mark.parametrize('script', [
    "sh -c -o errexit 'git push -f'", "sh -c +o errexit 'git push -f'",
])
def test_shell_named_options_fail_closed(script):
    from wuwei.shell import ParseError, normalize
    with pytest.raises(ParseError):
        normalize(script)


def test_comment_backslash_cannot_hide_next_command():
    from wuwei.shell import ParseError, normalize
    try:
        commands = normalize('git status\n# \\\ngit push -f')
    except ParseError:
        return
    assert commands[-1].argv == ['git', 'push', '-f']


@pytest.mark.parametrize('script', [
    'eval "git push -f"', 'eval git push -f',
    'nice git push -f', 'timeout 5 git push -f', 'sudo git push -f',
    'stdbuf -oL git push -f', 'setsid git push -f',
    "dash -c 'git push -f'", "ksh -c 'git push -f'",
    "busybox sh -c 'git push -f'",
])
def test_launcher_exposes_guarded_command(script):
    from wuwei.shell import normalize
    assert any(item.argv[:3] == ['git', 'push', '-f'] for item in normalize(script))


@pytest.mark.parametrize('script', [
    "trap 'git push -f' EXIT",
    '''xargs -I '{}' bash -c 'git push "$1"' _ '{}' ''',
    """sh -c 'nice "$@"' _ git push -f""",
    """sh -c 'nice "$1" push -f' _ git""",
])
def test_dynamic_launcher_fails_closed(script):
    from wuwei.shell import ParseError, normalize
    with pytest.raises(ParseError):
        normalize(script)


@pytest.mark.parametrize('argv', [
    ['watch', 'git', 'push', '-f'], ['parallel', 'git', 'push', ':::', '1'],
    ['unknown-launcher', '/usr/bin/gh', 'pr', 'merge'],
    ['git', '-c', 'x=y', 'git'],
])
def test_later_guarded_word_is_opaque(argv):
    from wuwei.shell import is_opaque
    assert is_opaque(argv)


@pytest.mark.parametrize('script,envs', [
    ('env VAR=x git status', [{'VAR': 'x'}]),
    ("A=outer env B=two sh -c 'A=inner git status; git push' | cat",
     [{'A': 'inner', 'B': 'two'}, {'A': 'outer', 'B': 'two'}, {}]),
    ("A=one env A=two command git status", [{'A': 'two'}]),
    ("A=one env -i B=two git status", [{'B': 'two'}]),
    ("A=one B=two env -u A git status", [{'B': 'two'}]),
])
def test_environment_is_preserved(script, envs):
    from wuwei.shell import normalize
    assert [item.env for item in normalize(script)] == envs


@pytest.mark.parametrize('script', [
    r"git $'\x70ush' -f", 'V=push; git $V -f', 'git ${X:-push} -f',
    'git push${IFS}-f', 'gh "$ACTION" merge', "echo $'literal'",
    "bash -c $'git push -f'",
])
def test_argument_expansion_fails_closed(script):
    from wuwei.shell import ParseError, normalize
    with pytest.raises(ParseError):
        normalize(script)


@pytest.mark.parametrize('script,word', [
    ("git commit -m '$literal'", '$literal'),
    (r'git commit -m \$literal', '$literal'),
    (r'git commit -m "\$literal"', '$literal'),
])
def test_literal_dollar_is_not_expansion(script, word):
    from wuwei.shell import normalize
    assert normalize(script)[0].argv[-1] == word


@pytest.mark.parametrize('script', [
    """python3 -c "subprocess.run(['git','push','-f'])" """,
    """perl -e 'system("git","push")' """,
    """python3 -c "os.system('git\tpush')" """,
    """python3.12 -c 'run("git")' """, """pypy3.11 -c 'run("gh")' """,
    """perl -E 'system("git")' """, """node -p 'run("git")' """,
    """php -r 'run("git")' """, """lua -e 'run("git")' """,
])
def test_opaque_interpreter_variants(script):
    import shlex
    from wuwei.shell import ParseError, is_opaque, normalize
    assert is_opaque(shlex.split(script))
    with pytest.raises(ParseError):
        normalize(script)


@pytest.mark.parametrize('script', [
    'alias g=git', 'unalias git', '. ./commands', 'source ./commands',
    'shopt -s expand_aliases', 'enable -f commands.so commands',
    "bash -c 'shopt -s expand_aliases\nalias g=git\ng push'",
    r"bash -c $'shopt -s expand_aliases\nalias g=git\ng push'",
])
def test_shell_mutation_fails_closed(script):
    from wuwei.shell import ParseError, normalize
    with pytest.raises(ParseError):
        normalize(script)


@pytest.mark.parametrize('script,expected', [
    ('npm test 2>&1 | tail', [['npm', 'test'], ['tail']]),
    ('git push > /dev/null', [['git', 'push']]),
    ('2>/dev/null git push -f 1>>log', [['git', 'push', '-f']]),
    ('cat < input <>output & git push -f', [['cat'], ['git', 'push', '-f']]),
    ('git status & git push -f &', [['git', 'status'], ['git', 'push', '-f']]),
    ("cat <<-'EOF'\n\tdata\n\tEOF\ngit push -f", [['cat'], ['git', 'push', '-f']]),
    ("cat <<'A' <<'B'\none\nA\ntwo\nB\ngit push", [['cat'], ['git', 'push']]),
    ("git commit -m \"$(cat <<'EOF'\nmessage with \"quotes\" and 'quotes'\n$V `literal`\nEOF\n)\"",
     [['git', 'commit', '-m', 'message with "quotes" and \'quotes\'\n$V `literal`']]),
])
def test_redirections_and_literal_heredocs(script, expected):
    from wuwei.shell import normalize
    assert [item.argv for item in normalize(script)] == expected


@pytest.mark.parametrize('script', [
    'git push >', 'git push > ; echo ok',
    'git push > $(echo file)', 'cat <<EOF\n$(git push)\nEOF',
    "cat <<'EOF'\nunterminated", 'git commit -m "$(echo message)"',
    "git commit -m \"$(cat <<'EOF'\nmessage\nEOF\ngit push\n)\"",
    "git commit -m \"$(cat <<EOF\nmessage\nEOF\n)\"",
])
def test_unsupported_redirections_and_substitutions_fail_closed(script):
    from wuwei.shell import ParseError, normalize
    with pytest.raises(ParseError):
        normalize(script)


@pytest.mark.parametrize('script', [
    'GIT_CONFIG_VALUE_0="$VALUE" git x',
    'env GIT_CONFIG_COUNT=$COUNT git x',
])
def test_dynamic_environment_fails_closed(script):
    from wuwei.shell import ParseError, normalize
    with pytest.raises(ParseError):
        normalize(script)


def test_background_command_has_subshell_scope():
    from wuwei.shell import normalize
    assert [(item.argv, item.subshell) for item in normalize('cd /tmp & git push')] == [
        (['cd', '/tmp'], True), (['git', 'push'], False)]


def test_opaque_combined_node_eval_print():
    from wuwei.shell import ParseError, is_opaque, normalize
    assert is_opaque(["node", "-pe", 'run("git")'])
    with pytest.raises(ParseError):
        normalize("""node -pe 'run("git")'""")


@pytest.mark.parametrize('script', [
    # D1: expansions anywhere in guarded words, including the program word.
    'git {push,status}', 'gh pr {merge,list}', 'git p*sh -f', 'git p?sh -f',
    'git [p]ush -f', 'git push origin {main,HEAD}',
    '{git,echo} push', '/tmp/{git,gh} push',
    # D2: launchers that construct argv from external input.
    'xargs git push', 'xargs -0 -r -n 1 -P2 -I{} git push {}',
    'parallel git push ::: main', "parallel 'git push {}' ::: main",
    r'find . -exec git push -f \;', r'find . -execdir git push -f \;',
    r'find . -ok git push -f \;', r'find . -okdir git push -f \;',
    'find . -exec git push -f {} +',
    # D3: interpreter input, including here-doc bodies discarded by tokenization.
    "python3 <<'EOF'\nimport os; os.system('git push')\nEOF",
    "python3 - <<'EOF'\nimport os; os.system('gh pr merge')\nEOF",
    "echo 'import os; os.system(\"git push\")' | python3",
    "printf 'system(\"git push\")' | ruby -",
    # D4: quoted mentions in arbitrary, unsupported launchers/interpreters.
    "awk 'BEGIN {system(\"git push\")}'", "caffeinate sh -c 'git push'",
    "watch 'git push'", "osascript -e 'do shell script \"git push\"'",
    "fish -c 'git push'", "unknown-launcher 'prefix;gh pr merge'",
    # R1: every mention must be accounted for, even alongside an exposed command.
    'echo hi # git push\ngit status',
    'command -v git', 'git status > git.log', 'echo > gh.log',
    "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.x GIT_CONFIG_VALUE_0='!git push -f' git x",
    "env A='git push' git status", "sh -c 'git status' 'gh pr merge'",
    "sudo -u git gh pr list", "find git -exec echo hi \\;",
])
def test_unaccounted_guarded_mentions_fail_closed(script):
    from wuwei.shell import ParseError, normalize
    with pytest.raises(ParseError, match='run git or gh as a plain command'):
        normalize(script)


@pytest.mark.parametrize('argv,expected', [
    (['python3'], True), (['python3', '-I'], True), (['python3', '-'], True),
    (['node'], True), (['perl', '-w'], True), (['ruby', '-'], True),
    (['php'], True), (['lua', '-'], True),
    (['python3', '-m', 'pytest', '-q'], True), (['node', '-v'], True),
    (['python3', '--version'], True),
    (['python3', 'script.py'], False), (['node', 'script.js'], False),
    (['python3', '-c', 'print(1)'], False), (['node', '-e', 'safe()'], False),
])
def test_interpreter_stdin_is_opaque(argv, expected):
    from wuwei.shell import is_opaque
    assert is_opaque(argv) is expected


@pytest.mark.parametrize('script,word', [
    ("git commit -m '{git gh} * ? [ $ `literal`'", '{git gh} * ? [ $ `literal`'),
    ('gh pr list --search "{git gh} * ? ["', '{git gh} * ? ['),
    (r'git show \{git\}\*\?\[', '{git}*?['),
    ("git commit -m \"$(cat <<'EOF'\ngit and gh: {braces} * ? [ $V `literal`\nEOF\n)\"",
     'git and gh: {braces} * ? [ $V `literal`'),
])
def test_guarded_literal_arguments_remain_supported(script, word):
    from wuwei.shell import normalize
    assert normalize(script)[0].argv[-1] == word


@pytest.mark.parametrize('script', [
    'echo git\\\nhub', "sh -c 'echo git\\\nhub'",
    "git status; python3 <<'EOF'\nrun('gh pr merge')\nEOF",
])
def test_unwrap_cannot_discard_mentions(script):
    from wuwei.shell import ParseError, normalize
    with pytest.raises(ParseError):
        normalize(script)


@pytest.mark.parametrize('argv', [
    ['python3', '-', 'argument'], ['python3', '-W', 'ignore'],
    ['python3', '-Werror'], ['node', '--require', 'module'],
])
def test_interpreter_options_do_not_imply_a_script(argv):
    from wuwei.shell import is_opaque
    assert is_opaque(argv)


@pytest.mark.parametrize('script', [
    "sh -c 'echo git'hub'; gi'\"'t status\"",
    'sh -c "echo git\\\nhub; g\\\nit status"',
    "echo \"$(cat <<'git'\nsafe\ngit\n)\"",
    "echo > \"$(cat <<'git'\nsafe\ngit\n)\"",
])
def test_source_mentions_cannot_be_replaced_by_decoded_mentions(script):
    from wuwei.shell import ParseError, normalize
    with pytest.raises(ParseError):
        normalize(script)


@pytest.mark.parametrize('script', [
    '''caffeinate -i sh -c 'g""it push -f' ''',
    "flock /tmp/l -c 'gi''t push -f'",
    '''watch 'g""it push -f' ''',
    r'watch "gi\t push -f"',
])
def test_obfuscated_launcher_mentions_fail_closed(script):
    from wuwei.shell import ParseError, normalize
    with pytest.raises(ParseError):
        normalize(script)


@pytest.mark.parametrize('script', [
    "echo push | xargs g''it", r'echo push | xargs gi\t',
    "echo pr merge | xargs g''h", r'echo pr merge | xargs g\h',
])
def test_xargs_obfuscated_guarded_program_fails_closed(script):
    from wuwei.shell import ParseError, normalize
    with pytest.raises(ParseError):
        normalize(script)


@pytest.mark.parametrize('script', [
    'git log @{u}..HEAD', 'git rev-parse --abbrev-ref @{upstream}',
    'git reset --soft HEAD@{1}', 'git stash show stash@{0}',
    'git push origin main}',
])
def test_literal_git_braces_are_allowed(script):
    from wuwei.shell import normalize
    assert normalize(script)[0].argv == script.split()


@pytest.mark.parametrize('script', [
    'git {push,--force}', 'git pu{s,}h', 'git show HEAD@{1..3}',
])
def test_brace_expansion_fails_closed(script):
    from wuwei.shell import ParseError, normalize
    with pytest.raises(ParseError):
        normalize(script)


@pytest.mark.parametrize('script,expected', [
    ('ls .git', ['ls', '.git']),
    ('cat .git/HEAD', ['cat', '.git/HEAD']),
    ('rg text --exclude-dir=.git', ['rg', 'text', '--exclude-dir=.git']),
    ("find . -not -path './.git/*'", ['find', '.', '-not', '-path', './.git/*']),
    ("rg -g '!.git' text", ['rg', '-g', '!.git', 'text']),
])
def test_dot_git_paths_are_not_guarded_mentions(script, expected):
    from wuwei.shell import normalize
    assert normalize(script)[0].argv == expected


@pytest.mark.parametrize('header,expected', [
    ("gh pr comment 12 --body-file - <<'EOF'", [['gh', 'pr', 'comment', '12', '--body-file', '-']]),
    ("git commit -F - <<'EOF'", [['git', 'commit', '-F', '-']]),
    ("<<'EOF' /usr/bin/git commit -F -", [['/usr/bin/git', 'commit', '-F', '-']]),
    ("git commit -F - <<'EOF'; echo done", [['git', 'commit', '-F', '-'], ['echo', 'done']]),
    ("git commit -F - <<'EOF' | cat", [['git', 'commit', '-F', '-'], ['cat']]),
])
def test_plain_guarded_command_heredoc_is_data(header, expected):
    from wuwei.shell import normalize
    assert [item.argv for item in normalize(header + '\ngit and gh documentation\nEOF')] == expected


@pytest.mark.parametrize('script', [
    "git status; python3 <<'EOF'\ngit push\nEOF",
    "python3 <<'EOF'; git status\ngit push\nEOF",
    "git status | python3 <<'EOF'\ngit push\nEOF",
    "python3 <<'EOF' | git status\ngit push\nEOF",
    "git commit -F - <<'A'; python3 <<'B'\ngit documentation\nA\ngit push\nB",
])
def test_other_commands_cannot_borrow_guarded_heredoc_exemption(script):
    from wuwei.shell import ParseError, normalize
    with pytest.raises(ParseError):
        normalize(script)


@pytest.mark.parametrize('script,targets', [
    ('echo data > state.json', ['state.json']),
    ('>> events.jsonl', ['events.jsonl']),
    ('2>state.json echo data >>events.jsonl', ['state.json', 'events.jsonl']),
    ('cat <>state.json', ['state.json']),
    ('echo data &>state.json', ['state.json']),
    ('echo data >|state.json', ['state.json']),
    ('echo data >&state.json', ['state.json']),
    ('cat <state.json 2>&1', []),
    ("sh -c 'echo data > state.json' >events.jsonl", ['events.jsonl', 'state.json']),
    ('(echo data) >state.json', ['state.json']),
    ('echo data | tee log >state.json', ['state.json']),
])
def test_output_targets_survive_normalization(script, targets):
    from wuwei.shell import normalize
    assert sorted(path for item in normalize(script) for path in item.writes) == sorted(targets)


@pytest.mark.parametrize('script', [
    'tee "$TARGET"', 'mv source {state,events}.json',
    "sed -i 's/a/b/' $FILE", 'dd of=$TARGET', 'truncate -s0 $FILE',
    'cd "$DEST"', 'cd ../*', 'echo data >*.json',
    'xargs tee', 'xargs cp source', 'xargs truncate -s0',
])
def test_state_writer_dynamic_forms_fail_closed(script):
    from wuwei.shell import ParseError, normalize
    with pytest.raises(ParseError):
        normalize(script)


@pytest.mark.parametrize('script', ['python3 -m pytest -q', 'python -m pip install x',
                                    "python3 -c 'open(\"state.json\", \"w\")'"])
def test_normalization_leaves_interpreter_policy_to_guards(script):
    from wuwei.shell import normalize
    assert normalize(script)


@pytest.mark.parametrize('redirect', ['>!', '>>!', '2>!', '2>>!'])
def test_zsh_clobber_targets(redirect):
    from wuwei.shell import normalize
    assert normalize('echo x ' + redirect + ' state.json')[0].writes == ('state.json',)


@pytest.mark.parametrize('script', ['echo x > "$FILE"', 'echo x > "$git"',
                                    'echo x > "$gh"', 'tee "$FILE"',
                                    "sh -c 'tee \"$FILE\"'"])
def test_nonliteral_path_error_retains_type(script):
    from wuwei import shell
    with pytest.raises(shell.ParseError) as error:
        shell.normalize(script)
    assert type(error.value).__name__ == 'NonliteralPathError'


@pytest.mark.parametrize('script', ['cp *.py sub/', 'mv build/*.whl dist/',
    'tee *.log', 'truncate -s0 *.log', 'sed -i s/a/b/ *.log', 'dd of=*.log'])
def test_writer_globs_are_left_for_guard_expansion(script):
    from wuwei.shell import normalize
    assert normalize(script)[0].argv == script.split()


@pytest.mark.parametrize('kind', ['binary', 'large', 'directory', 'fifo', 'missing', 'unreadable'])
def test_script_text_skips_unreadable_or_non_script_files(tmp_path, monkeypatch, kind):
    import os
    from pathlib import Path
    from wuwei.shell import script_text

    path = tmp_path / 'run.sh'
    if kind == 'directory':
        path.mkdir()
    elif kind == 'fifo':
        os.mkfifo(path)
    elif kind != 'missing':
        path.write_bytes(b'\xff\x00' if kind == 'binary' else b'x' * (65537 if kind == 'large' else 1))
    if kind == 'unreadable':
        def denied(*args, **kwargs):
            raise PermissionError('unreadable script')
        monkeypatch.setattr(Path, 'open', denied)
    assert script_text('./run.sh', tmp_path) is None


LAUNCHER = __import__('pathlib').Path(__file__).resolve().parents[1] / 'bin/wuwei'


@pytest.mark.parametrize('text,expected', [
    ('x=$(pwd)\n', False), (LAUNCHER.read_text(), False),
    ('git push --force origin main\n', True), ('g"i"t push', True), ('\\git push', True),
    ('echo `git push`', True), ("$'\\x67it' push", False),
])
def test_script_mentions_judges_literal_tokens(text, expected):
    from wuwei.shell import mentions
    assert mentions(text, {'git', 'gh'}, script=True) is expected


@pytest.mark.parametrize('text, expected', [
    ('x=$(pwd)', False),
    ('x=$(pwd); echo $x', False),
    ('x="$(pwd)"; echo "$x"', False),
    ('x=$y', False),
    ('X=$(pwd) make test', False),
    ('x=$(pwd); $x push', True),
    ('x=$(pwd) $cmd', True),
    ('a=gi; x=$(pwd) ${a}t push', True),
    ('x=$(git rev-parse HEAD)', True),
    ('x=$(pwd) && git push', True),
    ('$DEST push', True),
])
def test_command_mentions_skips_assignment_words(text, expected):
    from wuwei.shell import mentions
    assert mentions(text, {'git', 'gh'}) is expected


def test_command_mentions_skips_assignment_for_any_names():
    from wuwei.shell import mentions
    assert mentions('x=$(pwd); echo $x', {'push', 'commit'}) is False


@pytest.mark.parametrize('text, expected', [
    ('for r in a b; do git -C $r remote get-url origin; done', False),
    ('git -C "$r" status', False),
    ('git -C$r status', False),
    ('gh -R $r issue list', False),
    ('gh --repo $r issue list', False),
    ('gh --repo=$r issue list', False),
    ('git --git-dir $d log -1', False),
    ('git --work-tree=$w status', False),
    ('git -C "$(cat repo.txt)" log -1 | head -5', False),
    ('git "$VERB" origin main', True),
    ('git -C $r $VERB', True),
    ('git -C "a b" "$VERB" origin main', True),
    ('git -c "x.y=a;b" "$VERB" origin main', True),
    ('git -c $cfg status', True),
    ('git log $ref', True),
    ('git p* -f origin main', True),
    ("sh -c 'git $VERB origin main'", True),
    ('git status; sh -c "$CMD"', True),
    ('for r in */; do git -C $r status; done', True),
    ('read v < f; git -C -C $v origin main', True),
    ('read v < f; git --work-tree -C $v origin main', True),
    ('read v < f; git --git-dir -C $v origin main', True),
    ('git -C a -C $r status', False),
])
def test_command_mentions_ignores_directory_values(text, expected):
    from wuwei.shell import mentions
    assert mentions(text, {'push', 'commit'}) is expected


def test_is_opaque_stdin():
    from wuwei.shell import is_opaque
    assert is_opaque(['python3', '-m', 'pytest', '-q']) is True
    assert is_opaque(['python3']) is True
    assert is_opaque(['python3', '-m', 'pytest', '-q'], stdin=False) is False
    assert is_opaque(['python3'], stdin=False) is False
    assert is_opaque(['python3', '-c', 'import os; os.system("git push")'], stdin=False)
    assert is_opaque(['xargs', 'git', 'push'], stdin=False)
    assert is_opaque(['node', '-e', 'run("gh pr merge 1")'], stdin=False)


def _launcher_workspace(tmp_path, monkeypatch, record=True):
    import shutil
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    root = tmp_path / 'workspace'
    (root / '.wuwei').mkdir(parents=True)
    (root / 'worktrees/ITEM-1').mkdir(parents=True)
    recorded = tmp_path / 'previous-plugin/bin/wuwei'
    other = tmp_path / 'other/bin/wuwei'
    for copy in (recorded, other):
        copy.parent.mkdir(parents=True)
        shutil.copy(LAUNCHER, copy)
    if record:
        (root / '.wuwei/executable').write_text(f'{recorded}\n')
    return root, recorded, other


@pytest.mark.parametrize('where', ['.', 'worktrees/ITEM-1'])
def test_script_path_treats_launcher_as_cli(tmp_path, monkeypatch, where):
    from wuwei.shell import script_path
    root, recorded, other = _launcher_workspace(tmp_path, monkeypatch)
    cwd = root / where
    for raw in (f'{LAUNCHER} state get', f'sh {LAUNCHER} state get', f'{recorded} build check ITEM-1'):
        assert script_path(raw, cwd) is None, raw
    assert script_path(f'{other} state get', cwd) == other


def test_script_path_without_pointer_reads_copy(tmp_path, monkeypatch):
    from wuwei.shell import script_path
    root, recorded, _ = _launcher_workspace(tmp_path, monkeypatch, record=False)
    assert script_path(f'{recorded} state get', root) == recorded


# Issue #347: (readonly, publishes, inline, written names .wuwei).
CLASSIFY = [
    ('cd .wuwei/ziran && for r in a b c; do cat $r/report.json; done', (True, False, False, False)),
    ('ls; ls days/x; cat days/x/decisions/D-1.md; grep -n rm config.toml', (True, False, False, False)),
    ('W=$(cat .wuwei/executable); $W plan session abc --take-over; $W mcp check',
     (False, False, False, False)),
    ('python3 -P -c \'import subprocess;r=subprocess.run(["git","log","-1"]);'
     'print(open("config.toml").read())\'', (False, False, True, False)),
    ('mkdir -p ../scratch && cd ../scratch && ls', (False, False, False, False)),
    ('for r in a b; do git -C $r push origin main; done', (False, True, False, False)),
    ('x=$(git push origin main)', (False, True, False, False)),
    ('G=git; $G push origin main', (False, True, False, False)),
    ('G=git; $G config core.hooksPath x', (False, True, False, False)),
    ('W=cat; for W in gh; do $W pr merge 1; done', (False, True, False, False)),
    ('echo x > .wuwei/days/d/state.json', (False, False, False, True)),
    ('for r in a; do echo x > .wuwei/days/d/state.json; done', (False, False, False, True)),
    ('echo x > .wuwei/days/$(date +%F)/state.json', (False, False, False, True)),
    ('echo x | tee $(ls -d .wuwei/days/d)/state.json', (False, False, False, True)),
    ('T="tee .wuwei/days/d/state.json"; echo x | $T', (False, False, False, True)),
    ('python3 -c \'open(".wuwei/days/d/state.json", "w")\'', (False, False, True, True)),
    ('$x push origin main', (False, True, False, False)),
    ('${TOOL} ${VERB} -f', (False, True, False, False)),
    ('$DEPLOY apply', (False, True, False, False)),
    ('timeout 5 git push origin main', (False, True, False, False)),
    (r'find . -exec git push \;',(False, True, False, False)),
    ("sh -c 'for r in a; do git push; done'", (False, True, False, False)),
    ('for r in a b; do git -C $r log -1; done', (False, False, False, False)),
    ('for r in a b; do git -C $r config core.hooksPath x; done', (False, True, False, False)),
    ('for r in a b; do git -C $r p; done', (False, True, False, False)),
    ('echo "unterminated', (False, True, False, False)),
    ('for f in *.py; do wc -l $f; done', (True, False, False, False)),
    ('sed -n 1,40p x', (True, False, False, False)),
    ('sed -i s/a/b/ x', (False, False, False, False)),
    ('cat cmds.txt | xargs git', (False, True, False, False)),
    ('echo "gh pr merge 17"', (True, False, False, False)),
    ('grep -n "git push" notes.md', (True, False, False, False)),
    ('git show HEAD:d.py | python3', (False, True, False, False)),
    ("python3 - <<'PYEOF'\nimport subprocess\nsubprocess.run(['gh', 'pr', 'merge'])\nPYEOF\n",
     (False, True, True, False)),
    ("cat <<'EOF' | bash\nls\nEOF\n", (False, True, False, False)),
    ('cat <<EOF\n$(git push)\nEOF\n', (False, True, False, False)),
    ('cat x | sh', (False, True, False, False)),
    ('eval ls', (False, True, False, False)),
    ('cat `ls`', (True, False, False, False)),
    ('find . -name x -delete', (False, False, False, False)),
    # #616: checksum tools only read their operands and print digests.
    *((f'{tool} .wuwei/days/d/decisions/gate-a-quality.md', (True, False, False, False))
      for tool in ('shasum -a 256', 'sha1sum', 'sha256sum', 'sha512sum', 'md5sum', 'cksum')),
    ('shasum x > .wuwei/days/d/state.json', (False, False, False, True)),
]


@pytest.mark.parametrize('command, expected', CLASSIFY)
def test_classify_table(command, expected):
    from wuwei.shell import classify
    shape = classify(command)
    assert (shape.readonly, shape.publishes, shape.inline, '.wuwei' in shape.written) == expected


def test_classify_deploy_publishers():
    from wuwei.shell import classify
    assert classify('for r in a; do kubectl apply -f $r; done', ('kubectl',)).publishes
    assert not classify('for r in a; do kubectl apply -f $r; done').publishes


@pytest.mark.parametrize('command, readonly', [
    ('cd .wuwei; for f in days/d/decisions/D-*.md; do echo "### $f"; cat $f; done; '
     'cat days/d/state.json', True),
    ('for f in a; do echo $f; done | grep x', True),
    ('for f in a; do cat .wuwei/days/d/state.json | python3 -m json.tool; done', True),
    ("echo 'echo x > .wuwei/days/d/state.json' | sh", False),
    ("for i in 1; do echo 'echo x > .wuwei/days/d/state.json'; done | sh", False),
    ('echo .wuwei/config.toml | bash -s', False),
])
def test_issue_470_echo_and_pipes(command, readonly):
    # #470: echo is a read word; text piped into a non-read command counts as written.
    from wuwei.shell import classify, unread
    shape = classify(command)
    if readonly:
        assert shape.readonly and unread(command) == (0, '')
    else:
        assert not shape.readonly and '.wuwei' in shape.written


def _git_kind_cases():
    from wuwei import shell
    forms = [(['branch'], 'read'), (['tag'], 'read'), (['remote'], 'read'),
             (['branch', '--list'], 'read'), (['tag', '-l'], 'read'), (['remote', '-v'], 'read'),
             (['remote', 'get-url', 'origin'], 'read'), (['stash', 'list'], 'read'),
             (['worktree', 'list'], 'read'), (['config', '--get', 'x'], 'read'),
             (['bisect', 'log'], 'read'), (['branch', '-D', 'x'], 'write'), (['tag', 'v1'], 'write'),
             (['remote', 'add', 'x', 'u'], 'write'), (['stash'], 'write'),
             (['stash', 'pop'], 'write'), (['config', 'x', 'y'], 'write')]
    return [*(([verb], 'read') for verb in sorted(shell._GIT_READS)),
            *(([verb], 'write') for verb in sorted(shell._GIT_WRITES - set(shell._GIT_READ_FORMS))),
            *forms, ([], 'read'), (['-C', 'r'], 'read'),
            (['-c', 'alias.x=log', 'x'], 'unknown'), (['--config-env=a=B', 'log'], 'unknown'),
            (['$v', 'x'], 'unknown'), (['frobnicate'], 'unknown'), (['grep', '-Ocmd', 'x'], 'unknown'),
            (['grep', '--open-files-in-pager=cmd', 'x'], 'unknown'),
            (['fetch', '--upload-pack=cmd', 'o'], 'unknown'),
            (['ls-remote', '-u', 'cmd', 'o'], 'unknown'), (['ls-remote', '-ucmd', 'o'], 'unknown'),
            (['-C', 'r', 'grep', '-n', 'x'], 'read'), (['branch', '-a', '-D', 'x'], 'write')]


@pytest.mark.parametrize('args, expected', _git_kind_cases())
def test_issue_470_git_kind(args, expected):
    from wuwei.shell import git_kind
    assert git_kind(args) == expected


@pytest.mark.parametrize('command, parses', [
    ('R=widget; git -C $R log --oneline', True),
    ('S=abc1; R=widget; git -C "${R}" log "$S"', True),
    ('S=abc1; git log $S..origin/main', False),
    ('R=1; gh run view $R -R o/r', True),
    ('R=widget; git -C $R push origin main', False),
    ("R='x push origin main'; git -C $R log", False),
    ('R=-Ocmd; git grep $R x', False),
    ('git -C $R log', False),
    ('R=widget; git -C $R$S log', False),
    ('R=1; gh pr merge $R', False),
    ('R=pr; gh $R list', False),
])
def test_issue_470_variable_reads(command, parses):
    from wuwei.shell import ParseError, normalize
    try:
        normalize(command)
    except ParseError:
        assert not parses
    else:
        assert parses


def test_issue_470_git_tables():
    from wuwei.shell import _GIT_READ_FORMS, _GIT_READS, git_kind
    assert not _GIT_READS & set(_GIT_READ_FORMS)
    deploy_main = ('status diff log show rev-parse branch tag fetch checkout switch add commit '
                   'restore reset rebase stash ls-files ls-remote remote config worktree help '
                   'version symbolic-ref describe show-ref').split()
    assert [verb for verb in deploy_main if git_kind([verb]) == 'unknown'] == []


@pytest.mark.parametrize('command, expected', [
    ('ls; ls days/x; cat days/x/decisions/D-1.md; grep -n rm config.toml', (0, '')),
    ('W=$(cat .wuwei/executable); $W plan session abc --take-over; $W mcp check', 'unparsed'),
    ('python3 -P -c \'import subprocess;r=subprocess.run(["git","log","-1"]);'
     'print(open("config.toml").read())\'', 'unparsed'),
    ('for r in a b; do git -C $r push origin main; done', None),
    ('python3 -m pytest -q && git status', None),
])
def test_unread_table(command, expected):
    from wuwei.shell import UNPARSED, unread
    assert unread(command) == ((2, UNPARSED) if expected == 'unparsed' else expected)


@pytest.mark.parametrize('command,expected', [
    ('bash loop.sh', 'script loop.sh'), ('./loop.sh', 'script loop.sh'),
    ('gh pr view $(git rev-parse --abbrev-ref HEAD)', 'command substitution is unsupported'),
    ("python3 -c 'print(1)'", 'inline interpreter code'),
    ('''python3 -c "print(['gh','pr','view'])"''', 'inline interpreter code'),
    ("python3 - <<'EOF'\nprint(1)\nEOF", 'inline interpreter code'),
    ('cat x | python3', 'python3 code from input'),
    ('gh pr view 7', ''), ('git status', ''), ('npm test', ''),
])
def test_unreadable_names_what_a_guard_cannot_read(tmp_path, command, expected):
    # #530: the opaque warning names what the guards could not read.
    from wuwei import shell
    assert shell.unreadable(command, tmp_path) == expected


@pytest.mark.parametrize('script', [
    'git</dev/null push origin main', 'git>/tmp/x push origin main',
    'gh</dev/null pr merge 1 --admin', 'git;/bin/true', '/usr/bin/git push', 'git-push',
    'git${IFS}push${IFS}main/x',
])
def test_redirect_glued_to_guarded_name_is_a_mention(script):
    # #508 review F1: only path-segment characters may hide a directory component.
    from wuwei import shell
    assert shell._GUARDED.search(script)


@pytest.mark.parametrize('script', ['/a/508-git-in/gh/github/git-tools/bin/wuwei', '~/git/x'])
def test_guarded_name_as_directory_is_no_mention(script):
    from wuwei import shell
    assert not shell._GUARDED.search(script)


_READ_643 = "import json,sys; print(json.load(open('.wuwei/state.json'))['day'])"


@pytest.mark.parametrize('argv, expected', [
    (['python3', '-c', _READ_643], ''), (['python3', '-c', "open('x.bin', 'rb').read()"], ''),
    (['python3', '-c', "from pathlib import Path; print(Path('.wuwei') / 'state.json')"], ''),
    (['python3', '-c', "print(open('cli/wuwei/shell.py').read())"], ''),
    (['python3', '-I', '-c', _READ_643], ''), (['python3', '-Bc', _READ_643], ''),
    (['python3', '-c', "open(p, 'w')"], "'w'"), (['python3', '-c', 'open(p, mode="a+")'], '"a+"'),
    (['python3', '-c', "open(p, 'r+')"], "'r+'"),
    (['python3', '-c', 'Path(p).write_text(x)'], 'write_text'),
    (['python3', '-c', 'import os; os.replace(a, b)'], 'replace'),
    (['python3', '-c', 'import shutil; shutil.copy(a, b)'], 'shutil'),
    (['python3', '-c', 'import subprocess; subprocess.run(x)'], 'subprocess'),
    (['python3', '-c', 'import os; os.system(x)'], 'system'),
    (['python3', '-c', 'import os; os.makedirs(x)'], 'makedirs'),
    (['python3', '-c', 'import ctypes'], 'ctypes'),
    (['python3', '-c', "from wuwei.commands import main; main(['decide'])"], 'wuwei'),
    (['python3', '-c', 'import json, wuwei'], 'wuwei'),
    (['python3', '-c', 'import cli.wuwei.commands'], 'wuwei'),
    (['python3', '-c', r"open(p,'\x77')"], '\\'), (['python3', '-c', 'open(p,chr(119))'], 'chr'),
    (['python3', '-c', 'import sys;open(sys.argv[1],sys.argv[2])', 'p', 'w'], 'argv'),
    (['python3', '-c', 'import logging;logging.FileHandler(p)'], 'logging'),
    (['python3', '-c', 'FileHandler(p)'], 'Handler'), (['python3', '-c', 't.extractall(d)'], 'extract'),
    (['python3', '-c', 'import tarfile'], 'tarfile'), (['python3', '-c', 'import zipfile'], 'zipfile'),
    (['python3', '-c', "open(p,'W')"], "'W'"), (['python3', '-c', 'open(p,m.lower())'], 'lower'),
    (['python3', '-c', "open(p,os.environ['M'])"], 'environ'),
    (['python3', '-c', 'open(p,sys.stdin.read())'], 'stdin'), (['python3', '-c', 'open(p,input())'], 'input'),
    (['python3', '-c', 'open(p,m.decode())'], 'decode'), (['python3', '-c', 'o.__class__'], '__'),
    (['python3', '-c', 'vars(o)'], 'vars'), (['python3', '-c', 'globals()'], 'globals'),
    (['python3', '-c', 'IMPORT SHUTIL'], 'SHUTIL'),
    (['python3', 'x.py'], None), (['python3', '-m', 'json.tool', 'f'], None),
    (['python3', '-i', '-c', 'x'], None), (['python3', '-cprint(1)'], None),
    (['python3', '-c'], None), (['node', '-e', 'x'], None), (['cat', '-c', 'x'], None), ([], None),
])
def test_issue_643_snippet_write(argv, expected):
    from wuwei import shell
    assert shell.snippet_write(argv) == expected
@pytest.mark.parametrize('raw,names,expected', [
    ('gi\\\nt push', ('git',), True), ('g\\\nh pr merge 5', ('gh',), True),
    ('sh -c "g\\\nit push"', ('git',), True), ('echo hi', ('git',), False),
])
def test_mentions_joins_line_continuations(raw, names, expected):
    # #671: the shell joins backslash-newline before it reads the program name.
    from wuwei.shell import mentions
    assert mentions(raw, names) is expected


@pytest.mark.parametrize('script,expected', [
    ("cat > brief.md <<'EOF'\nThe shepherd falls back to gh.\n"
     "Raise the PR with gh pr create; then git push.\nEOF", [['cat']]),
    ("echo 'falls back to gh' > notes.md", [['echo', 'falls back to gh']]),
    ('grep -rn "gh pr" docs | head -20', [['grep', '-rn', 'gh pr', 'docs'], ['head', '-20']]),
    ('echo "git push"', [['echo', 'git push']]),
    ("git status; cat <<'EOF'\ngit push\nEOF", [['git', 'status'], ['cat']]),
    ("cat <<'EOF' | git status\ngit push\nEOF", [['cat'], ['git', 'status']]),
    ("cat <<'EOF'\n$(git push -f)\nEOF\ngit status", [['cat'], ['git', 'status']]),
])
def test_reader_text_is_data(script, expected):
    # #671: a reader's arguments and here-doc body are text, not a command.
    from wuwei.shell import normalize
    assert [item.argv for item in normalize(script)] == expected


def test_reader_text_keeps_its_write_target():
    from wuwei.shell import normalize
    found = normalize("cat > brief.md <<'EOF'\nfalls back to gh\nEOF")
    assert found[0].writes == ('brief.md',)


@pytest.mark.parametrize('script', [
    "echo 'git push' | sh", "echo 'import os; os.system(\"git push\")' | python3",
    'echo "gh pr merge 5" | xargs -I@ sh -c @', "cat <<'EOF' | python3\ngit push\nEOF",
    "cat <<'EOF' | tee out\ngit push\nEOF", "mkdir -p d && echo 'git push' > d/x",
    "printf 'git push' > x",
])
def test_reader_text_that_can_run_fails_closed(script):
    # #671: one command that is not a reader or git or gh voids the exemption for the call.
    from wuwei.shell import ParseError, normalize
    with pytest.raises(ParseError):
        normalize(script)


@pytest.mark.parametrize('script', [
    'g""it push', 'sh -c "gi""t push"', "eval 'gi''t push'", 'gi\\\nt push',
    'sh -c "gi\'t\' push"', 'bash -c "g\'\\\nit\' push"', "sh -c 'g\"\"it push'",
])
def test_constructed_names_resolve(script):
    # #671: a quote-split or continued name is parsed to the command it runs.
    from wuwei.shell import normalize
    assert [item.argv for item in normalize(script)] == [['git', 'push']]


@pytest.mark.parametrize('script', ["eval 'echo git'hub", "sh -c 'echo git'hub"])
def test_split_word_in_eval_or_shell_is_its_value(script):
    from wuwei.shell import normalize
    assert [item.argv for item in normalize(script)] == [['echo', 'github']]


@pytest.mark.parametrize('script,expected', [
    ('g""it push', 'git push'), ('sh -c "gi""t push"', 'git push'),
    ('x=git; $x push', 'git push'), ('x=gi; ${x}t push', 'git push'),
    ('g\\\nh pr merge 5 --admin', 'gh pr merge'),
    ('git push', ''), ('/usr/bin/git push', ''), ('echo "git push"', ''),
    ('$(printf git) push', ''), ('ls', ''),
])
def test_constructed_names_the_command(script, expected):
    # #671: the git or gh command a call builds without spelling it; never a variable's value.
    from wuwei.shell import constructed
    assert constructed(script) == expected


def test_constructed_variable_takes_one_value_per_call():
    # #671 review F1: a repeated variable is one value, and the enumeration is capped.
    import time
    from wuwei.shell import constructed
    assert constructed('x=gi; x=t; $x$x push') == ''
    start = time.monotonic()
    constructed('c=x; c=y; c=z; c=; a=gi; b=t; ' + '$c' * 30 + '$a$b push')
    constructed('a=1; a=2; b=1; b=2; c=1; c=2; d=1; d=2; e=1; e=2; f=1; f=2; g=1; g=2; '
                + '$a$b$c$d$e$f$g push')
    assert time.monotonic() - start < 1


@pytest.mark.parametrize('script', [
    "echo '[alias] x = !git push' >> .git/config",
    "cat > .git/hooks/pre-commit <<'EOF'\ngh pr merge 1 --admin\nEOF",
    "cat > .GIT/hooks/pre-commit <<'EOF'\ngh pr merge 1 --admin\nEOF",
])
def test_reader_text_written_under_git_dir_is_not_data(script):
    # #671 review F2: text written into git's own files can run, so it is not data.
    from wuwei.shell import ParseError, normalize
    with pytest.raises(ParseError):
        normalize(script)


def test_named_command_is_not_unreadable():
    from wuwei.shell import unreadable
    assert unreadable('x=git; $x push') == ''
    assert unreadable('$(printf git) push') != ''
