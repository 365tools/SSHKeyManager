"""历史重写测试：验证 author fix 的完整流程与 detached HEAD 修复"""
import subprocess
from pathlib import Path

import pytest

from sshm.core.rewrite import RewriteConfig, rewrite_history


def git(repo: Path, *args):
    return subprocess.run(['git', '-C', str(repo)] + list(args),
                          capture_output=True, text=True)


def setup_repo_with_commits(tmp_path: Path, authors):
    """创建含多作者提交的临时仓库"""
    repo = tmp_path / 'r'
    repo.mkdir()
    for name, email in authors:
        git(repo, 'init') if not (repo / '.git').exists() else None
        git(repo, 'config', 'user.name', name)
        git(repo, 'config', 'user.email', email)
        git(repo, 'commit', '--allow-empty', '-m', f'by {name}')
    return repo


class TestRewrite:
    def test_rewrite_name(self, tmp_path):
        repo = setup_repo_with_commits(tmp_path, [('Old', 'old@x.com')])
        r = rewrite_history(repo, RewriteConfig(old_name='Old', new_name='New'))
        assert r['matched_commits'] >= 1
        log = git(repo, 'log', '--format=%an').stdout
        assert 'New' in log
        assert 'Old' not in log

    def test_rewrite_email(self, tmp_path):
        repo = setup_repo_with_commits(tmp_path, [('Alice', 'alice@x.com')])
        r = rewrite_history(repo, RewriteConfig(old_email='alice@x.com',
                                                new_email='new@x.com'))
        assert r['matched_commits'] >= 1
        log = git(repo, 'log', '--format=%ae').stdout
        assert 'new@x.com' in log

    def test_rewrite_keeps_branch_attached(self, tmp_path):
        """重写后不应处于 detached HEAD（关键回归）"""
        repo = setup_repo_with_commits(tmp_path, [('Old', 'old@x.com')])
        rewrite_history(repo, RewriteConfig(old_name='Old', new_name='New'))
        branch = git(repo, 'rev-parse', '--abbrev-ref', 'HEAD').stdout.strip()
        assert branch in ('main', 'master'), f"detached: {branch}"

    def test_rewrite_no_match(self, tmp_path):
        repo = setup_repo_with_commits(tmp_path, [('Alice', 'a@x.com')])
        r = rewrite_history(repo, RewriteConfig(old_name='Nobody',
                                                new_name='X'))
        assert r['matched_commits'] == 0

    def test_rewrite_requires_old(self, tmp_path):
        repo = setup_repo_with_commits(tmp_path, [('Alice', 'a@x.com')])
        with pytest.raises(ValueError):
            rewrite_history(repo, RewriteConfig())
