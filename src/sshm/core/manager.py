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
from typing import Dict, List, Optional, Tuple, Union

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
    pad_cell,
    prompt_confirm,
    print_separator,
    print_section_header,
    print_table
)
from ..i18n import _
from .config import SSHConfigManager

# SSH 连接检测关键词（用于 test 命令的成功/失败判断）
_SSH_SUCCESS_MARKERS = (
    'successfully authenticated',
    'welcome to github',
    'welcome to gitlab',
    "you've successfully authenticated",
    'authenticated via ssh',
    'hi ',
    'successfully connected',
    'access granted',
    'connection established',
)
_SSH_FAILURE_MARKERS = (
    'permission denied',
    'fatal: ',
    'could not resolve hostname',
    'connection refused',
    'connection timed out',
    'authentication failed',
    'host key verification failed',
    'no such file or directory',
    'please make sure you have the correct access rights',
    'error: ',
    'invalid key',
    'denied',
    'unable to negotiate',
    'remote host identification has changed',
)
from .rewrite import RewriteConfig, rewrite_history, get_authors_in_repo
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

    def _ensure_directories(self) -> None:
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

    # 保留标签：original 为 use -g 切换时的系统备份，default 为默认密钥
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
            raise ValueError(_("err.label_empty"))
        label = label.strip()
        if not re.match(r'^[A-Za-z0-9][A-Za-z0-9_-]*$', label):
            raise ValueError(_(
                "err.label_invalid",
                label=label,
            ))
        if label.lower() in self.RESERVED_LABELS:
            raise ValueError(_("err.label_reserved", label=label))
        return True

    # ------------------------------------------------------------------------
    # 查询操作
    # ------------------------------------------------------------------------

    def list_keys(self, show_content: bool = False,
                  repo_path: Union[str, Path] = '.',
                  current_only: bool = False):
        """列出所有密钥（表格形式）

        Args:
            show_content: 是否显示公钥内容
            repo_path: Git 仓库路径，用于检测仓库级使用（默认当前目录）
            current_only: 仅显示当前仓库正在使用的密钥（list -c）
        """
        print_section_header(_("hdr.key_list"))
        print(f"\n{_('lbl.ssh_dir')} {self.ssh_dir}\n")

        keys_by_label = self._scan_all_keys()
        active_keys = self.state_manager.read_active_keys()

        if not keys_by_label:
            print("⚠️  " + _("msg.no_keys"))
            print("\n💡 " + _("msg.add_tip"))
            return

        # 指定仓库正在使用的密钥（仓库级，通过 remote URL 反解）
        repo_key = self._detect_repo_key_label(repo_path)

        # 按标签排序: 当前使用 -> 默认 -> 其他
        active_labels = set(active_keys.values())

        def sort_key(label: str) -> tuple[int, str]:
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
        global_scope = _('misc.global')
        repo_scope = _('misc.repo_level')
        headers = [_('lbl.status'), _('lbl.label'), _('lbl.file'), _('lbl.public'), _('lbl.size'),
                   _('lbl.modified'), _('lbl.alias'), _('lbl.scope')]
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
                print("⚠️  " + _("err.not_git_repo", path=Path(repo_path).resolve()))
            else:
                print("⚠️  " + _("msg.repo_key_missing"))
            print("   " + _("msg.configure_repo_tip"))
            print("   " + _("msg.or_list_all"))
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
            print_section_header("📋 " + _("hdr.public_contents"))
            for label, file_name, content in pub_map:
                print(f"\n[{label}] {file_name}.pub")
                print(f"  {content}\n")

        print_separator()
        print("💡 " + _("msg.use_tip"))
        print_separator()

    def list_backups(self) -> None:
        """列出所有备份"""
        print_section_header(_("hdr.backup_list"))

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
            # 跳过 use -g 切换的系统备份文件（id_*.original），不视为用户标签
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
            print(f"✅ {_('msg.backup_complete')} {backup_path}")
            print("📦 " + _("msg.files_backed_up", count=len(backed_up)))

        return backup_path

    def restore_backup(self, backup_name: Optional[str] = None,
                       key_type: Optional[str] = None,
                       skip_confirm: bool = False):
        """从备份恢复密钥"""
        print_section_header(_("hdr.restore"))

        if backup_name:
            backup_path = self.backup_dir / backup_name
            if not backup_path.exists():
                self._fail(f"❌ {_('err.backup_not_found')} {backup_path}")
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
            self._fail("❌ " + _("err.no_recoverable"))
            return

        print("\n📂 " + _("msg.will_restore_count", count=len(files)))
        for f in files:
            print(f"   - {f.name}")

        if not skip_confirm and not prompt_confirm("\n" + _("msg.restore_prompt")):
            self._fail("❌ " + _("misc.operation_cancelled"))
            return

        restored = []
        for f in files:
            try:
                shutil.copy2(f, self.ssh_dir / f.name)
                restored.append(f.name)
            except OSError as e:
                self._fail(f"❌ {_('err.restore_failed')} {f.name} ({e})")
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

    # ------------------------------------------------------------------------
    # 密钥创建与删除
    # ------------------------------------------------------------------------

    def add_key(self, label: str, email: str,
                key_type: str = DEFAULT_KEY_TYPE, host: Optional[str] = None,
                name: Optional[str] = None):
        """创建新密钥"""
        if key_type not in SUPPORTED_KEY_TYPES:
            raise ValueError(_(
                "err.unsupported_type",
                type=key_type, supported=', '.join(SUPPORTED_KEY_TYPES),
            ))

        self._validate_label(label)

        if not email or '@' not in email:
            raise ValueError(_(
                "err.invalid_email",
                email=email,
            ))

        key_file = self.ssh_dir / f"id_{key_type}.{label}"
        if key_file.exists():
            raise ValueError(_("err.key_exists", name=key_file.name))

        print(_("msg.creating_key", label=label, key_type=key_type))
        print(f"📧 {_('lbl.email_prompt')} {email}")

        cmd = [
            'ssh-keygen',
            '-t', key_type,
            '-C', email,
            '-f', str(key_file),
            '-N', ''
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"✅ {_('msg.key_created', name=key_file.name)}")

            if host:
                hostname = host
            else:
                hostname = self._get_hostname_for_label(label)
            # 持久化 label -> hostname 映射（供 use/remove/rename 使用）
            self.state_manager.write_host(label, hostname)
            if host:
                host_alias = self._get_host_alias(label)
                self.config_manager.update_host(host_alias, hostname, key_file)
                print(f"✅ {_('msg.ssh_config_updated', alias=host_alias, hostname=hostname)}")

            pub_file = Path(str(key_file) + '.pub')
            if pub_file.exists():
                pub_key = pub_file.read_text(encoding='utf-8').strip()
                print(f"\n📋 {_('msg.pub_key_content')}\n{pub_key}\n")
                print("💡 " + _("msg.add_to_platform"))

            # 记录作者信息（供 sshm author 使用）
            self.state_manager.write_author(label, name or '', email)
            if name:
                print(f"👤 {_('msg.author_recorded', name=name, email=email)}")

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
            self._fail(f"❌ {_('err.create_failed', err=detail)}")
        except Exception as e:
            self._fail(f"❌ {_('misc.error')}: {e}")

    def remove_key(self, label: str, key_type: Optional[str] = None):
        """删除密钥"""
        label_lower = label.lower()

        if label_lower == 'default':
            if key_type:
                confirm_msg = _("err.delete_default", type=key_type)
            else:
                confirm_msg = _("err.delete_all_default")

            if not prompt_confirm("⚠️  " + confirm_msg):
                self._fail("❌ " + _("misc.operation_cancelled"))
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
                        print(f"💾 {_('msg.auto_backed_up', path=backup_path)}")

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
                            print(f"💾 {_('msg.auto_backed_up', path=backup_path)}")

                        file.unlink()
                        removed_files.append(file.name)

        if removed_files:
            print(f"✅ {_('msg.deleted_count', count=len(removed_files))}")
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

            print(f"💡 {_('msg.tip_alias_remote', alias=self._get_host_alias(label))}")
            print("   " + _("msg.rerun_other_label"))
        else:
            self._fail(f"⚠️  {_('err.key_not_found', label=label)}")
    # ------------------------------------------------------------------------
    # 密钥切换
    # ------------------------------------------------------------------------

    def switch_key(self, label: str, key_type: Optional[str] = None):
        """切换默认密钥"""
        label_lower = label.lower()

        if label_lower in self.RESERVED_LABELS:
            label_msg = _('err.label_reserved_switch', label=label)
            self._fail(f"❌ {label_msg}")
            return

        if not key_type:
            key_type = self._detect_key_type_for_label(label)
            if not key_type:
                msg = _("err.key_not_found_short", label=label)
                self._fail(f"❌ {msg}")
                return
            print(f"🔍 {_('msg.auto_detected_type', key_type=key_type)}")

        source_file = self.ssh_dir / f"id_{key_type}.{label}"
        target_file = self.ssh_dir / f"id_{key_type}"

        if not source_file.exists():
            self._fail(f"❌ {_('err.key_missing', name=source_file.name)}")
            return

        if target_file.exists():
            active_keys = self.state_manager.read_active_keys()
            current_label = active_keys.get(key_type, 'original')

            original_backup = self.ssh_dir / f"id_{key_type}.original"
            if not original_backup.exists():
                self._copy_key_pair(target_file, original_backup)
                print(f"💾 {_('msg.original_backed_up', name=original_backup.name)}")

            if current_label != 'original':
                backup_file = self.ssh_dir / f"id_{key_type}.{current_label}"
                if not backup_file.exists():
                    self._copy_key_pair(target_file, backup_file)

        self._copy_key_pair(source_file, target_file)

        self.state_manager.write_active_key(key_type, label)

        self._update_ssh_config_alias(label, source_file)

        print(f"✅ {_('msg.switched_to', label=label, key_type=key_type)}")
        print(f"📁 {_('lbl.file_placeholder')} {target_file.name}")

        # 凭据↔人员自动联动：全局切换时自动设置全局 author（若 label 有绑定）
        self._apply_auto_author(label, repo_path=None, scope='global')

    def tag_key(self, key_type: Optional[str], new_label: str, switch_after: bool = False):
        """给默认密钥添加标签（key_type 为空时自动检测默认密钥类型）"""
        self._validate_label(new_label)

        if not key_type:
            key_type = self._detect_default_key_type()
            if not key_type:
                self._fail("❌ " + _("err.no_default_key"))
                return

        source_file = self.ssh_dir / f"id_{key_type}"
        target_file = self.ssh_dir / f"id_{key_type}.{new_label}"

        if not source_file.exists():
            self._fail(f"❌ {_('err.default_key_missing', name=source_file.name)}")
            return

        if target_file.exists():
            print(f"⚠️  {_('err.label_exists', new_label=new_label)}")
            if not prompt_confirm(_("misc.overwrite")):
                return

        self._copy_key_pair(source_file, target_file)

        # 继承默认密钥的元数据（host 映射 + 作者信息）
        # 默认密钥通常由 switch_key 从某标签复制而来，active_keys 记录了来源标签。
        self._inherit_metadata_from_default(key_type, new_label)

        print(f"✅ {_('msg.tag_added', new_label=new_label, key_type=key_type)}")

        if switch_after:
            self.switch_key(new_label, key_type)

    def _inherit_metadata_from_default(self, key_type: str, new_label: str):
        """给默认密钥打标签时，把默认密钥对应的 host/author 元数据继承给新标签。

        默认密钥的来源标签由 active_keys 记录；若无记录，则尝试从默认密钥的
        公钥注释提取 email 作为作者邮箱。
        """
        label_lower = new_label.lower()
        active_keys = self.state_manager.read_active_keys()
        source_label = active_keys.get(key_type, '')

        # 1. 继承 host 映射（来源标签有记录则继承，否则保留新标签自身兜底）
        if source_label:
            hosts = self.state_manager.read_hosts()
            if hosts.get(source_label):
                self.state_manager.write_host(label_lower, hosts[source_label])

        # 2. 继承/兜底 author：优先来源标签的 author，其次默认密钥 pubkey 注释 email
        author = None
        if source_label:
            author = self.state_manager.read_authors().get(source_label)
        if not author:
            email = self._extract_email_from_pubkey_default(key_type)
            if email:
                author = {'name': '', 'email': email}
        if author:
            self.state_manager.write_author(label_lower,
                                            author.get('name', '') or '',
                                            author.get('email', '') or '')

    def _extract_email_from_pubkey_default(self, key_type: str) -> Optional[str]:
        """从默认密钥（无标签）的公钥注释提取邮箱"""
        pub_file = self.ssh_dir / f"id_{key_type}.pub"
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

    def rename_tag(self, old_label: str, new_label: str,
                   key_type: str = DEFAULT_KEY_TYPE):
        """重命名密钥标签（处理该标签下的所有密钥类型，避免残留旧文件）"""
        old_label_lower = old_label.lower()
        new_label_lower = new_label.lower()

        if old_label_lower == 'default':
            self._fail("❌ " + _("err.cannot_rename_default"))
            return

        self._validate_label(new_label)
        if new_label_lower == old_label_lower:
            self._fail("⚠️  " + _("err.same_label"))
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
            msg = _("err.key_not_found_short", label=old_label)
            self._fail(f"❌ {msg}")
            return

        # 检查目标文件是否全部可用，避免部分重命名后中断
        for t in types_to_rename:
            new_file = self.ssh_dir / f"id_{t}.{new_label}"
            if new_file.exists():
                self._fail(f"⚠️  {_('err.target_exists', new_label=new_label, type=t)}")
                print(f"   {_('lbl.file_placeholder')} {new_file.name}")
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
            'msg.renamed',
            old=old_label, new=new_label, count=renamed_count,
            types=', '.join(types_to_rename),
        )
        print(f"✅ {renamed_msg}")
        print(f"💡 {_('msg.tip_alias', alias=self._get_host_alias(old_label))}")
        tip_msg = _("msg.rerun_new_label", new_label=new_label)
        print(f"   {tip_msg}")

    # ------------------------------------------------------------------------
    # Git 仓库相关操作 (use, info, test)
    # ------------------------------------------------------------------------

    def use_key_for_repo(self, label: str, repo_path: Union[str, Path] = '.',
                         skip_confirm: bool = False):
        """为指定 Git 仓库配置使用特定密钥"""
        repo_path = Path(repo_path).resolve()

        if not (repo_path / '.git').exists():
            self._fail(f"❌ {_('err.not_git_repo', path=repo_path)}")
            print("   " + _("err.run_in_repo"))
            return

        key_type = self._detect_key_type_for_label(label)
        if not key_type:
            msg = _("err.key_not_found_short", label=label)
            self._fail(f"❌ {msg}")
            return

        print_section_header(_("hdr.configure", label=label))
        print(f"📂 {_('lbl.repo_path')} {repo_path}\n")

        key_file = self.ssh_dir / f"id_{key_type}.{label}"

        try:
            result = subprocess.run(
                ['git', '-C', str(repo_path), 'remote', 'get-url', 'origin'],
                capture_output=True,
                text=True,
                check=True
            )
            current_url = result.stdout.strip()
            print(f"🔗 {_('lbl.current_remote_url')}\n   {current_url}\n")

            parsed = self._parse_git_url(current_url)
            if not parsed:
                self._fail("❌ " + _("err.failed_parse"))
                return

            platform, user, repo = parsed
            print(f"📊 {_('lbl.parsed_info')}")
            print(f"   {_('lbl.platform')} {platform}")
            print(f"   {_('lbl.user_org')} {user}")
            print(f"   {_('lbl.repo')} {repo}\n")

            # 私有化/非标准 Git：校验并自动对齐 hostname 映射
            repo_hostname = self._resolve_repo_hostname(current_url)
            if not self._align_hostname_with_repo(label, repo_hostname, skip_confirm):
                return

            # 确保 SSH config 别名存在且唯一（此时 hostname 已对齐，别名正确）
            host_alias = self._get_host_alias(label)
            self._update_ssh_config_alias(label, key_file)
            new_url = f"git@{host_alias}:{user}/{repo}.git"

            print(f"🔧 {_('lbl.new_remote_url')}")
            print(f"   {new_url}\n")

            if not skip_confirm:
                if not prompt_confirm(_("msg.update_url_prompt")):
                    self._fail("❌ " + _("misc.operation_cancelled"))
                    return

            # 先测试 SSH 连接，再更新 URL，避免留下无法认证的坏配置
            print("🧪 " + _("msg.testing_ssh"))
            test_ok, test_msg = self._test_ssh_connection(host_alias)
            if test_ok:
                print("✅ " + _("msg.ssh_test_passed"))
                if 'Hi' in test_msg or 'Welcome' in test_msg:
                    print(f"   {test_msg}")
            else:
                print("⚠️  " + _("msg.ssh_test_failed"))
                print(f"   {test_msg}")
                print("   " + _("msg.not_added_yet"))
                if not skip_confirm:
                    if not prompt_confirm(_("msg.update_url_anyway")):
                        self._fail("❌ " + _("misc.operation_cancelled"))
                        return

            subprocess.run(
                ['git', '-C', str(repo_path), 'remote', 'set-url', 'origin', new_url],
                check=True
            )
            print("✅ " + _("msg.remote_url_updated") + "\n")

            print("\n" + "=" * 70)
            print("✅ " + _("hdr.config_complete"))
            print(f"   cd {repo_path}")
            print(f"   git push")
            print("=" * 70)

            # 凭据↔人员自动联动：局部切换时自动设置仓库 author（若 label 有绑定）
            self._apply_auto_author(label, repo_path=str(repo_path), scope='local')

        except subprocess.CalledProcessError as e:
            if 'No such remote' in str(e.stderr):
                self._fail("❌ " + _("msg.no_origin_remote"))
                print("   " + _("msg.add_remote_first"))
            else:
                self._fail(f"❌ {_('err.git_failed', err=e)}")
        except subprocess.TimeoutExpired:
            self._fail("⚠️  " + _("msg.ssh_test_timed_out"))
        except Exception as e:
            self._fail(f"❌ {_('misc.error')}: {e}")

    # ------------------------------------------------------------------------
    # Git 仓库克隆 (clone)
    # ------------------------------------------------------------------------

    def clone_with_label(self, label: str, url: str,
                         target_dir: Optional[str] = None,
                         skip_confirm: bool = False):
        """使用指定密钥标签克隆 Git 仓库，并在克隆后为该仓库配置该密钥

        典型场景：本机默认用 A 账号，但想用 B 账号的密钥拉取 B 的仓库。
        流程：
        1. 校验标签存在可用密钥
        2. 解析 URL，得到平台 / 用户 / 仓库
        3. 对齐标签到仓库的真实 hostname（适配私有化 Git）
        4. 生成/复用 SSH config 别名（别名指向该标签私钥）
        5. 把 URL 中的 hostname 重写为别名（git@{alias}:user/repo.git），
           使 SSH 走该标签密钥
        6. git clone（可带自定义目录名）
        7. 克隆完成后为仓库设置作者（若标签有作者信息）
        """
        # 校验标签存在密钥
        key_type = self._detect_key_type_for_label(label)
        if not key_type:
            msg = _("err.key_not_found_short", label=label)
            self._fail(f"❌ {msg}")
            print("   " + _("msg.use_all_keys_tip"))
            return

        # 解析 URL
        parsed = self._parse_git_url(url)
        if not parsed:
            self._fail("❌ " + _("err.failed_parse"))
            return
        _platform, user, repo = parsed
        repo_name = repo.rstrip('.git') or repo

        print_section_header(_("hdr.clone", label=label))
        print(f"🔑 {_('lbl.key_type')}: {label} ({key_type})")
        print(f"🔗 {_('lbl.source_url')} {url}\n")

        # 对齐 hostname（适配私有化 Git），并确保 SSH config 别名存在
        repo_hostname = self._resolve_repo_hostname(url)
        if not self._align_hostname_with_repo(label, repo_hostname, skip_confirm):
            return

        key_file = self.ssh_dir / f"id_{key_type}.{label}"
        self._update_ssh_config_alias(label, key_file)

        # 重写为别名 URL：git@{alias}:user/repo.git
        host_alias = self._get_host_alias(label)
        new_url = f"git@{host_alias}:{user}/{repo_name}.git"

        print(f"🔧 {_('lbl.clone_url')}")
        print(f"   {new_url}\n")

        if not skip_confirm:
            if not prompt_confirm(_("msg.clone_confirm")):
                self._fail("❌ " + _("misc.operation_cancelled"))
                return

        # 执行 git clone（支持可选的目录名）
        clone_args = ['git', 'clone', new_url]
        if target_dir:
            clone_args.append(target_dir)
        try:
            subprocess.run(clone_args, check=True)
        except subprocess.CalledProcessError as e:
            detail = ((e.stderr or b'').decode('utf-8', 'replace').strip()
                      or str(e))
            self._fail(f"❌ {_('err.clone_failed', err=detail)}")
            return

        # 克隆完成后定位仓库目录（用于后续 author 设置）
        cloned_dir = target_dir or repo_name
        print(f"\n✅ {_('msg.clone_complete')} {cloned_dir}")
        print("   " + _("msg.repo_uses_key", label=label))

        # 设置作者（若标签有显式作者信息）。
        # 注意：这里禁用 remote 推断，因为 clone 的 remote 是 sshm 别名 URL，
        # 其 user 段是组织名而非作者名，推断会把 org 名错设成 user.name。
        author = self._get_author_info(label, repo_path=cloned_dir,
                                       infer_from_remote=False)
        if author and (author.get('name') or author.get('email')):
            print()
            self.set_repo_author(label, cloned_dir, skip_confirm=True,
                                 infer_from_remote=False)

        print("\n" + "=" * 70)
        print("✅ " + _("hdr.config_complete"))
        print(f"   cd {cloned_dir}")
        print(f"   git push")
        print("=" * 70)

    def _apply_auto_author(self, label: str, repo_path: Optional[str] = None,
                           scope: str = 'local', skip_confirm: bool = True):
        """凭据↔人员自动联动：切换凭据时，若该 label 绑定了 author，则自动设置。

        - scope='local'：设置仓库级 author（use_key_for_repo 调用）
        - scope='global'：设置全局 author（use -g / use --global 调用 switch_key）
        - 仅当 auto_author 开关开启且 label 有显式 author 绑定时才生效；
          无绑定则静默跳过，避免噪音。
        - infer_from_remote 关闭，避免把别名 URL 中的组织名错设成作者名。
        """
        if not self.state_manager.read_auto_author():
            return
        author = self._get_author_info(label, repo_path=None,
                                       infer_from_remote=False)
        if not author or not (author.get('name') or author.get('email')):
            return  # 无 author 绑定，不联动

        repo = Path(repo_path).resolve() if repo_path else Path.cwd()
        try:
            if author.get('name'):
                subprocess.run(
                    ['git', '-C', str(repo), 'config', f'--{scope}',
                     'user.name', author['name']],
                    check=True, capture_output=True
                )
            if author.get('email'):
                subprocess.run(
                    ['git', '-C', str(repo), 'config', f'--{scope}',
                     'user.email', author['email']],
                    check=True, capture_output=True
                )
        except (subprocess.CalledProcessError, OSError) as e:
            self._fail(f"⚠️  {_('err.auto_author_failed', err=e)}")
            return

        print(f"👤 {_('msg.auto_set_author', label=label)}: "
              f"{author.get('name', '') or ''} <{author.get('email', '') or ''}>")

    def show_auto_author(self) -> None:
        """显示凭据↔人员自动联动开关状态"""
        enabled = self.state_manager.read_auto_author()
        print_section_header(_("hdr.auto_author"))
        status = _("misc.on") if enabled else _("misc.off")
        print(f"🔀 {_('msg.auto_author_status', status=status)}")
        if enabled:
            print("   " + _("msg.auto_apply_desc"))
        else:
            print("   " + _("msg.auto_not_change"))
        print(f"   💡 {_('msg.auto_usage')}")

    def set_auto_author(self, enabled: bool):
        """开启/关闭凭据↔人员自动联动"""
        self.state_manager.write_auto_author(enabled)
        status = _("misc.on") if enabled else _("misc.off")
        print(f"🔀 {_('msg.auto_author_status', status=status)}")
        print("   " + (_("msg.auto_now_apply")
                       if enabled else
                       _("msg.auto_now_not")))

    # ------------------------------------------------------------------------
    # Git 仓库作者相关操作 (author)
    # ------------------------------------------------------------------------

    def fix_author(self, repo_path: Union[str, Path] = '.',
                   old_name: Optional[str] = None,
                   new_name: Optional[str] = None,
                   old_email: Optional[str] = None,
                   new_email: Optional[str] = None,
                   skip_confirm: bool = False):
        """重写 Git 历史中的作者/邮箱（修改所有历史中的这两处）。

        底层使用 git fast-export/fast-import（纯 Python，无外部依赖）。
        这是破坏性操作：会改写历史 commit hash，需强制推送。
        """
        repo_path = Path(repo_path).resolve()
        if not (repo_path / '.git').exists():
            self._fail(f"❌ {_('err.not_git_repo', path=repo_path)}")
            return

        if not old_name and not old_email:
            self._fail("❌ " + _("err.need_old"))
            return
        if not new_name and not new_email:
            self._fail("❌ " + _("err.need_new"))
            return

        print_section_header(_("hdr.rewrite"))
        print(f"📁 {_('lbl.repository')} {repo_path}")

        # 预览：列出历史中的作者
        authors = get_authors_in_repo(repo_path)
        print(f"\n🧑 {_('lbl.current_authors')}")
        for a in authors:
            print(f"   - {a}")

        # 构造规则并预估受影响提交
        cfg = RewriteConfig(old_name=old_name, new_name=new_name,
                            old_email=old_email, new_email=new_email)
        match_desc = []
        if old_name:
            match_desc.append(f"{_('misc.name')} '{old_name}' -> '{new_name or old_name}'")
        if old_email:
            match_desc.append(f"{_('misc.email')} '{old_email}' -> '{new_email or old_email}'")
        print(f"\n🔀 {_('lbl.rules')} {', '.join(match_desc)}")

        # 用 dry-run 预估（fast-export 到临时流，不导入）
        try:
            export = subprocess.run(
                ['git', '-C', str(repo_path), 'fast-export', '--all'],
                capture_output=True, text=True, encoding='utf-8',
                errors='replace')
            from .rewrite import _count_matches
            matched = _count_matches(export.stdout or '', cfg)
        except Exception:
            matched = 0
        if matched == 0:
            self._fail(f"⚠️  {_('err.no_matches')}")
            return
        print(f"ℹ️  {_('msg.will_rewrite_count', count=matched)}")

        # 破坏性操作确认
        print(f"\n⚠️  {_('msg.rewrites_history')}")
        print("   " + _("msg.force_push"))
        if not skip_confirm:
            if not prompt_confirm(_("msg.continue_rewrite")):
                self._fail("❌ " + _("misc.operation_cancelled"))
                return

        try:
            result = rewrite_history(repo_path, cfg)
        except Exception as e:
            self._fail(f"❌ {_('err.rewrite_failed', err=e)}")
            return

        print(f"\n✅ {_('msg.history_rewritten')}")
        print(f"   {_('msg.matched_commits', count=result.get('matched_commits', 0))}")
        print(f"   {_('msg.rewritten_lines', count=result.get('rewritten', 0))}")
        print(f"\n⚠️  {_('msg.refs_backed_up')}")
        print(f"   {_('msg.force_push_all')}")

    def show_repo_author(self, repo_path: Union[str, Path] = '.'):
        """显示当前 Git 仓库的作者配置"""
        print_section_header(_("hdr.author_info"))
        repo_path = Path(repo_path).resolve()

        if not (repo_path / '.git').exists():
            self._fail(f"❌ {_('err.not_git_repo', path=repo_path)}")
            print("   " + _("err.run_in_repo"))
            return

        print(f"📂 {_('lbl.repo_path')} {repo_path}\n")

        local_name = self._git_get_config(repo_path, 'local', 'user.name')
        local_email = self._git_get_config(repo_path, 'local', 'user.email')
        global_name = self._git_get_config(repo_path, 'global', 'user.name')
        global_email = self._git_get_config(repo_path, 'global', 'user.email')

        def fmt(value: Optional[str], source: str) -> str:
            if not value:
                return _("misc.not_set")
            return f"{value}  [{source}]"

        print(f"👤 {_('lbl.author_name')} {fmt(local_name, 'local')}")
        print(f"📧 {_('lbl.author_email')} {fmt(local_email, 'local')}")
        print()
        if global_name or global_email:
            g_author = f"{global_name or _('misc.not_set')} <{global_email or _('misc.not_set')}>"
            print(f"🌍 {_('lbl.global_author')} {g_author}")
        if local_name or local_email:
            print("   " + _("msg.current_effective"))
        print()
        print("💡 " + _("msg.author_list_tip"))
        print("   " + _("msg.quick_set"))
        print("   " + _("msg.clear_repo_config"))

    def set_repo_author(self, label: str, repo_path: Union[str, Path] = '.',
                        name: Optional[str] = None, email: Optional[str] = None,
                        scope: str = 'local', skip_confirm: bool = False,
                        infer_from_remote: bool = True):
        """为指定 Git 仓库设置作者信息（global 作用域不需要仓库）

        infer_from_remote：是否允许在标签无显式作者名时从 remote URL 推断。
        clone 场景应传 False，避免把别名 URL 中的组织名错设成作者名。
        """
        repo_path = Path(repo_path).resolve()

        if scope != 'global' and not (repo_path / '.git').exists():
            self._fail(f"❌ {_('err.not_git_repo', path=repo_path)}")
            print("   " + _("err.run_in_repo"))
            return

        author = self._get_author_info(label, name, email, repo_path,
                                       infer_from_remote)
        if not author:
            return

        print_section_header(_("hdr.set_author", label=label))
        print(f"📂 {_('lbl.repo_path')} {repo_path}\n")

        current_name = self._git_get_config(repo_path, scope, 'user.name')
        current_email = self._git_get_config(repo_path, scope, 'user.email')
        scope_name = _("misc.global") if scope == 'global' else _("misc.repo_level")

        # 摘要：未提供的字段明确展示当前值，并注明将保持不变
        not_set = _("misc.not_set")
        keep = _("msg.no_new_value")
        if author['name']:
            print(f"👤 {_('lbl.author_name')} {author['name']}")
        else:
            print(f"👤 {_('lbl.author_name')} {current_name or not_set}{keep}")
        if author['email']:
            print(f"📧 {_('lbl.author_email')} {author['email']}")
        else:
            print(f"📧 {_('lbl.author_email')} {current_email or not_set}{keep}")

        if (current_name or current_email) and not skip_confirm:
            print(f"\n⚠️  {_('msg.current_scope_author', scope=scope_name)}")
            print(f"   user.name: {current_name or not_set}")
            print(f"   user.email: {current_email or not_set}")
            if not prompt_confirm(_("misc.overwrite")):
                self._fail("❌ " + _("misc.operation_cancelled"))
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
                unchanged.append(f"user.name = {current_name or _('misc.not_set')}")
            if author['email']:
                subprocess.run(
                    ['git', '-C', str(repo_path), 'config', f'--{scope}', 'user.email', author['email']],
                    check=True, capture_output=True
                )
                changed.append(f"user.email = {author['email']}")
            else:
                unchanged.append(f"user.email = {current_email or _('misc.not_set')}")
        except subprocess.CalledProcessError as e:
            self._fail(f"❌ {_('err.git_failed', err=e)}")
            return

        if not changed:
            self._fail("\n⚠️  " + _("err.no_author_set"))
            return

        print(f"\n✅ {_('msg.set_scope', scope=scope_name)}")
        for item in changed:
            print(f"   - {item}")
        if unchanged:
            print("\nℹ️ " + _("msg.unchanged"))
            for item in unchanged:
                print(f"   - {item}")
        print("\n💡 " + _("msg.verify_cmd"))

    def unset_repo_author(self, repo_path: Union[str, Path] = '.',
                          scope: str = 'local'):
        """清除当前 Git 仓库的作者配置（回落到全局）"""
        repo_path = Path(repo_path).resolve()

        if not (repo_path / '.git').exists():
            self._fail(f"❌ {_('err.not_git_repo', path=repo_path)}")
            print("   " + _("err.run_in_repo"))
            return

        scope_name = _("misc.global") if scope == 'global' else _("misc.repo_level")
        fallback_name = _("misc.system_level") if scope == 'global' else _("misc.global")
        if not prompt_confirm(_(
            "msg.confirm_clear",
            scope=scope_name, fallback=fallback_name,
        )):
            self._fail("❌ " + _("misc.operation_cancelled"))
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
            print(f"✅ {_('msg.cleared_scope', scope=scope_name, keys=', '.join(removed))}")
        else:
            print("ℹ️  " + _("msg.no_config_clear"))

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
            self._fail("❌ " + _("msg.need_author"))
            print("   " + _("msg.author_usage"))
            print("   " + _("msg.fix_author_tip"))
            return

        self.state_manager.write_author(label_lower, final_name, final_email)

        not_set = _("misc.not_set")
        print_section_header(_("hdr.author_saved", label=label))
        print(f"👤 {_('lbl.author_name')} {final_name or not_set}")
        print(f"📧 {_('lbl.author_email')} {final_email or not_set}")
        print("\n✅ " + _("msg.saved_to_list"))
        print("   " + _("msg.use_author_list"))
        print("   " + _("msg.use_author_apply"))

    def list_authors(self, repo_path: Union[str, Path] = '.'):
        """列出所有已保存的作者

        Args:
            repo_path: Git 仓库路径，用于判断当前生效作者及其层级（默认当前目录）
        """
        print_section_header(_("hdr.saved_authors"))
        authors = self.state_manager.read_authors()
        if not authors:
            print("📭 " + _("err.no_authors"))
            print("   " + _("err.add_author_usage"))
            return

        not_set = _("misc.not_set")
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
                scope = _('misc.repo_level')    # 仓库级生效
            elif global_name or global_email:
                eff_name, eff_email = global_name, global_email
                scope = _('misc.global')        # 全局生效
        else:
            # 不在 git 仓库内：回退读取全局配置，展示全局生效
            global_name = self._git_get_config(Path.home(), 'global', 'user.name')
            global_email = self._git_get_config(Path.home(), 'global', 'user.email')
            if global_name or global_email:
                eff_name, eff_email = global_name, global_email
                scope = _('misc.global')

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

        print_table([_('lbl.status'), _('lbl.label'), _('lbl.name'), _('lbl.email'),
                     _('lbl.scope')],
                    rows, truncatable=[2, 3], center_cols=[0])

        print("\n💡 " + _("misc.usage"))
        print("   sshm author use <label> [--global]   # " + _("msg.apply_repo_global"))
        print("   sshm author remove <label>           # " + _("msg.remove_author"))
        print("   sshm author add <label> -n name -e email  # " + _("msg.add_update_author"))

    def remove_author(self, label: str, skip_confirm: bool = False):
        """从作者列表移除指定标签的作者（不影响已写入的 git config）"""
        label_lower = label.lower()
        authors = self.state_manager.read_authors()
        if label_lower not in authors:
            self._fail(f"❌ {_('err.author_not_found', label=label)}")
            print("   " + _("err.use_author_list"))
            return

        not_set = _("misc.not_set")
        info = authors[label_lower]
        print(_("msg.about_remove_author", label=label))
        print(f"  👤 {_('lbl.author_name')} {info.get('name') or not_set}")
        print(f"  📧 {_('lbl.author_email')} {info.get('email') or not_set}")

        if not skip_confirm and not prompt_confirm(_("msg.confirm_remove")):
            self._fail("❌ " + _("misc.operation_cancelled"))
            return

        self.state_manager.remove_author(label_lower)
        print(f"✅ {_('msg.author_removed', label=label)}")
        print("   " + _("msg.not_rolled_back"))

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
                         repo_path: Optional[Union[str, Path]] = None,
                         infer_from_remote: bool = True) -> Optional[Dict[str, str]]:
        """按优先级获取标签对应的作者信息

        infer_from_remote：当标签无显式作者名时，是否从 remote URL 推断用户名。
        在 clone 场景应传 False，因为 clone 的 remote 是 sshm 别名 URL
        （git@github-work:org/repo.git），其 user 段是组织名而非作者名。
        """
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
            result['email'] = self._extract_email_from_pubkey(label_lower) or ''

        # 3. 从 remote URL 推断用户名（最低优先级）
        if not result['name'] and repo_path is not None and infer_from_remote:
            result['name'] = self._infer_author_name_from_remote(
                Path(repo_path)) or ''

        if not (result['name'] or result['email']):
            key_type = self._detect_key_type_for_label(label)
            if not key_type:
                msg = _("err.key_not_found_short", label=label)
                self._fail(f"❌ {msg}")
                print("\n💡 " + _("msg.use_all_keys_tip"))
                return None
            msg = _("msg.not_usable_author", label=label)
            self._fail(f"⚠️  {msg}")
            print("   " + _("msg.available_remedies"))
            print(f"   - sshm add {label} <email> --name \"name\"   # " + _("msg.recreate_key"))
            print(f"   - sshm author {label} --name \"name\" --email <email>  # " + _("msg.temp_override"))
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

    def show_repo_info(self, repo_path: Union[str, Path] = '.'):
        """显示当前 Git 仓库的 SSH 配置信息"""
        print_section_header(_("hdr.repo_info"))

        repo_path = Path(repo_path).resolve()

        if not (repo_path / '.git').exists():
            self._fail(f"❌ {_('err.not_valid_git', path=repo_path)}")
            return

        print(f"📂 {_('lbl.repo_path')} {repo_path}")

        try:
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            remote_url = result.stdout.strip()
            print(f"🔗 {_('lbl.remote_url')} {remote_url}")

            parsed = self._parse_git_url(remote_url)
            if parsed:
                platform, user, repo = parsed
                print(f"\n📊 {_('lbl.parsed_info')}")
                print(f"  ├─ {_('lbl.platform')} {platform}")
                print(f"  ├─ {_('lbl.user_org')} {user}")
                print(f"  └─ {_('lbl.repo')} {repo}")

                ssh_pattern = r'git@([^:]+):'
                match = re.match(ssh_pattern, remote_url)
                if match:
                    host_alias = match.group(1)
                    # 反解别名对应的标签（容忍主机名首段含连字符，如 git-codecommit-{label}）
                    label = self._resolve_label_from_alias(host_alias)
                    if label:
                        print(f"\n🔑 {_('lbl.current_alias', alias=host_alias)}")

                        key_type = self._detect_key_type_for_label(label)
                        if key_type:
                            key_file = self.ssh_dir / f"id_{key_type}.{label}"
                            pub_file = self.ssh_dir / f"id_{key_type}.{label}.pub"

                            print(f"\n🗝️  {_('lbl.key_info')}")
                            print(f"  ├─ {_('lbl.label')}: {label}")
                            print(f"  ├─ {_('lbl.key_type')}: {key_type}")
                            print(f"  ├─ {_('lbl.private_key')} {key_file}")
                            print(f"  └─ {_('lbl.public_key')} {pub_file}")

                            ssh_config = self.config_manager.config_file
                            if ssh_config.exists():
                                # 按 Host 块解析，打印匹配该别名的完整配置块
                                block = self._extract_ssh_config_block(host_alias)
                                if block:
                                    print(f"\n📝 {_('lbl.ssh_config')}")
                                    for line in block:
                                        print(f"  {line}")
                        else:
                            msg = _("err.key_not_found_file", label=label)
                            print(f"\n⚠️  {msg}")
                    else:
                        print(f"\n💡 " + _("msg.current_alias_unconfigured"))
                        print(f"   " + _("msg.use_to_configure"))
                else:
                    print(f"\n💡 " + _("msg.https_url_tip"))
                    print(f"   " + _("msg.use_to_ssh"))
            else:
                print("\n⚠️  " + _("msg.failed_parse_url"))

        except subprocess.CalledProcessError as e:
            if 'No such remote' in str(e.stderr):
                print("\n⚠️  " + _("msg.no_origin_configured"))
            else:
                print(f"\n❌ {_('err.git_failed', err=e)}")
        except Exception as e:
            print(f"\n❌ {_('misc.error')}: {e}")

    def test_connection(self, label: Optional[str] = None, test_all: bool = False,
                       repo_path: Union[str, Path] = '.'):
        """测试 SSH 连接"""
        if test_all:
            print_section_header(_("hdr.test_all"))

            keys_by_label = self._scan_all_keys()
            if not keys_by_label:
                self._fail("❌ " + _("err.no_keys"))
                return

            results = []
            no_alias_msg = _("msg.no_alias_configured")
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
            print(_("hdr.test_results"))
            print("=" * 70)
            for label, host_alias, key_types, (success, message) in results:
                status = "✅" if success else "❌"
                print(f"{status} {pad_cell(label, 20)} "
                      f"({pad_cell(host_alias, 30)}) [{key_types}]")
                if not success:
                    print(f"    {message}")

            # 只要有任一连接失败，标记业务失败（供 CLI 层返回非零退出码）
            # 错误信息已在表格中逐条展示，这里仅置标志、不重复打印
            if any(not ok for _, _, _, (ok, _) in results):
                self._had_error = True

        elif label:
            print_section_header(_("hdr.test_one", label=label))

            key_type = self._detect_key_type_for_label(label)
            if not key_type:
                msg = _("err.key_not_found_files", label=label)
                self._fail(f"❌ {msg}")
                print(f"\n💡 " + _("msg.use_all_keys_tip"))
                return

            host_alias = self._get_host_alias(label)

            print(f"🔑 {_('lbl.key_type')}: {label}")
            print(f"🌐 {_('lbl.host')} {host_alias}")

            # 未配置 config 别名时无法路由到真实主机，直接给出友好提示
            # （与 test --all 分支一致，未配置视为不可连接，标记业务失败）
            if not self.config_manager.has_host(host_alias):
                print(f"\n⚠️  {_('msg.alias_not_configured', alias=host_alias)}")
                print(f"   " + _("msg.run_use_first", label=label))
                print(f"   " + _("msg.run_use_global", label=label))
                self._had_error = True
                return

            print(f"\n🧪 " + _("msg.testing"))

            success, message = self._test_ssh_connection(host_alias)
            if success:
                print(f"✅ {message}")
            else:
                self._fail(f"❌ {message}")
        else:
            print_section_header(_("hdr.test_current"))

            repo_path = Path(repo_path).resolve()

            if not (repo_path / '.git').exists():
                self._fail(f"❌ {_('err.not_valid_git', path=repo_path)}")
                return

            print(f"📂 {_('lbl.repo_path')} {repo_path}")

            try:
                result = subprocess.run(
                    ['git', 'remote', 'get-url', 'origin'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=True
                )
                remote_url = result.stdout.strip()
                print(f"🔗 {_('lbl.remote_url')} {remote_url}")

                ssh_pattern = r'git@([^:]+):'
                match = re.match(ssh_pattern, remote_url)
                if match:
                    host_alias = match.group(1)
                    print(f"\n🧪 {_('msg.testing_host', host=host_alias)}")

                    success, message = self._test_ssh_connection(host_alias)
                    if success:
                        print(f"✅ {message}")
                    else:
                        self._fail(f"❌ {message}")
                        print(f"\n💡 " + _("msg.check_config_tip"))
                        print(f"   " + _("msg.use_info"))
                else:
                    print("\n⚠️  " + _("msg.not_ssh_url"))
                    print("   " + _("msg.use_to_convert"))

            except subprocess.CalledProcessError as e:
                if 'No such remote' in str(e.stderr):
                    print("\n⚠️  " + _("msg.no_origin_configured"))
                else:
                    print(f"\n❌ {_('err.git_failed', err=e)}")
            except Exception as e:
                print(f"\n❌ {_('misc.error')}: {e}")

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
                    return (True, _("msg.auth_success", user=user))
                return (True, _("msg.connected"))

            # 2) 命中明确的失败关键词
            if any(m in low for m in _SSH_FAILURE_MARKERS):
                return (False, _("err.connection_failed",
                                 detail=output.strip()[:100]))

            # 3) 平台文案未知时以退出码兜底
            if result.returncode == 0:
                return (True, _("msg.connected"))
            return (False, _("err.connection_failed",
                             detail=output.strip()[:100]))

        except subprocess.TimeoutExpired:
            return (False, _("err.connection_timeout"))
        except FileNotFoundError:
            return (False, _("err.ssh_not_found"))
        except Exception as e:
            return (False, f"{_('misc.error')}: {str(e)}")

    def _extract_ssh_config_block(self, host_alias: str) -> List[str]:
        """从 SSH config 中提取指定 Host 别名对应的配置块（含 Host 行及缩进项）。

        按 SSH config 语义按块解析：一个块以顶格 `Host xxx` 开头，其后缩进的
        键值行归属该块，直到下一个顶格指令（如下一个 Host / HostName / 空行后
        的新指令）。精确匹配 Host 值（大小写敏感），避免子串误匹配。
        """
        if not self.config_file.exists():
            return []
        try:
            lines = self.config_file.read_text(encoding='utf-8').splitlines()
        except (OSError, UnicodeDecodeError):
            return []

        block: List[str] = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            # 检测 `Host <pattern>` 指令（顶格或缩进均视为指令边界）
            low = stripped.lower()
            if low.startswith('host ') or low == 'host':
                host_patterns = [p.strip() for p in
                                 stripped.split(' ', 1)[1].split()] if ' ' in stripped else []
                # 命中目标别名：收集该块直至下一个顶格指令
                if host_alias in host_patterns:
                    block.append(stripped)
                    for nxt in lines[i + 1:]:
                        nxt_strip = nxt.strip()
                        if not nxt_strip:
                            break
                        if not (nxt.startswith(' ') or nxt.startswith('\t')):
                            break
                        block.append(nxt_strip)
                    return block
        return []

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

        别名格式为 '{主域名}-{label}'，如 github.com-Eavelabs、
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
        - 简短别名（git@github-Eavelabs:...）：若 SSH config 有该 Host 块，
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

    def _align_hostname_with_repo(self, label: str,
                                  repo_hostname: Optional[str],
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

        print(f"\n⚠️  " + _("msg.hostname_differs",
                          host=repo_hostname, label=label, cur=current))
        print("   " + _("msg.private_server"))
        print("   " + _("msg.need_ssh_config", host=repo_hostname))

        if skip_confirm:
            self.state_manager.write_host(label, repo_hostname)
            print("✅ " + _("msg.host_updated", label=label, host=repo_hostname))
            return True

        if prompt_confirm(_("msg.create_matching", host=repo_hostname),
                          default='y'):
            self.state_manager.write_host(label, repo_hostname)
            print("✅ " + _("msg.host_updated", label=label, host=repo_hostname))
            return True
        self._fail("⚠️  " + _("msg.skipped_no_mapping"))
        return False

    def _detect_repo_key_label(self,
                               repo_path: Union[str, Path] = '.') -> Optional[str]:
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
        print(_("msg.ssh_config_alias",
                alias=host_alias, hostname=hostname))
        print(_("msg.alias_usage", alias=host_alias))

    def _remove_ssh_config_alias(self, label: str):
        """删除 SSH config 别名配置"""
        host_alias = self._get_host_alias(label)

        self.config_manager.remove_host(host_alias)
        self.state_manager.remove_host(label)
        print(_("msg.alias_removed", alias=host_alias))

    def _rename_ssh_config_alias(self, old_label: str, new_label: str, new_key_file: Path):
        """重命名 SSH config 别名配置（主机名保持不变，同一把密钥换标签）"""
        hostname = self._get_hostname_for_label(old_label)
        old_alias = self._get_host_alias(old_label)
        new_alias = self._get_host_alias(new_label)

        if old_alias != new_alias:
            self.config_manager.remove_host(old_alias)
            self.config_manager.update_host(new_alias, hostname, new_key_file.resolve())
            self.state_manager.write_host(new_label, hostname)
            print(_("msg.alias_updated",
                    old=old_alias, new=new_alias))
