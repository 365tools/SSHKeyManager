#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主程序入口 - 支持 python -m sshm 运行
"""

import sys
from pathlib import Path

from .constants import STATE_FILE_NAME
from .core.state import StateManager
from .i18n import load_from_state
from .utils.updater import UpdateManager

def _load_lang_before_parse() -> None:
    """在解析参数/显示帮助前应用语言（环境变量优先于状态文件）"""
    try:
        state = StateManager(Path.home() / '.ssh' / STATE_FILE_NAME)
        load_from_state(state.read_lang())
    except Exception:
        load_from_state(None)


def _silent_update_check() -> None:
    """非 update 命令时静默检查更新（不干扰用户）"""
    try:
        updater = UpdateManager()
        updater.check_and_notify()
    except Exception:
        # 静默失败，不影响正常使用
        pass


def _should_silent_check() -> bool:
    """判断是否需要静默更新检查（排除版本/帮助/更新命令自身）"""
    if 'update' in sys.argv:
        return False
    # 只检查第一个参数（命令行入口）
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    if not args:
        return False  # 无子命令（如 -v / --help / 空）
    return True


def main() -> None:
    """主函数入口"""
    # 无论 CLI 还是交互菜单，都先应用语言
    _load_lang_before_parse()

    # 检测双击运行（无参数）→ 进入交互菜单
    if len(sys.argv) == 1:
        from .cli.interactive import show_interactive_menu
        show_interactive_menu()
        return

    # 实际执行业务命令时静默检查更新
    if _should_silent_check():
        _silent_update_check()

    # 运行 Typer 应用
    from .cli.cli import app
    app()


if __name__ == '__main__':
    main()

