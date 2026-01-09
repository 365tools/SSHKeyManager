#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命令行参数解析器
"""

import argparse

from ..constants import VERSION, SUPPORTED_KEY_TYPES, DEFAULT_KEY_TYPE


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog='sshm',
        description=f'SSH Key Manager v{VERSION} - 多账号 Git SSH 密钥管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  sshm list                                           # 查看所有密钥
  sshm add github email@example.com                   # 创建 github 密钥
  sshm switch github                                  # 切换到 github 密钥
  sshm use github                                     # 为当前仓库配置使用 github 密钥
  sshm use work -p ~/project                          # 为指定仓库配置使用 work 密钥
  sshm info                                           # 查看当前仓库配置信息
  sshm test                                           # 测试当前仓库 SSH 连接
  sshm test github                                    # 测试指定密钥连接
  sshm test --all                                     # 测试所有密钥连接
  sshm update                                         # 更新到最新版本
  sshm update --check                                 # 仅检查是否有更新
  sshm --help                                         # 查看完整帮助
"""
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # list 命令
    list_parser = subparsers.add_parser('list', help='查看当前所有 SSH 密钥')
    list_parser.add_argument('-a', '--all', action='store_true',
                            help='显示公钥内容')
    
    # back 命令
    subparsers.add_parser('back', help='备份所有 SSH 密钥')
    
    # backups 命令
    subparsers.add_parser('backups', help='列出所有备份')
    
    # add 命令
    add_parser = subparsers.add_parser('add', help='创建新的 SSH 密钥')
    add_parser.add_argument('label', help='密钥标签')
    add_parser.add_argument('email', help='邮箱地址')
    add_parser.add_argument('-t', '--type', choices=SUPPORTED_KEY_TYPES,
                          default=DEFAULT_KEY_TYPE, help='密钥类型')
    add_parser.add_argument('-H', '--host', help='主机名（用于 SSH config）')
    
    # switch 命令
    switch_parser = subparsers.add_parser('switch', help='切换默认 SSH 密钥')
    switch_parser.add_argument('label', help='密钥标签')
    switch_parser.add_argument('-t', '--type', choices=SUPPORTED_KEY_TYPES,
                              help='密钥类型（默认自动检测）')
    
    # remove 命令
    remove_parser = subparsers.add_parser('remove', help='删除 SSH 密钥')
    remove_parser.add_argument('label', help='密钥标签')
    remove_parser.add_argument('-t', '--type', choices=SUPPORTED_KEY_TYPES,
                              help='指定删除的密钥类型（默认删除所有类型）')
    
    # tag 命令
    tag_parser = subparsers.add_parser('tag', help='给默认密钥添加标签')
    tag_parser.add_argument('label', help='新标签名')
    tag_parser.add_argument('-t', '--type', choices=SUPPORTED_KEY_TYPES,
                          help='密钥类型（默认自动检测）')
    tag_parser.add_argument('-s', '--switch', action='store_true',
                          help='打标签后立即切换')
    
    # rename 命令
    rename_parser = subparsers.add_parser('rename', help='重命名密钥标签')
    rename_parser.add_argument('old_label', help='旧标签名')
    rename_parser.add_argument('new_label', help='新标签名')
    rename_parser.add_argument('-t', '--type', choices=SUPPORTED_KEY_TYPES,
                             default=DEFAULT_KEY_TYPE, help='密钥类型')
    
    # use 命令
    use_parser = subparsers.add_parser('use', help='为当前 Git 仓库配置指定密钥')
    use_parser.add_argument('label', help='密钥标签')
    use_parser.add_argument('-p', '--path', default='.', 
                          help='Git 仓库路径（默认当前目录）')
    use_parser.add_argument('-y', '--yes', action='store_true',
                          help='跳过确认直接执行')
    
    # info 命令
    info_parser = subparsers.add_parser('info', help='显示 Git 仓库配置信息')
    info_parser.add_argument('-p', '--path', default='.', 
                           help='Git 仓库路径（默认当前目录）')
    
    # test 命令
    test_parser = subparsers.add_parser('test', help='测试 SSH 连接')
    test_parser.add_argument('label', nargs='?', 
                           help='密钥标签（不指定则测试当前仓库配置）')
    test_parser.add_argument('-p', '--path', default='.', 
                           help='Git 仓库路径（默认当前目录）')
    test_parser.add_argument('-a', '--all', action='store_true',
                           help='测试所有密钥')
    
    # update 命令
    update_parser = subparsers.add_parser('update', help='检查并更新到最新版本')
    update_parser.add_argument('--check', action='store_true',
                             help='仅检查更新，不执行更新')
    update_parser.add_argument('--force', action='store_true',
                             help='强制检查，忽略缓存')
    
    return parser
