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
    ('''/usr/bin/python3 -I -c 'run("git push")' ''', True),
    ('''node -e 'run("git push")' ''', True),
    ('''perl -e 'system("gh pr merge")' ''', True),
    ('''ruby -e 'system("git push")' ''', True),
    ('''env X=y bash -c 'python3 -c "run(\\\"git push\\\")"' ''', True),
    ('''python -c 'print("legit text")' ''', False),
    ('''python3 -c 'print("github")' ''', False),
    ('''echo 'python -c git push' ''', True),
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


def test_nested_script_continuation_cannot_hide_obfuscated_mention():
    from wuwei.shell import ParseError, normalize
    script = 'bash -c "g\'\\\nit\' push"'
    with pytest.raises(ParseError):
        normalize(script)


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
    'git status; echo "git push"', 'echo hi # git push\ngit status',
    'command -v git', 'git status > git.log', 'echo > gh.log',
    "cat <<'EOF'\n$(git push -f)\nEOF\ngit status",
    'cat <<"EOF"\ngit push -f\nEOF\ngit status',
    "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.x GIT_CONFIG_VALUE_0='!git push -f' git x",
    "env A='git push' git status", "sh -c 'git status' 'gh pr merge'",
    "sudo -u git gh pr list", "find git -exec echo hi \\;",
    'echo "git push"',  # Intentional false positive under the fail-closed rule.
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
    "/git/eval 'echo safe'", "/gh/busybox sh -c 'echo safe'",
    "eval 'echo git'hub", "sh -c 'echo git'hub",
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
    '''sh -c "gi't' push"''',
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
    "git status; cat <<'EOF'\ngit push\nEOF",
    "cat <<'EOF'; git status\ngit push\nEOF",
    "git status | cat <<'EOF'\ngit push\nEOF",
    "cat <<'EOF' | git status\ngit push\nEOF",
    "git commit -F - <<'A'; cat <<'B'\ngit documentation\nA\ngit push\nB",
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


def test_command_mentions_still_counts_substitutions():
    from wuwei.shell import mentions
    assert mentions('x=$(pwd)', {'git', 'gh'}) is True


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
