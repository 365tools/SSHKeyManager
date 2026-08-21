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
from typing import Optional

from ..constants import (
    BACKUP_DIR_NAME,
    DEFAULT_SSH_DIR,
    SSH_CONFIG_NAME,
    STATE_FILE_NAME,
)
from .commands import (
    AuthorCommands,
    HistoryCommands,
    KeyCommands,
    RepoCommands,
    SystemCommands,
)
from .services.git.author import AuthorService
from .services.git.gitrepo import GitRepoService
from .services.net.sshtest import SSHTester
from .services.ssh.config import SSHConfigManager
from .services.ssh.keystore import KeyStore
from .services.storage.backup import BackupService
from .services.storage.state import StateManager
from ..ui.output import ICON_ERR, ICON_WARN, print
from ..ui.tip import render_business_error


class SSHKeyManager:
    """SSH 密钥管理器 - 门面，组合服务与命令编排，公开 API 委托。"""

    # 保留标签：original 为 use -g 切换时的系统备份，default 为默认密钥
    RESERVED_LABELS = ("default", "original")

    def __init__(self, ssh_dir: Optional[Path] = None):
        """初始化管理器

        Args:
            ssh_dir: SSH 目录路径，默认为 ~/.ssh
        """
        self.ssh_dir = ssh_dir or DEFAULT_SSH_DIR
        self.backup_dir = self.ssh_dir / BACKUP_DIR_NAME
        self.config_file = self.ssh_dir / SSH_CONFIG_NAME
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
            self.ssh_dir,
            self.config_manager,
            self.state_manager,
            self.keystore,
            self._fail,
        )
        self.backup = BackupService(
            self.ssh_dir, self.backup_dir, self.state_file, self.config_file, self._fail
        )
        self.tester = SSHTester()
        self.author_service = AuthorService(
            self.state_manager, self.keystore, self.gitrepo, self._fail
        )

        # 命令编排组（与 CLI 分组一一对应：key/repo/backup/author/history/config）
        self.key = KeyCommands(self)
        self.repo = RepoCommands(self)
        self.author = AuthorCommands(self)
        self.history = HistoryCommands(self)
        self.config = SystemCommands(self)

        # 确保必要目录存在
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """确保必要的目录存在（委托 KeyStore，另确保备份目录）"""
        self.keystore.ensure_directories()
        self.backup_dir.mkdir(mode=0o700, exist_ok=True)

    def _fail(self, msg: str, *, icon: str = ICON_ERR, hint: Optional[str] = None):
        """记录业务失败并渲染统一错误（不抛异常，保持原有控制流）。

        Args:
            msg: 错误消息（不含图标前缀，调用点只传纯消息）。
            icon: 状态图标，默认 ❌（硬错误）；软告警传 ⚠️。
            hint: 可选建议行，渲染为 💡 tip 段。

        由 CLI 层在命令结束后检查 `_had_error` 决定退出码。
        统一走 `ui.tip.render_business_error`，避免各调用点自行拼 `❌` 与格式化。
        """
        self._had_error = True
        render_business_error(msg, icon=icon, hint=hint)

    def _warn(self, msg: str, *, hint: Optional[str] = None) -> None:
        """渲染统一软告警（⚠️ + 可选 💡 建议）。

        与 `_fail` 的区别：**不置 `_had_error`**，命令仍按成功退出。
        用于"提示但命令正常完成"的告警场景，避免误报非零退出码。
        """
        render_business_error(msg, icon=ICON_WARN, hint=hint)

    def _mark_error(self) -> None:
        """仅标记业务失败（不打印）。

        用于"已打印过详细错误提示、仅需置位退出码"的场景，避免与 `_fail`
        重复输出。命令层不应直接改 `_had_error`，统一走本方法或 `_fail`。
        """
        self._had_error = True
