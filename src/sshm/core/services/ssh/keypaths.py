#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSH 密钥文件路径/命名工具 - 密钥文件名的唯一构造与匹配入口。

收敛散落在 commands / services 中的 `f"id_{key_type}.{label}"` 手工拼串，
并接收原 ui.console 中放错层的 get_key_pattern（修复 core→ui 反向依赖：
业务层不再 import 表现层）。

命名约定：
    - 默认私钥:     id_<type>            （如 id_ed25519）
    - 带标签私钥:   id_<type>.<label>    （如 id_ed25519.github）
    - 公钥:         私钥名 + '.pub'
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple

# 密钥文件名匹配：id_<type>[.<后缀>]（后缀可为标签或 .pub）
_KEY_FILE_RE = re.compile(r'^id_(rsa|ed25519|ecdsa|dsa)(\.\w+)?$')


def get_key_pattern() -> re.Pattern[str]:
    """获取密钥文件名匹配模式"""
    return _KEY_FILE_RE


def private_key_path(ssh_dir: Path, key_type: str,
                     label: Optional[str] = None) -> Path:
    """私钥文件路径：label 存在 → id_<type>.<label>，否则 id_<type>。"""
    name = f"id_{key_type}.{label}" if label else f"id_{key_type}"
    return ssh_dir / name


def public_key_path(ssh_dir: Path, key_type: str,
                    label: Optional[str] = None) -> Path:
    """公钥文件路径（= 私钥名 + '.pub'）。"""
    return Path(f"{private_key_path(ssh_dir, key_type, label)}.pub")


def key_paths(ssh_dir: Path, key_type: str,
              label: Optional[str] = None) -> Tuple[Path, Path]:
    """私钥 + 公钥文件路径。"""
    private = private_key_path(ssh_dir, key_type, label)
    return private, Path(f"{private}.pub")
