#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
作者命令组 - 作者相关命令的编排（show / set / unset / add / update / delete / list / fix
以及 auto-author 开关）。

负责把用户意图翻译为对 AuthorService / StateManager / rewrite 的编排调用 +
渲染输出。共享状态与错误上报通过门面 SSHKeyManager（self.m）。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from ...i18n import _
from ...ui.output import (
    print,
    section as print_section_header,
    table as print_table,
    confirm as prompt_confirm,
)
from ...ui.tip import render_tip_block

if TYPE_CHECKING:
    from ..manager import SSHKeyManager


class AuthorCommands:
    """作者命令编排。"""

    def __init__(self, m: "SSHKeyManager"):
        self.m = m

    def auto_author(self, enabled: Optional[bool] = None) -> None:
        """密钥↔作者自动联动开关：无参数显示状态，传入 on/off 则设置。"""
        if enabled is None:
            enabled = self.m.state_manager.read_auto_author()
            print_section_header(_("hdr.auto_author"))
            status = _("misc.on") if enabled else _("misc.off")
            print(f"🔀 {_('msg.auto_author_status', status=status)}")
            if enabled:
                print("   " + _("msg.auto_apply_desc"))
            else:
                print("   " + _("msg.auto_not_change"))
            print(f"   💡 {_('msg.auto_usage')}")
        else:
            self.m.state_manager.write_auto_author(enabled)
            status = _("misc.on") if enabled else _("misc.off")
            print(f"🔀 {_('msg.auto_author_status', status=status)}")
            print("   " + (_("msg.auto_now_apply")
                           if enabled else
                           _("msg.auto_now_not")))

    def show(self, repo_path: Union[str, Path] = '.'):
        """显示当前 Git 仓库的作者配置"""
        print_section_header(_("hdr.author_info"))
        repo_path = Path(repo_path).resolve()

        if not (repo_path / '.git').exists():
            self.m._fail(f"❌ {_('err.not_git_repo', path=repo_path)}")
            print("   " + _("err.run_in_repo"))
            return

        print(f"{_('lbl.repo_path')} {repo_path}\n")

        local_name = self.m.author_service.git_get_config(repo_path, 'local', 'user.name')
        local_email = self.m.author_service.git_get_config(repo_path, 'local', 'user.email')
        global_name = self.m.author_service.git_get_config(repo_path, 'global', 'user.name')
        global_email = self.m.author_service.git_get_config(repo_path, 'global', 'user.email')

        # 统一为 `name <email>` 紧凑格式（local 与 global 保持一致）
        if local_name or local_email:
            local_author = f"{local_name or _('misc.not_set')} <{local_email or _('misc.not_set')}>"
            print(f"📍 {_('lbl.author')} {local_author}  ({_('misc.scope_repo')})")
        else:
            print(f"📍 {_('lbl.author')} {_('misc.not_set')}")
        print()
        if global_name or global_email:
            g_author = f"{global_name or _('misc.not_set')} <{global_email or _('misc.not_set')}>"
            print(f"🌍 {_('lbl.global_author')} {g_author}")
        if local_name or local_email:
            print("   " + _("msg.current_effective"))
        render_tip_block([
            f"💡 {_('msg.author_list_tip')}",
            "   " + _("msg.quick_set"),
            "   " + _("msg.clear_repo_config"),
        ])

    def use(self, label: str, repo_path: Union[str, Path] = '.',
            name: Optional[str] = None, email: Optional[str] = None,
            scope: str = 'local', skip_confirm: bool = False,
            infer_from_remote: bool = True):
        """为指定 Git 仓库设置作者信息（global 作用域不需要仓库）"""
        repo_path = Path(repo_path).resolve()

        if scope != 'global' and not (repo_path / '.git').exists():
            self.m._fail(f"❌ {_('err.not_git_repo', path=repo_path)}")
            print("   " + _("err.run_in_repo"))
            return

        author = self.m.author_service.get_author_info(label, name, email, repo_path,
                                         infer_from_remote)
        if not author:
            return

        print_section_header(_("hdr.set_author", label=label))
        print(f"{_('lbl.repo_path')} {repo_path}\n")

        current_name = self.m.author_service.git_get_config(repo_path, scope, 'user.name')
        current_email = self.m.author_service.git_get_config(repo_path, scope, 'user.email')
        scope_name = _("misc.scope_global") if scope == 'global' else _("misc.scope_repo")

        # 摘要：未提供的字段明确展示当前值，并注明将保持不变
        not_set = _("misc.not_set")
        keep = _("msg.no_new_value")
        if author['name']:
            print(f"{_('lbl.author_name')} {author['name']}")
        else:
            print(f"{_('lbl.author_name')} {current_name or not_set}{keep}")
        if author['email']:
            print(f"{_('lbl.author_email')} {author['email']}")
        else:
            print(f"{_('lbl.author_email')} {current_email or not_set}{keep}")

        if (current_name or current_email) and not skip_confirm:
            print(f"\n⚠️  {_('msg.current_scope_author', scope=scope_name)}")
            print(f"   user.name: {current_name or not_set}")
            print(f"   user.email: {current_email or not_set}")
            if not prompt_confirm(_("misc.overwrite")):
                self.m._fail("❌ " + _("misc.operation_cancelled"))
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
            self.m._fail(f"❌ {_('err.git_failed', err=e)}")
            return

        if not changed:
            self.m._fail("\n⚠️  " + _("err.no_author_set"))
            return

        print(f"\n✅ {_('msg.set_scope', scope=scope_name)}")
        for item in changed:
            print(f"   - {item}")
        if unchanged:
            print("\nℹ️ " + _("msg.unchanged"))
            for item in unchanged:
                print(f"   - {item}")
        print("\n💡 " + _("msg.verify_cmd"))

    def unset(self, repo_path: Union[str, Path] = '.',
              scope: str = 'local'):
        """清除当前 Git 仓库的作者配置（回落到全局）"""
        repo_path = Path(repo_path).resolve()

        if not (repo_path / '.git').exists():
            self.m._fail(f"❌ {_('err.not_git_repo', path=repo_path)}")
            print("   " + _("err.run_in_repo"))
            return

        scope_name = _("misc.scope_global") if scope == 'global' else _("misc.scope_repo")
        fallback_name = _("misc.scope_system") if scope == 'global' else _("misc.scope_global")
        if not prompt_confirm(_(
            "msg.confirm_clear",
            scope=scope_name, fallback=fallback_name,
        )):
            self.m._fail("❌ " + _("misc.operation_cancelled"))
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

    def add(self, label: str, name: Optional[str] = None,
            email: Optional[str] = None):
        """添加/更新作者到状态文件（author 列表）"""
        label_lower = label.lower()

        # 更新语义：未提供的字段保留已有值，邮箱缺失时尝试从公钥注释补全
        stored = self.m.state_manager.read_authors().get(label_lower, {})
        final_name = name or stored.get('name', '')
        final_email = (email or stored.get('email', '')
                       or self.m.author_service.extract_email_from_pubkey(label_lower) or '')

        if not (final_name or final_email):
            self.m._fail("❌ " + _("msg.need_author"))
            print("   " + _("msg.author_usage"))
            print("   " + _("msg.fix_author_tip"))
            return

        self.m.state_manager.write_author(label_lower, final_name, final_email)

        not_set = _("misc.not_set")
        print_section_header(_("hdr.author_saved", label=label))
        print(f"{_('lbl.author_name')} {final_name or not_set}")
        print(f"{_('lbl.author_email')} {final_email or not_set}")
        print("\n✅ " + _("msg.saved_to_list"))
        print("   " + _("msg.use_author_list"))
        print("   " + _("msg.use_author_apply"))

    def update(self, label: str, name: Optional[str] = None,
               email: Optional[str] = None):
        """更新已有作者的信息（name/email 至少提供一个，未提供的保留原值）"""
        label_lower = label.lower()
        authors = self.m.state_manager.read_authors()
        if label_lower not in authors:
            self.m._fail(f"❌ {_('err.author_not_found', label=label)}")
            print("   " + _("err.use_author_list"))
            return

        if not name and not email:
            self.m._fail("❌ " + _("msg.update_author_need"))
            return

        stored = authors[label_lower]
        final_name = name or stored.get('name', '')
        final_email = email or stored.get('email', '')
        self.m.state_manager.write_author(label_lower, final_name, final_email)

        not_set = _("misc.not_set")
        print_section_header(_("hdr.author_saved", label=label))
        print(f"{_('lbl.author_name')} {final_name or not_set}")
        print(f"{_('lbl.author_email')} {final_email or not_set}")
        print("\n✅ " + _("msg.updated_in_list"))

    def list(self, repo_path: Union[str, Path] = '.'):
        """列出所有已保存的作者"""
        print_section_header(_("hdr.saved_authors"))
        authors = self.m.state_manager.read_authors()
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
            local_name = self.m.author_service.git_get_config(repo, 'local', 'user.name')
            local_email = self.m.author_service.git_get_config(repo, 'local', 'user.email')
            global_name = self.m.author_service.git_get_config(repo, 'global', 'user.name')
            global_email = self.m.author_service.git_get_config(repo, 'global', 'user.email')

            if local_name or local_email:
                eff_name, eff_email = local_name, local_email
                scope = _('misc.scope_repo')    # 仓库级生效
            elif global_name or global_email:
                eff_name, eff_email = global_name, global_email
                scope = _('misc.scope_global')        # 全局生效
        else:
            # 不在 git 仓库内：回退读取全局配置，展示全局生效
            global_name = self.m.author_service.git_get_config(Path.home(), 'global', 'user.name')
            global_email = self.m.author_service.git_get_config(Path.home(), 'global', 'user.email')
            if global_name or global_email:
                eff_name, eff_email = global_name, global_email
                scope = _('misc.scope_global')

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
            icon = '📍' if is_active else ''
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
        print("   sshm author remove <label>           # " + _("msg.delete_author"))
        print("   sshm author add <label> -n name -e email  # " + _("msg.add_update_author"))

    def remove(self, label: str, skip_confirm: bool = False):
        """从作者列表删除指定标签的作者（不影响已写入的 git config）"""
        label_lower = label.lower()
        authors = self.m.state_manager.read_authors()
        if label_lower not in authors:
            self.m._fail(f"❌ {_('err.author_not_found', label=label)}")
            print("   " + _("err.use_author_list"))
            return

        not_set = _("misc.not_set")
        info = authors[label_lower]
        print(_("msg.about_delete_author", label=label))
        print(f"  {_('lbl.author_name')} {info.get('name') or not_set}")
        print(f"  {_('lbl.author_email')} {info.get('email') or not_set}")

        if not skip_confirm and not prompt_confirm(_("msg.confirm_delete")):
            self.m._fail("❌ " + _("misc.operation_cancelled"))
            return

        self.m.state_manager.delete_author(label_lower)
        print(f"✅ {_('msg.author_deleted', label=label)}")
        print("   " + _("msg.not_rolled_back"))
