#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
常量定义模块
"""

import re
from pathlib import Path
from typing import Optional

SUPPORTED_KEY_TYPES = ['ed25519', 'rsa', 'ecdsa', 'dsa']
DEFAULT_KEY_TYPE = 'ed25519'
STATE_FILE_NAME = '.sshm_state'
BACKUP_DIR_NAME = 'key_backups'

# 源码/打包时 CHANGELOG.md 的可能位置
_CHANGELOG_CANDIDATES = [
    Path(__file__).resolve().parent.parent.parent / 'docs' / 'CHANGELOG.md',  # 源码: src/sshm -> 项目/docs
    Path(__file__).resolve().parent.parent / 'CHANGELOG.md',                 # 打包: 归档根/CHANGELOG.md
]


def _load_version_from_changelog() -> Optional[str]:
    """从 CHANGELOG.md 解析最新已发布版本（`## [x.y.z] - date`）。

    取第一个非 Unreleased 的版本章节；找不到返回 None。
    """
    for path in _CHANGELOG_CANDIDATES:
        try:
            if not path.exists():
                continue
            text = path.read_text(encoding='utf-8', errors='replace')
            # 匹配 `## [x.y.z]` 或 `## [x.y.z] - date`
            match = re.search(r'^##\s+\[(\d+\.\d+(?:\.\d+)?)\]', text, re.M)
            if match:
                return match.group(1)
        except (OSError, UnicodeDecodeError):
            continue
    return None


def _load_version_from_metadata() -> Optional[str]:
    """从已安装包元数据读取版本（`pip install -e .` / 打包安装后可用）。"""
    try:
        from importlib.metadata import version
        return version('sshm')
    except Exception:
        return None


def _load_version() -> str:
    """多级自动解析当前版本（全链路无硬编码发布号）:

    1. 优先从 CHANGELOG.md 解析（源码/仓库运行时）
    2. 回退到已安装包的元数据版本（pip 安装后）
    3. 最终回退为开发版 '0.0.0'（表示未发布/非标准运行环境）
    """
    return (_load_version_from_changelog()
            or _load_version_from_metadata()
            or "0.0.0")


# 当前版本：完全自动解析（CHANGELOG / 包元数据），无需硬编码
VERSION = _load_version()
