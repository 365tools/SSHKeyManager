#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
备份服务 - 密钥备份 / 恢复 / 列表。

只负责备份目录相关操作，错误通过注入的 error_reporter（门面的 _fail）上报，
确认/输出走 Output 抽象（confirm / section / print）。
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from ..constants import STATE_FILE_NAME
from ..i18n import _
from ..ui.console import format_timestamp
from ..ui.output import confirm, print, section


class BackupService:
    """备份服务：backup / restore / list。"""

    def __init__(self, ssh_dir: Path, backup_dir: Path,
                 state_file: Path, config_file: Path,
                 error_reporter: Callable[[str], None]):
        self.ssh_dir = ssh_dir
        self.backup_dir = backup_dir
        self.state_file = state_file
        self.config_file = config_file
        self._error = error_reporter

    def backup_keys(self, silent: bool = False) -> Path:
        """备份所有密钥"""
        # 毫秒级时间戳：避免同一秒内多次备份合并到同一目录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        backup_path = self.backup_dir / f"backup_{timestamp}"
        backup_path.mkdir(mode=0o700, exist_ok=True)

        key_files = list(self.ssh_dir.glob('id_*'))
        backed_up: List[str] = []

        for key_file in key_files:
            if key_file.is_file():
                shutil.copy2(key_file, backup_path / key_file.name)
                backed_up.append(key_file.name)

        if self.state_file.exists():
            shutil.copy2(self.state_file, backup_path / STATE_FILE_NAME)
            backed_up.append(STATE_FILE_NAME)

        # 一并备份 SSH config（仅存档；恢复时不会自动覆盖当前 config）
        if self.config_file.exists():
            shutil.copy2(self.config_file, backup_path / 'config')
            backed_up.append('config')

        if not silent:
            print(f"✅ {_('msg.backup_complete')} {backup_path}")
            print("📦 " + _("msg.files_backed_up", count=len(backed_up)))

        return backup_path

    def list_backups(self) -> None:
        """列出所有备份"""
        section(_("hdr.backup_list"))

        backups = sorted(self.backup_dir.glob('backup_*'),
                         key=lambda x: x.stat().st_mtime, reverse=True)

        if not backups:
            print("📭 " + _("msg.no_backups"))
            return

        for i, backup in enumerate(backups, 1):
            mtime = datetime.fromtimestamp(backup.stat().st_mtime)
            files = list(backup.glob('id_*'))
            print(f"\n[{i}] {backup.name}")
            print(f"    {_('lbl.time')} {format_timestamp(mtime)}")
            print(f"    {_('lbl.files')} {len(files)}")
            print(f"    {_('lbl.path')} {backup}")

    def restore_backup(self, backup_name: Optional[str] = None,
                       key_type: Optional[str] = None,
                       skip_confirm: bool = False) -> None:
        """从备份恢复密钥"""
        section(_("hdr.restore"))

        if backup_name:
            # 校验备份名，防止路径穿越 / 绝对路径 / 家目录逃逸出备份目录
            candidate = Path(backup_name)
            if (candidate.is_absolute()
                    or '..' in candidate.parts
                    or str(backup_name).startswith('~')):
                self._error(f"❌ {_('err.invalid_backup_name', name=backup_name)}")
                return
            backup_path = self.backup_dir / backup_name
            if not backup_path.exists():
                self._error(f"❌ {_('err.backup_not_found')} {backup_path}")
                print("   " + _("err.use_backups_cmd"))
                return
        else:
            backups = sorted(self.backup_dir.glob('backup_*'),
                             key=lambda x: x.stat().st_mtime, reverse=True)
            if not backups:
                print("📭 " + _("err.no_backups_restore"))
                print("   " + _("err.use_backup_cmd"))
                return
            backup_path = backups[0]
            print(f"📦 {_('msg.will_use_latest')} {backup_path.name}")

        files = sorted(p for p in backup_path.glob('id_*') if p.is_file())
        if key_type:
            files = [f for f in files if f.name.startswith(f"id_{key_type}")]

        if not files:
            self._error("❌ " + _("err.no_recoverable"))
            return

        print("\n📂 " + _("msg.will_restore_count", count=len(files)))
        for f in files:
            print(f"   - {f.name}")

        if not skip_confirm and not confirm("\n" + _("msg.restore_prompt")):
            self._error("❌ " + _("misc.operation_cancelled"))
            return

        restored = []
        for f in files:
            try:
                shutil.copy2(f, self.ssh_dir / f.name)
                restored.append(f.name)
            except OSError as e:
                self._error(f"❌ {_('err.restore_failed')} {f.name} ({e})")
        # 恢复状态文件（包含 active_keys / authors / hosts 映射）
        state_backup = backup_path / STATE_FILE_NAME
        if state_backup.exists():
            shutil.copy2(state_backup, self.state_file)
            restored.append(STATE_FILE_NAME)

        if restored:
            print(f"\n✅ {_('msg.restored_count', count=len(restored))}")
            for name in restored:
                print(f"   - {name}")
            print("\n💡 " + _("msg.restore_tip"))

        # 备份中的 config 仅供存档，不自动覆盖当前配置，提示手动重建别名
        config_backup = backup_path / 'config'
        if config_backup.exists():
            print("\nℹ️  " + _("msg.backup_has_config"))
            print("   " + _("msg.regenerate_alias"))
