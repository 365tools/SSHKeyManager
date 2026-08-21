#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命令编排层 - 按命令分组，每个模块只负责一组相关命令的编排。

- keys.py   KeyCommands：密钥管理命令（list/add/remove/switch/tag/rename）
- repo.py   RepoCommands：Git 仓库命令（use/clone/info/test）
- author.py AuthorCommands：作者命令（author 系列 + auto-author）
- system.py SystemCommands：系统命令（lang）

命令类持有门面 SSHKeyManager 的引用（self.m），通过门面访问底层服务与错误上报，
自身只负责"把用户意图翻译成对服务的编排调用 + 渲染输出"。
"""

from .author import AuthorCommands
from .history import HistoryCommands
from .keys import KeyCommands
from .repo import RepoCommands
from .system import SystemCommands

__all__ = [
    "AuthorCommands",
    "HistoryCommands",
    "KeyCommands",
    "RepoCommands",
    "SystemCommands",
]
