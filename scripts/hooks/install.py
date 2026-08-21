#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
git hooks 安装脚本

把 scripts/hooks/pre-commit 模板安装为 .git/hooks/pre-commit，
使每次 git commit 自动运行 sshm 统一检查（pytest 等）。

用法:
    python scripts/hooks/install.py          # 安装
    python scripts/hooks/install.py --remove # 卸载（恢复空钩子）

原理:
    git 只会执行 .git/hooks/ 目录下命名的钩子。该目录属于本仓库本地配置，
    不入版本库，因此需要此脚本在 clone 后安装一次。
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

# 确保控制台使用 UTF-8（Windows 默认 GBK 无法输出 emoji）
# 用 getattr 访问 reconfigure，规避 typeshed 对 TextIO 未声明该方法导致的
# basedpyright reportAttributeAccessIssue。
_stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
_stderr_reconfigure = getattr(sys.stderr, "reconfigure", None)
if (
    sys.stdout.encoding
    and sys.stdout.encoding.lower() not in ("utf-8", "utf8")
    and _stdout_reconfigure
    and _stderr_reconfigure
):
    try:
        _stdout_reconfigure(encoding="utf-8")
        _stderr_reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
HOOKS_SRC = Path(__file__).resolve().parent / "pre-commit"
GIT_HOOKS_DIR = PROJECT_ROOT / ".git" / "hooks"
TARGET = GIT_HOOKS_DIR / "pre-commit"


def install() -> None:
    if not HOOKS_SRC.exists():
        print(f"❌ 未找到钩子模板: {HOOKS_SRC}")
        sys.exit(1)
    if not GIT_HOOKS_DIR.exists():
        print(f"❌ 未找到 .git/hooks 目录: {GIT_HOOKS_DIR}")
        print("   请确认在 git 仓库内运行本脚本。")
        sys.exit(1)

    content = HOOKS_SRC.read_text(encoding="utf-8")
    TARGET.write_text(content, encoding="utf-8")

    # 设置可执行权限（Unix）；Windows 由 git 识别 shebang 亦可执行
    if os.name != "nt":
        TARGET.chmod(TARGET.stat().st_mode | stat.S_IXUSR)

    print(f"✅ 已安装 pre-commit 钩子: {TARGET}")
    print("   下次 git commit 时将自动运行 scripts/check_all.py。")
    print("   快速模式: 设置环境变量 SSHM_COMMIT_FAST=1")
    print("   卸载: python scripts/hooks/install.py --remove")


def remove() -> None:
    if TARGET.exists():
        TARGET.unlink()
        print(f"🗑️  已移除 pre-commit 钩子: {TARGET}")
    else:
        print("ℹ️  未找到已安装的 pre-commit 钩子，无需移除。")


if __name__ == "__main__":
    if "--remove" in sys.argv[1:]:
        remove()
    else:
        install()
