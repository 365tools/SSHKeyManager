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
    
    def __init__(self, state_file: Path):
        self.state_file = state_file
    
    def read_active_keys(self) -> Dict[str, str]:
        """读取当前激活的密钥状态"""
        if not self.state_file.exists():
            return {}
        
        try:
            data = json.loads(self.state_file.read_text(encoding='utf-8'))
            # 确保标签为小写
            return {k: v.lower() if v else v for k, v in data.items()}
        except (json.JSONDecodeError, IOError):
            return {}
    
    def write_active_key(self, key_type: str, label: str):
        """写入当前激活的密钥状态"""
        state = self.read_active_keys()
        state[key_type] = label.lower()
        self.state_file.write_text(json.dumps(state, indent=2), encoding='utf-8')
    
    def remove_active_key(self, key_type: str):
        """移除指定类型的激活状态"""
        state = self.read_active_keys()
        if key_type in state:
            del state[key_type]
            self.state_file.write_text(json.dumps(state, indent=2), encoding='utf-8')
    
    def update_label(self, old_label: str, new_label: str):
        """更新状态文件中的标签名"""
        state = self.read_active_keys()
        old_label_lower = old_label.lower()
        new_label_lower = new_label.lower()
        
        updated = False
        for key_type, label in state.items():
            if label == old_label_lower:
                state[key_type] = new_label_lower
                updated = True
        
        if updated:
            self.state_file.write_text(json.dumps(state, indent=2), encoding='utf-8')
