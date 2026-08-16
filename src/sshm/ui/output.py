#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
输出抽象 - 将核心层与具体控制台输出解耦

核心层（core）不再直接调用内置 print，而是通过本模块的路由函数输出；
默认实现 ConsoleOutput 行为与原有 print 完全一致，因此现有 CLI / 测试
无需任何改动。后续 GUI / `--json` / 静默模式只需 `set_output()` 换实现。

设计：
- Output        ：接口（print / section / table / separator / confirm）
- ConsoleOutput ：默认实现，委托给 ui.console 与内置 print
- NullOutput    ：静默实现（供测试 / 无输出场景，confirm 恒为 True）
- 模块级当前输出 + set_output / get_output 注入点
- 路由函数与 core 层既有调用保持同名，行为委托给当前输出
"""

from __future__ import annotations

import builtins
from typing import Optional

from .console import (
    print_section_header,
    print_separator,
    print_table,
    prompt_confirm,
)

__all__ = [
    'Output', 'ConsoleOutput', 'NullOutput',
    'set_output', 'get_output',
    'print', 'section', 'table', 'separator', 'confirm',
]


class Output:
    """输出接口：核心层通过本接口输出，可替换为 GUI / JSON / 静默实现。"""

    def print(self, *args, **kwargs) -> None:
        raise NotImplementedError

    def section(self, title: str) -> None:
        raise NotImplementedError

    def table(self, headers, rows, **kwargs) -> None:
        raise NotImplementedError

    def separator(self, char: str = '=', length: int = 80) -> None:
        raise NotImplementedError

    def confirm(self, message: str, default: Optional[str] = None) -> bool:
        raise NotImplementedError


class ConsoleOutput(Output):
    """默认控制台输出：行为与原有 print / console 助手完全一致。"""

    def print(self, *args, **kwargs) -> None:
        builtins.print(*args, **kwargs)

    def section(self, title: str) -> None:
        print_section_header(title)

    def table(self, headers, rows, **kwargs) -> None:
        print_table(headers, rows, **kwargs)

    def separator(self, char: str = '=', length: int = 80) -> None:
        print_separator(char, length)

    def confirm(self, message: str, default: Optional[str] = None) -> bool:
        return prompt_confirm(message, default)


class NullOutput(Output):
    """静默输出：不产生任何输出；确认一律视为 True（自动通过）。"""

    def print(self, *args, **kwargs) -> None:
        pass

    def section(self, title: str) -> None:
        pass

    def table(self, headers, rows, **kwargs) -> None:
        pass

    def separator(self, char: str = '=', length: int = 80) -> None:
        pass

    def confirm(self, message: str, default: Optional[str] = None) -> bool:
        return True


# --------------------------------------------------------------------------
# 模块级当前输出（注入点）
# --------------------------------------------------------------------------
_current: Output = ConsoleOutput()


def set_output(output: Output) -> None:
    """替换当前输出实现（GUI / JSON / 静默模式入口）"""
    global _current
    _current = output


def get_output() -> Output:
    """获取当前输出实现"""
    return _current


# --------------------------------------------------------------------------
# 路由函数：与 core 层既有调用保持同名，行为委托给当前输出
# --------------------------------------------------------------------------
def print(*args, **kwargs) -> None:
    _current.print(*args, **kwargs)


def section(title: str) -> None:
    _current.section(title)


def table(headers, rows, **kwargs) -> None:
    _current.table(headers, rows, **kwargs)


def separator(char: str = '=', length: int = 80) -> None:
    _current.separator(char, length)


def confirm(message: str, default: Optional[str] = None) -> bool:
    return _current.confirm(message, default)
