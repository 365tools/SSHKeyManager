#!/usr/bin/env python3
"""
国际化 (i18n) 组装模块 - 提供翻译函数与语言状态管理

本模块只负责"组装"：从 language 包导入各语言字典，提供统一的翻译入口。
翻译字典本身位于 language 包：
  - language/templates.py  通用 key 模版（权威 key 清单 + 类型）
  - language/i18n_en.py        English (EN) 具体实现
  - language/i18n_zh.py        中文 (ZH) 具体实现

设计:
- 稳定 key（如 'cmd.list' / 'opt.label'）作为翻译键，
  英文 (EN) 与中文 (ZH) 两套字典均映射到同一 key。
- 默认语言为英文 (en)，可切换为中文 (zh)
- 语言优先级: SSHM_LANG 环境变量 > 状态文件 lang 字段 > 默认 en
- 支持 {placeholder} 占位符格式化
"""

import os

from .language.i18n_en import EN
from .language.i18n_zh import ZH

# 重新导出语言字典，便于外部直接访问
__all__ = [
    "EN",
    "ZH",
    "_",
    "get_lang",
    "load_from_state",
    "resolve_lang",
    "set_lang",
]


# --------------------------------------------------------------------------
# 当前语言（运行时可变）
# --------------------------------------------------------------------------
_current_lang: str = "en"


def set_lang(lang: str) -> None:
    """设置当前语言（en/zh），非法值回退 en"""
    global _current_lang
    _current_lang = lang if lang == "zh" else "en"


def get_lang() -> str:
    """获取当前语言"""
    return _current_lang


# --------------------------------------------------------------------------
# 语言解析
# --------------------------------------------------------------------------


def resolve_lang(env: str | None = None, state_lang: str | None = None) -> str:
    """解析最终语言: env > state > 'en'

    Args:
        env: SSHM_LANG 环境变量值
        state_lang: 状态文件中保存的 lang 字段
    """
    if env:
        e = env.strip().lower()
        if e in ("zh", "zh-cn", "zh_cn", "cn", "zh-hans", "zh_hans"):
            return "zh"
        if e in ("en", "en-us", "en_us", "us"):
            return "en"
    if state_lang:
        s = state_lang.strip().lower()
        if s in ("zh", "zh-cn", "zh_cn", "cn", "zh-hans", "zh_hans"):
            return "zh"
        if s in ("en", "en-us", "en_us", "us"):
            return "en"
    return "en"


def load_from_state(state_lang: str | None) -> None:
    """从状态文件加载语言并应用（环境变量优先）"""
    env = os.environ.get("SSHM_LANG")
    set_lang(resolve_lang(env, state_lang))


# --------------------------------------------------------------------------
# 翻译函数
# --------------------------------------------------------------------------


def _(text: str, **kwargs) -> str:
    """按当前语言查找稳定 key 对应的文本（支持 {placeholder} 格式化）

    Args:
        text: 稳定翻译 key（如 'cmd.list' / 'opt.label'）
        **kwargs: 占位符变量

    若当前语言字典中缺失该 key，回退到英文；英文也缺失则返回 key 本身，
    便于发现遗漏的翻译。
    """
    table = ZH if _current_lang == "zh" else EN
    result = table.get(text)
    if result is None:
        result = EN.get(text, text)
    if kwargs:
        try:
            result = result.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            pass
    return result
