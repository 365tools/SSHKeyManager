#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSH 密钥管理器 - 门面（Facade）

只负责组合底层服务与命令编排组，并把公开 API 委托出去，自身不做业务逻辑。
- 服务层：KeyStore / SSHTester / GitRepoService / BackupService / AuthorService
- 命令编排层（core/commands/）：KeyCommands / RepoCommands / AuthorCommands /
  SystemCommands（按指令分包，每模块单一职责）
- 状态：_had_error（软错误标志）与 _fail（软错误上报）
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from ..constants import BACKUP_DIR_NAME, DEFAULT_KEY_TYPE, STATE_FILE_NAME
from .author import AuthorService
from .backup import BackupService
from .commands import AuthorCommands, KeyCommands, RepoCommands, SystemCommands
from .config import SSHConfigManager
from .gitrepo import GitRepoService
from .keystore import KeyStore
from ..ui.output import print
from .sshtest import SSHTester
from .state import StateManager


class SSHKeyManager:
    """SSH 密钥管理器 - 门面，组合服务与命令编排，公开 API 委托。"""

    # 保留标签：original 为 use -g 切换时的系统备份，default 为默认密钥
    RESERVED_LABELS = ('default', 'original')

    def __init__(self, ssh_dir: Optional[Path] = None):
        """初始化管理器

        Args:
            ssh_dir: SSH 目录路径，默认为 ~/.ssh
        """
        self.ssh_dir = ssh_dir or Path.home() / '.ssh'
        self.backup_dir = self.ssh_dir / BACKUP_DIR_NAME
        self.config_file = self.ssh_dir / 'config'
        self.state_file = self.ssh_dir / STATE_FILE_NAME

        # 初始化子管理器
        self.config_manager = SSHConfigManager(self.config_file)
        self.state_manager = StateManager(self.state_file)

        # 应用输出语言（环境变量优先于状态文件）
        from ..i18n import load_from_state
        load_from_state(self.state_manager.read_lang())

        # 本次命令是否发生业务失败（供 CLI 层决定退出码）
        self._had_error = False

        # 组合服务（门面委托给聚焦服务）
        self.keystore = KeyStore(self.ssh_dir)
        self.gitrepo = GitRepoService(
            self.ssh_dir, self.config_manager, self.state_manager,
            self.keystore, self._fail)
        self.backup = BackupService(
            self.ssh_dir, self.backup_dir, self.state_file,
            self.config_file, self._fail)
        self.tester = SSHTester()
        self.author = AuthorService(
            self.state_manager, self.keystore, self.gitrepo, self._fail)

        # 命令编排组（按指令分包，每模块单一职责）
        self.keys = KeyCommands(self)
        self.repo = RepoCommands(self)
        self.author_cmds = AuthorCommands(self)
        self.system = SystemCommands(self)

        # 确保必要目录存在
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """确保必要的目录存在（委托 KeyStore，另确保备份目录）"""
        self.keystore.ensure_directories()
        self.backup_dir.mkdir(mode=0o700, exist_ok=True)

    def _fail(self, msg: str):
        """记录业务失败并打印错误信息（不抛异常，保持原有控制流）

        由 CLI 层在命令结束后检查 `_had_error` 决定退出码。
        """
        self._had_error = True
        print(msg)

    # ------------------------------------------------------------------
    # 密钥管理命令（委托 KeyCommands）
    # ------------------------------------------------------------------

    def list_keys(self, show_content: bool = False,
                  repo_path: Union[str, Path] = '.',
                  current_only: bool = False):
        return self.keys.list_keys(show_content, repo_path, current_only)

    def add_key(self, label: str, email: str,
                key_type: str = DEFAULT_KEY_TYPE, host: Optional[str] = None,
                name: Optional[str] = None):
        return self.keys.add_key(label, email, key_type, host, name)

    def remove_key(self, label: str, key_type: Optional[str] = None):
        return self.keys.remove_key(label, key_type)

    def switch_key(self, label: str, key_type: Optional[str] = None):
        return self.keys.switch_key(label, key_type)

    def tag_key(self, key_type: Optional[str], new_label: str,
                switch_after: bool = False):
        return self.keys.tag_key(key_type, new_label, switch_after)

    def rename_tag(self, old_label: str, new_label: str,
                   key_type: str = DEFAULT_KEY_TYPE):
        return self.keys.rename_tag(old_label, new_label, key_type)

    def _validate_label(self, label: str) -> bool:
        return self.keys._validate_label(label)

    # ------------------------------------------------------------------
    # 备份（委托 BackupService）
    # ------------------------------------------------------------------

    def backup_keys(self, silent: bool = False):
        return self.backup.backup_keys(silent)

    def list_backups(self) -> None:
        return self.backup.list_backups()

    def restore_backup(self, backup_name: Optional[str] = None,
                       key_type: Optional[str] = None,
                       skip_confirm: bool = False):
        return self.backup.restore_backup(backup_name, key_type, skip_confirm)

    # ------------------------------------------------------------------
    # Git 仓库命令（委托 RepoCommands）
    # ------------------------------------------------------------------

    def use_key_for_repo(self, label: str, repo_path: Union[str, Path] = '.',
                         skip_confirm: bool = False):
        return self.repo.use_key_for_repo(label, repo_path, skip_confirm)

    def clone_with_label(self, label: str, url: str,
                         target_dir: Optional[str] = None,
                         skip_confirm: bool = False):
        return self.repo.clone_with_label(label, url, target_dir, skip_confirm)

    def show_repo_info(self, repo_path: Union[str, Path] = '.'):
        return self.repo.show_repo_info(repo_path)

    def test_connection(self, label: Optional[str] = None, test_all: bool = False,
                        repo_path: Union[str, Path] = '.'):
        return self.repo.test_connection(label, test_all, repo_path)

    # ------------------------------------------------------------------
    # 作者命令（委托 AuthorCommands）
    # ------------------------------------------------------------------

    def show_auto_author(self) -> None:
        return self.author_cmds.show_auto_author()

    def set_auto_author(self, enabled: bool):
        return self.author_cmds.set_auto_author(enabled)

    def show_repo_author(self, repo_path: Union[str, Path] = '.'):
        return self.author_cmds.show_repo_author(repo_path)

    def set_repo_author(self, label: str, repo_path: Union[str, Path] = '.',
                        name: Optional[str] = None, email: Optional[str] = None,
                        scope: str = 'local', skip_confirm: bool = False,
                        infer_from_remote: bool = True):
        return self.author_cmds.set_repo_author(
            label, repo_path, name, email, scope, skip_confirm, infer_from_remote)

    def unset_repo_author(self, repo_path: Union[str, Path] = '.',
                          scope: str = 'local'):
        return self.author_cmds.unset_repo_author(repo_path, scope)

    def add_author(self, label: str, name: Optional[str] = None,
                   email: Optional[str] = None):
        return self.author_cmds.add_author(label, name, email)

    def list_authors(self, repo_path: Union[str, Path] = '.'):
        return self.author_cmds.list_authors(repo_path)

    def remove_author(self, label: str, skip_confirm: bool = False):
        return self.author_cmds.remove_author(label, skip_confirm)

    def fix_author(self, repo_path: Union[str, Path] = '.',
                   old_name: Optional[str] = None,
                   new_name: Optional[str] = None,
                   old_email: Optional[str] = None,
                   new_email: Optional[str] = None,
                   skip_confirm: bool = False):
        return self.author_cmds.fix_author(
            repo_path, old_name, new_name, old_email, new_email, skip_confirm)

    # ------------------------------------------------------------------
    # 系统命令（委托 SystemCommands）
    # ------------------------------------------------------------------

    def set_language(self, lang: str) -> str:
        return self.system.set_language(lang)

    def update(self, check: bool = False, force: bool = False) -> Optional[int]:
        return self.system.update(check, force)

    def add_to_path(self) -> None:
        return self.system.add_to_path()

    # ------------------------------------------------------------------
    # 作者服务委托（AuthorService）
    # ------------------------------------------------------------------

    def _get_author_info(self, label: str, name: Optional[str] = None,
                         email: Optional[str] = None,
                         repo_path: Optional[Union[str, Path]] = None,
                         infer_from_remote: bool = True) -> Optional[Dict[str, str]]:
        return self.author.get_author_info(
            label, name, email, repo_path, infer_from_remote)

    def _extract_email_from_pubkey(self, label: str) -> Optional[str]:
        return self.author.extract_email_from_pubkey(label)

    def _infer_author_name_from_remote(self, repo_path: Path) -> Optional[str]:
        return self.author.infer_author_name_from_remote(repo_path)

    def _git_get_config(self, repo_path: Path, scope: str,
                        key: str) -> Optional[str]:
        return self.author.git_get_config(repo_path, scope, key)

    def _apply_auto_author(self, label: str, repo_path: Optional[str] = None,
                           scope: str = 'local', skip_confirm: bool = True):
        return self.author.apply_auto_author(label, repo_path, scope, skip_confirm)

    # ------------------------------------------------------------------
    # 底层服务委托（供既有内部调用点 / 测试兼容，保持私有 API 稳定）
    # ------------------------------------------------------------------

    def _scan_all_keys(self) -> Dict[str, List[Dict]]:
        return self.keystore.scan_all_keys()

    def _detect_key_type_for_label(self, label: str) -> Optional[str]:
        return self.keystore.detect_key_type_for_label(label)

    def _detect_default_key_type(self) -> Optional[str]:
        return self.keystore.detect_default_key_type()

    def _copy_key_pair(self, source: Path, target: Path):
        return self.keystore.copy_key_pair(source, target)

    def _extract_email_from_pubkey_default(self, key_type: str) -> Optional[str]:
        return self.keystore.extract_email_from_pubkey(key_type)

    def _test_ssh_connection(self, host: str) -> Tuple[bool, str]:
        return self.tester.test(host)

    def _parse_git_url(self, url: str) -> Optional[Tuple[str, str, str]]:
        return self.gitrepo.parse_git_url(url)

    @staticmethod
    def _platform_from_hostname(hostname: str) -> str:
        return GitRepoService.platform_from_hostname(hostname)

    def _get_hostname_for_label(self, label: str) -> str:
        return self.gitrepo.get_hostname_for_label(label)

    def _get_host_alias(self, label: str) -> str:
        return self.gitrepo.get_host_alias(label)

    def _resolve_label_from_alias(self, host_alias: str) -> Optional[str]:
        return self.gitrepo.resolve_label_from_alias(host_alias)

    def _resolve_repo_hostname(self, url: str) -> Optional[str]:
        return self.gitrepo.resolve_repo_hostname(url)

    def _extract_ssh_config_block(self, host_alias: str) -> List[str]:
        return self.gitrepo.extract_ssh_config_block(host_alias)

    def _align_hostname_with_repo(self, label: str,
                                  repo_hostname: Optional[str],
                                  skip_confirm: bool) -> bool:
        return self.gitrepo.align_hostname_with_repo(
            label, repo_hostname, skip_confirm)

    def _detect_repo_key_label(self,
                               repo_path: Union[str, Path] = '.') -> Optional[str]:
        return self.gitrepo.detect_repo_key_label(repo_path)

    def _update_ssh_config_alias(self, label: str, key_file: Path):
        return self.gitrepo.update_ssh_config_alias(label, key_file)

    def _remove_ssh_config_alias(self, label: str):
        return self.gitrepo.remove_ssh_config_alias(label)

    def _rename_ssh_config_alias(self, old_label: str, new_label: str,
                                 new_key_file: Path):
        return self.gitrepo.rename_ssh_config_alias(
            old_label, new_label, new_key_file)
