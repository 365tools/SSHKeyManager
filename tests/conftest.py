"""pytest 共享 fixtures：隔离真实 ~/.ssh 与 git 仓库"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

# 确保 src 在模块搜索路径
SRC = Path(__file__).resolve().parent.parent / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def tmp_ssh_dir(tmp_path: Path) -> Path:
    """每个测试独立的临时 SSH 目录（隔离真实 ~/.ssh）"""
    d = tmp_path / '.ssh'
    d.mkdir()
    return d


@pytest.fixture
def manager(tmp_ssh_dir: Path):
    """基于临时 SSH 目录的 SSHKeyManager 实例"""
    from sshm.core.manager import SSHKeyManager
    return SSHKeyManager(ssh_dir=tmp_ssh_dir)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """临时 Git 仓库（含一个初始提交）"""
    repo = tmp_path / 'repo'
    repo.mkdir()

    def git(*args: str):
        subprocess.run(['git', '-C', str(repo)] + list(args),
                       check=True, capture_output=True, text=True)

    git('init')
    git('config', 'user.email', 'test@example.com')
    git('config', 'user.name', 'Tester')
    (repo / 'file.txt').write_text('hello', encoding='utf-8')
    git('add', '.')
    git('commit', '-m', 'init')
    return repo


@pytest.fixture
def cli_runner():
    """Typer CLI 测试运行器"""
    from typer.testing import CliRunner
    from sshm.cli.cli import app
    return CliRunner(), app
