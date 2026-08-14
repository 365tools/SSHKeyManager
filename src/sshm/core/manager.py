#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSH 密钥管理器 - 核心业务逻辑
"""

import re
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from ..constants import (
    SUPPORTED_KEY_TYPES,
    DEFAULT_KEY_TYPE,
    BACKUP_DIR_NAME,
    STATE_FILE_NAME
)
from ..utils import (
    get_key_pattern,
    format_timestamp,
    format_size,
    prompt_confirm,
    print_separator,
    print_section_header,
    print_table
)
from ..i18n import _
from .config import SSHConfigManager
from .state import StateManager


class SSHKeyManager:
    """SSH 密钥管理器 - 核心业务逻辑"""
    
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
        
        # 确保必要目录存在
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保必要的目录存在"""
        self.ssh_dir.mkdir(mode=0o700, exist_ok=True)
        self.backup_dir.mkdir(mode=0o700, exist_ok=True)
    
    def _fail(self, msg: str):
        """记录业务失败并打印错误信息（不抛异常，保持原有控制流）

        由 CLI 层在命令结束后检查 `_had_error` 决定退出码。
        """
        self._had_error = True
        print(msg)
    
    # ------------------------------------------------------------------------
    # 标签合法性校验（所有标签入口统一使用）
    # ------------------------------------------------------------------------

    # 保留标签：original 为 switch 的系统备份，default 为默认密钥
    RESERVED_LABELS = ('default', 'original')

    def _validate_label(self, label: str) -> bool:
        """校验标签合法性（add/tag/rename 统一入口）

        规则:
        - 非空
        - 仅允许字母、数字、下划线、连字符，且首字符为字母/数字
        - 不允许 '.'（会破坏密钥扫描正则）、'/' '\\'（路径穿越）、
          空格、'#'（破坏 config 注释）、'*?'（破坏 glob）
        - 不允许保留名称 default / original
        """
        if not label or not label.strip():
            raise ValueError(_("Label cannot be empty"))
        label = label.strip()
        if not re.match(r'^[A-Za-z0-9][A-Za-z0-9_-]*$', label):
            raise ValueError(_(
                "Invalid label '{label}': only letters, digits, underscore(_) "
                "and hyphen(-) are allowed, and it cannot start with a symbol",
                label=label,
            ))
        if label.lower() in self.RESERVED_LABELS:
            raise ValueError(_("Label '{label}' is a reserved name and cannot "
                              "be used", label=label))
        return True
    
    # ------------------------------------------------------------------------
    # 查询操作
    # ------------------------------------------------------------------------
    
    def list_keys(self, show_content: bool = False, repo_path: str = '.',
                  current_only: bool = False):
        """列出所有密钥（表格形式）

        Args:
            show_content: 是否显示公钥内容
            repo_path: Git 仓库路径，用于检测仓库级使用（默认当前目录）
            current_only: 仅显示当前仓库正在使用的密钥（list -c）
        """
        print_section_header(_("sshm - Key List"))
        print(f"\n{_('SSH directory:')} {self.ssh_dir}\n")

        keys_by_label = self._scan_all_keys()
        active_keys = self.state_manager.read_active_keys()

        if not keys_by_label:
            print("⚠️  " + _("No key files found"))
            print("\n💡 " + _("Tip: use 'sshm add <label> <email>' to create a new key"))
            return

        # 指定仓库正在使用的密钥（仓库级，通过 remote URL 反解）
        repo_key = self._detect_repo_key_label(repo_path)

        # 按标签排序: 当前使用 -> 默认 -> 其他
        active_labels = set(active_keys.values())

        def sort_key(label):
            label_lower = label.lower()
            if label_lower in active_labels or label_lower == repo_key:
                priority = 0
            elif label_lower == 'default':
                priority = 1
            else:
                priority = 2
            return (priority, label_lower)

        sorted_labels = sorted(keys_by_label.keys(), key=sort_key)

        # 收集表格数据（首列 Status 用 ✨ 标记正在使用；Scope 区分仓库级/全局）
        global_scope = _('global')
        repo_scope = _('repo-level')
        headers = [_('Status'), _('Label'), _('File'), _('Public'), _('Size'),
                   _('Modified'), _('Alias'), _('Scope')]
        rows = []
        pub_map = []

        for label in sorted_labels:
            for key in keys_by_label[label]:
                is_active = active_keys.get(key['type']) == label.lower()
                is_repo = label.lower() == repo_key

                # list -c：仅显示当前仓库正在使用的密钥
                if current_only and not is_repo:
                    continue

                icon = '✨' if (is_active or is_repo) else ''
                # 作用域优先级：仓库级 > 全局（仓库级更"当前"）
                if is_repo:
                    scope = repo_scope
                elif is_active:
                    scope = global_scope
                else:
                    scope = ''

                host_alias = self._get_host_alias(label)
                alias_display = (
                    f"git@{host_alias}:user/repo.git"
                    if self.config_manager.has_host(host_alias)
                    else '-'
                )

                rows.append([
                    icon,
                    label.upper(),
                    key['private'].name,
                    '✅' if key['has_pub'] else '❌',
                    format_size(key['size']),
                    format_timestamp(key['mtime']),
                    alias_display,
                    scope,
                ])

                if show_content and key['has_pub']:
                    pub_map.append((
                        label.upper(),
                        key['private'].name,
                        key['public'].read_text(encoding='utf-8').strip(),
                    ))

        # list -c 且无匹配时，给出友好提示而非空表格
        if current_only and not rows:
            if not (Path(repo_path).resolve() / '.git').exists():
                print("⚠️  " + _("Not a git repository: {path}", path=Path(repo_path).resolve()))
            else:
                print("⚠️  " + _("No key is configured for the current repo"))
            print("   " + _("Use 'sshm use <label>' to configure a key for this repo"))
            print("   " + _("Or run 'sshm list' to view all keys"))
            return

        # 窄终端下省略"修改时间"列，并为"文件/别名"列启用自动压缩
        term_width = shutil.get_terminal_size((100, 24)).columns
        if term_width < 100:
            headers = headers[:5] + headers[6:]
            rows = [row[:5] + row[6:] for row in rows]
            truncatable = [2, 5]  # 文件、别名
        else:
            truncatable = [2, 6]

        print_table(headers, rows, truncatable=truncatable,
                    term_width=term_width, center_cols=[0])

        # 公钥内容单独展示（避免破坏表格对齐）
        if show_content and pub_map:
            print_section_header("📋 " + _("Public Key Contents"))
            for label, file_name, content in pub_map:
                print(f"\n[{label}] {file_name}.pub")
                print(f"  {content}\n")

        print_separator()
        print("💡 " + _("Tip: use 'use <label> --global' to configure the global default key"))
        print_separator()
    
    def list_backups(self):
        """列出所有备份"""
        print_section_header(_("Backup List"))
        
        backups = sorted(self.backup_dir.glob('backup_*'), 
                        key=lambda x: x.stat().st_mtime, reverse=True)
        
        if not backups:
            print("📭 " + _("No backups yet"))
            return
        
        for i, backup in enumerate(backups, 1):
            mtime = datetime.fromtimestamp(backup.stat().st_mtime)
            files = list(backup.glob('id_*'))
            print(f"\n[{i}] {backup.name}")
            print(f"    {_('Time:')} {format_timestamp(mtime)}")
            print(f"    {_('Files:')} {len(files)}")
            print(f"    {_('Path:')} {backup}")
    
    def _scan_all_keys(self) -> Dict[str, List[Dict]]:
        """扫描所有密钥文件"""
        keys_by_label = {}
        key_pattern = get_key_pattern()
        
        for file in self.ssh_dir.glob('id_*'):
            if not file.is_file() or file.name.endswith('.pub'):
                continue
            
            match = key_pattern.match(file.name)
            if not match:
                continue
            
            key_type = match.group(1)
            label = match.group(2)[1:] if match.group(2) else 'default'
            # 跳过 switch 命令的系统备份文件（id_*.original），不视为用户标签
            if label.lower() == 'original':
                continue
            
            pub_file = self.ssh_dir / f"{file.name}.pub"
            key_info = {
                'type': key_type,
                'private': file,
                'public': pub_file,
                'has_pub': pub_file.exists(),
                'size': file.stat().st_size,
                'mtime': datetime.fromtimestamp(file.stat().st_mtime)
            }
            
            if label not in keys_by_label:
                keys_by_label[label] = []
            keys_by_label[label].append(key_info)
        
        return keys_by_label
    
    # ------------------------------------------------------------------------
    # 备份操作
    # ------------------------------------------------------------------------
    
    def backup_keys(self, silent: bool = False):
        """备份所有密钥"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f"backup_{timestamp}"
        backup_path.mkdir(mode=0o700, exist_ok=True)
        
        key_files = list(self.ssh_dir.glob('id_*'))
        backed_up = []
        
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
            print(f"✅ {_('Backup complete:')} {backup_path}")
            print("📦 " + _("files backed up", count=len(backed_up)))
        
        return backup_path
    
    def restore_backup(self, backup_name: Optional[str] = None,
                       key_type: Optional[str] = None,
                       skip_confirm: bool = False):
        """从备份恢复密钥"""
        print_section_header(_("Restore Keys from Backup"))

        if backup_name:
            backup_path = self.backup_dir / backup_name
            if not backup_path.exists():
                self._fail(f"❌ {_('Backup not found:')} {backup_path}")
                print("   " + _("Use 'sshm backups' to view available backups"))
                return
        else:
            backups = sorted(self.backup_dir.glob('backup_*'),
                             key=lambda x: x.stat().st_mtime, reverse=True)
            if not backups:
                print("📭 " + _("No backups to restore"))
                print("   " + _("Use 'sshm backup' to create a backup"))
                return
            backup_path = backups[0]
            print(f"📦 {_('Will use latest backup:')} {backup_path.name}")

        files = sorted(p for p in backup_path.glob('id_*') if p.is_file())
        if key_type:
            files = [f for f in files if f.name.startswith(f"id_{key_type}")]

        if not files:
            self._fail("❌ " + _("No recoverable key files in backup"))
            return

        print("\n📂 " + _("Will restore the following {count} file(s):", count=len(files)))
        for f in files:
            print(f"   - {f.name}")

        if not skip_confirm and not prompt_confirm("\n" + _("Restore? (existing files will be overwritten)")):
            self._fail("❌ " + _("operation cancelled"))
            return

        restored = []
        for f in files:
            try:
                shutil.copy2(f, self.ssh_dir / f.name)
                restored.append(f.name)
            except OSError as e:
                self._fail(f"❌ {_('Restore failed:')} {f.name} ({e})")
        # 恢复状态文件（包含 active_keys / authors / hosts 映射）
        state_backup = backup_path / STATE_FILE_NAME
        if state_backup.exists():
            shutil.copy2(state_backup, self.state_file)
            restored.append(STATE_FILE_NAME)

        if restored:
            print(f"\n✅ {_('Restored {count} file(s):', count=len(restored))}")
            for name in restored:
                print(f"   - {name}")
            print("\n💡 " + _("Tip: use 'sshm list' to view restored keys"))

        # 备份中的 config 仅供存档，不自动覆盖当前配置，提示手动重建别名
        config_backup = backup_path / 'config'
        if config_backup.exists():
            print("\nℹ️  " + _("Backup contains SSH config; for safety it will NOT overwrite current config"))
            print("   " + _("Run 'sshm use <label>' to regenerate alias config"))
    
    # ------------------------------------------------------------------------
    # 密钥创建与删除
    # ------------------------------------------------------------------------
    
    def add_key(self, label: str, email: str,
                key_type: str = DEFAULT_KEY_TYPE, host: Optional[str] = None,
                name: Optional[str] = None):
        """创建新密钥"""
        if key_type not in SUPPORTED_KEY_TYPES:
            raise ValueError(_(
                "Unsupported key type: {type}, supported: {supported}",
                type=key_type, supported=', '.join(SUPPORTED_KEY_TYPES),
            ))
        
        self._validate_label(label)
        
        if not email or '@' not in email:
            raise ValueError(_(
                "Invalid email: {email}, please provide a valid email e.g. user@example.com",
                email=email,
            ))
        
        key_file = self.ssh_dir / f"id_{key_type}.{label}"
        if key_file.exists():
            raise ValueError(_("Key already exists: {name}", name=key_file.name))
        
        print(_("Creating new key: {label} ({key_type})", label=label, key_type=key_type))
        print(f"📧 {_('Email:')} {email}")
        
        cmd = [
            'ssh-keygen',
            '-t', key_type,
            '-C', email,
            '-f', str(key_file),
            '-N', ''
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"✅ {_('Key created successfully: {name}', name=key_file.name)}")
            
            if host:
                hostname = host
            else:
                hostname = self._get_hostname_for_label(label)
            # 持久化 label -> hostname 映射（供 use/remove/rename 使用）
            self.state_manager.write_host(label, hostname)
            if host:
                host_alias = self._get_host_alias(label)
                self.config_manager.update_host(host_alias, hostname, key_file)
                print(f"✅ {_('SSH config updated: Host {alias} -> {hostname}', alias=host_alias, hostname=hostname)}")
            
            pub_file = Path(str(key_file) + '.pub')
            if pub_file.exists():
                pub_key = pub_file.read_text(encoding='utf-8').strip()
                print(f"\n📋 {_('Public key content:')}\n{pub_key}\n")
                print("💡 " + _("Add this public key to your Git platform (GitHub/GitLab etc.)"))

            # 记录作者信息（供 sshm author 使用）
            self.state_manager.write_author(label, name or '', email)
            if name:
                print(f"👤 {_('Author info recorded: {name} <{email}>', name=name, email=email)}")
        
        except subprocess.CalledProcessError as e:
            # 清理可能残留的密钥文件（ssh-keygen 失败时可能已创建部分文件）
            for p in (key_file, Path(str(key_file) + '.pub')):
                try:
                    if p.exists():
                        p.unlink()
                except OSError:
                    pass
            detail = ((e.stderr or b'').decode('utf-8', 'replace').strip()
                      or str(e))
            self._fail(f"❌ {_('Create failed: {err}', err=detail)}")
        except Exception as e:
            self._fail(f"❌ {_('error')}: {e}")    
    def remove_key(self, label: str, key_type: Optional[str] = None):
        """删除密钥"""
        label_lower = label.lower()
        
        if label_lower == 'default':
            if key_type:
                confirm_msg = _("About to delete default key ({type}), continue?", type=key_type)
            else:
                confirm_msg = _("About to delete all default keys, continue?")
            
            if not prompt_confirm("⚠️  " + confirm_msg):
                self._fail("❌ " + _("operation cancelled"))
                return
        
        removed_files = []
        
        if label_lower == 'default':
            if key_type:
                patterns = [f"id_{key_type}", f"id_{key_type}.pub"]
            else:
                patterns = ["id_ed25519", "id_ed25519.pub", 
                          "id_rsa", "id_rsa.pub",
                          "id_ecdsa", "id_ecdsa.pub",
                          "id_dsa", "id_dsa.pub"]
            
            for pattern in patterns:
                file = self.ssh_dir / pattern
                if file.exists() and file.is_file():
                    if not removed_files:
                        backup_path = self.backup_keys(silent=True)
                        print(f"💾 {_('Auto-backed up to: {path}', path=backup_path)}")
                    
                    file.unlink()
                    removed_files.append(file.name)
        else:
            if key_type:
                patterns = [f"id_{key_type}.{label}", f"id_{key_type}.{label}.pub"]
            else:
                patterns = [f"id_*.{label}", f"id_*.{label}.pub"]
            
            for pattern in patterns:
                for file in self.ssh_dir.glob(pattern):
                    if file.is_file():
                        if not removed_files:
                            backup_path = self.backup_keys(silent=True)
                            print(f"💾 {_('Auto-backed up to: {path}', path=backup_path)}")
                        
                        file.unlink()
                        removed_files.append(file.name)
        
        if removed_files:
            print(f"✅ {_('Deleted {count} file(s):', count=len(removed_files))}")
            for f in removed_files:
                print(f"   - {f}")
            
            self._remove_ssh_config_alias(label)
            self.state_manager.remove_author(label)
            self.state_manager.remove_host(label)
            
            # 清理 active 状态：从已删除文件名中推导密钥类型
            # （不能在删除文件后调用 _detect_key_type_for_label，文件已不存在）
            removed_types = set()
            for name in removed_files:
                m = re.match(r'^id_(rsa|ed25519|ecdsa|dsa)(?:\.|$)', name)
                if m:
                    removed_types.add(m.group(1))
            for kt in removed_types:
                active_keys = self.state_manager.read_active_keys()
                if active_keys.get(kt) == label_lower:
                    self.state_manager.remove_active_key(kt)
            
            print(f"💡 {_('Tip: if any repo uses alias {alias} in its remote URL,', alias=self._get_host_alias(label))}")
            print("   " + _("re-run 'sshm use <other-label>' in that repo to update config"))
        else:
            self._fail(f"⚠️  {_('Key not found: {label}', label=label)}")    
    # ------------------------------------------------------------------------
    # 密钥切换
    # ------------------------------------------------------------------------
    
    def switch_key(self, label: str, key_type: Optional[str] = None):
        """切换默认密钥"""
        label_lower = label.lower()
        
        if label_lower in self.RESERVED_LABELS:
            label_msg = _('Label "{label}" is a reserved name and cannot be switched to', label=label)
            self._fail(f"❌ {label_msg}")
            return
        
        if not key_type:
            key_type = self._detect_key_type_for_label(label)
            if not key_type:
                msg = _("No key found for label '{label}'", label=label)
                self._fail(f"❌ {msg}")
                return
            print(f"🔍 {_('Auto-detected key type: {key_type}', key_type=key_type)}")
        
        source_file = self.ssh_dir / f"id_{key_type}.{label}"
        target_file = self.ssh_dir / f"id_{key_type}"
        
        if not source_file.exists():
            self._fail(f"❌ {_('Key does not exist: {name}', name=source_file.name)}")
            return
        
        if target_file.exists():
            active_keys = self.state_manager.read_active_keys()
            current_label = active_keys.get(key_type, 'original')
            
            original_backup = self.ssh_dir / f"id_{key_type}.original"
            if not original_backup.exists():
                self._copy_key_pair(target_file, original_backup)
                print(f"💾 {_('Original key backed up as: {name}', name=original_backup.name)}")
            
            if current_label != 'original':
                backup_file = self.ssh_dir / f"id_{key_type}.{current_label}"
                if not backup_file.exists():
                    self._copy_key_pair(target_file, backup_file)
        
        self._copy_key_pair(source_file, target_file)
        
        self.state_manager.write_active_key(key_type, label)
        
        self._update_ssh_config_alias(label, source_file)
        
        print(f"✅ {_('Switched to key: {label} ({key_type})', label=label, key_type=key_type)}")
        print(f"📁 {_('File:')} {target_file.name}")
    
    def tag_key(self, key_type: str, new_label: str, switch_after: bool = False):
        """给默认密钥添加标签"""
        self._validate_label(new_label)
        
        if not key_type:
            key_type = self._detect_default_key_type()
            if not key_type:
                self._fail("❌ " + _("No default key found"))
                return
        
        source_file = self.ssh_dir / f"id_{key_type}"
        target_file = self.ssh_dir / f"id_{key_type}.{new_label}"
        
        if not source_file.exists():
            self._fail(f"❌ {_('Default key does not exist: {name}', name=source_file.name)}")
            return
        
        if target_file.exists():
            print(f"⚠️  {_('Label already exists: {new_label}', new_label=new_label)}")
            if not prompt_confirm(_("Overwrite?")):
                return
        
        self._copy_key_pair(source_file, target_file)
        
        print(f"✅ {_('Tag added: {new_label} ({key_type})', new_label=new_label, key_type=key_type)}")
        
        if switch_after:
            self.switch_key(new_label, key_type)
    
    def rename_tag(self, old_label: str, new_label: str, 
                   key_type: str = DEFAULT_KEY_TYPE):
        """重命名密钥标签（处理该标签下的所有密钥类型，避免残留旧文件）"""
        old_label_lower = old_label.lower()
        new_label_lower = new_label.lower()
        
        if old_label_lower == 'default':
            self._fail("❌ " + _("Cannot rename the 'default' label"))
            return
        
        self._validate_label(new_label)
        if new_label_lower == old_label_lower:
            self._fail("⚠️  " + _("Old and new labels are the same, no need to rename"))
            return
        
        # 确定要重命名的密钥类型集合：
        # - 未指定类型时，处理该标签下所有已存在的类型（多类型共存场景）
        # - 指定类型时，仅处理指定类型
        if key_type:
            types_to_rename = [key_type]
        else:
            types_to_rename = [
                t for t in SUPPORTED_KEY_TYPES
                if (self.ssh_dir / f"id_{t}.{old_label}").exists()
            ]
        
        if not types_to_rename:
            msg = _("No key found for label '{label}'", label=old_label)
            self._fail(f"❌ {msg}")
            return
        
        # 检查目标文件是否全部可用，避免部分重命名后中断
        for t in types_to_rename:
            new_file = self.ssh_dir / f"id_{t}.{new_label}"
            if new_file.exists():
                self._fail(f"⚠️  {_('Target label already exists: {new_label} ({type})', new_label=new_label, type=t)}")
                print(f"   {_('File: {name}', name=new_file.name)}")
                return
        
        renamed_count = 0
        last_new_file = None
        for t in types_to_rename:
            old_file = self.ssh_dir / f"id_{t}.{old_label}"
            new_file = self.ssh_dir / f"id_{t}.{new_label}"
            
            old_file.rename(new_file)
            old_pub = Path(str(old_file) + '.pub')
            if old_pub.exists():
                old_pub.rename(Path(str(new_file) + '.pub'))
            last_new_file = new_file
            renamed_count += 1
        
        if last_new_file:
            self._rename_ssh_config_alias(old_label, new_label, last_new_file)
        
        self.state_manager.update_label(old_label, new_label)
        
        renamed_msg = _(
            'Renamed: {old} -> {new} ({count} type(s): {types})',
            old=old_label, new=new_label, count=renamed_count,
            types=', '.join(types_to_rename),
        )
        print(f"✅ {renamed_msg}")
        print(f"💡 {_('Tip: if any repo uses alias {alias},', alias=self._get_host_alias(old_label))}")
        tip_msg = _("re-run 'sshm use {new_label}' in that repo to update remote URL", new_label=new_label)
        print(f"   {tip_msg}")
    
    # ------------------------------------------------------------------------
    # Git 仓库相关操作 (use, info, test)
    # ------------------------------------------------------------------------
    
    def use_key_for_repo(self, label: str, repo_path: str = '.', 
                         skip_confirm: bool = False):
        """为指定 Git 仓库配置使用特定密钥"""
        repo_path = Path(repo_path).resolve()
        
        if not (repo_path / '.git').exists():
            self._fail(f"❌ {_('Not a git repository: {path}', path=repo_path)}")
            print("   " + _("Please run this command inside a Git repository"))
            return
        
        key_type = self._detect_key_type_for_label(label)
        if not key_type:
            msg = _("No key found for label '{label}'", label=label)
            self._fail(f"❌ {msg}")
            return
        
        print_section_header(_("Configure Key for Git Repo: {label}", label=label))
        print(f"📂 {_('Repo path:')} {repo_path}\n")

        key_file = self.ssh_dir / f"id_{key_type}.{label}"

        try:
            result = subprocess.run(
                ['git', '-C', str(repo_path), 'remote', 'get-url', 'origin'],
                capture_output=True,
                text=True,
                check=True
            )
            current_url = result.stdout.strip()
            print(f"🔗 {_('Current Remote URL:')}\n   {current_url}\n")
            
            parsed = self._parse_git_url(current_url)
            if not parsed:
                self._fail("❌ " + _("Failed to parse Git URL"))
                return
            
            platform, user, repo = parsed
            print(f"📊 {_('Parsed info:')}")
            print(f"   {_('Platform:')} {platform}")
            print(f"   {_('User/Org:')} {user}")
            print(f"   {_('Repo:')} {repo}\n")

            # 私有化/非标准 Git：校验并自动对齐 hostname 映射
            repo_hostname = self._resolve_repo_hostname(current_url)
            if not self._align_hostname_with_repo(label, repo_hostname, skip_confirm):
                return

            # 确保 SSH config 别名存在且唯一（此时 hostname 已对齐，别名正确）
            host_alias = self._get_host_alias(label)
            self._update_ssh_config_alias(label, key_file)
            new_url = f"git@{host_alias}:{user}/{repo}.git"
            
            print(f"🔧 {_('New Remote URL:')}")
            print(f"   {new_url}\n")
            
            if not skip_confirm:
                if not prompt_confirm(_("Update Remote URL?")):
                    self._fail("❌ " + _("operation cancelled"))
                    return

            # 先测试 SSH 连接，再更新 URL，避免留下无法认证的坏配置
            print("🧪 " + _("Testing SSH connection..."))
            test_ok, test_msg = self._test_ssh_connection(host_alias)
            if test_ok:
                print("✅ " + _("SSH connection test passed!"))
                if 'Hi' in test_msg or 'Welcome' in test_msg:
                    print(f"   {test_msg}")
            else:
                print("⚠️  " + _("SSH connection test failed"))
                print(f"   {test_msg}")
                print("   " + _("The public key may not have been added to the platform yet."))
                if not skip_confirm:
                    if not prompt_confirm(_("SSH test failed, still update the remote URL?")):
                        self._fail("❌ " + _("operation cancelled"))
                        return

            subprocess.run(
                ['git', '-C', str(repo_path), 'remote', 'set-url', 'origin', new_url],
                check=True
            )
            print("✅ " + _("Remote URL updated") + "\n")

            print("\n" + "=" * 70)
            print("✅ " + _("Configuration complete! Now you can use:"))
            print(f"   cd {repo_path}")
            print(f"   git push")
            print("=" * 70)
            
        except subprocess.CalledProcessError as e:
            if 'No such remote' in str(e.stderr):
                self._fail("❌ " + _("No 'origin' remote found"))
                print("   " + _("Please add a remote first: git remote add origin <url>"))
            else:
                self._fail(f"❌ {_('Git command failed: {err}', err=e)}")
        except subprocess.TimeoutExpired:
            self._fail("⚠️  " + _("SSH connection test timed out"))
        except Exception as e:
            self._fail(f"❌ {_('error')}: {e}")    
    # ------------------------------------------------------------------------
    # Git 仓库作者相关操作 (author)
    # ------------------------------------------------------------------------

    def show_repo_author(self, repo_path: str = '.'):
        """显示当前 Git 仓库的作者配置"""
        print_section_header(_("Git Repo Author Info"))
        repo_path = Path(repo_path).resolve()

        if not (repo_path / '.git').exists():
            self._fail(f"❌ {_('Not a git repository: {path}', path=repo_path)}")
            print("   " + _("Please run this command inside a Git repository"))
            return

        print(f"📂 {_('Repo path:')} {repo_path}\n")

        local_name = self._git_get_config(repo_path, 'local', 'user.name')
        local_email = self._git_get_config(repo_path, 'local', 'user.email')
        global_name = self._git_get_config(repo_path, 'global', 'user.name')
        global_email = self._git_get_config(repo_path, 'global', 'user.email')

        def fmt(value, source):
            if not value:
                return _("not set")
            return f"{value}  [{source}]"

        print(f"👤 {_('Author name:')} {fmt(local_name, 'local')}")
        print(f"📧 {_('Author email:')} {fmt(local_email, 'local')}")
        print()
        if global_name or global_email:
            g_author = f"{global_name or _('not set')} <{global_email or _('not set')}>"
            print(f"🌍 {_('Global author:')} {g_author}")
        if local_name or local_email:
            print("   " + _("Current effective: repo-level (local) config overrides global"))
        print()
        print("💡 " + _("Tip: use 'sshm author list' to view saved authors"))
        print("   " + _("Use 'sshm author use <label>' to quickly set the current repo author"))
        print("   " + _("Use 'sshm author unset' to clear repo-level config"))

    def set_repo_author(self, label: str, repo_path: str = '.',
                        name: Optional[str] = None, email: Optional[str] = None,
                        scope: str = 'local', skip_confirm: bool = False):
        """为指定 Git 仓库设置作者信息（global 作用域不需要仓库）"""
        repo_path = Path(repo_path).resolve()

        if scope != 'global' and not (repo_path / '.git').exists():
            self._fail(f"❌ {_('Not a git repository: {path}', path=repo_path)}")
            print("   " + _("Please run this command inside a Git repository"))
            return

        author = self._get_author_info(label, name, email, repo_path)
        if not author:
            return

        print_section_header(_("Set Author for Git Repo: {label}", label=label))
        print(f"📂 {_('Repo path:')} {repo_path}\n")

        current_name = self._git_get_config(repo_path, scope, 'user.name')
        current_email = self._git_get_config(repo_path, scope, 'user.email')
        scope_name = _("global") if scope == 'global' else _("repo-level")

        # 摘要：未提供的字段明确展示当前值，并注明将保持不变
        not_set = _("not set")
        keep = _("(no new value, keeping current)")
        if author['name']:
            print(f"👤 {_('Author name:')} {author['name']}")
        else:
            print(f"👤 {_('Author name:')} {current_name or not_set}{keep}")
        if author['email']:
            print(f"📧 {_('Author email:')} {author['email']}")
        else:
            print(f"📧 {_('Author email:')} {current_email or not_set}{keep}")

        if (current_name or current_email) and not skip_confirm:
            print(f"\n⚠️  {_('Current {scope} author configured:', scope=scope_name)}")
            print(f"   user.name: {current_name or not_set}")
            print(f"   user.email: {current_email or not_set}")
            if not prompt_confirm(_("Overwrite?")):
                self._fail("❌ " + _("operation cancelled"))
                return

        changed = []
        unchanged = []
        try:
            if author['name']:
                subprocess.run(
                    ['git', '-C', str(repo_path), 'config', f'--{scope}', 'user.name', author['name']],
                    check=True, capture_output=True
                )
                changed.append(f"user.name = {author['name']}")
            else:
                unchanged.append(f"user.name = {current_name or _('not set')}")
            if author['email']:
                subprocess.run(
                    ['git', '-C', str(repo_path), 'config', f'--{scope}', 'user.email', author['email']],
                    check=True, capture_output=True
                )
                changed.append(f"user.email = {author['email']}")
            else:
                unchanged.append(f"user.email = {current_email or _('not set')}")
        except subprocess.CalledProcessError as e:
            self._fail(f"❌ {_('Git command failed: {err}', err=e)}")
            return

        if not changed:
            self._fail("\n⚠️  " + _("No author info available to set"))
            return

        print(f"\n✅ {_('Set ({scope}):', scope=scope_name)}")
        for item in changed:
            print(f"   - {item}")
        if unchanged:
            print("\nℹ️ " + _("Unchanged (keeping current):"))
            for item in unchanged:
                print(f"   - {item}")
        print("\n💡 " + _("Verify: git config user.name && git config user.email"))

    def unset_repo_author(self, repo_path: str = '.', scope: str = 'local'):
        """清除当前 Git 仓库的作者配置（回落到全局）"""
        repo_path = Path(repo_path).resolve()

        if not (repo_path / '.git').exists():
            self._fail(f"❌ {_('Not a git repository: {path}', path=repo_path)}")
            print("   " + _("Please run this command inside a Git repository"))
            return

        scope_name = _("global") if scope == 'global' else _("repo-level")
        fallback_name = _("system-level") if scope == 'global' else _("global")
        if not prompt_confirm(_(
            "Confirm clearing current {scope} author config? It will fall back to {fallback} config",
            scope=scope_name, fallback=fallback_name,
        )):
            self._fail("❌ " + _("operation cancelled"))
            return

        removed = []
        for key in ('user.name', 'user.email'):
            try:
                subprocess.run(
                    ['git', '-C', str(repo_path), 'config', f'--{scope}', '--unset-all', key],
                    check=True, capture_output=True
                )
                removed.append(key)
            except subprocess.CalledProcessError:
                pass

        if removed:
            print(f"✅ {_('Cleared ({scope}): {keys}', scope=scope_name, keys=', '.join(removed))}")
        else:
            print("ℹ️  " + _("No config found to clear"))

    def add_author(self, label: str, name: Optional[str] = None,
                   email: Optional[str] = None):
        """添加/更新作者到状态文件（author 列表）"""
        label_lower = label.lower()

        # 更新语义：未提供的字段保留已有值，邮箱缺失时尝试从公钥注释补全
        stored = self.state_manager.read_authors().get(label_lower, {})
        final_name = name or stored.get('name', '')
        final_email = (email or stored.get('email', '')
                       or self._extract_email_from_pubkey(label_lower) or '')

        if not (final_name or final_email):
            self._fail("❌ " + _("Need at least a name or email"))
            print("   " + _("Usage: sshm author add <label> -n \"name\" -e \"email\""))
            print("   " + _("Tip: if a key with this label exists, email is auto-filled from the public key comment"))
            return

        self.state_manager.write_author(label_lower, final_name, final_email)

        not_set = _("not set")
        print_section_header(_("Author saved: {label}", label=label))
        print(f"👤 {_('Name:')} {final_name or not_set}")
        print(f"📧 {_('Email:')} {final_email or not_set}")
        print("\n✅ " + _("Saved to author list"))
        print("   " + _("Use 'sshm author list' to view all authors"))
        print("   " + _("Use 'sshm author use <label>' to apply to the current repo"))

    def list_authors(self, repo_path: str = '.'):
        """列出所有已保存的作者

        Args:
            repo_path: Git 仓库路径，用于判断当前生效作者及其层级（默认当前目录）
        """
        print_section_header(_("Saved Authors List"))
        authors = self.state_manager.read_authors()
        if not authors:
            print("📭 " + _("No saved authors yet"))
            print("   " + _("Use 'sshm author add <label> -n name -e email' to add an author"))
            return

        not_set = _("not set")
        repo = Path(repo_path).resolve()
        in_repo = (repo / '.git').exists()

        # 读取当前生效作者（local 覆盖 global），用于标记"正在使用"及其层级
        eff_name = eff_email = None
        scope = None
        if in_repo:
            local_name = self._git_get_config(repo, 'local', 'user.name')
            local_email = self._git_get_config(repo, 'local', 'user.email')
            global_name = self._git_get_config(repo, 'global', 'user.name')
            global_email = self._git_get_config(repo, 'global', 'user.email')

            if local_name or local_email:
                eff_name, eff_email = local_name, local_email
                scope = _('repo-level')    # 仓库级生效
            elif global_name or global_email:
                eff_name, eff_email = global_name, global_email
                scope = _('global')        # 全局生效
        else:
            # 不在 git 仓库内：回退读取全局配置，展示全局生效
            global_name = self._git_get_config(Path.home(), 'global', 'user.name')
            global_email = self._git_get_config(Path.home(), 'global', 'user.email')
            if global_name or global_email:
                eff_name, eff_email = global_name, global_email
                scope = _('global')

        eff_email_lower = (eff_email or '').lower()
        eff_name_lower = (eff_name or '').lower()

        rows = []
        for label in sorted(authors):
            info = authors[label]
            name = info.get('name') or ''
            email = info.get('email') or ''
            # 正在使用判断：邮箱精确匹配优先，其次姓名匹配
            is_active = bool(email and email.lower() == eff_email_lower) \
                or (not email and name and name.lower() == eff_name_lower)
            icon = '✨' if is_active else ''
            label_scope = scope if is_active else ''
            rows.append([
                icon,
                label.upper(),
                name or not_set,
                email or not_set,
                label_scope,
            ])

        print_table([_('Status'), _('Label'), _('Name:'), _('Email:'),
                     _('Scope')],
                    rows, truncatable=[2, 3], center_cols=[0])

        print("\n💡 " + _("Usage:"))
        print("   sshm author use <label> [--global]   # " + _("Apply to current repo/global"))
        print("   sshm author remove <label>           # " + _("Remove author"))
        print("   sshm author add <label> -n name -e email  # " + _("Add/update author"))

    def remove_author(self, label: str, skip_confirm: bool = False):
        """从作者列表移除指定标签的作者（不影响已写入的 git config）"""
        label_lower = label.lower()
        authors = self.state_manager.read_authors()
        if label_lower not in authors:
            self._fail(f"❌ {_('Saved author not found: {label}', label=label)}")
            print("   " + _("Use 'sshm author list' to view saved authors"))
            return

        not_set = _("not set")
        info = authors[label_lower]
        print(_("About to remove author: {label}", label=label))
        print(f"  👤 {_('Name:')} {info.get('name') or not_set}")
        print(f"  📧 {_('Email:')} {info.get('email') or not_set}")

        if not skip_confirm and not prompt_confirm(_("Confirm remove?")):
            self._fail("❌ " + _("operation cancelled"))
            return

        self.state_manager.remove_author(label_lower)
        print(f"✅ {_('Author removed: {label}', label=label)}")
        print("   " + _("Note: already-applied git config will NOT be rolled back"))

    # ------------------------------------------------------------------------
    # 语言设置
    # ------------------------------------------------------------------------

    def set_language(self, lang: str) -> str:
        """设置输出语言并持久化到状态文件

        Args:
            lang: 'en' 或 'zh'

        Returns:
            实际生效的语言（非法值回退 'en'）
        """
        lang = lang if lang == 'zh' else 'en'
        self.state_manager.write_lang(lang)
        from ..i18n import set_lang
        set_lang(lang)
        return lang

    def get_language(self) -> str:
        """获取当前生效的语言"""
        from ..i18n import get_lang
        return get_lang()

    def _git_get_config(self, repo_path: Path, scope: str, key: str) -> Optional[str]:
        """读取 git 配置项（local/global）"""
        try:
            result = subprocess.run(
                ['git', '-C', str(repo_path), 'config', f'--{scope}', key],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip() or None
        except (subprocess.CalledProcessError, OSError):
            return None

    def _get_author_info(self, label: str, name: Optional[str] = None,
                         email: Optional[str] = None,
                         repo_path: Optional[Path] = None) -> Optional[Dict[str, str]]:
        """按优先级获取标签对应的作者信息"""
        label_lower = label.lower()
        result = {'name': name or '', 'email': email or ''}

        # 1. 状态文件中的 authors 映射（add 时自动记录）
        stored = self.state_manager.read_authors().get(label_lower)
        if stored:
            if not result['name']:
                result['name'] = stored.get('name', '')
            if not result['email']:
                result['email'] = stored.get('email', '')

        # 2. 从公钥注释提取邮箱（-C email 写入）
        if not result['email']:
            result['email'] = self._extract_email_from_pubkey(label_lower)

        # 3. 从 remote URL 推断用户名（最低优先级）
        if not result['name'] and repo_path is not None:
            result['name'] = self._infer_author_name_from_remote(repo_path) or ''

        if not (result['name'] or result['email']):
            key_type = self._detect_key_type_for_label(label)
            if not key_type:
                msg = _("No key found for label '{label}'", label=label)
                self._fail(f"❌ {msg}")
                print("\n💡 " + _("Use 'sshm list' to view all available keys"))
                return None
            msg = _("Label '{label}' has no usable author info", label=label)
            self._fail(f"⚠️  {msg}")
            print("   " + _("Available remedies:"))
            print(f"   - sshm add {label} <email> --name \"name\"   # " + _("recreate key and record author"))
            print(f"   - sshm author {label} --name \"name\" --email <email>  # " + _("temporary override"))
            return None

        return result

    def _extract_email_from_pubkey(self, label: str) -> Optional[str]:
        """从公钥注释中提取邮箱（-C email 写入）"""
        key_type = self._detect_key_type_for_label(label)
        if not key_type:
            return None
        pub_file = self.ssh_dir / f"id_{key_type}.{label}.pub"
        if not pub_file.exists():
            return None
        try:
            parts = pub_file.read_text(encoding='utf-8').strip().split()
            if len(parts) >= 3:
                comment = parts[-1]
                if re.match(r'^[^@\s]+@[^@\s]+$', comment):
                    return comment
        except (OSError, UnicodeDecodeError):
            pass
        return None

    def _infer_author_name_from_remote(self, repo_path: Path) -> Optional[str]:
        """从 remote URL 推断用户名（git@github.com:allureyc/repo.git → allureyc）"""
        try:
            result = subprocess.run(
                ['git', '-C', str(repo_path), 'remote', 'get-url', 'origin'],
                capture_output=True, text=True, check=True
            )
            parsed = self._parse_git_url(result.stdout.strip())
            if parsed:
                return parsed[1]
        except (subprocess.CalledProcessError, OSError):
            pass
        return None

    def show_repo_info(self, repo_path: str = '.'):
        """显示当前 Git 仓库的 SSH 配置信息"""
        print_section_header(_("Git Repo Config Info"))
        
        repo_path = Path(repo_path).resolve()
        
        if not (repo_path / '.git').exists():
            self._fail(f"❌ {_('Not a valid Git repository: {path}', path=repo_path)}")
            return
        
        print(f"📂 {_('Repo path:')} {repo_path}")
        
        try:
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            remote_url = result.stdout.strip()
            print(f"🔗 {_('Remote URL:')} {remote_url}")
            
            parsed = self._parse_git_url(remote_url)
            if parsed:
                platform, user, repo = parsed
                print(f"\n📊 {_('Parsed info:')}")
                print(f"  ├─ {_('Platform:')} {platform}")
                print(f"  ├─ {_('User/Org:')} {user}")
                print(f"  └─ {_('Repo:')} {repo}")
                
                ssh_pattern = r'git@([^:]+):'
                match = re.match(ssh_pattern, remote_url)
                if match:
                    host_alias = match.group(1)
                    # 反解别名对应的标签（容忍主机名首段含连字符，如 git-codecommit-{label}）
                    label = self._resolve_label_from_alias(host_alias)
                    if label:
                        print(f"\n🔑 {_('Current alias in use: {alias}', alias=host_alias)}")
                        
                        key_type = self._detect_key_type_for_label(label)
                        if key_type:
                            key_file = self.ssh_dir / f"id_{key_type}.{label}"
                            pub_file = self.ssh_dir / f"id_{key_type}.{label}.pub"
                            
                            print(f"\n🗝️  {_('Key info:')}")
                            print(f"  ├─ {_('Label')}: {label}")
                            print(f"  ├─ {_('key type')}: {key_type}")
                            print(f"  ├─ {_('Private key:')} {key_file}")
                            print(f"  └─ {_('Public key:')} {pub_file}")
                            
                            ssh_config = self.config_manager.config_file
                            if ssh_config.exists():
                                with open(ssh_config, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                    if host_alias.lower() in content.lower():
                                        print(f"\n📝 {_('SSH Config:')}")
                                        lines = content.split('\n')
                                        in_host = False
                                        for line in lines:
                                            if host_alias.lower() in line.lower():
                                                in_host = True
                                            if in_host:
                                                print(f"  {line}")
                                                if line.strip() and not line.startswith(' ') and not line.startswith('\t') and host_alias.lower() not in line.lower():
                                                    break
                        else:
                            msg = _("No key file found for label '{label}'", label=label)
                            print(f"\n⚠️  {msg}")
                    else:
                        print(f"\n💡 " + _("Tip: using a standard SSH URL or unconfigured alias"))
                        print(f"   " + _("Use 'sshm use <label>' to configure a key"))
                else:
                    print(f"\n💡 " + _("Tip: using an HTTPS URL"))
                    print(f"   " + _("Use 'sshm use <label>' to convert to SSH and configure a key"))
            else:
                print("\n⚠️  " + _("Failed to parse remote URL"))
                
        except subprocess.CalledProcessError as e:
            if 'No such remote' in str(e.stderr):
                print("\n⚠️  " + _("No 'origin' remote configured"))
            else:
                print(f"\n❌ {_('Git command failed: {err}', err=e)}")
        except Exception as e:
            print(f"\n❌ {_('error')}: {e}")
    
    def test_connection(self, label: Optional[str] = None, test_all: bool = False, 
                       repo_path: str = '.'):
        """测试 SSH 连接"""
        if test_all:
            print_section_header(_("Test All SSH Key Connections"))
            
            keys_by_label = self._scan_all_keys()
            if not keys_by_label:
                self._fail("❌ " + _("No keys found"))
                return
            
            results = []
            no_alias_msg = _("no alias configured, run 'sshm use <label>' first")
            for label, key_infos in keys_by_label.items():
                host_alias = self._get_host_alias(label)
                key_types = ', '.join([k['type'] for k in key_infos])
                
                # 未配置 config 别名的标签无法路由，跳过并给出明确提示
                if not self.config_manager.has_host(host_alias):
                    results.append((label, host_alias, key_types,
                                    (False, no_alias_msg)))
                    continue
                
                result = self._test_ssh_connection(host_alias)
                results.append((label, host_alias, key_types, result))
            
            print("\n" + "=" * 70)
            print(_("Test Results Summary:"))
            print("=" * 70)
            for label, host_alias, key_types, (success, message) in results:
                status = "✅" if success else "❌"
                print(f"{status} {pad_cell(label, 20)} ({pad_cell(host_alias, 30)}) [{key_types}]")
                if not success:
                    print(f"    {message}")
            
        elif label:
            print_section_header(_("Test SSH Connection: {label}", label=label))
            
            key_type = self._detect_key_type_for_label(label)
            if not key_type:
                msg = _("No key found for label '{label}' (key files)", label=label)
                self._fail(f"❌ {msg}")
                print(f"\n💡 " + _("Use 'sshm list' to view all available keys"))
                return
            
            host_alias = self._get_host_alias(label)
            
            print(f"🔑 {_('key label')}: {label}")
            print(f"🌐 {_('Host:')} {host_alias}")
            
            # 未配置 config 别名时无法路由到真实主机，直接给出友好提示
            if not self.config_manager.has_host(host_alias):
                print(f"\n⚠️  {_('Alias {alias} not configured in SSH config', alias=host_alias)}")
                print(f"   " + _("Run 'sshm use {label}' first to create the alias config", label=label))
                print(f"   " + _("Or run 'sshm use {label} --global' to set as global default before testing", label=label))
                return
            
            print(f"\n🧪 " + _("Testing connection..."))
            
            success, message = self._test_ssh_connection(host_alias)
            if success:
                print(f"✅ {message}")
            else:
                self._fail(f"❌ {message}")        
        else:
            print_section_header(_("Test Current Repo SSH Connection"))
            
            repo_path = Path(repo_path).resolve()
            
            if not (repo_path / '.git').exists():
                self._fail(f"❌ {_('Not a valid Git repository: {path}', path=repo_path)}")
                return
            
            print(f"📂 {_('Repo path:')} {repo_path}")
            
            try:
                result = subprocess.run(
                    ['git', 'remote', 'get-url', 'origin'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=True
                )
                remote_url = result.stdout.strip()
                print(f"🔗 {_('Remote URL:')} {remote_url}")
                
                ssh_pattern = r'git@([^:]+):'
                match = re.match(ssh_pattern, remote_url)
                if match:
                    host_alias = match.group(1)
                    print(f"\n🧪 {_('Testing {host}...', host=host_alias)}")
                    
                    success, message = self._test_ssh_connection(host_alias)
                    if success:
                        print(f"✅ {message}")
                    else:
                        self._fail(f"❌ {message}")
                        print(f"\n💡 " + _("Tip: check that your key config is correct"))
                        print(f"   " + _("Use 'sshm info' to view config details"))
                else:
                    print("\n⚠️  " + _("Current URL is not an SSH URL, cannot test connection"))
                    print("   " + _("Use 'sshm use <label>' to convert to SSH URL"))
                    
            except subprocess.CalledProcessError as e:
                if 'No such remote' in str(e.stderr):
                    print("\n⚠️  " + _("No 'origin' remote configured"))
                else:
                    print(f"\n❌ {_('Git command failed: {err}', err=e)}")
            except Exception as e:
                print(f"\n❌ {_('error')}: {e}")
    
    def _test_ssh_connection(self, host: str) -> Tuple[bool, str]:
        """测试 SSH 连接（兼容 GitHub/GitLab/Bitbucket/自建 Git 平台）

        优先用平台成功/失败关键词判断；平台文案未知时以退出码兜底。
        """
        try:
            result = subprocess.run(
                ['ssh', '-T', f'git@{host}'],
                capture_output=True,
                text=True,
                timeout=10
            )

            output = (result.stdout or '') + (result.stderr or '')
            low = output.lower()

            # 1) 命中明确的成功关键词
            if any(m in low for m in _SSH_SUCCESS_MARKERS):
                match = (re.search(r'Hi ([^!]+)!', output)
                         or re.search(r'Welcome to [^,]+, (@?[\w.-]+)', output))
                user = match.group(1) if match else None
                if user:
                    return (True, _("Authenticated successfully! (Hi {user}!)", user=user))
                return (True, _("Connected successfully!"))

            # 2) 命中明确的失败关键词
            if any(m in low for m in _SSH_FAILURE_MARKERS):
                return (False, _("Connection failed: {detail}",
                                 detail=output.strip()[:100]))

            # 3) 平台文案未知时以退出码兜底
            if result.returncode == 0:
                return (True, _("Connected successfully!"))
            return (False, _("Connection failed: {detail}",
                             detail=output.strip()[:100]))

        except subprocess.TimeoutExpired:
            return (False, _("Connection timed out"))
        except FileNotFoundError:
            return (False, _("ssh command not found"))
        except Exception as e:
            return (False, f"{_('error')}: {str(e)}")
    
    def _parse_git_url(self, url: str) -> Optional[Tuple[str, str, str]]:
        """解析 Git URL，支持 ssh://、git@、https:// 三种格式"""
        # scp-like 格式: git@github.com:user/repo.git
        ssh_pattern = r'git@([^:]+):([^/]+)/(.+?)(?:\.git)?$'
        match = re.match(ssh_pattern, url)
        if match:
            hostname, user, repo = match.groups()
            return (self._platform_from_hostname(hostname), user, repo)
        
        # 带协议前缀的 SSH 格式: ssh://git@host/user/repo.git
        #  或 ssh://git@host:port/user/repo.git
        ssh2_pattern = r'ssh://(?:git@)?([^/:]+)(?::\d+)?/([^/]+)/(.+?)(?:\.git)?$'
        match = re.match(ssh2_pattern, url)
        if match:
            hostname, user, repo = match.groups()
            return (self._platform_from_hostname(hostname), user, repo)
        
        # HTTPS 格式: https://host/user/repo.git
        https_pattern = r'https?://([^/]+)/([^/]+)/(.+?)(?:\.git)?$'
        match = re.match(https_pattern, url)
        if match:
            hostname, user, repo = match.groups()
            return (self._platform_from_hostname(hostname), user, repo)
        
        return None

    @staticmethod
    def _platform_from_hostname(hostname: str) -> str:
        """从主机名推断平台标识（取首段，去掉可能的端口）"""
        hostname = hostname.split(':')[0]
        if '-' in hostname:
            return hostname.split('-')[0]
        return hostname.split('.')[0]
    
    # ------------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------------

    def _copy_key_pair(self, source: Path, target: Path):
        """复制密钥对（私钥 + 可选公钥），公钥缺失时不中断"""
        shutil.copy2(source, target)
        pub_source = Path(str(source) + '.pub')
        if pub_source.exists():
            shutil.copy2(pub_source, Path(str(target) + '.pub'))

    def _detect_key_type_for_label(self, label: str) -> Optional[str]:
        """检测指定标签的密钥类型"""
        for key_type in SUPPORTED_KEY_TYPES:
            key_file = self.ssh_dir / f"id_{key_type}.{label}"
            if key_file.exists():
                return key_type
        return None
    
    def _detect_default_key_type(self) -> Optional[str]:
        """检测默认密钥类型"""
        for key_type in SUPPORTED_KEY_TYPES:
            key_file = self.ssh_dir / f"id_{key_type}"
            if key_file.exists():
                return key_type
        return None
    
    def _get_hostname_for_label(self, label: str) -> str:
        """根据标签获取主机名（优先使用 add 时记录的映射）"""
        label_lower = label.lower()
        hosts = self.state_manager.read_hosts()
        if label_lower in hosts and hosts[label_lower]:
            return hosts[label_lower]

        hostname_map = {
            'github': 'github.com',
            'gitlab': 'gitlab.com',
            'gitee': 'gitee.com',
            'bitbucket': 'bitbucket.org',
        }
        for key, host in hostname_map.items():
            if key in label_lower:
                return host
        return 'github.com'
    
    def _get_host_alias(self, label: str) -> str:
        """生成 SSH config 别名（统一小写，避免大小写变体冲突）

        别名格式为 '{主域名}-{label}'，如 github.com-eavelabs、
        gitlab.com-xxx、git.build.ingka.ikea.com-allureyc。
        主域名 = 完整 hostname 移除最后一个 '.' 之后的 TLD 段，
        再把剩余的 '.' 替换为 '-'。这样生成的别名：
        - SSH 可接受（不含 '>' 等非法字符）
        - 极大避免不同服务器的主域名前缀冲突
        （如 github.com→github-xxx，git.build.ingka.ikea.com→
          git-build-ingka-ikea-xxx）
        """
        hostname = self._get_hostname_for_label(label)
        # 移除最后一个 '.' 之后的 TLD 段（如 .com/.org/.net）
        base = hostname
        if '.' in hostname:
            base = hostname.rsplit('.', 1)[0]
        # 剩余 '.' 替换为 '-'
        main_domain = base.replace('.', '-')
        return f"{main_domain}-{label.lower()}"

    def _resolve_label_from_alias(self, host_alias: str) -> Optional[str]:
        """从 SSH config 别名反解标签

        别名格式为 '{主机名首段}-{label}'，但主机名首段本身可能含连字符
        （如 git-codecommit.us-east-1.amazonaws.com → 'git-codecommit-{label}'），
        因此不能直接按 '-' 切分。这里遍历 hosts 映射与密钥标签，
        用完整别名精确匹配，避免反向解析出错。
        """
        host_alias_lower = host_alias.lower()
        candidates = list(self.state_manager.read_hosts().keys())
        candidates.extend(self._scan_all_keys().keys())
        for label in candidates:
            if self._get_host_alias(label) == host_alias_lower:
                return label
        return None

    def _resolve_repo_hostname(self, url: str) -> Optional[str]:
        """从 Git remote URL 提取真实主机名（别名优先从 SSH config HostName 反查）

        返回 SSH 实际连接的目标 hostname：
        - 真实 hostname（git@github.com:... → github.com）
        - 简短别名（git@github-eavelabs:...）：若 SSH config 有该 Host 块，
          反查其 HostName 得到真实域名（最准）；否则视为真实 hostname

        已配置 SSH config 的别名，HostName 就是 SSH 真正连接的域名，
        以此还原最准确。
        """
        ssh2_match = re.match(r'ssh://(?:git@)?([^/:]+)', url)
        host = ssh2_match.group(1) if ssh2_match else None
        if not host:
            ssh_match = re.match(r'git@([^:]+):', url)
            host = ssh_match.group(1) if ssh_match else None
        if not host:
            https_match = re.match(r'https?://([^/]+)/', url)
            host = https_match.group(1) if https_match else None
        if not host:
            return None

        # 若 SSH config 中存在该 Host 块，反查其 HostName 得到真实域名
        resolved = self.config_manager.get_hostname(host)
        if resolved:
            return resolved
        return host

    def _align_hostname_with_repo(self, label: str, repo_hostname: str,
                                  skip_confirm: bool) -> bool:
        """确保标签映射到仓库的真实 hostname（适配私有化 Git）

        当仓库 hostname 与标签当前映射不一致时（如私有 GitLab），提示用户：
        - 标签含已知平台关键词（github/gitlab 等）且仓库是私有域名 → 建议创建匹配配置
        - 用户确认（或 -y）后，持久化 host 映射并返回 True；否则返回 False
        """
        if not repo_hostname:
            return True
        current = self._get_hostname_for_label(label)
        if current == repo_hostname:
            return True

        print(f"\n⚠️  " + _("The repo hostname ({host}) differs from the one mapped to label '{label}' ({cur})",
                          host=repo_hostname, label=label, cur=current))
        print("   " + _("This is likely a private/self-hosted Git server."))
        print("   " + _("To connect, an SSH config matching '{host}' is needed.", host=repo_hostname))

        if skip_confirm:
            self.state_manager.write_host(label, repo_hostname)
            print("✅ " + _("Updated host mapping: {label} -> {host}", label=label, host=repo_hostname))
            return True

        if prompt_confirm(_("Create matching SSH config for '{host}' and use it?", host=repo_hostname),
                          default='y'):
            self.state_manager.write_host(label, repo_hostname)
            print("✅ " + _("Updated host mapping: {label} -> {host}", label=label, host=repo_hostname))
            return True
        self._fail("⚠️  " + _("Skipped. The key may not work for this repo without a matching host mapping."))
        return False

    def _detect_repo_key_label(self, repo_path: str = '.') -> Optional[str]:
        """检测当前 Git 仓库正在使用的密钥标签（仓库级）

        通过解析 remote URL 中的 SSH 别名，反解出对应的密钥标签。
        非 git 仓库、无 SSH remote 或无法反解时返回 None。
        """
        repo = Path(repo_path).resolve()
        if not (repo / '.git').exists():
            return None
        try:
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                cwd=repo, capture_output=True, text=True, check=True
            )
            remote_url = result.stdout.strip()
        except (subprocess.CalledProcessError, OSError):
            return None

        match = re.match(r'git@([^:]+):', remote_url)
        if not match:
            return None
        return self._resolve_label_from_alias(match.group(1))
    
    def _update_ssh_config_alias(self, label: str, key_file: Path):
        """自动更新 SSH config 别名配置"""
        hostname = self._get_hostname_for_label(label)
        host_alias = self._get_host_alias(label)
        
        self.config_manager.update_host(host_alias, hostname, key_file.resolve())
        self.state_manager.write_host(label, hostname)
        print(_("SSH config alias: {alias} -> {hostname}",
                alias=host_alias, hostname=hostname))
        print(_("   usage: git@{alias}:user/repo.git", alias=host_alias))

    def _remove_ssh_config_alias(self, label: str):
        """删除 SSH config 别名配置"""
        host_alias = self._get_host_alias(label)
        
        self.config_manager.remove_host(host_alias)
        self.state_manager.remove_host(label)
        print(_("SSH config alias removed: {alias}", alias=host_alias))

    def _rename_ssh_config_alias(self, old_label: str, new_label: str, new_key_file: Path):
        """重命名 SSH config 别名配置（主机名保持不变，同一把密钥换标签）"""
        hostname = self._get_hostname_for_label(old_label)
        old_alias = self._get_host_alias(old_label)
        new_alias = self._get_host_alias(new_label)

        if old_alias != new_alias:
            self.config_manager.remove_host(old_alias)
            self.config_manager.update_host(new_alias, hostname, new_key_file.resolve())
            self.state_manager.write_host(new_label, hostname)
            print(_("SSH config alias updated: {old} -> {new}",
                    old=old_alias, new=new_alias))
