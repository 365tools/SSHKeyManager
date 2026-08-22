#!/usr/bin/env python3
"""
PyInstaller 入口点 - 使用绝对导入避免打包问题
用于构建独立可执行文件
"""

import os
import sys

# 确保 src 目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 使用绝对导入
from sshm.__main__ import main

if __name__ == "__main__":
    main()
