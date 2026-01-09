#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyInstaller 入口点 - 使用绝对导入避免打包问题
用于构建独立可执行文件
"""

import sys
import os

# 确保 src 目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 使用绝对导入
from sshm.cli.parser import create_parser
from sshm.cli.commands import handle_command
from sshm.cli.interactive import show_interactive_menu
from sshm.utils.updater import UpdateManager


def main():
    """主函数入口"""
    # 检测双击运行（无参数）
    if len(sys.argv) == 1:
        show_interactive_menu()
        return
    
    # 解析命令行参数
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 非 update 命令时，静默检查更新（不干扰用户）
    if args.command != 'update':
        try:
            updater = UpdateManager()
            updater.check_and_notify()
        except:
            # 静默失败，不影响正常使用
            pass
    
    # 处理命令
    handle_command(args)


if __name__ == '__main__':
    main()
