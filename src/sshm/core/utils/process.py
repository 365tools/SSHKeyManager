#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
进程/子进程工具 - 统一 git / 命令执行约定。

收敛散落在各服务/命令中的 `subprocess.run(['git', '-C', ...], ...)` 样板：
统一捕获输出、UTF-8 文本模式、失败抛 subprocess.CalledProcessError
（由调用方按业务需要 try/except 处理，如 git 不存在 / 非仓库目录）。
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Union


def run_checked(cmd: List[str], *, timeout: int | None = None
                ) -> subprocess.CompletedProcess:
    """运行命令并统一捕获输出（UTF-8 文本，失败抛异常）。

    - check=True：非零退出码抛 subprocess.CalledProcessError
    - capture_output=True：同时捕获 stdout/stderr
    - 显式 UTF-8 解码，避免 Windows 下按本地代码页（GBK）误解码 git 输出
    """
    return subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=timeout,
    )


def git(repo: Union[str, Path], *args: str) -> subprocess.CompletedProcess:
    """在指定仓库目录执行 git 命令（`git -C <repo> <args...>`）。"""
    return run_checked(['git', '-C', str(repo), *args])
