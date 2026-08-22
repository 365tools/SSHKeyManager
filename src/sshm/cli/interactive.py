#!/usr/bin/env python3
"""
交互式菜单 - 双击运行时的用户界面
"""

from rich.prompt import Confirm as RichConfirm
from rich.prompt import Prompt as RichPrompt

from ..constants import DEFAULT_KEY_TYPE, VERSION
from ..core import SSHKeyManager
from ..core.services.net.updater import UpdateManager
from ..i18n import _
from ..language import K
from ..ui.console import print_section_header, print_separator, wait_for_key
from ..ui.output import print


def get_input(prompt: str, required: bool = True) -> str:
    """获取用户输入（基于 rich.prompt，支持必填校验与默认值）"""
    return str(RichPrompt.ask(prompt, default="", show_default=False)).strip() if not required else _ask_required(prompt)


def _ask_required(prompt: str) -> str:
    """必填输入：循环直到非空，空时给出提示"""
    while True:
        value = str(RichPrompt.ask(prompt, default="", show_default=False)).strip()
        if value:
            return value
        print("⚠️  " + _(K.menu.empty_field))


def _ask(prompt: str) -> str:
    """可选输入：允许空值"""
    return str(RichPrompt.ask(prompt, default="", show_default=False)).strip()


def _ask_confirm(prompt: str) -> bool:
    """确认输入（基于 rich.prompt.Confirm）"""
    return bool(RichConfirm.ask(prompt, default=False))


def show_interactive_menu() -> None:
    """显示交互式菜单（双击运行时）"""
    print_section_header(_(K.hdr.interactive))
    print("\n" + _(K.menu.welcome) + "\n")
    print(f"{_(K.lbl.current_version)} v{VERSION}")
    print("\n" + _(K.menu.gui_tip))
    print("  " + _(K.menu.all_ops))
    print_separator()

    manager = SSHKeyManager()

    while True:
        print("\n" + _(K.menu.choose))
        print("  [01] " + _(K.menu.view_all))
        print("  [02] " + _(K.menu.create_new))
        print("  [03] " + _(K.menu.delete_key))
        print("  [04] " + _(K.menu.backup_all))
        print("  [05] " + _(K.menu.view_backups))
        print("  [06] " + _(K.menu.restore))
        print("  [07] " + _(K.menu.save_label))
        print("  [08] " + _(K.menu.rename))
        print("  [09] " + _(K.menu.configure))
        print("  [10] " + _(K.menu.clone))
        print("  [11] " + _(K.menu.author))
        print("  [12] " + _(K.menu.info))
        print("  [13] " + _(K.menu.test))
        print("  [14] " + _(K.menu.update))
        print("  [15] " + _(K.menu.add_path))
        print("  [16] " + _(K.menu.help))
        print("  [Q]  " + _(K.menu.exit))

        # 读取输入
        choice = _ask(_(K.menu.enter_option)).upper()

        print()

        try:
            # 处理选项
            if choice in ["1", "01"]:
                manager.key.list(show_content=False)

            elif choice in ["2", "02"]:
                print(_(K.lbl.create_new_key))
                label = get_input(_(K.prompt.enter_label))
                email = get_input(_(K.prompt.enter_email))
                host = _ask(_(K.prompt.enter_host))
                ktype = _ask(_(K.prompt.enter_type, default=DEFAULT_KEY_TYPE))
                if not ktype:
                    ktype = DEFAULT_KEY_TYPE

                manager.key.create(label, email, ktype, host if host else None)

            elif choice in ["3", "03"]:
                print(_(K.lbl.delete_key))
                manager.key.list(show_content=False)
                print()
                label = get_input(_(K.prompt.enter_delete_label))
                manager.key.remove(label)

            elif choice in ["4", "04"]:
                manager.backup.create()

            elif choice in ["5", "05"]:
                manager.backup.list()

            elif choice in ["6", "06"]:
                print(_(K.hdr.restore))
                manager.backup.restore()

            elif choice in ["7", "07"]:
                print(_(K.lbl.save_as_label))
                label = get_input(_(K.prompt.enter_new_label))
                switch = _ask_confirm(_(K.prompt.switch_after))
                manager.key.label(None, label, switch)

            elif choice in ["8", "08"]:
                print(_(K.lbl.rename_label))
                manager.key.list(show_content=False)
                print()
                old_label = get_input(_(K.prompt.enter_old_label))
                new_label = get_input(_(K.prompt.enter_new_label))
                manager.key.rename(old_label, new_label)

            elif choice in ["9", "09"]:
                print(_(K.lbl.configure_repo_key))
                manager.key.list(show_content=False)
                print()
                label = get_input(_(K.prompt.enter_use_label))
                manager.repo.use(label, ".", False)

            elif choice == "10":
                print(_(K.lbl.clone_repo))
                manager.key.list(show_content=False)
                print()
                label = get_input(_(K.prompt.enter_clone_label))
                url = get_input(_(K.prompt.enter_clone_url))
                manager.repo.clone(label, url, None, False)

            elif choice == "11":
                while True:
                    print(_(K.hdr.author_manage))
                    print("\n" + _(K.menu.choose))
                    print("  [1] " + _(K.menu.view_repo_author))
                    print("  [2] " + _(K.menu.view_saved_list))
                    print("  [3] " + _(K.menu.add_update_author))
                    print("  [4] " + _(K.menu.use_author_set))
                    print("  [5] " + _(K.menu.delete_author))
                    print("  [0] " + _(K.menu.back_main))
                    sub_choice = _ask(_(K.menu.enter_option))
                    if sub_choice == "1":
                        manager.author.show(".")
                    elif sub_choice == "2":
                        manager.author.list()
                    elif sub_choice == "3":
                        print(_(K.lbl.add_update_author))
                        label = get_input(_(K.prompt.enter_author_label))
                        name = _ask(_(K.prompt.enter_author_name))
                        email = _ask(_(K.prompt.enter_author_email))
                        manager.author.add(label, name or None, email or None)
                    elif sub_choice == "4":
                        print(_(K.lbl.use_author_set))
                        manager.author.list()
                        print()
                        label = get_input(_(K.prompt.enter_author_label))
                        scope = "global" if _ask_confirm(_(K.prompt.apply_global)) else "local"
                        manager.author.use(label, ".", scope=scope, skip_confirm=False)
                    elif sub_choice == "5":
                        print(_(K.lbl.delete_author))
                        manager.author.list()
                        print()
                        label = get_input(_(K.prompt.enter_delete_author))
                        manager.author.remove(label)
                    elif sub_choice == "0":
                        break
                    else:
                        print("⚠️  " + _(K.menu.invalid))
                    print()

            elif choice == "12":
                manager.repo.info(".")

            elif choice == "13":
                print(_(K.lbl.test_connection))
                label = _ask(_(K.prompt.enter_test_label))
                if not label:
                    manager.repo.test(None, False, ".")
                elif label.lower() == "all":
                    manager.repo.test(None, True, ".")
                else:
                    manager.repo.test(label, False, ".")

            elif choice == "14":
                updater = UpdateManager()
                info = updater.check_update()
                if info:
                    print(f"\n🎉 {_(K.upd.new_version, version=info['version'])}")
                    print(f"{_(K.upd.release_date)} {info.get('published_at', 'Unknown')}")
                    print(f"\n{_(K.upd.update_notes)}\n{info.get('body', '')}")
                else:
                    print("\n✅ " + _(K.upd.up_to_date))

            elif choice == "15":
                manager.config.add_to_path()

            elif choice == "16":
                show_help()

            elif choice == "Q":
                print(_(K.menu.goodbye) + " 👋")
                break
            else:
                print("⚠️  " + _(K.menu.invalid))

        except KeyboardInterrupt:
            # 用户在输入时按 Ctrl+C：友好退出而非 traceback
            print(f"\n👋 {_(K.menu.goodbye)}")
            break
        except Exception as e:
            print(f"\n❌ {_(K.menu.operation_failed)} {e}")

        if choice != "Q":
            wait_for_key()


def show_help() -> None:
    """显示帮助信息（由 Typer 自动生成，命令清单/示例/参数说明全自动聚合）"""
    from typing import cast

    import click
    from typer.main import get_command

    from .app import app

    # 通过 Click 命令对象渲染帮助文本（避免依赖 typer.testing 测试工具）
    # typer 返回的 Command 带 typer._click 类型桩，与 click 包类型不兼容，
    # 用 cast 收窄为 click.Command 以满足类型检查（运行时为同一对象）。
    cmd = cast(click.Command, get_command(app))
    ctx = click.Context(cmd, info_name="sshm")
    print(cmd.get_help(ctx))
