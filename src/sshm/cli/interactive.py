#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互式菜单 - 双击运行时的用户界面
"""

import sys

from ..constants import VERSION, DEFAULT_KEY_TYPE
from ..core import SSHKeyManager
from ..i18n import _
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
        print("⚠️  " + _("This field cannot be empty, please enter a value"))


def show_interactive_menu():
    """显示交互式菜单（双击运行时）"""
    print_section_header(_("sshm - Interactive Menu"))
    print("\n" + _("Welcome to sshm!") + "\n")
    print(f"{_('Current version:')} v{VERSION}")
    print("\n" + _("This is a command-line tool. On Windows, using sshm_gui.bat is recommended for a better experience."))
    print("  " + _("You can also complete all operations here."))
    print_separator()
    
    manager = SSHKeyManager()
    
    while True:
        print("\n" + _("Please choose an operation:"))
        print("  [01] " + _("View all keys (list)"))
        print("  [02] " + _("Create new key (add)"))
        print("  [03] " + _("Delete key (remove)"))
        print("  [04] " + _("Backup all keys (backup)"))
        print("  [05] " + _("View backup list (backups)"))
        print("  [06] " + _("Restore from backup (restore)"))
        print("  [07] " + _("Save default key as label (tag)"))
        print("  [08] " + _("Rename label (rename)"))
        print("  [09] " + _("Configure repo key (use)"))
        print("  [10] " + _("Manage/view author (author)"))
        print("  [11] " + _("View current config (info)"))
        print("  [12] " + _("Test connection (test)"))
        print("  [13] " + _("Check for updates (update)"))
        print("  [14] " + _("Add to PATH"))
        print("  [15] " + _("View full help"))
        print("  [Q]  " + _("Exit"))
        
        print("\n" + _("Please enter an option: "), end='', flush=True)
        
        # 读取输入
        choice = input().strip().upper()
        
        print()
        
        try:
            # 处理选项
            if choice in ['1', '01']:
                manager.list_keys(show_content=False)
                
            elif choice in ['2', '02']:
                print(_("Create new key"))
                label = get_input(_("Enter key label (e.g. github, work): "))
                email = get_input(_("Enter email address: "))
                host = input(_("Enter host address (e.g. github.com, leave empty to skip): ")).strip()
                ktype = input(_("Enter key type (ed25519/rsa, default {default}): ", default=DEFAULT_KEY_TYPE)).strip()
                if not ktype:
                    ktype = DEFAULT_KEY_TYPE
                
                manager.add_key(label, email, ktype, host if host else None)
                
            elif choice in ['3', '03']:
                print(_("Delete key"))
                manager.list_keys(show_content=False)
                print()
                label = get_input(_("Enter the label to delete: "))
                manager.remove_key(label)
                
            elif choice in ['4', '04']:
                manager.backup_keys()
                
            elif choice in ['5', '05']:
                manager.list_backups()
                
            elif choice in ['6', '06']:
                print(_("Restore from backup"))
                manager.restore_backup()
                
            elif choice in ['7', '07']:
                print(_("Save as label"))
                label = get_input(_("Enter new label: "))
                switch = input(_("Switch immediately after tagging? [y/N]: ")).lower() == 'y'
                manager.tag_key(None, label, switch)
                
            elif choice in ['8', '08']:
                print(_("Rename label"))
                manager.list_keys(show_content=False)
                print()
                old_label = get_input(_("Enter old label: "))
                new_label = get_input(_("Enter new label: "))
                manager.rename_tag(old_label, new_label)
            
            elif choice in ['9', '09']:
                print(_("Configure repo key"))
                manager.list_keys(show_content=False)
                print()
                label = get_input(_("Enter key label to use: "))
                manager.use_key_for_repo(label, '.', False)
            
            elif choice == '10':
                while True:
                    print(_("Author management"))
                    print("\n" + _("Please choose an operation:"))
                    print("  [1] " + _("View current repo author"))
                    print("  [2] " + _("View saved author list"))
                    print("  [3] " + _("Add/update author"))
                    print("  [4] " + _("Use author to set current repo"))
                    print("  [5] " + _("Remove author"))
                    print("  [0] " + _("Back to main menu"))
                    print("\n" + _("Please enter an option: "), end='', flush=True)
                    sub_choice = input().strip()
                    print()
                    if sub_choice == '1':
                        manager.show_repo_author('.')
                    elif sub_choice == '2':
                        manager.list_authors()
                    elif sub_choice == '3':
                        print(_("Add/update author"))
                        label = get_input(_("Enter author label: "))
                        name = input(_("Enter author name (leave empty to skip): ")).strip()
                        email = input(_("Enter author email (leave empty to auto-fill from public key): ")).strip()
                        manager.add_author(label, name or None, email or None)
                    elif sub_choice == '4':
                        print(_("Use author to set current repo"))
                        manager.list_authors()
                        print()
                        label = get_input(_("Enter author label: "))
                        scope = 'global' if get_input(
                            _("Apply to global? [y/N]: "), required=False
                        ).lower() == 'y' else 'local'
                        manager.set_repo_author(label, '.', scope=scope,
                                                skip_confirm=False)
                    elif sub_choice == '5':
                        print(_("Remove author"))
                        manager.list_authors()
                        print()
                        label = get_input(_("Enter the author label to remove: "))
                        manager.remove_author(label)
                    elif sub_choice == '0':
                        break
                    else:
                        print("⚠️  " + _("Invalid option, please try again"))
                    print()
            
            elif choice == '11':
                manager.show_repo_info('.')
            
            elif choice == '12':
                print(_("Test connection"))
                label = input(_("Enter label to test (leave empty for current repo, 'all' for all): ")).strip()
                if not label:
                    manager.test_connection(None, False, '.')
                elif label.lower() == 'all':
                    manager.test_connection(None, True, '.')
                else:
                    manager.test_connection(label, False, '.')
            
            elif choice == '13':
                updater = UpdateManager()
                info = updater.check_update()
                if info:
                    print(f"\n🎉 {_('New version found: {version}', version=info['version'])}")
                    print(f"{_('Release date:')} {info.get('published_at', 'Unknown')}")
                    print(f"\n{_('Update notes:')}\n{info.get('body', '')}")
                else:
                    print("\n✅ " + _("You are up to date!"))
            
            elif choice == '14':
                add_to_path()
                
            elif choice == '15':
                show_help()
                
            elif choice == 'Q':
                print(_("Goodbye!") + " 👋")
                break
            else:
                print("⚠️  " + _("Invalid option, please try again"))
                
        except Exception as e:
            print(f"\n❌ {_('Operation failed:')} {e}")
            
        if choice != 'Q':
            wait_for_key()


def show_help():
    """显示帮助信息"""
    title = _("sshm v{version} - Multi-account Git SSH key management tool", version=VERSION)
    usage = _("Usage:")
    commands = _("Commands:")
    detailed = _("For detailed help:")
    project = _("Project home:")
    print(f"""
{title}

{usage}
  sshm <command> [options]

{commands}
  list              {_('view current all SSH keys')}
  backup            {_('backup all SSH keys')}
  backups           {_('list all backups')}
  restore           {_('restore keys from backup')}
  add               {_('create a new SSH key (with label)')}
  remove            {_('delete an SSH key')}
  tag               {_('save the current default key as a label')}
  rename            {_('rename key label')}
  use               {_('configure a key for a Git repo')}
  author            {_('manage/view/set Git repo author')}
  info              {_('display Git repo config info')}
  test              {_('test SSH connection')}
  update            {_('check for updates')}
  lang              {_('set the output language')}

{_('Examples:')}
  sshm list                                           # view all keys
  sshm backup                                         # backup all keys
  sshm backups                                        # view backup list
  sshm add github email@example.com -H github.com     # create github key
  sshm add work work@company.com -t rsa               # create RSA key
  sshm use github --global                            # set as global default
  sshm use github                                     # use github key for repo
  sshm use github --author                            # configure key and set author
  sshm author                                         # view current repo author
  sshm author list                                    # list saved authors
  sshm author add github -n "Allure Ye" -e x@y.com    # add/update author
  sshm author use github                              # set repo author
  sshm author use github --global                     # set global author
  sshm author remove github                           # remove author
  sshm author unset                                   # clear author config
  sshm info                                           # view repo config
  sshm test                                           # test current repo
  sshm test --all                                     # test all keys

{detailed} sshm <command> --help
{project} https://github.com/eavelabs/sshm
""")
