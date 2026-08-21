"""历史重写测试：验证 author fix 的完整流程与 detached HEAD 修复"""

import os
import subprocess
from pathlib import Path

import pytest

from sshm.core.services.git.rewrite import (
    RewriteConfig,
    get_authors_in_repo,
    rewrite_history,
)


# 清除全部 GIT_* 污染变量：测试必须操作隔离的临时仓库（mock 项目），
# 绝不碰当前项目仓库。在 git hook（如 pre-commit）内运行时 git 会设置
# GIT_DIR、GIT_INDEX_FILE、GIT_AUTHOR_*/GIT_COMMITTER_* 等变量，若不清除
# 会导致 -C <repo> 失效、重写落到当前仓库，或提交作者被环境变量覆盖。
def _clean_env() -> dict:
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("GIT_"):
            env.pop(key, None)
    return env


def git(repo: Path, *args):
    return subprocess.run(
        ["git", "-C", str(repo)] + list(args),
        capture_output=True,
        text=True,
        env=_clean_env(),
    )


def setup_repo_with_commits(tmp_path: Path, authors):
    """创建含多作者提交的临时仓库"""
    repo = tmp_path / "r"
    repo.mkdir()
    for name, email in authors:
        git(repo, "init") if not (repo / ".git").exists() else None
        git(repo, "config", "user.name", name)
        git(repo, "config", "user.email", email)
        git(repo, "commit", "--allow-empty", "-m", f"by {name}")
    return repo


class TestRewrite:
    def test_rewrite_name(self, tmp_path):
        repo = setup_repo_with_commits(tmp_path, [("Old", "old@x.com")])
        r = rewrite_history(repo, RewriteConfig(old_name="Old", new_name="New"))
        assert r["matched_commits"] >= 1
        log = git(repo, "log", "--format=%an").stdout
        assert "New" in log
        assert "Old" not in log

    def test_rewrite_email(self, tmp_path):
        repo = setup_repo_with_commits(tmp_path, [("Alice", "alice@x.com")])
        r = rewrite_history(
            repo, RewriteConfig(old_email="alice@x.com", new_email="new@x.com")
        )
        assert r["matched_commits"] >= 1
        log = git(repo, "log", "--format=%ae").stdout
        assert "new@x.com" in log

    def test_rewrite_keeps_branch_attached(self, tmp_path):
        """重写后不应处于 detached HEAD（关键回归）"""
        repo = setup_repo_with_commits(tmp_path, [("Old", "old@x.com")])
        rewrite_history(repo, RewriteConfig(old_name="Old", new_name="New"))
        branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        assert branch in ("main", "master"), f"detached: {branch}"

    def test_rewrite_no_match(self, tmp_path):
        repo = setup_repo_with_commits(tmp_path, [("Alice", "a@x.com")])
        r = rewrite_history(repo, RewriteConfig(old_name="Nobody", new_name="X"))
        assert r["matched_commits"] == 0

    def test_rewrite_requires_old(self, tmp_path):
        repo = setup_repo_with_commits(tmp_path, [("Alice", "a@x.com")])
        with pytest.raises(ValueError):
            rewrite_history(repo, RewriteConfig())


class TestRewriteMatchAll:
    """--author <label> 的全量刷新模式：把历史所有作者统一为目标。"""

    def test_match_all_unifies_authors(self, tmp_path):
        """多作者历史全量刷新为同一目标 name/email"""
        repo = setup_repo_with_commits(
            tmp_path, [("Alice", "a@x.com"), ("Bob", "b@x.com"), ("Carol", "c@x.com")]
        )
        r = rewrite_history(
            repo, RewriteConfig(match_all=True, new_name="Unified", new_email="u@x.com")
        )
        assert r["matched_commits"] > 0
        assert r["rewritten"] > 0
        log = git(repo, "log", "--format=%an|%ae").stdout
        for line in log.splitlines():
            name, email = line.split("|")
            assert name == "Unified"
            assert email == "u@x.com"

    def test_match_all_requires_new(self, tmp_path):
        """match_all 模式必须提供 new_name 或 new_email"""
        repo = setup_repo_with_commits(tmp_path, [("Alice", "a@x.com")])
        with pytest.raises(ValueError):
            rewrite_history(repo, RewriteConfig(match_all=True))

    def test_match_all_name_keeps_email(self, tmp_path):
        """--name NEW 单值全量：只刷 name，email 保持不变"""
        repo = setup_repo_with_commits(
            tmp_path, [("Alice", "a@x.com"), ("Bob", "b@x.com")]
        )
        r = rewrite_history(repo, RewriteConfig(match_all=True, new_name="Unified"))
        assert r["rewritten"] > 0
        log = git(repo, "log", "--format=%an|%ae").stdout
        for line in log.splitlines():
            name, email = line.split("|")
            assert name == "Unified"
            assert email in ("a@x.com", "b@x.com")

    def test_match_all_email_keeps_name(self, tmp_path):
        """--email NEW 单值全量：只刷 email，name 保持不变"""
        repo = setup_repo_with_commits(
            tmp_path, [("Alice", "a@x.com"), ("Bob", "b@x.com")]
        )
        r = rewrite_history(repo, RewriteConfig(match_all=True, new_email="u@x.com"))
        assert r["rewritten"] > 0
        log = git(repo, "log", "--format=%an|%ae").stdout
        for line in log.splitlines():
            name, email = line.split("|")
            assert email == "u@x.com"
            assert name in ("Alice", "Bob")


class TestSplitPair:
    """author fix 成对参数 --name/--email 的 OLD:NEW / NEW 解析。"""

    def _split(self, value):
        from sshm.core.commands.history import HistoryCommands

        return HistoryCommands._split_pair(value)

    def test_single_value_is_full_rewrite(self):
        """单值（无冒号）→ (None, NEW)，表示全量刷新"""
        assert self._split("NewName") == (None, "NewName")
        assert self._split("new@x.com") == (None, "new@x.com")

    def test_pair_value_is_precise_replace(self):
        """OLD:NEW → (OLD, NEW)，表示用 NEW 替换 OLD"""
        assert self._split("Old:New") == ("Old", "New")
        assert self._split("alice@x.com:new@x.com") == ("alice@x.com", "new@x.com")

    def test_empty_value(self):
        """空值/None → (None, None)"""
        assert self._split(None) == (None, None)
        assert self._split("") == (None, None)

    def test_multi_colon_keeps_rest(self):
        """含多个冒号时只在第一个冒号处切分（name 允许含冒号）"""
        assert self._split("A:B:C") == ("A", "B:C")


class TestRewriteExcludesOriginalRefs:
    """回归：重写产生的 refs/original/ 备份不应再被 --all 系列操作扫到。

    此前 bug：rewrite_history 用 `git fast-export --all` 导出、get_authors_in_repo
    用 `git log --all`，都会把 refs/original/（旧历史备份）纳入范围，导致：
    - 重写后 `author fix` 预览仍列出旧作者；
    - 再次 fix 时 matched 计数反复命中旧备份，永远改不干净。
    """

    def _run_git(self, repo: Path, *args):
        return subprocess.run(
            ["git", "-C", str(repo)] + list(args),
            capture_output=True,
            text=True,
            env=_clean_env(),
        )

    def test_authors_after_rewrite_ignores_backup(self, tmp_path):
        """重写邮箱后，预览不应再从 refs/original 看到旧邮箱。"""
        repo = setup_repo_with_commits(
            tmp_path, [("Old", "old@x.com"), ("Old", "old@x.com")]
        )
        rewrite_history(
            repo, RewriteConfig(old_email="old@x.com", new_email="new@x.com")
        )
        # 确认备份命名空间确实存在（这是触发 bug 的前提）
        refs = self._run_git(repo, "for-each-ref", "--format=%(refname)").stdout
        assert any(r.startswith("refs/original/") for r in refs.splitlines())

        # 修复后：真实历史与预览都不再包含旧邮箱
        log = self._run_git(repo, "log", "--format=%ae").stdout
        assert "old@x.com" not in log
        assert "new@x.com" in log
        authors = get_authors_in_repo(repo)
        assert not any("old@x.com" in a for a in authors)

    def test_second_rewrite_no_false_positive(self, tmp_path):
        """第二次 fix（已无可匹配项）不应因 refs/original 虚报匹配。"""
        repo = setup_repo_with_commits(tmp_path, [("Alice", "a@x.com")])
        rewrite_history(repo, RewriteConfig(old_name="Alice", new_name="Bob"))
        # 已全部重写，再匹配旧名应为 0（此前会从 refs/original 误报命中）
        r = rewrite_history(repo, RewriteConfig(old_name="Alice", new_name="Carol"))
        assert r["matched_commits"] == 0
        assert r["rewritten"] == 0
