"""CLI 帮助测试：验证所有命令/子命令的 --help 正常生成"""
import pytest


@pytest.mark.parametrize('args', [
    ['list'], ['backup'], ['backups'], ['add'], ['remove'], ['tag'],
    ['rename'], ['use'], ['clone'], ['info'], ['test'], ['auto-author'],
    ['author'], ['lang'], ['update'],
])
def test_help_command(args, cli_runner):
    """每个一级命令的 --help 都能正常生成"""
    runner, app = cli_runner
    result = runner.invoke(app, args + ['--help'])
    assert result.exit_code == 0, f"{args} help failed: {result.exception}"
    assert 'Usage' in result.output


@pytest.mark.parametrize('args', [
    ['author', 'list'], ['author', 'add'], ['author', 'remove'],
    ['author', 'use'], ['author', 'unset'], ['author', 'fix'],
])
def test_author_subcommands_help(args, cli_runner):
    """author 各子命令的 --help 正常"""
    runner, app = cli_runner
    result = runner.invoke(app, args + ['--help'])
    assert result.exit_code == 0, f"{args} help failed: {result.exception}"
    assert 'Usage' in result.output


def test_main_help_lists_all_commands(cli_runner):
    """主 --help 包含所有命令"""
    runner, app = cli_runner
    result = runner.invoke(app, ['--help'])
    assert result.exit_code == 0
    for cmd in ['list', 'add', 'remove', 'tag', 'rename', 'backup', 'backups',
                'restore', 'use', 'clone', 'info', 'test', 'auto-author',
                'author', 'lang', 'update']:
        assert cmd in result.output, f"{cmd} missing from help"


def test_version_flag(cli_runner):
    """-v / --version 输出版本"""
    from sshm.constants import VERSION
    runner, app = cli_runner
    r1 = runner.invoke(app, ['-v'])
    assert r1.exit_code == 0
    assert VERSION in r1.output
    r2 = runner.invoke(app, ['--version'])
    assert r2.exit_code == 0
    assert VERSION in r2.output
