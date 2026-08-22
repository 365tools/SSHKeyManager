#!/usr/bin/env python3
"""
常量定义模块
"""

import re
from pathlib import Path

SUPPORTED_KEY_TYPES = ["ed25519", "rsa", "ecdsa", "dsa"]
DEFAULT_KEY_TYPE = "ed25519"
STATE_FILE_NAME = ".sshm_state"
BACKUP_DIR_NAME = "key_backups"

# 默认 SSH 目录与 SSH config 文件名（跨模块唯一来源，避免各处硬编码）
DEFAULT_SSH_DIR = Path.home() / ".ssh"
SSH_CONFIG_NAME = "config"

# 源码/打包时 CHANGELOG.md 的可能位置
_CHANGELOG_CANDIDATES = [
    Path(__file__).resolve().parent.parent.parent / "docs" / "CHANGELOG.md",  # 源码: src/sshm -> 项目/docs
    Path(__file__).resolve().parent.parent / "CHANGELOG.md",  # 打包: 归档根/CHANGELOG.md
]


def _load_version_from_changelog() -> str | None:
    """从 CHANGELOG.md 解析最新已发布版本（`## [x.y.z] - date`）。

    取第一个非 Unreleased 的版本章节；找不到返回 None。
    """
    for path in _CHANGELOG_CANDIDATES:
        try:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            # 匹配 `## [x.y.z]` 或 `## [x.y.z] - date`
            match = re.search(r"^##\s+\[(\d+\.\d+(?:\.\d+)?)\]", text, re.MULTILINE)
            if match:
                return match.group(1)
        except (OSError, UnicodeDecodeError):
            continue
    return None


def _load_version_from_file() -> str | None:
    """从版本文件 `src/sshm/_version.txt` 读取当前版本。

    与 `pyproject.toml` 的 `version = { file = "src/sshm/_version.txt" }`
    保持一致（构建期与运行期用同一来源），避免因 import 包触发依赖而失败。
    """
    candidates = [
        Path(__file__).resolve().parent / "_version.txt",  # 源码/打包: src/sshm/_version.txt
    ]
    for path in candidates:
        try:
            if not path.exists():
                continue
            ver = path.read_text(encoding="utf-8").strip()
            if ver:
                return ver
        except (OSError, UnicodeDecodeError):
            continue
    return None


def _load_version_from_metadata() -> str | None:
    """从已安装包元数据读取版本（`pip install -e .` / 打包安装后可用）。"""
    try:
        from importlib.metadata import version

        return version("sshm")
    except Exception:
        return None


def _load_version() -> str:
    """多级自动解析当前版本（全链路无硬编码发布号）:

    1. 优先从版本文件 `_version.txt` 读取（与 pyproject 构建一致，不 import 包）
    2. 回退到 CHANGELOG.md 解析（仓库运行时）
    3. 再回退到已安装包的元数据版本（pip 安装后）
    4. 最终回退为开发版 '0.0.0'（表示未发布/非标准运行环境）
    """
    return _load_version_from_file() or _load_version_from_changelog() or _load_version_from_metadata() or "0.0.0"


# 当前版本：完全自动解析（版本文件 / CHANGELOG / 包元数据），无需硬编码
VERSION = _load_version()
