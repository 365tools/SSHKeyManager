#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命令处理器 - 路由命令到具体的业务逻辑
"""

import os
import sys
from ..core import SSHKeyManager
from ..i18n import _, get_lang
from ..utils.updater import UpdateManager


def handle_command(args):
    """处理命令行命令"""
    manager = SSHKeyManager()
    
    try:
        if args.command == 'list':
            if getattr(args, 'current', False):
                manager.list_keys(show_content=args.all,
                                  repo_path=args.path, current_only=True)
            else:
                manager.list_keys(show_content=args.all, repo_path=args.path)
        
        elif args.command == 'backup':
            manager.backup_keys()
        
        elif args.command == 'backups':
            manager.list_backups()
        
        elif args.command == 'restore':
            manager.restore_backup(args.backup, args.type, args.yes)
        
        elif args.command == 'add':
            manager.add_key(args.label, args.email, args.type, args.host, args.name)
        
        elif args.command == 'remove':
            manager.remove_key(args.label, args.type)
        
        elif args.command == 'tag':
            manager.tag_key(args.type, args.label, args.switch)
        
        elif args.command == 'rename':
            manager.rename_tag(args.old_label, args.new_label, args.type)
        
        elif args.command == 'use':
            if args.global_:
                manager.switch_key(args.label)
                if args.author:
                    print()
                    manager.set_repo_author(args.label, '.', scope='global',
                                            skip_confirm=args.yes)
            else:
                manager.use_key_for_repo(args.label, args.path, args.yes)
                if args.author:
                    print()
                    manager.set_repo_author(args.label, args.path, skip_confirm=args.yes)
        
        elif args.command == 'author':
            action = getattr(args, 'action', None)
            if action == 'list':
                manager.list_authors()
            elif action == 'add':
                manager.add_author(args.label, args.name, args.email)
            elif action == 'remove':
                manager.remove_author(args.label, args.yes)
            elif action == 'use':
                scope = 'global' if args.global_ else 'local'
                manager.set_repo_author(
                    args.label, args.path, args.name, args.email,
                    scope, args.yes
                )
            elif action == 'unset':
                scope = 'global' if args.global_ else 'local'
                manager.unset_repo_author(args.path, scope)
            else:
                manager.show_repo_author(args.path)
        
        elif args.command == 'info':
            manager.show_repo_info(args.path)
        
        elif args.command == 'test':
            manager.test_connection(args.label, args.all, args.path)
        
        elif args.command == 'lang':
            handle_lang_command(manager, args)
        
        elif args.command == 'update':
            handle_update_command(args)
        
        # 业务失败（manager 打印 ❌/⚠️ 并置 _had_error）→ 非零退出码
        if manager._had_error:
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  " + _("operation cancelled"))
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ {_('error')}: {e}")
        if os.environ.get('SSHM_DEBUG'):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def handle_lang_command(manager, args):
    """处理语言切换命令"""
    if not getattr(args, 'lang', None):
        # 显示当前语言
        cur = get_lang()
        name = 'Chinese' if cur == 'zh' else 'English'
        print(_("Current language:") + f" {name} ({cur})")
        print(_("Available languages: en (English), zh (Chinese)"))
        return

    lang = args.lang.lower()
    if lang not in ('en', 'zh'):
        print(f"❌ {_('error')}: {lang} - {_('Available languages: en (English), zh (Chinese)')}")
        sys.exit(1)

    manager.set_language(lang)
    if lang == 'zh':
        print(_("Language set to Chinese"))
    else:
        print(_("Language set to English"))


def handle_update_command(args):
    """处理更新命令"""
    updater = UpdateManager()
    
    print("=" * 80)
    print(_("Check for Updates"))
    print("=" * 80)
    print(f"\n{_('Current version:')} v{updater.current_version}")
    print(f"{_('Platform:')} {updater.platform}")
    
    # 检查更新
    print("\n" + _("Checking for updates..."))
    update_info = updater.check_update(force=args.force)
    
    if not update_info:
        print("✅ " + _("You are up to date!"))
        return
    
    # 显示更新信息
    print(f"\n🎉 {_('New version found: {version}', version=update_info['version'])}")
    print(f"{_('Release date:')} {update_info.get('published_at', 'Unknown')}")
    
    if update_info.get('body'):
        print(f"\n{_('Update notes:')}")
        # 显示前10行
        lines = update_info['body'].split('\n')[:10]
        for line in lines:
            print(f"  {line}")
        if len(update_info['body'].split('\n')) > 10:
            print("  ...")
    
    # 仅检查模式
    if args.check:
        hint = _("Run 'sshm update' to update to the latest version")
        print(f"\n💡 {hint}")
        return
    
    # 确认更新
    print()
    try:
        response = input(_("Update to {version}? [Y/n] ", version=update_info['version']))
        if response.lower() == 'n':
            print("❌ " + _("Update cancelled"))
            return
    except KeyboardInterrupt:
        print("\n❌ " + _("Update cancelled"))
        return
    
    # 执行更新
    print()
    success = updater.download_and_update(update_info['download_url'])
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
