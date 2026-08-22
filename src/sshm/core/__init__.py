#!/usr/bin/env python3
"""
核心模块初始化
"""

# 注意: 必须使用直接导入(非延迟/__getattr__), 否则 PyInstaller 静态分析
# 无法追踪到 sshm.core.manager 等子模块, 打包后运行时报 ModuleNotFoundError
from .manager import SSHKeyManager
from .services.ssh.config import SSHConfigManager
from .services.storage.state import StateManager

__all__ = ["SSHConfigManager", "SSHKeyManager", "StateManager"]
