#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sshm - 企业级多账号 SSH 密钥管理工具

功能特性:
- 🏷️ 标签化管理多个 SSH 密钥
- 🔄 一键切换默认密钥
- ⚙️ 自动生成和维护 SSH config
- 💾 智能备份保护
- 📊 状态追踪和可视化
- 🔍 Git 仓库配置管理
- ✅ SSH 连接测试

作者: Eavelabs
版本: 0.0.1
许可: MIT
"""

from .constants import VERSION
from .core import SSHKeyManager, SSHConfigManager, StateManager
from .utils import setup_windows_console

__version__ = VERSION
__all__ = [
    'VERSION',
    'SSHKeyManager',
    'SSHConfigManager',
    'StateManager',
    'setup_windows_console'
]

# 自动初始化 Windows 控制台
setup_windows_console()
