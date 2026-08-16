"""manager 单元测试：用临时 SSH 目录隔离，不触碰真实 ~/.ssh"""
import pytest
from pathlib import Path


class TestStatePersistence:
    def test_write_read_host(self, manager):
        manager.state_manager.write_host('work', 'gitlab.private.com')
        assert manager.state_manager.read_hosts()['work'] == 'gitlab.private.com'

    def test_write_read_author(self, manager):
        manager.state_manager.write_author('work', 'Alice', 'a@x.com')
        assert manager.state_manager.read_authors()['work'] == {
            'name': 'Alice', 'email': 'a@x.com'}

    def test_active_key(self, manager):
        manager.state_manager.write_active_key('ed25519', 'work')
        assert manager.state_manager.read_active_keys()['ed25519'] == 'work'

    def test_auto_author_default_true(self, manager):
        assert manager.state_manager.read_auto_author() is True

    def test_auto_author_toggle(self, manager):
        manager.state_manager.write_auto_author(False)
        assert manager.state_manager.read_auto_author() is False


class TestAutoAuthor:
    def test_set_get(self, manager):
        manager.set_auto_author(False)
        assert manager.state_manager.read_auto_author() is False
        manager.set_auto_author(True)
        assert manager.state_manager.read_auto_author() is True


class TestLabelValidation:
    def test_add_key_sshkeygen_called(self, manager, tmp_ssh_dir, monkeypatch):
        """add_key 应调用 ssh-keygen 并持久化 host"""
        calls = []
        import subprocess
        def fake_run(cmd, **kw):
            calls.append(cmd)
            # 模拟生成密钥文件
            name = cmd[cmd.index('-f') + 1]
            Path(name).write_bytes(b'k')
            Path(name + '.pub').write_bytes(b'p a@b.com')
            return subprocess.CompletedProcess(cmd, 0, b'', b'')
        monkeypatch.setattr('sshm.core.commands.keys.subprocess.run', fake_run)
        manager.add_key('work', 'a@b.com')
        assert any('ssh-keygen' in c for c in calls)
        # host 已持久化（默认 github.com）
        assert manager.state_manager.read_hosts()['work'] == 'github.com'

    def test_add_key_invalid_type(self, manager):
        with pytest.raises(ValueError):
            manager.add_key('x', 'a@b.com', key_type='dsa-invalid')

    def test_add_key_invalid_email(self, manager):
        with pytest.raises(ValueError):
            manager.add_key('x', 'not-an-email')


class TestKeyDetection:
    def _create_keys(self, tmp_ssh_dir, key_type, label):
        for ext in ('', '.pub'):
            p = tmp_ssh_dir / f'id_{key_type}.{label}{ext}'
            p.write_bytes(b'k')

    def test_detect_key_type(self, manager, tmp_ssh_dir):
        self._create_keys(tmp_ssh_dir, 'ed25519', 'github')
        assert manager._detect_key_type_for_label('github') == 'ed25519'

    def test_list_keys_output(self, manager, tmp_ssh_dir, capsys):
        self._create_keys(tmp_ssh_dir, 'ed25519', 'github')
        manager.list_keys()
        out = capsys.readouterr().out
        assert 'github' in out


class TestVersion:
    def test_version_from_changelog(self):
        from sshm.constants import VERSION
        assert isinstance(VERSION, str)
        assert VERSION.count('.') >= 1
