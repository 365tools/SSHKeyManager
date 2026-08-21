#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
历史重写命令组 - 重写 Git 历史作者/邮箱的编排。

负责把用户意图翻译为对 rewrite 模块的编排调用 + 渲染输出。
共享状态与错误上报通过门面 SSHKeyManager（self.m）。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from ...i18n import _
from ...ui.output import (
    print,
    section as print_section_header,
    status as output_status,
    confirm as prompt_confirm,
)

if TYPE_CHECKING:
    from ..manager import SSHKeyManager


class HistoryCommands:
    """历史重写命令组（对应 CLI `sshm history rewrite`）。"""

    def __init__(self, m: "SSHKeyManager"):
        self.m = m

    @staticmethod
    def _split_pair(value: Optional[str]):
        """解析 'OLD:NEW' 或 'NEW' 形式的参数。

        Returns:
            (old, new)：old 仅在包含 ':' 时非空。
        """
        if not value:
            return None, None
        if ':' in value:
            old, _, new = value.partition(':')
            return (old or None), (new or None)
        return None, value

    def rewrite(self, repo_path: Union[str, Path] = '.',
                name: Optional[str] = None,
                email: Optional[str] = None,
                author: Optional[str] = None,
                skip_confirm: bool = False):
        """重写 Git 历史中的作者/邮箱。

        三种互斥模式：
        1. --author <label>  全量刷新：把历史所有作者/邮箱统一为该 label
        2. --name NEW / --email NEW   全量刷新该字段：所有 name/email 统一为新值
        3. --name OLD:NEW / --email OLD:NEW   精细替换：OLD -> NEW
        """
        from ..services.git.rewrite import RewriteConfig, get_authors_in_repo, rewrite_history

        repo_path = Path(repo_path).resolve()
        if not (repo_path / '.git').exists():
            self.m._fail(_('err.not_git_repo', path=repo_path))
            return

        old_name, new_name = self._split_pair(name)
        old_email, new_email = self._split_pair(email)

        # 模式判定
        precise = bool(old_name or old_email)          # 精细替换（OLD:NEW）
        full_name = bool(new_name and not old_name)    # --name 单值全量
        full_email = bool(new_email and not old_email)  # --email 单值全量
        full_author = bool(author)                      # --author <label> 全量

        # 互斥校验：精细替换不能与任何全量刷新混用
        if precise and (full_author or full_name or full_email):
            self.m._fail(_("err.author_exclusive"))
            return
        # --author 不能与 --name/--email 单值全量混用
        if full_author and (full_name or full_email):
            self.m._fail(_("err.author_exclusive"))
            return

        if author:
            # 从作者列表读取 label 对应的 name/email
            stored = self.m.state_manager.read_authors().get(author.lower())
            if not stored:
                self.m._fail(_('err.author_not_found', label=author),
                             hint=_("err.use_author_list"))
                return
            match_all = True
            new_name = stored.get('name') or None
            new_email = stored.get('email') or None
            if not new_name and not new_email:
                self.m._fail(_("err.author_empty", label=author))
                return
        elif full_name or full_email:
            # 单值全量刷新：match_all 模式，只刷新提供的字段
            match_all = True
        else:
            match_all = False
            if not old_name and not old_email:
                self.m._fail(_("err.need_old"))
                return
            if not new_name and not new_email:
                self.m._fail(_("err.need_new"))
                return

        print_section_header(_("hdr.rewrite"))
        print(f"{_('lbl.repo_path')} {repo_path}")

        # 预览：列出历史中的作者
        authors = get_authors_in_repo(repo_path)
        print(f"\n{_('lbl.current_authors')}")
        for a in authors:
            print(f"   - {a}")

        # 构造规则并预估受影响提交
        cfg = RewriteConfig(old_name=old_name, new_name=new_name,
                            old_email=old_email, new_email=new_email,
                            match_all=match_all)
        if match_all:
            # 只展示实际被刷新的字段（--author 全量刷两者；单值只刷其一）
            parts = []
            if new_name:
                parts.append(f"{_('misc.name')} -> '{new_name}'")
            if new_email:
                parts.append(f"{_('misc.email')} -> '{new_email}'")
            match_desc = [f"{_('misc.all')} [{' | '.join(parts)}]"]
        else:
            match_desc = []
            if old_name:
                match_desc.append(f"{_('misc.name')} '{old_name}' -> '{new_name or old_name}'")
            if old_email:
                match_desc.append(f"{_('misc.email')} '{old_email}' -> '{new_email or old_email}'")
        print(f"\n⚙️ {_('lbl.rules')} {', '.join(match_desc)}")

        # 用 dry-run 预估（fast-export 到临时流，不导入）。
        # 显式传活跃 refs（排除 refs/original/ 备份），避免 matched 计数
        # 反复命中已重写过的旧历史。
        try:
            from ..services.git.rewrite import _active_refs, _count_matches
            active = _active_refs(repo_path)
            export = subprocess.run(
                ['git', '-C', str(repo_path), 'fast-export'] + active,
                capture_output=True, text=True, encoding='utf-8',
                errors='replace')
            matched = _count_matches(export.stdout or '', cfg)
        except Exception:
            matched = 0
        if matched == 0:
            self.m._fail(_('err.no_matches'), icon='⚠️')
            return
        print(f"ℹ️  {_('msg.will_rewrite_count', count=matched)}")

        # 破坏性操作确认
        print(f"\n⚠️  {_('msg.rewrites_history')}")
        print("   " + _("msg.force_push"))
        if not skip_confirm:
            if not prompt_confirm(_("msg.continue_rewrite")):
                self.m._fail(_("misc.operation_cancelled"))
                return

        try:
            with output_status(_('msg.rewriting')):
                result = rewrite_history(repo_path, cfg)
        except Exception as e:
            self.m._fail(_('err.rewrite_failed', err=e))
            return

        print(f"\n✅ {_('msg.history_rewritten')}")
        print(f"   {_('msg.matched_commits', count=result.get('matched_commits', 0))}")
        print(f"   {_('msg.rewritten_lines', count=result.get('rewritten', 0))}")
        print(f"\n⚠️  {_('msg.refs_backed_up')}")
        print(f"   {_('msg.force_push_all')}")
