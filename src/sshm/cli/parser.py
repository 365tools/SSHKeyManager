#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命令行参数解析器
"""

import argparse
import re
import sys

from ..constants import VERSION, SUPPORTED_KEY_TYPES, DEFAULT_KEY_TYPE
from ..i18n import _


class SSHArgumentParser(argparse.ArgumentParser):
    """带友好错误提示的参数解析器

    argparse 默认报错只输出 usage + error，对不熟悉 CLI 的用户不够友好。
    此子类在报错后追加可操作的提示（查看用法、列出可用标签等）。
    子命令会自动继承此类（add_subparsers 默认使用父 parser 的类型）。
    """

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n")

    def exit(self, status=0, message=None):
        if message:
            sys.stderr.write(message)
        if status != 0:
            hint = self._build_error_hint(message or '')
            if hint:
                sys.stderr.write('\n' + hint + '\n')
        sys.exit(status)

    def _build_error_hint(self, message):
        """根据错误消息生成可操作的提示"""
        parts = self.prog.split()
        cmd = ' '.join(parts[1:]) if len(parts) > 1 else None
        hints = []
        if cmd:
            hints.append(_("Tip: run 'sshm {cmd} --help' to view full usage", cmd=cmd))
        else:
            hints.append(_("Tip: run 'sshm --help' to view all commands"))

        # 缺少必填参数时，引导查看已有标签
        m = re.search(r"required:\s*(.+)", message)
        if m:
            missing = [s.strip() for s in m.group(1).split(',')]
            if any(name in missing for name in ('label', 'email',
                                                'old_label', 'new_label')):
                if cmd and cmd.split()[0] == 'author':
                    hints.append(_("Tip: run 'sshm author list' to view existing author labels"))
                else:
                    hints.append(_("Tip: run 'sshm list' to view existing key labels"))
        return "\n".join(hints)


def create_parser() -> SSHArgumentParser:
    """创建命令行参数解析器"""
    desc = _("sshm v{version} - Multi-account Git SSH key management tool",
             version=VERSION)
    examples = _("Examples:")
    epilog = f"""
{examples}:
  sshm list                                           # view all keys
  sshm add github email@example.com                   # create github key
  sshm use github --global                            # set as global default key
  sshm use github                                     # use github key for current repo
  sshm use work -p ~/project                          # use work key for a repo
  sshm use github --author                            # configure key and set author
  sshm author                                         # view current repo author
  sshm author list                                    # list saved authors
  sshm author add github -n "Allure Ye" -e x@y.com    # add/update author
  sshm author use github                              # set current repo author
  sshm author use github --global                     # set global author config
  sshm author remove github                           # remove an author
  sshm author use github -n "Allure Ye" -e x@y.com    # apply with temporary override
  sshm author unset                                   # clear repo-level author config
  sshm author unset --global                          # clear global author config
  sshm list -c                                        # show only the key used by current repo
  sshm info                                           # view current repo config detail
  sshm test                                           # test current repo SSH connection
  sshm test github                                    # test a specific key
  sshm test --all                                     # test all keys
  sshm update                                         # update to latest version
  sshm update --check                                 # check for updates only
  sshm lang zh                                        # switch output language to Chinese
  sshm --help                                         # view full help
"""
    parser = SSHArgumentParser(
        prog='sshm',
        description=desc,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )
    
    subparsers = parser.add_subparsers(dest='command', help=_('available commands'))
    
    # list 命令
    list_parser = subparsers.add_parser('list', help=_('view SSH keys (all or current repo)'))
    list_parser.add_argument('-a', '--all', action='store_true',
                            help=_('show public key contents'))
    list_parser.add_argument('-c', '--current', action='store_true',
                            help=_('show current repo key config (same as info)'))
    list_parser.add_argument('-p', '--path', default='.',
                            help=_('Git repo path (with -c)'))
    
    # backup 命令
    subparsers.add_parser('backup', help=_('backup all SSH keys to archive'))
    
    # backups 命令
    subparsers.add_parser('backups', help=_('list all backup archives'))
    
    # restore 命令
    restore_parser = subparsers.add_parser('restore', help=_('restore keys from a backup'))
    restore_parser.add_argument('backup', nargs='?',
                               help=_('backup name (default: restore latest backup)'))
    restore_parser.add_argument('-t', '--type', choices=SUPPORTED_KEY_TYPES,
                               help=_('only restore keys of the specified type'))
    restore_parser.add_argument('-y', '--yes', action='store_true',
                               help=_('skip confirmation prompts'))
    
    # add 命令
    add_parser = subparsers.add_parser('add', help=_('create a new SSH key'))
    add_parser.add_argument('label', help=_('key label'))
    add_parser.add_argument('email', help=_('email address'))
    add_parser.add_argument('-t', '--type', choices=SUPPORTED_KEY_TYPES,
                          default=DEFAULT_KEY_TYPE, help=_('key type'))
    add_parser.add_argument('-H', '--host', help=_('hostname (for SSH config)'))
    add_parser.add_argument('-n', '--name', help=_('author name (auto-recorded for sshm author)'))
    
    # remove 命令
    remove_parser = subparsers.add_parser('remove', help=_('delete an SSH key'))
    remove_parser.add_argument('label', help=_('key label'))
    remove_parser.add_argument('-t', '--type', choices=SUPPORTED_KEY_TYPES,
                              help=_('specify key type to delete (default: all types)'))
    
    # tag 命令
    tag_parser = subparsers.add_parser('tag', help=_('save the current default key as a label'))
    tag_parser.add_argument('label', help=_('new label'))
    tag_parser.add_argument('-t', '--type', choices=SUPPORTED_KEY_TYPES,
                          help=_('key type (default: auto-detect)'))
    tag_parser.add_argument('-s', '--switch', action='store_true',
                          help=_('switch after tagging'))
    
    # rename 命令
    rename_parser = subparsers.add_parser('rename', help=_('rename a key label'))
    rename_parser.add_argument('old_label', help=_('old label'))
    rename_parser.add_argument('new_label', help=_('new label name'))
    rename_parser.add_argument('-t', '--type', choices=SUPPORTED_KEY_TYPES,
                             default=DEFAULT_KEY_TYPE, help=_('key type'))
    
    # use 命令
    use_parser = subparsers.add_parser('use', help=_('configure the specified key for a Git repo'))
    use_parser.add_argument('label', help=_('key label'))
    use_parser.add_argument('-p', '--path', default='.', 
                          help=_('Git repo path (default: current directory)'))
    use_parser.add_argument('-g', '--global', dest='global_', action='store_true',
                          help=_('configure as global default key'))
    use_parser.add_argument('-y', '--yes', action='store_true',
                          help=_('skip confirmation and execute directly'))
    use_parser.add_argument('-a', '--author', action='store_true',
                          help=_('configure the key and set author at the same time'))

    # author 命令（一级子命令体系）
    author_parser = subparsers.add_parser('author', help=_('manage/view/set Git repo author'))
    author_parser.add_argument('-p', '--path', default='.',
                              help=_('Git repo path (default: current directory, used for view/clear)'))
    author_sub = author_parser.add_subparsers(dest='action', metavar='<subcommand>',
                                              help=_('subcommands: list/add/remove/use/unset'))

    # author list - 列出所有已保存作者
    author_sub.add_parser('list', help=_('list all saved authors'))

    # author add <标签> [-n 姓名] [-e 邮箱]
    add_author_parser = author_sub.add_parser('add', help=_('add/update an author to the list'))
    add_author_parser.add_argument('label', help=_('author label'))
    add_author_parser.add_argument('-n', '--name', help=_('author name'))
    add_author_parser.add_argument('-e', '--email', help=_('author email (auto-filled from public key comment if omitted)'))

    # author remove <标签> [-y]
    remove_author_parser = author_sub.add_parser('remove', help=_('remove an author from the list'))
    remove_author_parser.add_argument('label', help=_('author label'))
    remove_author_parser.add_argument('-y', '--yes', action='store_true',
                                     help=_('skip confirmation and execute directly'))

    # author use <标签> [-p 路径] [-n 姓名] [-e 邮箱] [--global] [-y]
    use_author_parser = author_sub.add_parser('use', help=_('use author info to set repo/global'))
    use_author_parser.add_argument('label', help=_('author label'))
    use_author_parser.add_argument('-p', '--path', default='.',
                                  help=_('Git repo path (default: current directory)'))
    use_author_parser.add_argument('-n', '--name', help=_('temporarily override author name'))
    use_author_parser.add_argument('-e', '--email', help=_('temporarily override author email'))
    use_author_parser.add_argument('-g', '--global', dest='global_', action='store_true',
                                  help=_('set as global author config'))
    use_author_parser.add_argument('-y', '--yes', action='store_true',
                                  help=_('skip confirmation and execute directly'))

    # author unset [-p 路径] [--global]
    unset_author_parser = author_sub.add_parser('unset', help=_('clear author config (fall back to parent)'))
    unset_author_parser.add_argument('-p', '--path', default='.',
                                    help=_('Git repo path (default: current directory)'))
    unset_author_parser.add_argument('-g', '--global', dest='global_', action='store_true',
                                    help=_('clear global author config'))
    
    # info 命令
    info_parser = subparsers.add_parser('info', help=_('display Git repo config info'))
    info_parser.add_argument('-p', '--path', default='.', 
                           help=_('Git repo path (default: current directory)'))
    
    # test 命令
    test_parser = subparsers.add_parser('test', help=_('test SSH connection'))
    test_parser.add_argument('label', nargs='?', 
                           help=_('key label (omit to test current repo)'))
    test_parser.add_argument('-p', '--path', default='.', 
                           help=_('Git repo path'))
    test_parser.add_argument('-a', '--all', action='store_true',
                           help=_('test all keys'))
    
    # update 命令
    update_parser = subparsers.add_parser('update', help=_('check and update to the latest version'))
    update_parser.add_argument('--check', action='store_true',
                             help=_('check for updates only, without updating'))
    update_parser.add_argument('--force', action='store_true',
                             help=_('force check, ignore cache'))

    # lang 命令（切换输出语言）
    lang_parser = subparsers.add_parser('lang', help=_('set the output language'))
    lang_parser.add_argument('lang', nargs='?',
                            help=_('en or zh (omitted: show current language)'))
    
    return parser
