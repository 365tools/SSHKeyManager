#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互式菜单 - 双击运行时的用户界面
"""

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
        print("⚠️  " + _("menu.empty_field"))


def show_interactive_menu() -> None:
    """显示交互式菜单（双击运行时）"""
    print_section_header(_("hdr.interactive"))
    print("\n" + _("menu.welcome") + "\n")
    print(f"{_('lbl.current_version')} v{VERSION}")
    print("\n" + _("menu.gui_tip"))
    print("  " + _("menu.all_ops"))
    print_separator()

    manager = SSHKeyManager()

    while True:
        print("\n" + _("menu.choose"))
        print("  [01] " + _("menu.view_all"))
        print("  [02] " + _("menu.create_new"))
        print("  [03] " + _("menu.delete_key"))
        print("  [04] " + _("menu.backup_all"))
        print("  [05] " + _("menu.view_backups"))
        print("  [06] " + _("menu.restore"))
        print("  [07] " + _("menu.save_label"))
        print("  [08] " + _("menu.rename"))
        print("  [09] " + _("menu.configure"))
        print("  [10] " + _("menu.clone"))
        print("  [11] " + _("menu.author"))
        print("  [12] " + _("menu.info"))
        print("  [13] " + _("menu.test"))
        print("  [14] " + _("menu.update"))
        print("  [15] " + _("menu.add_path"))
        print("  [16] " + _("menu.help"))
        print("  [Q]  " + _("menu.exit"))

        print("\n" + _("menu.enter_option"), end='', flush=True)

        # 读取输入
        choice = input().strip().upper()

        print()

        try:
            # 处理选项
            if choice in ['1', '01']:
                manager.list_keys(show_content=False)

            elif choice in ['2', '02']:
                print(_("lbl.create_new_key"))
                label = get_input(_("prompt.enter_label"))
                email = get_input(_("prompt.enter_email"))
                host = input(_("prompt.enter_host")).strip()
                ktype = input(_("prompt.enter_type", default=DEFAULT_KEY_TYPE)).strip()
                if not ktype:
                    ktype = DEFAULT_KEY_TYPE

                manager.add_key(label, email, ktype, host if host else None)

            elif choice in ['3', '03']:
                print(_("lbl.delete_key"))
                manager.list_keys(show_content=False)
                print()
                label = get_input(_("prompt.enter_delete_label"))
                manager.remove_key(label)

            elif choice in ['4', '04']:
                manager.backup_keys()

            elif choice in ['5', '05']:
                manager.list_backups()

            elif choice in ['6', '06']:
                print(_("hdr.restore"))
                manager.restore_backup()

            elif choice in ['7', '07']:
                print(_("lbl.save_as_label"))
                label = get_input(_("prompt.enter_new_label"))
                switch = input(_("prompt.switch_after")).lower() == 'y'
                manager.tag_key(None, label, switch)

            elif choice in ['8', '08']:
                print(_("lbl.rename_label"))
                manager.list_keys(show_content=False)
                print()
                old_label = get_input(_("prompt.enter_old_label"))
                new_label = get_input(_("prompt.enter_new_label"))
                manager.rename_tag(old_label, new_label)

            elif choice in ['9', '09']:
                print(_("lbl.configure_repo_key"))
                manager.list_keys(show_content=False)
                print()
                label = get_input(_("prompt.enter_use_label"))
                manager.use_key_for_repo(label, '.', False)

            elif choice == '10':
                print(_("lbl.clone_repo"))
                manager.list_keys(show_content=False)
                print()
                label = get_input(_("prompt.enter_clone_label"))
                url = get_input(_("prompt.enter_clone_url"))
                manager.clone_with_label(label, url, None, False)

            elif choice == '11':
                while True:
                    print(_("hdr.author_manage"))
                    print("\n" + _("menu.choose"))
                    print("  [1] " + _("menu.view_repo_author"))
                    print("  [2] " + _("menu.view_saved_list"))
                    print("  [3] " + _("menu.add_update_author"))
                    print("  [4] " + _("menu.use_author_set"))
                    print("  [5] " + _("menu.remove_author"))
                    print("  [0] " + _("menu.back_main"))
                    print("\n" + _("menu.enter_option"), end='', flush=True)
                    sub_choice = input().strip()
                    print()
                    if sub_choice == '1':
                        manager.show_repo_author('.')
                    elif sub_choice == '2':
                        manager.list_authors()
                    elif sub_choice == '3':
                        print(_("lbl.add_update_author"))
                        label = get_input(_("prompt.enter_author_label"))
                        name = input(_("prompt.enter_author_name")).strip()
                        email = input(_("prompt.enter_author_email")).strip()
                        manager.add_author(label, name or None, email or None)
                    elif sub_choice == '4':
                        print(_("lbl.use_author_set"))
                        manager.list_authors()
                        print()
                        label = get_input(_("prompt.enter_author_label"))
                        scope = 'global' if get_input(
                            _("prompt.apply_global"), required=False
                        ).lower() == 'y' else 'local'
                        manager.set_repo_author(label, '.', scope=scope,
                                                skip_confirm=False)
                    elif sub_choice == '5':
                        print(_("lbl.remove_author"))
                        manager.list_authors()
                        print()
                        label = get_input(_("prompt.enter_remove_author"))
                        manager.remove_author(label)
                    elif sub_choice == '0':
                        break
                    else:
                        print("⚠️  " + _("menu.invalid"))
                    print()

            elif choice == '12':
                manager.show_repo_info('.')

            elif choice == '13':
                print(_("lbl.test_connection"))
                label = input(_("prompt.enter_test_label")).strip()
                if not label:
                    manager.test_connection(None, False, '.')
                elif label.lower() == 'all':
                    manager.test_connection(None, True, '.')
                else:
                    manager.test_connection(label, False, '.')

            elif choice == '14':
                updater = UpdateManager()
                info = updater.check_update()
                if info:
                    print(f"\n🎉 {_('upd.new_version', version=info['version'])}")
                    print(f"{_('upd.release_date')} {info.get('published_at', 'Unknown')}")
                    print(f"\n{_('upd.update_notes')}\n{info.get('body', '')}")
                else:
                    print("\n✅ " + _("upd.up_to_date"))

            elif choice == '15':
                add_to_path()

            elif choice == '16':
                show_help()

            elif choice == 'Q':
                print(_("menu.goodbye") + " 👋")
                break
            else:
                print("⚠️  " + _("menu.invalid"))

        except KeyboardInterrupt:
            # 用户在输入时按 Ctrl+C：友好退出而非 traceback
            print(f"\n👋 {_('menu.goodbye')}")
            break
        except Exception as e:
            print(f"\n❌ {_('menu.operation_failed')} {e}")

        if choice != 'Q':
            wait_for_key()


def show_help() -> None:
    """显示帮助信息（由 Typer 自动生成，命令清单/示例/参数说明全自动聚合）"""
    import click
    from typer.main import get_command

    from .cli import app
    # 通过 Click 命令对象渲染帮助文本（避免依赖 typer.testing 测试工具）
    cmd = get_command(app)
    ctx = click.Context(cmd, info_name='sshm')
    print(cmd.get_help(ctx))
