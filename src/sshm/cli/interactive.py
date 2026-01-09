#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互式菜单 - 双击运行时的用户界面
"""

import sys

from ..constants import VERSION, DEFAULT_KEY_TYPE
from ..core import SSHKeyManager
from ..utils import print_separator, print_section_header, wait_for_key
from ..utils.system import add_to_path
from ..utils.updater import UpdateManager


def get_input(prompt: str, required: bool = True) -> str:
    """获取用户输入"""
    while True:
        value = input(prompt).strip()
        if value:
            return value
        if not required:
            return ""
        print("⚠️  此处不能为空，请输入")


def show_interactive_menu():
    """显示交互式菜单（双击运行时）"""
    print_section_header("🔑 SSH Key Manager - 交互式菜单")
    print("\n欢迎使用 SSH 密钥管理器！\n")
    print(f"当前版本: v{VERSION}")
    print("\n提示: 这是一个命令行工具。在 Windows 上推荐使用 sshm_gui.bat 获得更好的体验。")
    print("      你也可以直接在此界面完成所有操作。")
    print_separator()
    
    manager = SSHKeyManager()
    
    while True:
        print("\n请选择操作：")
        print("  [1] 查看所有密钥 (list)")
        print("  [2] 创建新密钥 (add)")
        print("  [3] 切换默认密钥 (switch)")
        print("  [4] 删除密钥 (remove)")
        print("  [5] 备份所有密钥 (backup)")
        print("  [6] 查看备份列表 (backups)")
        print("  [7] 将默认密钥另存为标签 (tag)")
        print("  [8] 重命名标签 (rename)")
        print("  [9] 配置仓库密钥 (use)")
        print("  [10] 查看当前配置 (info)")
        print("  [11] 测试连接 (test)")
        print("  [12] 检查更新 (update)")
        print("  [13] 添加到环境变量 (PATH)")
        print("  [14] 查看完整帮助")
        print("  [Q] 退出")
        
        print("\n请输入选项: ", end='', flush=True)
        
        # 读取输入
        choice = input().strip().upper()
        
        print()
        
        try:
            # 处理选项
            if choice == '1':
                manager.list_keys(show_content=False)
                
            elif choice == '2':
                print("--- 创建新密钥 ---")
                label = get_input("请输入密钥标签 (如: github, work): ")
                email = get_input("请输入邮箱地址: ")
                host = input("请输入主机地址 (如: github.com，留空跳过): ").strip()
                ktype = input(f"请输入密钥类型 (ed25519/rsa, 默认 {DEFAULT_KEY_TYPE}): ").strip()
                if not ktype:
                    ktype = DEFAULT_KEY_TYPE
                
                manager.add_key(label, email, ktype, host if host else None)
                
            elif choice == '3':
                print("--- 切换默认密钥 ---")
                manager.list_keys(show_content=False)
                print()
                label = get_input("请输入要切换到的标签: ")
                manager.switch_key(label)
                
            elif choice == '4':
                print("--- 删除密钥 ---")
                manager.list_keys(show_content=False)
                print()
                label = get_input("请输入要删除的标签: ")
                manager.remove_key(label)
                
            elif choice == '5':
                manager.backup_keys()
                
            elif choice == '6':
                manager.list_backups()
                
            elif choice == '7':
                print("--- 另存为标签 ---")
                label = get_input("请输入新标签名: ")
                switch = input("添加后是否立即切换? [y/N]: ").lower() == 'y'
                manager.tag_key(None, label, switch)
                
            elif choice == '8':
                print("--- 重命名标签 ---")
                manager.list_keys(show_content=False)
                print()
                old_label = get_input("请输入旧标签名: ")
                new_label = get_input("请输入新标签名: ")
                manager.rename_tag(old_label, new_label)
            
            elif choice == '9':
                print("--- 配置仓库密钥 ---")
                manager.list_keys(show_content=False)
                print()
                label = get_input("请输入要使用的密钥标签: ")
                manager.use_key_for_repo(label, '.', False)
            
            elif choice == '10':
                manager.show_repo_info('.')
            
            elif choice == '11':
                print("--- 测试连接 ---")
                label = input("请输入要测试的标签 (留空测试当前仓库, 'all' 测试所有): ").strip()
                if not label:
                    manager.test_connection(None, False, '.')
                elif label.lower() == 'all':
                    manager.test_connection(None, True, '.')
                else:
                    manager.test_connection(label, False, '.')
            
            elif choice == '12':
                updater = UpdateManager()
                info = updater.check_update()
                if info:
                    print(f"\n🎉 发现新版本: {info['version']}")
                    print(f"发布时间: {info.get('published_at', 'Unknown')}")
                    print(f"\n更新内容:\n{info.get('body', '')}")
                else:
                    print("\n✅ 已是最新版本")
            
            elif choice == '13':
                add_to_path()
                
            elif choice == '14':
                show_help()
                
            elif choice == 'Q':
                print("再见！👋")
                break
            else:
                print("⚠️  无效选项，请重新选择")
                
        except Exception as e:
            print(f"\n❌ 操作失败: {e}")
            
        if choice != 'Q':
            wait_for_key()


def show_help():
    """显示帮助信息"""
    print(f"""
SSH Key Manager v{VERSION} - 多账号 Git SSH 密钥管理工具

使用方法:
  sshm <command> [options]

命令列表:
  list              查看当前所有 SSH 密钥
  backup            备份所有 SSH 密钥 
  backups           列出所有备份
  add               创建新的 SSH 密钥（带标签）
  switch            切换默认 SSH 密钥
  remove            删除 SSH 密钥
  tag               将当前默认密钥另存为指定标签
  rename            重命名密钥标签
  use               为 Git 仓库配置指定密钥
  info              显示 Git 仓库配置信息
  test              测试 SSH 连接
  update            检查更新

示例:
  sshm list                                           # 查看所有密钥
  sshm backup                                         # 备份所有密钥
  sshm backups                                        # 查看备份列表
  sshm add github email@example.com -H github.com     # 创建 github 密钥
  sshm add work work@company.com -t rsa               # 创建 RSA 密钥
  sshm switch github                                  # 切换到 github 密钥
  sshm use github                                     # 为当前仓库配置 github 密钥
  sshm info                                           # 查看当前仓库配置
  sshm test                                           # 测试当前仓库连接
  sshm test --all                                     # 测试所有密钥连接

详细帮助: sshm <command> --help
项目主页: https://github.com/365tools/SSHKeyManager
""")
