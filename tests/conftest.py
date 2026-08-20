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
    """临时 Git 仓库（含一个初始提交）

    所有 git 操作使用「干净环境」：屏蔽外部 GIT_DIR 等污染变量（例如
    pre-commit 钩子内运行测试时 git 会设置 GIT_DIR），确保操作始终作用于
    本临时 mock 仓库，绝不触碰当前项目仓库。
    """
    repo = tmp_path / 'repo'
    repo.mkdir()

    # 移除全部 GIT_* 变量，彻底隔离外部 git 环境（hook 会设置 GIT_DIR、
    # GIT_INDEX_FILE、GIT_AUTHOR_*/GIT_COMMITTER_* 等，会污染临时 mock 仓库）
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}

    def git(*args: str):
        subprocess.run(['git', '-C', str(repo)] + list(args),
                       check=True, capture_output=True, text=True,
                       env=clean_env)

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
    from sshm.cli.app import app
    return CliRunner(), app
