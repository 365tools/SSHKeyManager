#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sshm 安全测试脚本（沙箱模式）
用临时 SSH 目录模拟，不会触碰真实 ~/.ssh 中的任何密钥。

用法:
  python -X utf8 scripts/sandbox_test.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))

from sshm.core.manager import SSHKeyManager


def init_git_repo(root: Path) -> Path:
    """在临时目录中初始化一个 Git 仓库"""
    repo = root / 'sandbox_repo'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=repo, check=True)
    return repo


def main():
    ssh_dir = Path(tempfile.mkdtemp(prefix='sshm_test_'))
    print(f'[沙箱] 临时 SSH 目录: {ssh_dir}\n')
    m = SSHKeyManager(ssh_dir)

    # 1. 创建密钥（真实调用 ssh-keygen，生成在临时目录）
    print('>>> sshm add github dev@example.com --name "Dev One"')
    m.add_key('github', 'dev@example.com', name='Dev One')
    print()

    print('>>> sshm add work dev@example.com -t ed25519 -H github.com --name "Dev Work"')
    m.add_key('work', 'dev@example.com', key_type='ed25519', host='github.com', name='Dev Work')
    print()

    # 2. 列表（表格）
    print('>>> sshm list')
    m.list_keys()
    print()

    print('>>> sshm list --all')
    m.list_keys(show_content=True)
    print()

    # 3. 切换（use --global 等价于旧 switch）
    print('>>> sshm use work --global')
    m.switch_key('work')
    print()

    print('>>> sshm list (切换后)')
    m.list_keys()
    print()

    # 4. 备份
    print('>>> sshm backup')
    backup_path = m.backup_keys()
    print(f'    备份目录: {backup_path}\n')

    print('>>> sshm backups')
    m.list_backups()
    print()

    # 4.1 hosts 映射检查
    hosts = m.state_manager.read_hosts()
    print(f'[检查] hosts 映射: {hosts}')
    assert hosts.get('work') == 'github.com', 'work 标签应记录主机映射 github.com'
    print('[检查] 通过: add -H 已持久化 hosts 映射\n')

    # 5. 仓库作者功能
    print('>>> 初始化临时 Git 仓库')
    repo = init_git_repo(ssh_dir)
    print(f'    仓库路径: {repo}\n')

    print('>>> sshm author -p <repo> (设置前查看)')
    m.show_repo_author(str(repo))
    print()

    print('>>> sshm author github -p <repo> (设置作者)')
    m.set_repo_author('github', str(repo))
    print()

    print('>>> sshm author -p <repo> (设置后查看)')
    m.show_repo_author(str(repo))
    print()

    print('>>> sshm author work -p <repo> --yes (覆盖为 work)')
    m.set_repo_author('work', str(repo), skip_confirm=True)
    print()

    print('>>> sshm author --unset 需要交互确认，沙箱中跳过')
    print()

    # 5.1 作者列表管理（add/list/remove）
    print('>>> sshm author add personal -n "Dev Personal" -e work@example.com')
    m.add_author('personal', name='Dev Personal', email='work@example.com')
    print()

    print('>>> sshm author list')
    m.list_authors()
    print()

    authors = m.state_manager.read_authors()
    print(f'[检查] authors 映射: {authors}')
    assert authors.get('personal', {}).get('email') == 'work@example.com', 'add 后应保存邮箱'
    assert authors.get('personal', {}).get('name') == 'Dev Personal', 'add 后应保存姓名'
    print('[检查] 通过: author add 已保存姓名和邮箱到列表\n')

    print('>>> sshm author remove personal --yes')
    m.remove_author('personal', skip_confirm=True)
    print()

    authors = m.state_manager.read_authors()
    assert 'personal' not in authors, 'remove 后应从列表移除'
    print('[检查] 通过: author remove 已从列表移除作者\n')

    # 6. use 命令（验证自动创建 SSH config 别名）
    print('>>> sshm use github -p <repo> --yes')
    m.use_key_for_repo('github', str(repo), skip_confirm=True)
    print()

    host_alias = 'github-github'
    has_host = m.config_manager.has_host(host_alias)
    print(f'[检查] SSH config 中是否存在别名 {host_alias}: {has_host}')
    assert has_host, f'use 后应自动创建 SSH config 别名 {host_alias}'
    print('[检查] 通过: use 自动创建 SSH config 别名正常\n')

    # 7. 重命名（验证 authors / hosts 联动）
    print('>>> sshm rename work personal')
    m.rename_tag('work', 'personal')
    print()

    print('>>> sshm author personal -p <repo> --yes (重命名后仍可按新标签设置)')
    m.set_repo_author('personal', str(repo), skip_confirm=True)
    print()

    hosts = m.state_manager.read_hosts()
    print(f'[检查] 重命名后 hosts 映射: {hosts}')
    assert 'personal' in hosts and 'work' not in hosts, 'rename 后 hosts 映射应迁移到新标签'
    print('[检查] 通过: rename 联动迁移 hosts 映射正常\n')

    # 8. 删除（验证 authors / hosts 联动清理）
    print('>>> sshm remove github')
    m.remove_key('github')
    print()

    authors = m.state_manager.read_authors()
    print(f'[检查] 删除后 authors 映射: {authors}')
    assert 'github' not in authors, '删除 github 后 authors 应同步清理'
    hosts = m.state_manager.read_hosts()
    assert 'github' not in hosts, '删除 github 后 hosts 应同步清理'
    print('[检查] 通过: remove 联动清理 authors/hosts 正常\n')

    # 9. restore 恢复（先删掉 personal，再从备份恢复）
    print('>>> sshm remove personal')
    m.remove_key('personal')
    print()

    print('>>> sshm restore (默认恢复最新备份，含删除 personal 时的自动备份)')
    m.restore_backup(skip_confirm=True)
    print()

    print('[检查] 恢复后 personal 密钥应存在')
    assert (ssh_dir / 'id_ed25519.personal').exists(), '恢复后 personal 私钥应存在'
    assert (ssh_dir / 'id_ed25519.personal.pub').exists(), '恢复后 personal 公钥应存在'
    print('[检查] 通过: restore 恢复密钥正常\n')

    print('>>> sshm list (最终状态)')
    m.list_keys()
    print()

    print('[沙箱] 测试完成，临时目录将在退出后由系统清理。')


if __name__ == '__main__':
    main()
