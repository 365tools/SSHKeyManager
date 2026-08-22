"""keypaths 工具测试：密钥文件名匹配与路径构造。"""

from pathlib import Path

from sshm.core.services.ssh.keypaths import (
    get_key_pattern,
    key_paths,
    private_key_path,
    public_key_path,
)


def test_key_pattern_matches_valid_names():
    pattern = get_key_pattern()
    assert pattern.match("id_ed25519")
    assert pattern.match("id_ed25519.github")
    assert pattern.match("id_rsa")
    assert pattern.match("id_ecdsa.foo")
    assert not pattern.match("id_weird")
    assert not pattern.match("foo")


def test_key_file_default(tmp_path):
    assert private_key_path(tmp_path, "ed25519") == tmp_path / "id_ed25519"


def test_key_file_labeled(tmp_path):
    assert private_key_path(tmp_path, "ed25519", "github") == tmp_path / "id_ed25519.github"


def test_pub_key_file(tmp_path):
    assert public_key_path(tmp_path, "ed25519") == tmp_path / "id_ed25519.pub"
    assert public_key_path(tmp_path, "ed25519", "github") == tmp_path / "id_ed25519.github.pub"


def test_key_paths(tmp_path):
    priv, pub = key_paths(tmp_path, "ed25519", "github")
    assert priv == tmp_path / "id_ed25519.github"
    assert pub == tmp_path / "id_ed25519.github.pub"
    assert str(pub) == f"{priv}.pub"


def test_key_paths_return_type(tmp_path):
    priv, pub = key_paths(tmp_path, "rsa")
    assert isinstance(priv, Path) and isinstance(pub, Path)
