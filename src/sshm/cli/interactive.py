#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互式菜单 - 双击运行时的用户界面
"""

import sys

from ..constants import VERSION
from ..core import SSHKeyManager
from ..utils import print_separator, print_section_header, wait_for_key
from ..utils.system import add_to_path


def show_interactive_menu():
    """显示交互式菜单（双击运行时）"""
    print_section_header("🔑 SSH Key Manager - 交互式菜单")
    print("\n欢迎使用 SSH 密钥管理器！\n")
    print("这是一个命令行工具，需要配合命令使用。")
    print("\n常用命令：")
    print("  sshm list              - 查看所有密钥")
    print("  sshm add <标签> <邮箱>  - 创建新密钥")
    print("  sshm switch <标签>     - 切换默认密钥")
    print("  sshm --help            - 查看完整帮助")
    print_separator()
    
    manager = SSHKeyManager()
    
    while True:
        print("\n请选择操作：")
        print("  [1] 查看当前所有密钥")
        print("  [2] 查看密钥详情（含公钥）")
        print("  [3] 查看备份列表")
        print("  [4] 添加到环境变量（PATH）")
        print("  [5] 查看完整帮助")
        print("  [Q] 退出")
        
        print("\n请输入选项: ", end='', flush=True)
        
        # 读取输入
        if sys.platform == 'win32':
            try:
                import msvcrt
                choice = msvcrt.getch().decode('utf-8', errors='ignore').upper()
                print(choice)
            except:
                choice = input().upper()
        else:
            choice = input().upper()
        
        print()
        
        # 处理选项
        if choice == '1':
            manager.list_keys(show_content=False)
            wait_for_key()
        elif choice == '2':
            manager.list_keys(show_content=True)
            wait_for_key()
        elif choice == '3':
            manager.list_backups()
            wait_for_key()
        elif choice == '4':
            add_to_path()
            wait_for_key()
        elif choice == '5':
            show_help()
            wait_for_key()
        elif choice == 'Q':
            print("再见！👋")
            break
        else:
            print("⚠️  无效选项，请重新选择")


def show_help():
    """显示帮助信息"""
    print(f"""
SSH Key Manager v{VERSION} - 多账号 Git SSH 密钥管理工具

使用方法:
  sshm <command> [options]

命令列表:
  list              查看当前所有 SSH 密钥
  back              备份所有 SSH 密钥
  backups           列出所有备份
  add               创建新的 SSH 密钥（带标签）
  switch            切换默认 SSH 密钥
  remove            删除 SSH 密钥
  tag               给默认密钥添加标签
  rename            重命名密钥标签
  use               为 Git 仓库配置指定密钥
  info              显示 Git 仓库配置信息
  test              测试 SSH 连接

示例:
  sshm list                                           # 查看所有密钥
  sshm list -a                                        # 查看所有密钥（含公钥）
  sshm back                                           # 备份所有密钥
  sshm backups                                        # 查看备份列表
  sshm add github email@example.com -H github.com     # 创建 github 密钥
  sshm add work work@company.com -t rsa               # 创建 RSA 密钥
  sshm switch github                                  # 切换到 github 密钥
  sshm use github                                     # 为当前仓库配置 github 密钥
  sshm info                                           # 查看当前仓库配置
  sshm test                                           # 测试当前仓库连接
  sshm test --all                                     # 测试所有密钥连接

详细帮助: sshm <command> --help
项目主页: https://github.com/yourusername/SSHManager
""")
