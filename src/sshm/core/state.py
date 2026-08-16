#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
状态管理器 - 负责密钥状态的持久化
"""

import json
from pathlib import Path
from typing import Dict


class StateManager:
    """密钥状态管理器"""

    # 顶层保留字段，不参与 active_keys 映射
    RESERVED_KEYS = ('authors', 'hosts', 'lang')

    def __init__(self, state_file: Path):
        self.state_file = state_file

    def _read_state(self) -> dict:
        """读取完整状态文件（兼容旧格式）"""
        if not self.state_file.exists():
            return {}
        try:
            data = json.loads(self.state_file.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, IOError):
            # 状态文件损坏：备份原文件，避免后续写入静默覆盖丢失数据
            try:
                corrupt_backup = self.state_file.with_suffix('.state.corrupt')
                self.state_file.rename(corrupt_backup)
            except OSError:
                pass
        return {}

    def _write_state(self, state: dict):
        """写入完整状态文件"""
        self.state_file.write_text(json.dumps(state, indent=2), encoding='utf-8')

    # ------------------------------------------------------------------
    # active_keys 相关
    # ------------------------------------------------------------------

    def read_active_keys(self) -> Dict[str, str]:
        """读取当前激活的密钥状态"""
        state = self._read_state()
        active = {}
        for k, v in state.items():
            if k in self.RESERVED_KEYS:
                continue
            # 兼容旧格式：标签为小写
            active[k] = v.lower() if isinstance(v, str) else v
        return active

    def write_active_key(self, key_type: str, label: str):
        """写入当前激活的密钥状态"""
        state = self._read_state()
        state[key_type] = label.lower()
        self._write_state(state)

    def remove_active_key(self, key_type: str):
        """移除指定类型的激活状态"""
        state = self._read_state()
        if key_type in state:
            del state[key_type]
            self._write_state(state)

    def update_label(self, old_label: str, new_label: str):
        """更新状态文件中的标签名（含作者与主机映射）"""
        state = self._read_state()
        old_label_lower = old_label.lower()
        new_label_lower = new_label.lower()

        updated = False
        for key_type, label in state.items():
            if key_type in self.RESERVED_KEYS:
                continue
            if label == old_label_lower:
                state[key_type] = new_label_lower
                updated = True

        authors = state.get('authors')
        if isinstance(authors, dict) and old_label_lower in authors:
            authors[new_label_lower] = authors.pop(old_label_lower)
            updated = True

        hosts = state.get('hosts')
        if isinstance(hosts, dict) and old_label_lower in hosts:
            hosts[new_label_lower] = hosts.pop(old_label_lower)
            updated = True

        if updated:
            self._write_state(state)

    # ------------------------------------------------------------------
    # authors 相关
    # ------------------------------------------------------------------

    def read_authors(self) -> Dict[str, Dict[str, str]]:
        """读取作者信息映射 {label: {'name': str, 'email': str}}"""
        state = self._read_state()
        authors = state.get('authors', {})
        return authors if isinstance(authors, dict) else {}

    def write_author(self, label: str, name: str, email: str):
        """写入指定标签的作者信息"""
        state = self._read_state()
        authors = state.setdefault('authors', {})
        if not isinstance(authors, dict):
            authors = state['authors'] = {}
        authors[label.lower()] = {'name': name or '', 'email': email or ''}
        self._write_state(state)

    def remove_author(self, label: str):
        """移除指定标签的作者信息"""
        state = self._read_state()
        authors = state.get('authors')
        if isinstance(authors, dict) and label.lower() in authors:
            del authors[label.lower()]
            self._write_state(state)

    # ------------------------------------------------------------------
    # hosts 相关（label -> hostname 映射，供 use/remove/rename 使用）
    # ------------------------------------------------------------------

    def read_hosts(self) -> Dict[str, str]:
        """读取标签到主机名的映射 {label: hostname}"""
        state = self._read_state()
        hosts = state.get('hosts', {})
        return hosts if isinstance(hosts, dict) else {}

    def write_host(self, label: str, hostname: str):
        """写入指定标签的主机名映射"""
        state = self._read_state()
        hosts = state.setdefault('hosts', {})
        if not isinstance(hosts, dict):
            hosts = state['hosts'] = {}
        hosts[label.lower()] = hostname
        self._write_state(state)

    def remove_host(self, label: str):
        """移除指定标签的主机名映射"""
        state = self._read_state()
        hosts = state.get('hosts')
        if isinstance(hosts, dict) and label.lower() in hosts:
            del hosts[label.lower()]
            self._write_state(state)

    # ------------------------------------------------------------------
    # lang 相关（输出语言设置）
    # ------------------------------------------------------------------

    def read_lang(self) -> str:
        """读取保存的输出语言（'en'/'zh'，默认 'en'）"""
        state = self._read_state()
        lang = state.get('lang')
        return lang if isinstance(lang, str) else 'en'

    def write_lang(self, lang: str):
        """保存输出语言设置（'en'/'zh'）"""
        state = self._read_state()
        state['lang'] = lang if lang == 'zh' else 'en'
        self._write_state(state)

    # ------------------------------------------------------------------
    # auto_author 相关（凭据切换时自动联动人员）
    # ------------------------------------------------------------------

    def read_auto_author(self) -> bool:
        """读取凭据-author 自动联动开关（默认开启）"""
        state = self._read_state()
        return state.get('auto_author', True)

    def write_auto_author(self, enabled: bool):
        """保存凭据-author 自动联动开关"""
        state = self._read_state()
        state['auto_author'] = bool(enabled)
        self._write_state(state)
