#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命令处理器 - 路由命令到具体的业务逻辑
"""

import sys
from ..core import SSHKeyManager
from ..utils.updater import UpdateManager


def handle_command(args):
    """处理命令行命令"""
    manager = SSHKeyManager()
    
    try:
        if args.command == 'list':
            manager.list_keys(show_content=args.all)
        
        elif args.command == 'backup':
            manager.backup_keys()
        
        elif args.command == 'backups':
            manager.list_backups()
        
        elif args.command == 'add':
            manager.add_key(args.label, args.email, args.type, args.host)
        
        elif args.command == 'switch':
            manager.switch_key(args.label, args.type)
        
        elif args.command == 'remove':
            manager.remove_key(args.label, args.type)
        
        elif args.command == 'tag':
            manager.tag_key(args.type, args.label, args.switch)
        
        elif args.command == 'rename':
            manager.rename_tag(args.old_label, args.new_label, args.type)
        
        elif args.command == 'use':
            manager.use_key_for_repo(args.label, args.path, args.yes)
        
        elif args.command == 'info':
            manager.show_repo_info(args.path)
        
        elif args.command == 'test':
            manager.test_connection(args.label, args.all, args.path)
        
        elif args.command == 'update':
            handle_update_command(args)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)


def handle_update_command(args):
    """处理更新命令"""
    updater = UpdateManager()
    
    print("=" * 80)
    print("检查更新")
    print("=" * 80)
    print(f"\n当前版本: v{updater.current_version}")
    print(f"平台: {updater.platform}")
    
    # 检查更新
    print("\n正在检查更新...")
    update_info = updater.check_update(force=args.force)
    
    if not update_info:
        print("✅ 已是最新版本！")
        return
    
    # 显示更新信息
    print(f"\n🎉 发现新版本: {update_info['version']}")
    print(f"发布时间: {update_info.get('published_at', 'Unknown')}")
    
    if update_info.get('body'):
        print(f"\n更新内容:")
        # 显示前10行
        lines = update_info['body'].split('\n')[:10]
        for line in lines:
            print(f"  {line}")
        if len(update_info['body'].split('\n')) > 10:
            print("  ...")
    
    # 仅检查模式
    if args.check:
        print(f"\n💡 运行 'sshm update' 更新到最新版本")
        return
    
    # 确认更新
    print()
    try:
        response = input(f"是否更新到 {update_info['version']}? [Y/n] ")
        if response.lower() == 'n':
            print("❌ 已取消更新")
            return
    except KeyboardInterrupt:
        print("\n❌ 已取消更新")
        return
    
    # 执行更新
    print()
    success = updater.download_and_update(update_info['download_url'])
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
