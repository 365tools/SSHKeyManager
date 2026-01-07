#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主程序入口 - 支持 python -m sshm 运行
"""

import sys
from .cli import create_parser, handle_command, show_interactive_menu


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
    
    # 处理命令
    handle_command(args)


if __name__ == '__main__':
    main()
