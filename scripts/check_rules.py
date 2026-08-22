#!/usr/bin/env python3
"""
业务层统一规则检测脚本。

校验 src/sshm/core 与 commands/ 层的架构规范（区别于 check_consistency 的
命令定义层校验和 check_deadcode 的死代码检测）：

  1. commands/ 禁止直接改 self.m._had_error（应走 _fail / _mark_error）
  2. commands/ 禁止 raise 业务异常（仅校验函数可用 raise ValidationError）
  3. commands/ 输出必须从 ..ui.output 导入 print/section/table/confirm
     （不允许依赖内置 print）
  4. commands/ 命令类构造器形参统一为 m
  5. 服务层（core/ 非 commands）禁止 import commands/（分层违例）
  6. 模块文件名不得重复直接父包路径中的词
     （如 language/templates.py、cli/app.py 命名避免与父包重复）

用法:
    python scripts/check_rules.py
退出码 0 表示全部符合规则，非 0 表示存在违规。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SSHM = ROOT / "src" / "sshm"
CORE = SSHM / "core"
COMMANDS = CORE / "commands"


def _py_files(base: Path) -> list[Path]:
    return sorted(p for p in base.rglob("*.py"))


# ---------------------------------------------------------------------------
# 规则 1: commands/ 禁止直接改 self.m._had_error
# ---------------------------------------------------------------------------


def check_had_error_direct() -> list[str]:
    """检测 commands/ 中直接给 self.m._had_error 赋值（应走 _fail/_mark_error）。

    只检测赋值（_had_error 出现在赋值语句左侧），不检测读取
    （如 `if manager._had_error` 是合法的 CLI 退出码判断）。
    """
    problems = []

    def _target_has(target, attr_name) -> bool:
        """递归检查赋值目标是否含 attr_name 属性。"""
        if isinstance(target, ast.Attribute) and target.attr == attr_name:
            return True
        if isinstance(target, (ast.Tuple, ast.List)):
            return any(_target_has(t, attr_name) for t in target.elts)
        return False

    for p in _py_files(COMMANDS):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if _target_has(t, "_had_error"):
                        problems.append(f"{p.name}: {node.lineno} - direct self.m._had_error assignment; use _fail/_mark_error")
    return problems


# ---------------------------------------------------------------------------
# 规则 2: commands/ 禁止 raise（仅允许 raise ValidationError 校验异常）
# ---------------------------------------------------------------------------


def check_raise() -> list[str]:
    problems = []
    for p in _py_files(COMMANDS):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and node.exc is not None:
                # 提取 raise X(...) 的异常类名
                exc = node.exc
                exc_name = None
                if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
                    exc_name = exc.func.id
                elif isinstance(exc, ast.Name):
                    exc_name = exc.id
                # ValidationError 是合法校验异常（CLI 层统一捕获），其余禁止
                if exc_name not in ("ValidationError",):
                    problems.append(f"{p.name}: {node.lineno} - 'raise {exc_name or '?'}' in command layer; use _fail() or ValidationError")
    return problems


# ---------------------------------------------------------------------------
# 规则 3: commands/ 输出必须从 ..ui.output 导入
# ---------------------------------------------------------------------------


def check_output_import() -> list[str]:
    """检测 commands/ 是否有 print( 调用但未从 ..ui.output 导入 print。

    若模块导入了 print（来自 ui.output），则模块内的 print(...) 是合法的。
    """
    problems = []
    for p in _py_files(COMMANDS):
        text = p.read_text(encoding="utf-8")
        tree = ast.parse(text)
        # 判断模块是否导入了 ui.output 的 print
        imported_print = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if "ui.output" in mod:
                    for alias in node.names:
                        if alias.name == "print":
                            imported_print = True
            # import ... as print
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname == "print":
                        imported_print = True
        # 找模块内 print(...) 调用（不含被重绑定的函数定义）
        if not imported_print:
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
                    # 排除 print 是函数参数名的情况（粗略）
                    problems.append(f"{p.name}: {node.lineno} - uses builtin print(); add 'from ..ui.output import print'")
    return problems


# ---------------------------------------------------------------------------
# 规则 4: commands/ 命令类构造器形参统一为 m
# ---------------------------------------------------------------------------


def check_ctor_param() -> list[str]:
    problems = []
    for p in _py_files(COMMANDS):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                        args = [a.arg for a in item.args.args]
                        # 形参 [self, X]：X 应 == m
                        if len(args) >= 2 and args[1] != "m":
                            problems.append(f"{p.name}: {item.lineno} - {node.name}.__init__ param '{args[1]}', expected 'm'")
    return problems


# ---------------------------------------------------------------------------
# 规则 5: 服务层（core/ 非 commands）禁止 import commands/
# ---------------------------------------------------------------------------


def check_service_import_commands() -> list[str]:
    problems = []
    service_files = [p for p in _py_files(CORE) if p.parent != COMMANDS]
    for p in service_files:
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if "commands" in mod and "sshm.core.commands" in mod:
                    problems.append(f"{p.name}: {node.lineno} - service layer imports '{mod}'")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "commands" in alias.name:
                        problems.append(f"{p.name}: {node.lineno} - service layer imports '{alias.name}'")
    return problems


# ---------------------------------------------------------------------------
# 规则 6: 文件名不得重复直接父包路径中的词
# 例：文件名 `i18n_language` 的 `language` 重复了父包 `language`
#     文件名 `cli` 重复了父包 `cli`（应消除为 `templates.py`、`app.py`）。
# ---------------------------------------------------------------------------


def check_filename_pkg_duplicate() -> list[str]:
    problems = []
    for p in sorted(SSHM.rglob("*.py")):
        if p.name == "__init__.py" or "__pycache__" in p.parts:
            continue
        parent = p.parent.name  # 直接父目录名，如 'language' / 'cli'
        filename = p.stem  # 文件名（去 .py），如 'i18n_language' / 'templates'
        # 分词对比：文件名任一分词 == 父包名（去下划线）
        parent_clean = parent.replace("_", "").lower()
        if not parent_clean:
            continue
        for part in filename.split("_"):
            if part.lower() == parent_clean:
                problems.append(f"{p.relative_to(ROOT)}: filename '{filename}' duplicates parent package '{parent}'")
                break
    return problems


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def main() -> int:
    problems: list[str] = []

    problems += [f"[had_error] {x}" for x in check_had_error_direct()]
    problems += [f"[raise] {x}" for x in check_raise()]
    problems += [f"[output-import] {x}" for x in check_output_import()]
    problems += [f"[ctor-param] {x}" for x in check_ctor_param()]
    problems += [f"[service-import] {x}" for x in check_service_import_commands()]
    problems += [f"[pkg-dup] {x}" for x in check_filename_pkg_duplicate()]

    if problems:
        print(f"Found {len(problems)} rule violation(s):")
        for p_ in problems:
            print(f"  [X] {p_}")
        return 1

    print("[OK] All business-layer rules satisfied.")
    print(f"  - commands/: {len(_py_files(COMMANDS))} files checked")
    print(f"  - core/: {len([p for p in _py_files(CORE) if p.parent != COMMANDS])} service files checked")
    print(f"  - sshm/ pkg naming: {len(_py_files(SSHM))} modules checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
