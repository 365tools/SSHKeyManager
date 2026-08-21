#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统命令组 - 系统级命令的编排（lang / update / add_path）。

只负责把用户意图翻译为对 StateManager / UpdateManager / path 的编排调用 + 渲染。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ...i18n import _
from ...language import K
from ...ui.output import print, separator as print_separator

if TYPE_CHECKING:
    from ..manager import SSHKeyManager


class SystemCommands:
    """系统命令编排。"""

    def __init__(self, m: "SSHKeyManager"):
        self.m = m

    def show(self) -> None:
        """显示当前系统配置总览（语言 + 自动作者联动开关）。"""
        from ...i18n import get_lang
        from ...ui.output import section as print_section_header

        lang = get_lang()
        name = "Chinese" if lang == "zh" else "English"
        print_section_header(_(K.hdr.auto_author))
        print(f"   {_(K.lbl.current_language)} {name} ({lang})")

        auto_author = self.m.state_manager.read_auto_author()
        status = _(K.misc.on) if auto_author else _(K.misc.off)
        print(f"   🔀 {_(K.msg.auto_author_status, status=status)}")

    def language(self, lang: str) -> str:
        """设置输出语言并持久化到状态文件

        Args:
            lang: 'en' 或 'zh'

        Returns:
            实际生效的语言（非法值回退 'en'）
        """
        lang = lang if lang == "zh" else "en"
        self.m.state_manager.write_lang(lang)
        from ...i18n import set_lang

        set_lang(lang)
        return lang

    def update(self, check: bool = False, force: bool = False) -> Optional[int]:
        """检查并更新到最新版本。

        Returns:
            退出码（0 成功 / 1 失败）；无需退出（已最新 / 仅检查 / 取消）返回 None
        """
        from ..services.net.updater import UpdateManager

        updater = UpdateManager()
        print_separator()
        print(_(K.hdr.update))
        print_separator()
        print(f"\n{_(K.lbl.current_version)} v{updater.current_version}")
        print(f"{_(K.lbl.platform)} {updater.platform}")

        print("\n" + _(K.upd.checking))
        update_info = updater.check_update(force=force)

        if not update_info:
            print("✅ " + _(K.upd.up_to_date))
            return None

        print(f"\n🎉 {_(K.upd.new_version, version=update_info['version'])}")
        print(
            f"{_(K.upd.release_date)} {update_info.get('published_at') or _(K.msg.unknown)}"
        )

        if update_info.get("body"):
            print(f"\n{_(K.upd.update_notes)}")
            for line in update_info["body"].split("\n")[:10]:
                print(f"  {line}")
            if len(update_info["body"].split("\n")) > 10:
                print("  ...")

        if check:
            print(f"\n💡 {_(K.upd.run_update)}")
            return None

        print()
        try:
            response = input(_(K.upd.prompt, version=update_info["version"]))
            if response.lower() == "n":
                self.m._fail(_(K.upd.cancelled))
                return None
        except KeyboardInterrupt:
            self.m._fail(_(K.upd.cancelled))
            return None

        print()
        success = updater.download_and_update(update_info["download_url"])
        return 0 if success else 1

    def add_to_path(self) -> None:
        """把当前可执行文件目录添加到系统 PATH"""
        from ..services.ssh.path import add_to_path

        add_to_path()
