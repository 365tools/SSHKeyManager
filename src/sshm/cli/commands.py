#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命令处理器 - 路由命令到具体的业务逻辑
"""

import sys
from ..core import SSHKeyManager


def handle_command(args):
    """处理命令行命令"""
    manager = SSHKeyManager()
    
    try:
        if args.command == 'list':
            manager.list_keys(show_content=args.all)
        
        elif args.command == 'back':
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
    
    except KeyboardInterrupt:
        print("\n\n⚠️  操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)
