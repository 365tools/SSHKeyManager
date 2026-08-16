#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
控制台工具模块 - 格式化输出、Windows 编码修复等
"""

import re
import shutil
import sys
import unicodedata
from datetime import datetime
from typing import Iterable, Optional

try:
    from wcwidth import wcswidth as _wcswidth
    from wcwidth import wcwidth as _wcwidth_char
except ImportError:  # pragma: no cover - wcwidth 为正式依赖，缺失时降级
    _wcswidth = None
    _wcwidth_char = None


def setup_windows_console() -> None:
    """修复 Windows 控制台 UTF-8 编码问题。

    设置控制台代码页为 UTF-8，并重新包装 stdout/stderr 为 UTF-8 编码，
    以支持 emoji 输出。注意：必须在任何 Typer/click 输出之前完成。
    """
    if sys.platform != 'win32':
        return

    try:
        import ctypes
        import io
        kernel32 = ctypes.windll.kernel32
        # 设置控制台代码页为 UTF-8 (65001)
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)

        # 仅当 stdout/stderr 是真实交互控制台时才重新包装，
        # 避免在测试（pytest 捕获）等非 tty 环境下破坏输出对象。
        if hasattr(sys.stdout, 'buffer') and getattr(sys.stdout, 'isatty', lambda: False)():
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding='utf-8', errors='replace',
                line_buffering=True, write_through=True)
        if hasattr(sys.stderr, 'buffer') and getattr(sys.stderr, 'isatty', lambda: False)():
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding='utf-8', errors='replace',
                line_buffering=True, write_through=True)
    except Exception:
        pass  # 静默失败


def get_key_pattern() -> re.Pattern[str]:
    """获取密钥文件名匹配模式"""
    return re.compile(r'^id_(rsa|ed25519|ecdsa|dsa)(\.\w+)?$')


def format_timestamp(dt: datetime) -> str:
    """格式化时间戳"""
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def format_size(size_bytes: int) -> str:
    """格式化文件大小为人类可读形式"""
    size = float(size_bytes)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size < 1024 or unit == 'TB':
            return f"{int(size)} B" if unit == 'B' else f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size_bytes} B"


def get_display_width(text: str) -> int:
    """计算字符串在终端中的显示宽度（中文/emoji 按双宽计）

    优先使用 wcwidth 库（Unicode 标准宽度，正确处理 emoji 与
    变体选择符），未安装时回退到内置的 Unicode 判断逻辑。
    """
    if _wcswidth is not None:
        try:
            width = _wcswidth(text)
            if width >= 0:
                return width
        except Exception:
            pass
    return sum(_char_width(ch) for ch in text)


def _char_width(ch: str) -> int:
    """计算单个字符的显示宽度（wcwidth 优先，含零宽变体选择符处理）"""
    if _wcwidth_char is not None:
        try:
            width = _wcwidth_char(ch)
            if width >= 0:
                return width
        except Exception:
            pass
    code = ord(ch)
    # 零宽字符：变体选择符（emoji 后续 FE0F/FE0E）、零宽连接符等
    if code in (0x200B, 0x200C, 0x200D, 0x2060) \
            or 0xFE00 <= code <= 0xFE0F:
        return 0
    # 常见 emoji/符号区域（多数终端按双宽渲染）
    if 0x2600 <= code <= 0x27FF or 0x2B00 <= code <= 0x2BFF \
            or 0x1F000 <= code <= 0x1FAFF:
        return 2
    if unicodedata.east_asian_width(ch) in ('W', 'F', 'A'):
        return 2
    return 1


def pad_cell(text: Optional[str], width: int, align: str = 'left') -> str:
    """按显示宽度对齐单元格文本，超宽时截断并追加省略号。

    text 为 None 时按空串处理（适配解包自 Unknown 元组的调用点）。
    """
    text = text or ''
    text_width = get_display_width(text)
    if text_width > width:
        result = ''
        result_width = 0
        ellipsis_width = _char_width('…')
        for ch in text:
            ch_width = _char_width(ch)
            if result_width + ch_width > width - ellipsis_width:
                break
            result += ch
            result_width += ch_width
        if result_width + ellipsis_width <= width:
            result += '…'
        return result

    padding = width - text_width
    if align == 'right':
        return ' ' * padding + text
    if align == 'center':
        left = padding // 2
        return ' ' * left + text + ' ' * (padding - left)
    return text + ' ' * padding


def print_table(headers: list,
                rows: list,
                truncatable: Optional[Iterable[int]] = None,
                term_width: Optional[int] = None,
                center_cols: Optional[Iterable[int]] = None) -> None:
    """以表格形式打印数据，自动处理 CJK/emoji 对齐与窄终端压缩

    Args:
        headers: 表头列表
        rows: 数据行列表（二维列表）
        truncatable: 窄终端下允许压缩的列索引集合
        term_width: 终端宽度，默认自动检测
        center_cols: 数据居中对齐的列索引集合（表头始终居中）
    """
    headers = [str(h) for h in headers]
    rows = [[str(cell) for cell in row] for row in rows]
    n_cols = len(headers)
    if n_cols == 0:
        return
    center_cols = set(center_cols or [])

    if term_width is None:
        term_width = shutil.get_terminal_size((100, 24)).columns
    truncatable = set(truncatable or [])

    # 计算每列自然宽度
    widths = [get_display_width(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], get_display_width(cell))

    # 压缩可截断列以适配终端宽度（每列至少保留 8 列宽）
    overflow = sum(widths) + 3 * n_cols + 1 - term_width
    if overflow > 0:
        for i in sorted(truncatable, key=lambda x: widths[x], reverse=True):
            if overflow <= 0:
                break
            max_shrink = widths[i] - 8
            if max_shrink <= 0:
                continue
            shrink = min(max_shrink, overflow)
            widths[i] -= shrink
            overflow -= shrink

    # 渲染
    line_sep = '+' + '+'.join('-' * (w + 2) for w in widths) + '+'
    print(line_sep)
    header_cells = [pad_cell(h, w, align='center') for h, w in zip(headers, widths)]
    print('| ' + ' | '.join(header_cells) + ' |')
    print(line_sep)
    for row in rows:
        cells = [
            pad_cell(row[i], widths[i],
                     align='center' if i in center_cols else 'left')
            for i in range(n_cols)
        ]
        print('| ' + ' | '.join(cells) + ' |')
        print(line_sep)


def prompt_confirm(message: str, default: Optional[str] = None) -> bool:
    """确认提示

    Args:
        message: 提示文本
        default: 回车时的默认值，'y' 默认确认，'n' 默认拒绝，None 时回车视为拒绝
    """
    if default == 'y':
        response = input(f"{message} [Y/n]: ").lower().strip()
        return response in ['y', 'yes'] or response == ''
    if default == 'n':
        response = input(f"{message} [y/N]: ").lower().strip()
        return response in ['y', 'yes']
    response = input(f"{message} (y/n): ").lower().strip()
    return response in ['y', 'yes']


def print_separator(char: str = '=', length: int = 80) -> None:
    """打印分隔线"""
    print(char * length)


def print_section_header(title: str) -> None:
    """打印章节标题"""
    print_separator()
    print(title)
    print_separator()


def wait_for_key() -> None:
    """等待用户按键"""
    from ..i18n import _
    print(f"\n{_('menu.press_any')}")
    if sys.platform == 'win32':
        try:
            import msvcrt
            msvcrt.getch()
        except Exception:
            input()
    else:
        input()
