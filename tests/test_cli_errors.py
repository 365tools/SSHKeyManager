"""CLI 错误处理测试：残缺指令、非法指令、非法参数"""
import pytest


def test_unknown_command(cli_runner):
    """未知指令应报错退出（非零）"""
    runner, app = cli_runner
    result = runner.invoke(app, ['nonexistent-command'])
    assert result.exit_code != 0


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
        manager.add_key('x', 'a@b.com', key_type='invalid-type')


def test_add_invalid_email(cli_runner, manager):
    """非法邮箱应报错"""
    with pytest.raises(ValueError):
        manager.add_key('x', 'not-an-email')


def test_add_duplicate_key(cli_runner, tmp_ssh_dir):
    """重复密钥应报错"""
    from sshm.core.manager import SSHKeyManager
    m = SSHKeyManager(ssh_dir=tmp_ssh_dir)
    # 手工创建密钥文件（避免依赖 ssh-keygen 慢）
    (tmp_ssh_dir / 'id_ed25519.github').write_bytes(b'k')
    (tmp_ssh_dir / 'id_ed25519.github.pub').write_bytes(b'p a@b.com')
    with pytest.raises(ValueError):
        m.add_key('github', 'a@b.com')


def test_use_nonexistent_label(cli_runner, manager, git_repo):
    """使用不存在的标签应报错（_had_error）"""
    manager.use_key_for_repo('nonexistent', str(git_repo), skip_confirm=True)
    assert manager._had_error is True


def test_fix_author_requires_match(cli_runner, manager, git_repo):
    """fix_author 无匹配条件应报错（_had_error 置位）"""
    manager.fix_author(str(git_repo))
    assert manager._had_error is True
