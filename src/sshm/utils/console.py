#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
控制台工具模块 - 格式化输出、Windows 编码修复等
"""

import sys
import io
import re
from datetime import datetime


def setup_windows_console():
    """修复 Windows 控制台 UTF-8 编码问题"""
    if sys.platform != 'win32':
        return
    
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        
        # 设置控制台代码页为 UTF-8 (65001)
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
        
        # 重新包装 stdout/stderr
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer,
                encoding='utf-8',
                errors='replace',
                line_buffering=True,
                write_through=True
            )
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer,
                encoding='utf-8',
                errors='replace',
                line_buffering=True,
                write_through=True
            )
    except Exception:
        pass  # 静默失败


def get_key_pattern():
    """获取密钥文件名匹配模式"""
    return re.compile(r'^id_(rsa|ed25519|ecdsa|dsa)(\.\w+)?$')


def format_timestamp(dt: datetime) -> str:
    """格式化时间戳"""
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    return f"{size_bytes} bytes"


def prompt_confirm(message: str) -> bool:
    """确认提示"""
    response = input(f"{message} (y/n): ").lower().strip()
    return response in ['y', 'yes']


def print_separator(char='=', length=80):
    """打印分隔线"""
    print(char * length)


def print_section_header(title: str):
    """打印章节标题"""
    print_separator()
    print(title)
    print_separator()


def wait_for_key():
    """等待用户按键"""
    print("\n按任意键继续...")
    if sys.platform == 'win32':
        try:
            import msvcrt
            msvcrt.getch()
        except:
            input()
    else:
        input()
