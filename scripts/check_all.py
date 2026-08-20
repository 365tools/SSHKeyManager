#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一提交前检查调度器 (check_all.py)

在 git commit 前运行，确保改动通过所有必要检查。
设计为**可扩展**：新增检查只需实现一个函数并注册到 `CHECKS` 表，
无需改动调度逻辑。

用法:
    python scripts/check_all.py            # 完整检查（默认，含 pytest + pyright）
    python scripts/check_all.py --fast     # 快速检查（语法编译 + i18n，秒级）
    python scripts/check_all.py --skip pytest   # 跳过指定检查
    python scripts/check_all.py --list     # 列出所有已注册检查

退出码: 所有检查通过返回 0，任一失败返回 1（供 git hook 阻断提交）。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

# 确保控制台使用 UTF-8（Windows 默认 GBK 无法输出 emoji）
# 用 getattr 访问 reconfigure，规避 typeshed 对 TextIO 未声明该方法导致的
# basedpyright reportAttributeAccessIssue。
_stdout_reconfigure = getattr(sys.stdout, 'reconfigure', None)
_stderr_reconfigure = getattr(sys.stderr, 'reconfigure', None)
if (sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8')
        and _stdout_reconfigure and _stderr_reconfigure):
    try:
        _stdout_reconfigure(encoding='utf-8')
        _stderr_reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass

# 切换到项目根目录（scripts/ 的上级目录）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)


# ---------------------------------------------------------------------------
# 检查项定义
# ---------------------------------------------------------------------------
# 每个检查是 (name, is_fast, func) 三元组：
#   name      - 检查名称（供 --skip / 输出使用）
#   is_fast   - 是否为"快速检查"（--fast 时只跑这些）
#   func      - 检查函数：返回 (ok: bool, detail: str)
# ---------------------------------------------------------------------------


def _run(*args: str) -> tuple[bool, str]:
    """运行子命令并捕获输出。返回 (是否成功, 结果摘要)。"""
    try:
        result = subprocess.run(
            args, capture_output=True, text=True,
            encoding='utf-8', errors='replace', cwd=PROJECT_ROOT,
        )
        if result.returncode == 0:
            return True, _tail(result.stdout, result.stderr)
        return False, _tail(result.stdout, result.stderr)
    except FileNotFoundError:
        return False, f"命令未找到: {' '.join(args)}"


def _tail(*outputs: str, lines: int = 8) -> str:
    """合并并截取输出末尾若干行（避免刷屏）"""
    merged = '\n'.join(s for s in outputs if s).strip()
    if not merged:
        return '(无输出)'
    parts = merged.splitlines()
    return '\n'.join(parts[-lines:]) if len(parts) > lines else merged


def check_compile() -> tuple[bool, str]:
    """语法编译检查：确保所有 src 文件可被 py_compile 编译（秒级）。"""
    ok, detail = _run(
        sys.executable, '-m', 'compileall', '-q', '-f', '-q',
        str(PROJECT_ROOT / 'src'),
    )
    return ok, detail


def check_i18n() -> tuple[bool, str]:
    """i18n 一致性检查：只跑 test_i18n.py（key 模版/EN/ZH 同步、占位符一致）。"""
    ok, detail = _run(
        sys.executable, '-m', 'pytest', '-q', 'tests/test_i18n.py',
    )
    return ok, detail


# pytest 并行度：默认 3（实测对含 git 重写测试的套件最优）。
# 可通过环境变量 SSHM_TEST_JOBS 覆盖（0 = 串行；-1 = auto 用满 CPU）。
_TEST_JOBS_DEFAULT = 3


def _test_jobs() -> int:
    try:
        return int(os.environ.get('SSHM_TEST_JOBS', str(_TEST_JOBS_DEFAULT)))
    except ValueError:
        return _TEST_JOBS_DEFAULT


def check_pytest() -> tuple[bool, str]:
    """完整测试：运行全部 pytest（含 i18n 一致性守门测试）。

    默认启用 xdist 并行（-n 3）以加速；未安装 xdist 或显式设
    SSHM_TEST_JOBS=0 时自动回退串行，保证结果确定可复现。
    """
    jobs = _test_jobs()
    base = [sys.executable, '-m', 'pytest', '-q']
    # 尝试并行；若 xdist 不可用会报错，回退串行
    if jobs != 0:
        ok, detail = _run(*base, '-n', str(jobs))
        if ok:
            return ok, f"[{jobs} worker] {detail}"
        # 并行失败（多半是 xdist 未安装），回退串行
        print("  ⚠️  xdist 并行不可用，回退串行")
    return _run(*base)


def check_pyright() -> tuple[bool, str]:
    """类型检查：basedpyright 0 error / 0 warning / 0 note。"""
    # 显式指定解释器：避免 basedpyright 自动探测到空/损坏的 .venv 而解析不到依赖
    ok, detail = _run(sys.executable, '-m', 'basedpyright',
                      '--pythonpath', sys.executable)
    return ok, detail


def check_consistency() -> tuple[bool, str]:
    """三位一体一致性：CLI命令=注册表=manager方法 命名对齐。"""
    return _run(sys.executable, str(PROJECT_ROOT / 'scripts' / 'check_consistency.py'))


def check_rules() -> tuple[bool, str]:
    """业务层统一规则：架构规范检测。"""
    return _run(sys.executable, str(PROJECT_ROOT / 'scripts' / 'check_rules.py'))


def check_deadcode() -> tuple[bool, str]:
    """死代码/冗余检测（含 basedpyright unused + i18n 占位符）。"""
    return _run(sys.executable, str(PROJECT_ROOT / 'scripts' / 'check_deadcode.py'))


def check_cli() -> tuple[bool, str]:
    """CLI 输出标准化检查（自动导出所有指令+场景+执行+校验）。"""
    return _run(sys.executable, str(PROJECT_ROOT / 'scripts' / 'cli_snapshot.py'),
                '--check')


def check_rich_output() -> tuple[bool, str]:
    """输出统一性检查：确保输出走 rich（不允许散落的内置 print）。"""
    return _run(sys.executable, str(PROJECT_ROOT / 'scripts' / 'check_rich_output.py'))


# ---------------------------------------------------------------------------
# 检查注册表（新增检查在此登记即可）
# ---------------------------------------------------------------------------
# 元素: (name, is_fast, func)
CHECKS: List[tuple[str, bool, Callable[[], tuple[bool, str]]]] = [
    ('compile',      True, check_compile),       # 语法编译（快速）
    ('i18n',         True, check_i18n),          # 多语言 key 一致性（快速）
    ('consistency',  False, check_consistency),  # 三位一体一致性
    ('rules',        False, check_rules),        # 业务层统一规则
    ('deadcode',     False, check_deadcode),     # 死代码/冗余
    ('cli',          False, check_cli),          # CLI 输出标准化
    ('rich_output',  False, check_rich_output),  # 输出统一性（走 rich，无内置 print）
    ('pytest',       False, check_pytest),       # 完整测试
    ('pyright',      False, check_pyright),      # 类型检查
]

# 各检查对应的人类可读说明
CHECKS_HELP: Dict[str, str] = {
    'compile': '语法编译检查（所有 src 文件可编译）',
    'i18n':    'i18n key 模版 / EN / ZH 一致性（含占位符）',
    'consistency': '三位一体一致性（CLI命令=注册表=manager方法）',
    'rules':    '业务层统一规则检测',
    'deadcode': '死代码/冗余检测（含 basedpyright unused）',
    'cli':      'CLI 输出标准化检查（导出指令+场景+执行+校验）',
    'rich_output': '输出统一性检查（输出必须走 rich，不允许散落的内置 print）',
    'pytest':  '完整单元测试套件',
    'pyright': 'basedpyright 类型检查（0 error 0 warning）',
}


# ---------------------------------------------------------------------------
# 调度逻辑
# ---------------------------------------------------------------------------

def run_checks(fast: bool = False,
               skip: Optional[List[str]] = None) -> int:
    """运行选定的检查并汇总结果。

    Args:
        fast: 仅运行 is_fast=True 的快速检查
        skip: 需要跳过的检查名称列表

    Returns:
        退出码（0 全通过，1 有失败）
    """
    skip = skip or []
    results: List[tuple[str, bool, str]] = []

    print('=' * 60)
    print('🔍 sshm 提交前检查')
    print('=' * 60)

    for name, is_fast, func in CHECKS:
        if fast and not is_fast:
            print(f"  ⏭️  [跳过-快速模式] {name}")
            continue
        if name in skip:
            print(f"  ⏭️  [跳过] {name}")
            continue
        print(f"  ⏳ [{name}] {CHECKS_HELP.get(name, '')}...", flush=True)
        ok, detail = func()
        mark = '✅' if ok else '❌'
        print(f"  {mark} [{name}]")
        if not ok:
            print(f"     └─ {detail}")
        results.append((name, ok, detail))

    print('-' * 60)
    failed = [n for n, ok, _ in results if not ok]
    if failed:
        print(f"❌ 检查未通过: {', '.join(failed)}")
        return 1
    print("✅ 全部检查通过")
    return 0


def _parse_args(argv: List[str]) -> tuple[bool, List[str]]:
    """解析命令行参数"""
    fast = False
    skip: List[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == '--fast':
            fast = True
        elif arg == '--list':
            print('可用检查:')
            for name, is_fast, _ in CHECKS:
                tag = '[fast]' if is_fast else '[full]'
                print(f"  {tag} {name:<10} {CHECKS_HELP.get(name, '')}")
            sys.exit(0)
        elif arg == '--skip' and i + 1 < len(argv):
            skip.extend(argv[i + 1].split(','))
            i += 1
        else:
            print(f"未知参数: {arg}", file=sys.stderr)
            print(__doc__)
            sys.exit(2)
        i += 1
    return fast, skip


if __name__ == '__main__':
    fast, skip = _parse_args(sys.argv[1:])
    sys.exit(run_checks(fast=fast, skip=skip))
