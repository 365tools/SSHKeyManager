#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
展示层 - 输出抽象与终端渲染。

- output.py：Output 抽象（核心层输出边界）+ ConsoleOutput / NullOutput 实现
- console.py：终端渲染（表格 / 对齐 / 确认 / Windows 编码修复 / 通用格式化）

核心层（core）只依赖 Output 抽象；cli 等适配层直接使用 console 渲染能力。
"""

from .console import (
    setup_windows_console,
    format_timestamp,
    format_size,
    get_display_width,
    pad_cell,
    prompt_confirm,
    print_separator,
    print_section_header,
    print_table,
    wait_for_key,
)
from .output import ConsoleOutput, NullOutput, Output

__all__ = [
    'setup_windows_console',
    'format_timestamp',
    'format_size',
    'get_display_width',
    'pad_cell',
    'prompt_confirm',
    'print_separator',
    'print_section_header',
    'print_table',
    'wait_for_key',
    'Output', 'ConsoleOutput', 'NullOutput',
]
