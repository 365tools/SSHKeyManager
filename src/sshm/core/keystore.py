#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
密钥文件仓库 - 只负责 ~/.ssh 目录下的密钥文件扫描 / 检测 / 复制。

不涉及任何业务编排、状态持久化或输出；SSHKeyManager 组合本服务并做门面委托。
"""

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..constants import SUPPORTED_KEY_TYPES
from ..ui.console import get_key_pattern


class KeyStore:
    """密钥文件仓库：扫描 / 检测 / 复制密钥文件。"""

    def __init__(self, ssh_dir: Path):
        self.ssh_dir = ssh_dir

    def ensure_directories(self) -> None:
        """确保必要的目录存在"""
        self.ssh_dir.mkdir(mode=0o700, exist_ok=True)

    def scan_all_keys(self) -> Dict[str, List[Dict]]:
        """扫描所有密钥文件"""
        keys_by_label: Dict[str, List[Dict]] = {}
        key_pattern = get_key_pattern()

        for file in self.ssh_dir.glob('id_*'):
            if not file.is_file() or file.name.endswith('.pub'):
                continue

            match = key_pattern.match(file.name)
            if not match:
                continue

            key_type = match.group(1)
            label = match.group(2)[1:] if match.group(2) else 'default'
            # 跳过 use -g 切换的系统备份文件（id_*.original），不视为用户标签
            if label.lower() == 'original':
                continue

            pub_file = self.ssh_dir / f"{file.name}.pub"
            key_info = {
                'type': key_type,
                'private': file,
                'public': pub_file,
                'has_pub': pub_file.exists(),
                'size': file.stat().st_size,
                'mtime': datetime.fromtimestamp(file.stat().st_mtime),
            }

            if label not in keys_by_label:
                keys_by_label[label] = []
            keys_by_label[label].append(key_info)

        return keys_by_label

    def detect_key_type_for_label(self, label: str) -> Optional[str]:
        """检测指定标签的密钥类型"""
        for key_type in SUPPORTED_KEY_TYPES:
            key_file = self.ssh_dir / f"id_{key_type}.{label}"
            if key_file.exists():
                return key_type
        return None

    def detect_default_key_type(self) -> Optional[str]:
        """检测默认密钥类型"""
        for key_type in SUPPORTED_KEY_TYPES:
            key_file = self.ssh_dir / f"id_{key_type}"
            if key_file.exists():
                return key_type
        return None

    def copy_key_pair(self, source: Path, target: Path) -> None:
        """复制密钥对（私钥 + 可选公钥），公钥缺失时不中断"""
        shutil.copy2(source, target)
        pub_source = Path(str(source) + '.pub')
        if pub_source.exists():
            shutil.copy2(pub_source, Path(str(target) + '.pub'))

    def extract_email_from_pubkey(self, key_type: str,
                                  label: Optional[str] = None) -> Optional[str]:
        """从公钥注释提取邮箱（ssh-keygen -C email 写入）

        label 为 None 时读取默认密钥（id_{type}.pub），否则读取带标签的公钥。
        """
        if label:
            pub_file = self.ssh_dir / f"id_{key_type}.{label}.pub"
        else:
            pub_file = self.ssh_dir / f"id_{key_type}.pub"
        if not pub_file.exists():
            return None
        try:
            parts = pub_file.read_text(encoding='utf-8').strip().split()
            if len(parts) >= 3:
                comment = parts[-1]
                if re.match(r'^[^@\s]+@[^@\s]+$', comment):
                    return comment
        except (OSError, UnicodeDecodeError):
            pass
        return None
