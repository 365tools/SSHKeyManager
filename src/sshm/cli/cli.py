#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Typer CLI 应用 - sshm 命令行入口

基于 Typer 框架声明式定义命令，自动生成帮助/参数校验/补全。
命令集中在此文件中，业务逻辑委托给 SSHKeyManager。
"""

import typer

from ..constants import VERSION, DEFAULT_KEY_TYPE
from ..core import SSHKeyManager
from ..i18n import _
from ..language import K

app = typer.Typer(
    name="sshm",
    help=_(K.cmd.app_help),
    add_completion=True,
    no_args_is_help=True,
    rich_markup_mode="rich",
)


# ===========================================================================
# 通用辅助
# ===========================================================================

def _manager() -> SSHKeyManager:
    return SSHKeyManager()


def _fail_exit(manager: SSHKeyManager) -> None:
    """业务层报错时以非零码退出"""
    if getattr(manager, '_had_error', False):
        raise typer.Exit(code=1)


# ===========================================================================
# 密钥管理命令
# ===========================================================================

@app.command("list", help=_(K.cmd.list))
def cmd_list(
    all: bool = typer.Option(False, "--all", "-a", help=_("opt.all")),
    current: bool = typer.Option(False, "--current", "-c", help=_("opt.current")),
    path: str = typer.Option(".", "--path", "-p", help=_("opt.path_with_c")),
):
    manager = _manager()
    if current:
        manager.list_keys(show_content=all, repo_path=path, current_only=True)
    else:
        manager.list_keys(show_content=all, repo_path=path)
    _fail_exit(manager)


@app.command("backup", help=_(K.cmd.backup))
def cmd_backup() -> None:
    manager = _manager()
    manager.backup_keys()
    _fail_exit(manager)


@app.command("backups", help=_(K.cmd.backups))
def cmd_backups() -> None:
    manager = _manager()
    manager.list_backups()
    _fail_exit(manager)


@app.command("restore", help=_(K.cmd.restore))
def cmd_restore(
    backup: str = typer.Argument(None, help=_("opt.backup_name")),
    type: str = typer.Option(None, "--type", "-t", help=_("opt.type_only")),
    yes: bool = typer.Option(False, "--yes", "-y", help=_("opt.yes_prompts")),
):
    manager = _manager()
    manager.restore_backup(backup, type, yes)
    _fail_exit(manager)


@app.command("add", help=_(K.cmd.add))
def cmd_add(
    label: str = typer.Argument(..., help=_("opt.label")),
    email: str = typer.Argument(..., help=_("opt.email")),
    type: str = typer.Option(DEFAULT_KEY_TYPE, "--type", "-t", help=_("opt.type")),
    host: str = typer.Option(None, "--host", "-H", help=_("opt.host")),
    name: str = typer.Option(None, "--name", "-n", help=_("opt.name")),
):
    manager = _manager()
    manager.add_key(label, email, type, host, name)
    _fail_exit(manager)


@app.command("remove", help=_(K.cmd.remove))
def cmd_remove(
    label: str = typer.Argument(..., help=_("opt.label")),
    type: str = typer.Option(None, "--type", "-t", help=_("opt.type_all")),
):
    manager = _manager()
    manager.remove_key(label, type)
    _fail_exit(manager)


@app.command("tag", help=_(K.cmd.tag))
def cmd_tag(
    label: str = typer.Argument(..., help=_("opt.new_label")),
    type: str = typer.Option(None, "--type", "-t", help=_("opt.type_auto")),
    switch: bool = typer.Option(False, "--switch", "-s", help=_("opt.switch_after")),
):
    manager = _manager()
    manager.tag_key(type, label, switch)
    _fail_exit(manager)


@app.command("rename", help=_(K.cmd.rename))
def cmd_rename(
    old_label: str = typer.Argument(..., help=_("opt.old_label")),
    new_label: str = typer.Argument(..., help=_("opt.new_label_name")),
    type: str = typer.Option(DEFAULT_KEY_TYPE, "--type", "-t", help=_("opt.type")),
):
    manager = _manager()
    manager.rename_tag(old_label, new_label, type)
    _fail_exit(manager)


# ===========================================================================
# Git 仓库命令
# ===========================================================================

@app.command("use", help=_(K.cmd.use))
def cmd_use(
    label: str = typer.Argument(..., help=_("opt.label")),
    path: str = typer.Option(".", "--path", "-p", help=_("opt.path")),
    global_: bool = typer.Option(False, "--global", "-g", help=_("opt.global")),
    yes: bool = typer.Option(False, "--yes", "-y", help=_("opt.yes")),
    author: bool = typer.Option(False, "--author", "-a", help=_("opt.author_same")),
):
    manager = _manager()
    if global_:
        manager.switch_key(label)
        if author:
            print()
            manager.set_repo_author(label, path, scope="global", skip_confirm=yes)
    else:
        manager.use_key_for_repo(label, path, yes)
        if author:
            print()
            manager.set_repo_author(label, path, skip_confirm=yes)
    _fail_exit(manager)


@app.command("clone", help=_(K.cmd.clone))
def cmd_clone(
    label: str = typer.Argument(..., help=_("opt.clone_label")),
    url: str = typer.Argument(..., help=_("opt.url")),
    target: str = typer.Argument(None, help=_("opt.target")),
    yes: bool = typer.Option(False, "--yes", "-y", help=_("opt.yes")),
):
    manager = _manager()
    manager.clone_with_label(label, url, target, yes)
    _fail_exit(manager)


@app.command("info", help=_(K.cmd.info))
def cmd_info(
    path: str = typer.Option(".", "--path", "-p", help=_("opt.path")),
):
    manager = _manager()
    manager.show_repo_info(path)
    _fail_exit(manager)


@app.command("test", help=_(K.cmd.test))
def cmd_test(
    label: str = typer.Argument(None, help=_("opt.test_label")),
    path: str = typer.Option(".", "--path", "-p", help=_("opt.path")),
    all: bool = typer.Option(False, "--all", "-a", help=_("opt.test_all")),
):
    manager = _manager()
    manager.test_connection(label, all, path)
    _fail_exit(manager)


# ===========================================================================
# 作者命令
# ===========================================================================

@app.command("auto-author", help=_(K.cmd.auto_author))
def cmd_auto_author(
    on: str = typer.Argument(None, help=_("opt.on_off")),
    show: bool = typer.Option(False, "--show", "-s", help=_("opt.show_status")),
):
    manager = _manager()
    if show or on is None:
        manager.show_auto_author()
    else:
        manager.set_auto_author(on == "on")
    _fail_exit(manager)


# ---------------------------------------------------------------------------
# author 子命令（嵌套 Typer）
# ---------------------------------------------------------------------------

author_app = typer.Typer(
    name="author",
    help=_(K.cmd.author),
    no_args_is_help=False,
    rich_markup_mode="rich",
)


@author_app.command("list", help=_(K.cmd.author_list))
def author_list() -> None:
    manager = _manager()
    manager.list_authors()
    _fail_exit(manager)


@author_app.command("add", help=_(K.cmd.author_add))
def author_add(
    label: str = typer.Argument(..., help=_("opt.author_label")),
    name: str = typer.Option(None, "--name", "-n", help=_("opt.author_name")),
    email: str = typer.Option(None, "--email", "-e", help=_("opt.author_email")),
):
    manager = _manager()
    manager.add_author(label, name, email)
    _fail_exit(manager)


@author_app.command("remove", help=_(K.cmd.author_remove))
def author_remove(
    label: str = typer.Argument(..., help=_("opt.author_label")),
    yes: bool = typer.Option(False, "--yes", "-y", help=_("opt.yes")),
):
    manager = _manager()
    manager.remove_author(label, yes)
    _fail_exit(manager)


@author_app.command("use", help=_(K.cmd.author_use))
def author_use(
    label: str = typer.Argument(..., help=_("opt.author_label")),
    path: str = typer.Option(".", "--path", "-p", help=_("opt.path")),
    name: str = typer.Option(None, "--name", "-n", help=_("opt.override_name")),
    email: str = typer.Option(None, "--email", "-e", help=_("opt.override_email")),
    global_: bool = typer.Option(False, "--global", "-g", help=_("opt.global_author")),
    yes: bool = typer.Option(False, "--yes", "-y", help=_("opt.yes")),
):
    manager = _manager()
    scope = "global" if global_ else "local"
    manager.set_repo_author(label, path, name, email, scope, yes)
    _fail_exit(manager)


@author_app.command("unset", help=_(K.cmd.author_unset))
def author_unset(
    path: str = typer.Option(".", "--path", "-p", help=_("opt.path")),
    global_: bool = typer.Option(False, "--global", "-g", help=_("opt.clear_global")),
):
    manager = _manager()
    scope = "global" if global_ else "local"
    manager.unset_repo_author(path, scope)
    _fail_exit(manager)


@author_app.command("fix", help=_(K.cmd.author_fix))
def author_fix(
    path: str = typer.Option(".", "--path", "-p", help=_("opt.path")),
    old_name: str = typer.Option(None, "--old-name", help=_("opt.old_name")),
    new_name: str = typer.Option(None, "--new-name", help=_("opt.new_name")),
    old_email: str = typer.Option(None, "--old-email", help=_("opt.old_email")),
    new_email: str = typer.Option(None, "--new-email", help=_("opt.new_email")),
    yes: bool = typer.Option(False, "--yes", "-y", help=_("opt.yes")),
):
    manager = _manager()
    manager.fix_author(path, old_name, new_name, old_email, new_email, yes)
    _fail_exit(manager)


app.add_typer(author_app)


# ===========================================================================
# 系统命令
# ===========================================================================

@app.command("lang", help=_(K.cmd.lang))
def cmd_lang(
    lang: str = typer.Argument(None, help=_("opt.lang_value")),
):
    manager = _manager()
    if not lang:
        from ..i18n import get_lang
        cur = get_lang()
        name = "Chinese" if cur == "zh" else "English"
        print(_("lbl.current_language") + f" {name} ({cur})")
        print(_("lbl.available_languages"))
        return
    lang = lang.lower()
    if lang not in ("en", "zh"):
        print(f"❌ {_('misc.error')}: {lang} - {_('lbl.available_languages')}")
        raise typer.Exit(code=1)
    manager.set_language(lang)
    if lang == "zh":
        print(_("msg.lang_zh"))
    else:
        print(_("msg.lang_en"))
    _fail_exit(manager)


@app.command("update", help=_(K.cmd.update))
def cmd_update(
    check: bool = typer.Option(False, "--check", help=_("opt.check_only")),
    force: bool = typer.Option(False, "--force", help=_("opt.force_check")),
):
    """检查并更新到最新版本（编排委托 SystemCommands）"""
    manager = _manager()
    code = manager.update(check=check, force=force)
    if code is not None:
        raise typer.Exit(code=code)


# ===========================================================================
# 入口
# ===========================================================================

def _version_callback(value: bool) -> None:
    if value:
        print(f"sshm v{VERSION}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-v",
        help=_(K.cmd.version),
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """sshm - Multi-account Git SSH key management tool"""
    # 无任何子命令时由 Typer 自动打印帮助（no_args_is_help=True）
    pass
