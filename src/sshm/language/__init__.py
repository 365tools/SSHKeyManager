#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
language 包 - 多语言翻译字典与 key 模版

结构:
  - i18n_language.py  通用 key 模版（权威 key 清单 + 类型约束）
  - i18n_en.py        English (EN) 具体实现
  - i18n_zh.py        中文 (ZH) 具体实现

翻译入口函数（`_` / set_lang 等）统一由外层 `sshm.i18n` 组装，本包只负责
提供语言字典数据，避免循环依赖。
"""

from .i18n_en import EN
from .i18n_zh import ZH
from .i18n_language import (
    KEYS,
    LANGUAGES,
    KEY_GROUPS,
    LanguageDict,
)

__all__ = [
    'EN', 'ZH',
    'KEYS', 'LANGUAGES', 'KEY_GROUPS', 'LanguageDict',
]
