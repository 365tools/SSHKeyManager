#!/usr/bin/env python3
"""
language 包 - 多语言翻译字典与 key 模版

结构:
  - templates.py      通用 key 模版（权威 key 清单 + 类型约束）
  - i18n_en.py        English (EN) 具体实现
  - i18n_zh.py        中文 (ZH) 具体实现

翻译入口函数（`_` / set_lang 等）统一由外层 `sshm.i18n` 组装，本包只负责
提供语言字典数据，避免循环依赖。
"""

from .i18n_en import EN
from .i18n_zh import ZH
from .keys import K
from .templates import (
    KEY_GROUPS,
    KEYS,
    LANGUAGES,
    LanguageDict,
)

__all__ = [
    "EN",
    "KEYS",
    "KEY_GROUPS",
    "LANGUAGES",
    "ZH",
    "K",
    "LanguageDict",
]
