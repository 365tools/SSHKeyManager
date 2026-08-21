#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把代码中 `_('group.key')` 字面量批量替换为 `_(K.group.key)`（i18n K 常量收敛）。

约定：key 形如 `group.rest`（恰好一个点，rest 为合法 Python 标识符）。
- 不在 KEYS 模板中的 key 保持字面量不动（门禁允许两种形式）
- 已用 K.* 的调用不动
- 自动为每个用到 K 的文件补充 `from ...language import K`（与现有 i18n 导入同深度）

用法：
    python scripts/apply_k_constants.py            # 实际替换
    python scripts/apply_k_constants.py --dry-run  # 只预览改动
"""

from __future__ import annotations

import keyword
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC / "sshm"))

from sshm.language.templates import KEYS  # noqa: E402

# 匹配 `_('key')` / _("key")，key 含点号、rest 为标识符
_CALL_RE = re.compile(r"\b_\s*\(\s*['\"]([a-z][a-z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*)['\"]")
# i18n 导入行：from <dots>i18n import _...
_I18N_IMPORT_RE = re.compile(r"^(from (\.*)i18n import .*)$", re.M)
# 已有 K 导入
_K_IMPORT_RE = re.compile(
    r"^\s*from \.*language import .*\bK\b|^\s*import .*\bK\b", re.M
)


def _k_expr(key: str) -> str:
    group, _, rest = key.partition(".")
    return f"K.{group}.{rest}"


def main() -> int:
    dry = "--dry-run" in sys.argv
    missing: list[tuple[str, str]] = []
    total = 0
    for py in sorted(SRC.rglob("*.py")):
        text = py.read_text(encoding="utf-8")
        orig = text
        used_keys: set[str] = set()

        def repl(m: re.Match) -> str:
            key = m.group(1)
            if key not in KEYS:
                missing.append((str(py.relative_to(SRC)), key))
                return m.group(0)
            # rest 为 Python 关键字（如 opt.global / sys.continue）无法用 K.attr 访问，
            # 保持字面量形式（门禁允许两种形式）。
            if keyword.iskeyword(key.partition(".")[2]):
                return m.group(0)
            used_keys.add(key)
            # 注意：只替换 `_(` 到 key 结尾引号的部分，不补右括号——
            # 原调用自带的 `)`（或 `, 参数`）会自然闭合，避免多出一对括号。
            return f"_({_k_expr(key)}"

        text = _CALL_RE.sub(repl, text)
        if text == orig:
            continue

        # 需要 K 导入且文件尚未导入 K
        if used_keys and not _K_IMPORT_RE.search(text):
            i18n_m = _I18N_IMPORT_RE.search(text)
            # 仅当 i18n 导入是单行（不以 '(' 结尾）时才自动插入 K 导入
            if i18n_m and not i18n_m.group(0).rstrip().endswith("("):
                line = i18n_m.group(1)
                dots = re.match(r"from (\.*)i18n", line).group(1)
                k_import = f"from {dots}language import K"
                # 插到 i18n 导入行之后
                text = text[: i18n_m.end()] + "\n" + k_import + text[i18n_m.end() :]

        if text == orig:
            continue
        total += len(used_keys)
        print(
            ("DRY" if dry else "MOD")
            + f" {py.relative_to(SRC)}  ({len(used_keys)} keys)"
        )
        if not dry:
            py.write_text(text, encoding="utf-8")

    print(f"\n共替换 {total} 个 key；未登记在 KEYS 的（保持字面量）: {len(missing)}")
    for path, key in missing[:20]:
        print(f"  [MISSING] {path}: {key}")
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
