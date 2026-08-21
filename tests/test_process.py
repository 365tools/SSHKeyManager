"""process 工具测试：run_checked / git 统一执行约定。"""

import subprocess
import sys

import pytest

from sshm.core.utils.process import git, run_checked


def test_run_checked_captures_output():
    result = run_checked([sys.executable, "-c", 'print("hi")'])
    assert result.returncode == 0
    assert result.stdout == "hi\n"


def test_run_checked_raises_on_failure():
    with pytest.raises(subprocess.CalledProcessError):
        run_checked([sys.executable, "-c", "raise SystemExit(3)"])


def test_git_builds_command(git_repo):
    # 在临时 git 仓库内执行 git 命令
    result = git(git_repo, "rev-parse", "--is-inside-work-tree")
    assert result.returncode == 0
    assert result.stdout.strip() == "true"


def test_git_fails_in_non_repo(tmp_path):
    with pytest.raises(subprocess.CalledProcessError):
        git(tmp_path, "rev-parse", "HEAD")
