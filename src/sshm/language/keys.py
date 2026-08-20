#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
类型安全的翻译 key 常量 - 新增代码建议用 `K.*` 代替裸字符串。

从权威 KEYS 模版自动生成**嵌套命名空间**：按 key 的『点号前缀』分组，
`cmd.app_help` -> `K.cmd.app_help`（保留原文点号与下划线，无需反向还原）。
这样在写 `_()` 时获得 IDE 补全 / 全局重命名支持；守门测试会同时校验
代码中使用的 `K.*` 均已登记（见 tests/test_i18n.py）。

约定：KEYS 中每个 key 形如 `group.rest`（恰好一个点，rest 内可含下划线）。
"""

from types import SimpleNamespace

from .templates import KEYS


def _build_ns(mapping: dict) -> SimpleNamespace:
    """递归构建嵌套 SimpleNamespace：叶子值为完整 key 字符串。"""
    return SimpleNamespace(**{
        k: (_build_ns(v) if isinstance(v, dict) else v)
        for k, v in mapping.items()
    })


def _group_keys() -> dict:
    """按点号前缀把 KEYS 分组：'cmd.list' -> {'cmd': {'list': 'cmd.list'}}"""
    groups: dict = {}
    for key in KEYS:
        group, _, rest = key.partition('.')
        groups.setdefault(group, {})[rest] = key
    return groups


# 示例：K.cmd.list == 'cmd.list'；K.opt.path_with_c == 'opt.path_with_c'
K = _build_ns(_group_keys())

__all__ = ['K']
