#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
密钥命令组 - 密钥管理相关命令的编排（list / add / remove / switch / tag / rename）。

只负责"把用户意图翻译为对服务（KeyStore / StateManager / BackupService 等）的
编排调用 + 渲染输出"。共享状态与错误上报通过门面 SSHKeyManager（self.m）。
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from ...constants import DEFAULT_KEY_TYPE, SUPPORTED_KEY_TYPES
from ...i18n import _
from ...ui.console import format_size, format_timestamp
from ..errors import ValidationError
from ...ui.output import (
    print,
    section as print_section_header,
    separator as print_separator,
    table as print_table,
    confirm as prompt_confirm,
)

if TYPE_CHECKING:
    from ..manager import SSHKeyManager


class KeyCommands:
    """密钥管理命令编排。"""

    def __init__(self, m: "SSHKeyManager"):
        self.m = m

    # ------------------------------------------------------------------
    # 标签合法性校验（所有标签入口统一使用）
    # ------------------------------------------------------------------

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
            raise ValidationError(_("err.label_empty"))
        label = label.strip()
        if not re.match(r'^[A-Za-z0-9][A-Za-z0-9_-]*$', label):
            raise ValidationError(_(
                "err.label_invalid",
                label=label,
            ))
        if label.lower() in self.m.RESERVED_LABELS:
            raise ValidationError(_("err.label_reserved", label=label))
        return True

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def list_keys(self, show_content: bool = False,
                  repo_path: Union[str, Path] = '.',
                  current_only: bool = False):
        """列出所有密钥（表格形式）"""
        print_section_header(_("hdr.key_list"))
        print(f"\n{_('lbl.ssh_dir')} {self.m.ssh_dir}\n")

        keys_by_label = self.m._scan_all_keys()
        active_keys = self.m.state_manager.read_active_keys()

        if not keys_by_label:
            print("⚠️  " + _("msg.no_keys"))
            print("\n💡 " + _("msg.add_tip"))
            return

        # 指定仓库正在使用的密钥（仓库级，通过 remote URL 反解）
        repo_key = self.m._detect_repo_key_label(repo_path)

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

                host_alias = self.m._get_host_alias(label)
                alias_display = (
                    f"git@{host_alias}:user/repo.git"
                    if self.m.config_manager.has_host(host_alias)
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

    # ------------------------------------------------------------------
    # 创建 / 删除
    # ------------------------------------------------------------------

    def add_key(self, label: str, email: str,
                key_type: str = DEFAULT_KEY_TYPE, host: Optional[str] = None,
                name: Optional[str] = None):
        """创建新密钥"""
        if key_type not in SUPPORTED_KEY_TYPES:
            raise ValidationError(_(
                "err.unsupported_type",
                type=key_type, supported=', '.join(SUPPORTED_KEY_TYPES),
            ))

        self._validate_label(label)

        if not email or '@' not in email:
            raise ValidationError(_(
                "err.invalid_email",
                email=email,
            ))

        key_file = self.m.ssh_dir / f"id_{key_type}.{label}"
        if key_file.exists():
            raise ValidationError(_("err.key_exists", name=key_file.name))

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
                hostname = self.m._get_hostname_for_label(label)
            # 持久化 label -> hostname 映射（供 use/remove/rename 使用）
            self.m.state_manager.write_host(label, hostname)
            if host:
                host_alias = self.m._get_host_alias(label)
                self.m.config_manager.update_host(host_alias, hostname, key_file)
                print(f"✅ {_('msg.ssh_config_updated', alias=host_alias, hostname=hostname)}")

            pub_file = Path(str(key_file) + '.pub')
            if pub_file.exists():
                pub_key = pub_file.read_text(encoding='utf-8').strip()
                print(f"\n📋 {_('msg.pub_key_content')}\n{pub_key}\n")
                print("💡 " + _("msg.add_to_platform"))

            # 记录作者信息（供 sshm author 使用）
            self.m.state_manager.write_author(label, name or '', email)
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
            self.m._fail(f"❌ {_('err.create_failed', err=detail)}")
        except Exception as e:
            self.m._fail(f"❌ {_('misc.error')}: {e}")

    def remove_key(self, label: str, key_type: Optional[str] = None):
        """删除密钥"""
        label_lower = label.lower()

        if label_lower == 'default':
            if key_type:
                confirm_msg = _("err.delete_default", type=key_type)
            else:
                confirm_msg = _("err.delete_all_default")

            if not prompt_confirm("⚠️  " + confirm_msg):
                self.m._fail("❌ " + _("misc.operation_cancelled"))
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
                file = self.m.ssh_dir / pattern
                if file.exists() and file.is_file():
                    if not removed_files:
                        backup_path = self.m.backup_keys(silent=True)
                        print(f"💾 {_('msg.auto_backed_up', path=backup_path)}")

                    file.unlink()
                    removed_files.append(file.name)
        else:
            if key_type:
                patterns = [f"id_{key_type}.{label}", f"id_{key_type}.{label}.pub"]
            else:
                patterns = [f"id_*.{label}", f"id_*.{label}.pub"]

            for pattern in patterns:
                for file in self.m.ssh_dir.glob(pattern):
                    if file.is_file():
                        if not removed_files:
                            backup_path = self.m.backup_keys(silent=True)
                            print(f"💾 {_('msg.auto_backed_up', path=backup_path)}")

                        file.unlink()
                        removed_files.append(file.name)

        if removed_files:
            print(f"✅ {_('msg.deleted_count', count=len(removed_files))}")
            for f in removed_files:
                print(f"   - {f}")

            self.m._remove_ssh_config_alias(label)
            self.m.state_manager.remove_author(label)
            self.m.state_manager.remove_host(label)

            # 清理 active 状态：从已删除文件名中推导密钥类型
            # （不能在删除文件后调用 _detect_key_type_for_label，文件已不存在）
            removed_types = set()
            for name in removed_files:
                mm = re.match(r'^id_(rsa|ed25519|ecdsa|dsa)(?:\.|$)', name)
                if mm:
                    removed_types.add(mm.group(1))
            for kt in removed_types:
                active_keys = self.m.state_manager.read_active_keys()
                if active_keys.get(kt) == label_lower:
                    self.m.state_manager.remove_active_key(kt)

            print(f"💡 {_('msg.tip_alias_remote', alias=self.m._get_host_alias(label))}")
            print("   " + _("msg.rerun_other_label"))
        else:
            self.m._fail(f"⚠️  {_('err.key_not_found', label=label)}")

    # ------------------------------------------------------------------
    # 切换 / 打标签 / 重命名
    # ------------------------------------------------------------------

    def switch_key(self, label: str, key_type: Optional[str] = None):
        """切换默认密钥"""
        label_lower = label.lower()

        if label_lower in self.m.RESERVED_LABELS:
            label_msg = _('err.label_reserved_switch', label=label)
            self.m._fail(f"❌ {label_msg}")
            return

        if not key_type:
            key_type = self.m._detect_key_type_for_label(label)
            if not key_type:
                msg = _("err.key_not_found_short", label=label)
                self.m._fail(f"❌ {msg}")
                return
            print(f"🔍 {_('msg.auto_detected_type', key_type=key_type)}")

        source_file = self.m.ssh_dir / f"id_{key_type}.{label}"
        target_file = self.m.ssh_dir / f"id_{key_type}"

        if not source_file.exists():
            self.m._fail(f"❌ {_('err.key_missing', name=source_file.name)}")
            return

        if target_file.exists():
            active_keys = self.m.state_manager.read_active_keys()
            current_label = active_keys.get(key_type, 'original')

            original_backup = self.m.ssh_dir / f"id_{key_type}.original"
            if not original_backup.exists():
                self.m._copy_key_pair(target_file, original_backup)
                print(f"💾 {_('msg.original_backed_up', name=original_backup.name)}")

            if current_label != 'original':
                backup_file = self.m.ssh_dir / f"id_{key_type}.{current_label}"
                if not backup_file.exists():
                    self.m._copy_key_pair(target_file, backup_file)

        self.m._copy_key_pair(source_file, target_file)

        self.m.state_manager.write_active_key(key_type, label)

        self.m._update_ssh_config_alias(label, source_file)

        print(f"✅ {_('msg.switched_to', label=label, key_type=key_type)}")
        print(f"📁 {_('lbl.file_placeholder')} {target_file.name}")

        # 凭据↔人员自动联动：全局切换时自动设置全局 author（若 label 有绑定）
        self.m.author.apply_auto_author(label, repo_path=None, scope='global')

    def tag_key(self, key_type: Optional[str], new_label: str,
                switch_after: bool = False):
        """给默认密钥添加标签（key_type 为空时自动检测默认密钥类型）"""
        self._validate_label(new_label)

        if not key_type:
            key_type = self.m._detect_default_key_type()
            if not key_type:
                self.m._fail("❌ " + _("err.no_default_key"))
                return

        source_file = self.m.ssh_dir / f"id_{key_type}"
        target_file = self.m.ssh_dir / f"id_{key_type}.{new_label}"

        if not source_file.exists():
            self.m._fail(f"❌ {_('err.default_key_missing', name=source_file.name)}")
            return

        if target_file.exists():
            print(f"⚠️  {_('err.label_exists', new_label=new_label)}")
            if not prompt_confirm(_("misc.overwrite")):
                return

        self.m._copy_key_pair(source_file, target_file)

        # 继承默认密钥的元数据（host 映射 + 作者信息）
        # 默认密钥通常由 switch_key 从某标签复制而来，active_keys 记录了来源标签。
        self._inherit_metadata_from_default(key_type, new_label)

        print(f"✅ {_('msg.tag_added', new_label=new_label, key_type=key_type)}")

        if switch_after:
            self.m.switch_key(new_label, key_type)

    def _inherit_metadata_from_default(self, key_type: str, new_label: str):
        """给默认密钥打标签时，把默认密钥对应的 host/author 元数据继承给新标签。

        默认密钥的来源标签由 active_keys 记录；若无记录，则尝试从默认密钥的
        公钥注释提取 email 作为作者邮箱。
        """
        label_lower = new_label.lower()
        active_keys = self.m.state_manager.read_active_keys()
        source_label = active_keys.get(key_type, '')

        # 1. 继承 host 映射（来源标签有记录则继承，否则保留新标签自身兜底）
        if source_label:
            hosts = self.m.state_manager.read_hosts()
            if hosts.get(source_label):
                self.m.state_manager.write_host(label_lower, hosts[source_label])

        # 2. 继承/兜底 author：优先来源标签的 author，其次默认密钥 pubkey 注释 email
        author = None
        if source_label:
            author = self.m.state_manager.read_authors().get(source_label)
        if not author:
            email = self.m._extract_email_from_pubkey_default(key_type)
            if email:
                author = {'name': '', 'email': email}
        if author:
            self.m.state_manager.write_author(label_lower,
                                              author.get('name', '') or '',
                                              author.get('email', '') or '')

    def rename_tag(self, old_label: str, new_label: str,
                   key_type: str = DEFAULT_KEY_TYPE):
        """重命名密钥标签（处理该标签下的所有密钥类型，避免残留旧文件）"""
        old_label_lower = old_label.lower()
        new_label_lower = new_label.lower()

        if old_label_lower == 'default':
            self.m._fail("❌ " + _("err.cannot_rename_default"))
            return

        self._validate_label(new_label)
        if new_label_lower == old_label_lower:
            self.m._fail("⚠️  " + _("err.same_label"))
            return

        # 确定要重命名的密钥类型集合：
        # - 未指定类型时，处理该标签下所有已存在的类型（多类型共存场景）
        # - 指定类型时，仅处理指定类型
        if key_type:
            types_to_rename = [key_type]
        else:
            types_to_rename = [
                t for t in SUPPORTED_KEY_TYPES
                if (self.m.ssh_dir / f"id_{t}.{old_label}").exists()
            ]

        if not types_to_rename:
            msg = _("err.key_not_found_short", label=old_label)
            self.m._fail(f"❌ {msg}")
            return

        # 检查目标文件是否全部可用，避免部分重命名后中断
        for t in types_to_rename:
            new_file = self.m.ssh_dir / f"id_{t}.{new_label}"
            if new_file.exists():
                self.m._fail(f"⚠️  {_('err.target_exists', new_label=new_label, type=t)}")
                print(f"   {_('lbl.file_placeholder')} {new_file.name}")
                return

        renamed_count = 0
        last_new_file = None
        for t in types_to_rename:
            old_file = self.m.ssh_dir / f"id_{t}.{old_label}"
            new_file = self.m.ssh_dir / f"id_{t}.{new_label}"

            old_file.rename(new_file)
            old_pub = Path(str(old_file) + '.pub')
            if old_pub.exists():
                old_pub.rename(Path(str(new_file) + '.pub'))
            last_new_file = new_file
            renamed_count += 1

        if last_new_file:
            self.m._rename_ssh_config_alias(old_label, new_label, last_new_file)

        self.m.state_manager.update_label(old_label, new_label)

        renamed_msg = _(
            'msg.renamed',
            old=old_label, new=new_label, count=renamed_count,
            types=', '.join(types_to_rename),
        )
        print(f"✅ {renamed_msg}")
        print(f"💡 {_('msg.tip_alias', alias=self.m._get_host_alias(old_label))}")
        tip_msg = _("msg.rerun_new_label", new_label=new_label)
        print(f"   {tip_msg}")
