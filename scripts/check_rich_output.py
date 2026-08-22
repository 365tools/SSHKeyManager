#!/usr/bin/env python3
"""
输出统一性检查脚本 - 找出所有"未走 rich 的裸 print()"调用。

背景：项目的富文本输出统一由 ui.output.print（rich Console 封装）承担，
保证首行空行/emoji 着色/分隔线一致。但部分文件直接用 Python 内置 print()
导致输出风格不统一（缺首行空行、无颜色、缩进不一致）。

本脚本用 AST 精确解析：对每个 .py，判断每个 `print(` 调用到底引用的是
Python 内置 print，还是已从 ui.output/ui.console 引入的 rich 封装。
只报告"内置 print"调用，供人工统一。

豁免白名单（刻意保留内置 print 的场景，见 EXEMPT_REASONS）：
  - ui/console.py       仅 print_separator 的非 tty 降级路径：rich 的 Rule
    在非 tty/管道下渲染不理想，刻意用内置 print 输出纯横线。

用法：python scripts/check_rich_output.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# 确保控制台 UTF-8（Windows 默认 GBK 无法输出 emoji）
_stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
_stderr_reconfigure = getattr(sys.stderr, "reconfigure", None)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8") and _stdout_reconfigure and _stderr_reconfigure:
    try:
        _stdout_reconfigure(encoding="utf-8")
        _stderr_reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sshm"

# 白名单：这些文件允许存在内置 print（相对 SRC 的路径 + 理由）
EXEMPT: dict[str, str] = {
    "ui/console.py": "print_separator 非 tty 降级路径，rich Rule 在管道下渲染不理想",
}


class PrintUsageFinder(ast.NodeVisitor):
    """收集每个 print 调用及其是否解析为内置 print。"""

    def __init__(self) -> None:
        self.imported_names: set[str] = set()  # 已引入的 rich print 别名
        self.builtin_prints: list[tuple[int, str]] = []  # (行号, 片段)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module and ("ui.output" in node.module or "ui.console" in node.module):
            for alias in node.names:
                if alias.name == "print":
                    self.imported_names.add(alias.asname or "print")
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # print(...)
        func = node.func
        name = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            # 形如 xxx.print(...)，多半不是内置，跳过
            name = None
        if name == "print" and name not in self.imported_names:
            # 内置 print 调用
            try:
                snippet = ast.get_source_segment(_SRC[node], node) or ""
            except Exception:
                snippet = "print(...)"
            self.builtin_prints.append((node.lineno, snippet.replace("\n", " ")[:70]))
        self.generic_visit(node)


def analyze(path: Path) -> list[tuple[int, str]]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    _SRC[path] = source
    finder = PrintUsageFinder()
    finder.visit(tree)
    return finder.builtin_prints


_SRC: dict[Path, str] = {}


def main() -> bool:
    total = 0
    report: list[tuple[Path, list[tuple[int, str]]]] = []
    for py in SRC.rglob("*.py"):
        rel = py.relative_to(SRC).as_posix()  # 相对 sshm/ 的路径
        if rel in EXEMPT:
            continue  # 白名单：见 EXEMPT 注释
        hits = analyze(py)
        if hits:
            report.append((py.relative_to(SRC.parent), hits))
            total += len(hits)

    if not report:
        print("✅ 命令行输出均走 rich 封装（ui.output.print），未发现内置 print()。")
        print(f"   （白名单豁免 {len(EXEMPT)} 个文件，见 EXEMPT 注释）")
        return False

    print(f"⚠️  发现 {len(report)} 个文件使用 Python 内置 print()（共 {total} 处），不走 rich：\n")
    for rel, hits in report:
        print(f"  {rel}")
        for lineno, content in hits:
            print(f"      L{lineno:>4}: {content}")
        print()
    print("提示：将这些 print 改为从 ui.output 引入的 rich print，并在调用前补首行空行。")
    return True


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
