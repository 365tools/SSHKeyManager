"""CLI 错误处理测试：残缺指令、非法指令、非法参数"""
import pytest


def test_unknown_command(cli_runner):
    """未知指令应报错退出（非零）"""
    runner, app = cli_runner
    result = runner.invoke(app, ['nonexistent-command'])
    assert result.exit_code != 0


# --------------------------------------------------------------------------
# 未知命令"你是不是要找"建议（cli.suggest）
# --------------------------------------------------------------------------

def test_suggest_unknown_top_level():
    """未知顶层命令应给出相近子命令全路径建议（如 list → key list 等）"""
    from sshm.cli import suggest
    assert suggest.suggest(['list']) == [
        'sshm key list', 'sshm backup list', 'sshm author list']


def test_suggest_group_typo():
    """顶层分组拼写错误应建议相近分组"""
    from sshm.cli import suggest
    assert suggest.suggest(['keyz']) == ['sshm key']


def test_suggest_subcommand_typo_in_group():
    """组内子命令拼写错误只在该组内建议"""
    from sshm.cli import suggest
    assert suggest.suggest(['key', 'lst']) == ['sshm key list']


def test_suggest_no_match_no_suggestion():
    """无相近候选时返回空列表（提示查看 --help，而非误导）"""
    from sshm.cli import suggest
    assert suggest.suggest(['key', 'qwerty']) == []


def test_suggest_valid_commands_return_none():
    """合法命令路径返回 None，不应干预正常解析"""
    from sshm.cli import suggest
    assert suggest.suggest(['key', 'list']) is None
    assert suggest.suggest(['key']) is None
    assert suggest.suggest(['key', 'create', 'mylabel', 'a@b.com']) is None
    assert suggest.suggest(['config', 'language', 'en']) is None


def test_suggest_help_flags_not_interfered():
    """帮助/版本选项不应被建议逻辑干预"""
    from sshm.cli import suggest
    assert suggest.suggest(['--help']) is None
    assert suggest.suggest(['--version']) is None
    assert suggest.suggest(['-h', 'list']) is None


def test_render_error_structure_top_level(capsys):
    """顶层未知命令的错误渲染结构：
    错误消息无上方分隔线，随后 💡 Did you mean 块 + 💡 More commands 块，
    各块之间以分隔线衔接。"""
    from sshm.cli import suggest

    suggest.render_error(['list'], ['sshm key list', 'sshm backup list',
                                    'sshm author list'])
    out = capsys.readouterr().out

    # 顶部先空一行（与常规命令输出一致），随后才是 ❌ 错误消息（上方无分隔线）
    assert out.startswith('\n❌ No such command'), repr(out[:120])
    # 💡 Did you mean 块（建议行带 ➖ 前缀）
    assert '💡 Did you mean:' in out
    assert '➖ sshm key list' in out
    # 💡 More commands 块（顶层展示分组）
    assert '💡 More commands in this group' in out
    assert '➖ sshm key' in out


def test_render_error_structure_in_group(capsys):
    """组内未知子命令的错误：More commands 展示该分组的命令清单。"""
    from sshm.cli import suggest

    suggest.render_error(['key', 'lst'], ['sshm key list'])
    out = capsys.readouterr().out

    assert '❌ No such command' in out
    assert "in group 'key'" in out
    assert '💡 Did you mean:' in out
    assert '➖ sshm key list' in out
    # 组内错误 → 展示 key 组命令
    assert '💡 More commands in this group' in out
    assert '➖ sshm key create' in out


def test_render_usage_error_missing_argument(capsys):
    """缺必填参数：统一 ❌ 渲染 + 用法提示，而非 Click 原生面板。"""
    from click.exceptions import UsageError
    from sshm.cli import suggest

    exc = UsageError('Missing argument')
    suggest.render_usage_error(exc, ['key', 'switch'])
    out = capsys.readouterr().out

    # 统一模板：❌ 错误消息开头（非 ┌─ Error 面板）
    assert '┌─ Error' not in out
    assert '❌' in out
    # 用法提示块
    assert '💡' in out


def test_render_usage_error_missing_parameter_shows_usage_and_commands(capsys):
    """缺必填参数应额外展示该命令所需参数 + 同组相关命令。"""
    from sshm.cli import suggest

    # 用真实 Typer app + standalone_mode=False 触发真实 MissingParameter
    # （模拟 `sshm key switch` 缺 LABEL），再交给统一渲染
    import sys
    from unittest import mock

    from sshm.cli.app import app

    exc = None
    with mock.patch.object(sys, 'argv', ['sshm', 'key', 'switch']):
        try:
            app(standalone_mode=False)
        except Exception as e:  # noqa: BLE001 - 捕获任意 Click 用法异常用于测试
            exc = e
    assert exc is not None
    assert type(exc).__name__ == 'MissingParameter'

    suggest.render_usage_error(exc, ['key', 'switch'])
    out = capsys.readouterr().out

    # 缺参数 → 展示完整签名 + 每参数含义（必填/可选 + 枚举支持值）
    assert '💡 Usage: sshm key switch <LABEL> [--type/-t ed25519|rsa|ecdsa|dsa]' in out
    assert 'Required  key label' in out
    assert '[--type/-t ed25519|rsa|ecdsa|dsa]' in out
    assert 'Optional  key type (default: auto-detect)' in out
    # 相关命令（带 ➖ 前缀）：key switch 显式关联跨组 repo use（为仓库配置密钥），
    # 而非默认的同组其余命令
    assert '💡 More commands in this group' in out
    assert '➖ sshm repo use' in out
    assert 'configure a key for a Git repo' in out


def test_render_usage_error_bad_parameter(capsys):
    """非法枚举值：保留 Click 的错误文案，套统一 ❌ 模板。"""
    from click.exceptions import BadParameter
    from sshm.cli import suggest

    exc = BadParameter("'x' is not one of 'a', 'b'.")
    suggest.render_usage_error(exc, ['key', 'create', 'l', 'e', '--type', 'x'])
    out = capsys.readouterr().out

    assert '┌─ Error' not in out
    assert '❌' in out
    assert "not one of" in out
    assert '💡' in out


def test_render_usage_error_unknown_command_reuses_suggestion(capsys):
    """未知命令的 UsageError 应复用完整命令建议。"""
    from click.exceptions import UsageError
    from sshm.cli import suggest

    suggest.render_usage_error(UsageError('No such command'),
                               ['key', 'lst'])
    out = capsys.readouterr().out

    assert '💡 Did you mean:' in out
    assert '➖ sshm key list' in out


def test_add_missing_args(cli_runner):
    """add 缺少必填参数应报错"""
    runner, app = cli_runner
    # 只给 label 不给 email
    result = runner.invoke(app, ['add', 'mylabel'])
    assert result.exit_code != 0


def test_add_invalid_key_type(cli_runner, manager):
    """非法密钥类型应报错"""
    from sshm.core.manager import SSHKeyManager
    with pytest.raises(ValueError):
        manager.key.create('x', 'a@b.com', key_type='invalid-type')


def test_add_invalid_email(cli_runner, manager):
    """非法邮箱应报错"""
    with pytest.raises(ValueError):
        manager.key.create('x', 'not-an-email')


def test_add_duplicate_key(cli_runner, tmp_ssh_dir):
    """重复密钥应报错"""
    from sshm.core.manager import SSHKeyManager
    m = SSHKeyManager(ssh_dir=tmp_ssh_dir)
    # 手工创建密钥文件（避免依赖 ssh-keygen 慢）
    (tmp_ssh_dir / 'id_ed25519.github').write_bytes(b'k')
    (tmp_ssh_dir / 'id_ed25519.github.pub').write_bytes(b'p a@b.com')
    with pytest.raises(ValueError):
        m.key.create('github', 'a@b.com')


def test_use_nonexistent_label(cli_runner, manager, git_repo):
    """使用不存在的标签应报错（_had_error）"""
    manager.repo.use('nonexistent', str(git_repo), skip_confirm=True)
    assert manager._had_error is True


def test_fix_author_requires_match(cli_runner, manager, git_repo):
    """fix_author 无匹配条件应报错（_had_error 置位）"""
    manager.history.rewrite(str(git_repo))
    assert manager._had_error is True
