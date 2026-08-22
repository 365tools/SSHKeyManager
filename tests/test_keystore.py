"""KeyStore 单元测试：密钥文件扫描 / 检测 / 复制"""

from pathlib import Path

import pytest


@pytest.fixture
def ks(tmp_ssh_dir: Path):
    from sshm.core.services.ssh.keystore import KeyStore

    return KeyStore(tmp_ssh_dir)


@pytest.fixture
def sample_keys(tmp_ssh_dir: Path):
    """创建一组测试密钥文件"""
    (tmp_ssh_dir / "id_ed25519").write_bytes(b"priv")
    (tmp_ssh_dir / "id_ed25519.pub").write_text("ssh-ed25519 AAAA pub@email.com")
    (tmp_ssh_dir / "id_ed25519.work").write_bytes(b"priv-work")
    (tmp_ssh_dir / "id_ed25519.work.pub").write_text("ssh-ed25519 CCCC work@mail.com")
    (tmp_ssh_dir / "id_rsa").write_bytes(b"priv-rsa")
    (tmp_ssh_dir / "id_rsa.pub").write_text("ssh-rsa BBBB pub@work.com")
    # 非密钥文件（不应被扫描）
    (tmp_ssh_dir / "README").write_text("not a key")
    return tmp_ssh_dir


class TestEnsureDirectories:
    def test_creates_dir(self, tmp_path):
        from sshm.core.services.ssh.keystore import KeyStore

        d = tmp_path / ".ssh"
        KeyStore(d).ensure_directories()
        assert d.is_dir()


class TestScanAllKeys:
    def test_groups_by_label(self, ks, sample_keys):
        result = ks.scan_all_keys()
        assert "default" in result
        assert "work" in result
        # default: id_ed25519（无标签后缀），也可能有 id_rsa（同为 default）
        assert "work" in result

    def test_key_info_fields(self, ks, sample_keys):
        result = ks.scan_all_keys()
        info = result["default"][0]
        assert info["type"] in ("ed25519", "rsa")
        assert info["private"].name.startswith("id_")
        assert info["has_pub"] is True
        assert info["size"] > 0

    def test_ignores_non_key_files(self, ks, sample_keys):
        # README 不应出现在结果中
        all_priv = [i["private"].name for infos in ks.scan_all_keys().values() for i in infos]
        assert "README" not in all_priv

    def test_empty_dir(self, ks):
        assert ks.scan_all_keys() == {}


class TestDetectKeyType:
    def test_detect_for_label(self, ks, sample_keys):
        assert ks.detect_key_type_for_label("work") == "ed25519"

    def test_detect_missing_label(self, ks, sample_keys):
        assert ks.detect_key_type_for_label("nope") is None

    def test_detect_default(self, ks, sample_keys):
        assert ks.detect_default_key_type() in ("ed25519", "rsa")

    def test_detect_default_none(self, ks):
        assert ks.detect_default_key_type() is None


class TestCopyKeyPair:
    def test_copies_private_and_public(self, ks, sample_keys, tmp_ssh_dir):
        source = tmp_ssh_dir / "id_ed25519.work"
        target = tmp_ssh_dir / "id_ed25519.copied"
        ks.copy_key_pair(source, target)
        assert target.exists()
        assert Path(str(target) + ".pub").exists()

    def test_copies_private_only_when_no_pub(self, ks, tmp_ssh_dir):
        # 只有私钥无公钥：复制私钥，不报错
        source = tmp_ssh_dir / "id_ed25519.nopub"
        source.write_bytes(b"x")
        target = tmp_ssh_dir / "id_ed25519.copied2"
        ks.copy_key_pair(source, target)
        assert target.exists()
        assert not Path(str(target) + ".pub").exists()

    def test_copy_preserves_content(self, ks, tmp_ssh_dir):
        source = tmp_ssh_dir / "id_ed25519.src"
        source.write_bytes(b"secret-content")
        target = tmp_ssh_dir / "id_ed25519.dst"
        ks.copy_key_pair(source, target)
        assert target.read_bytes() == b"secret-content"


class TestExtractEmailFromPubkey:
    def test_extracts_from_ed25519(self, ks, sample_keys):
        assert ks.extract_email_from_pubkey("ed25519") == "pub@email.com"

    def test_extracts_from_rsa(self, ks, sample_keys):
        assert ks.extract_email_from_pubkey("rsa") == "pub@work.com"

    def test_missing_key_returns_none(self, ks):
        # 目录中无任何密钥，读不到公钥
        assert ks.extract_email_from_pubkey("ed25519") is None

    def test_invalid_comment_returns_none(self, ks, tmp_ssh_dir):
        (tmp_ssh_dir / "id_ecdsa.pub").write_text("ssh-ecdsa ABC not-an-email")
        assert ks.extract_email_from_pubkey("ecdsa") is None
