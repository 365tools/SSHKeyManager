#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三位一体一致性校验脚本。

校验 CLI 命令名 / 注册表 / manager 分组方法 三层命名是否对齐：
  1. registry.GROUPS 里每个 (group, name) 都有 app.py 的 @<group>_app.command("name")
  2. app.py 命令函数体内的 manager.<group>.<method>() 调用，method 与命令名 name 一致
     （即「CLI 命令名 = manager 分组属性 = manager 方法名」三位一体）
  3. app.py 引用的 manager.<group> 属性在 manager.py 有 self.<group> = ... 定义
  4. help_key 命名规范：cmd.{group}_{name}（连字符转下划线）
  5. 每个命令尾部的 _show_tip(group, current) 与其命令所属分组/命令名一致
  6. help_key 引用的 K.cmd.xxx 必须存在于 i18n KEYS

用法:
    python scripts/check_consistency.py
退出码 0 表示全部一致，非 0 表示存在不一致。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI_PY = ROOT / 'src' / 'sshm' / 'cli' / 'app.py'
MANAGER_PY = ROOT / 'src' / 'sshm' / 'core' / 'manager.py'


# ---------------------------------------------------------------------------
# 1. 解析 registry.GROUPS
# ---------------------------------------------------------------------------

def parse_registry() -> dict[str, list[tuple[str, str]]]:
    """从 registry.py 解析 GROUPS，返回 {group: [(name, help_key), ...]}。

    help_key 解析 CommandMeta 第二参数（K.cmd.xxx 属性链），返回 'cmd.xxx'。
    """
    registry_py = ROOT / 'src' / 'sshm' / 'cli' / 'registry.py'
    tree = ast.parse(registry_py.read_text(encoding='utf-8'))
    groups: dict[str, list[tuple[str, str]]] = {}
    for node in tree.body:
        target = None
        value = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target, value = node.target.id, node.value
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    target, value = t.id, node.value
        if target != 'GROUPS' or not isinstance(value, ast.Dict):
            continue
        for k, v in zip(value.keys, value.values):
            group = ast.literal_eval(k)
            entries: list[tuple[str, str]] = []
            if isinstance(v, ast.List):
                for item in v.elts:
                    if isinstance(item, ast.Call) and item.args:
                        name = ast.literal_eval(item.args[0])
                        # 解析 help_key：K.cmd.xxx -> 'cmd.xxx'
                        help_key = None
                        if len(item.args) > 1 and isinstance(item.args[1], ast.Attribute):
                            parts = []
                            cur = item.args[1]
                            while isinstance(cur, ast.Attribute):
                                parts.append(cur.attr)
                                cur = cur.value
                            if isinstance(cur, ast.Name) and cur.id == 'K':
                                help_key = '.'.join(reversed(parts))
                        entries.append((name, help_key))
            groups[group] = entries
    return groups


def parse_show_tip_calls() -> list[tuple[str, str]]:
    """解析 app.py 里所有 _show_tip("group", "name") 调用。"""
    tree = ast.parse(CLI_PY.read_text(encoding='utf-8'))
    calls: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == '_show_tip' and len(node.args) >= 2:
                g = ast.literal_eval(node.args[0])
                n = ast.literal_eval(node.args[1])
                calls.append((g, n))
    return calls


def parse_i18n_keys() -> set[str]:
    """解析 templates.py 的 KEYS（cmd.* 集合）。"""
    py = ROOT / 'src' / 'sshm' / 'language' / 'templates.py'
    tree = ast.parse(py.read_text(encoding='utf-8'))
    keys: set[str] = set()
    for node in tree.body:
        target = None
        value = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target, value = node.target.id, node.value
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    target, value = t.id, node.value
        if target == 'KEYS' and isinstance(value, (ast.Tuple, ast.List, ast.Set)):
            for elt in value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    keys.add(elt.value)
    return keys


# ---------------------------------------------------------------------------
# 2. 解析 app.py 的命令定义与 manager 调用
# ---------------------------------------------------------------------------

def parse_cli() -> dict[tuple[str, str], list[str]]:
    """解析 app.py，返回 {(group, command): [manager_methods, ...]}。

    其中 manager_methods 是从命令函数体内提取的 manager.<group>.<method> 调用。
    """
    tree = ast.parse(CLI_PY.read_text(encoding='utf-8'))
    # 建立 Typer 变量名 -> group 映射（key_app -> key）
    app_to_group: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.endswith('_app'):
                    group = t.id[:-4]  # key_app -> key
                    app_to_group[t.id] = group

    result: dict[tuple[str, str], list[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            # 匹配 @xxx_app.command("name") 或 @xxx_app.callback(...)
            func = dec.func
            if isinstance(func, ast.Attribute) and func.attr in ('command', 'callback'):
                if isinstance(func.value, ast.Name) and func.value.id in app_to_group:
                    group = app_to_group[func.value.id]
                    name = None
                    if dec.args and isinstance(dec.args[0], ast.Constant):
                        name = dec.args[0].value
                    # callback（invoke_without_command）没有子命令名，跳过命令校验
                    if func.attr == 'callback':
                        continue
                    # 提取函数体内 manager.<group>.<method> 调用
                    methods = _extract_manager_calls(node)
                    result[(group, name)] = methods
                    break
    return result


def _extract_manager_calls(func: ast.FunctionDef) -> list[str]:
    """提取函数体内 manager.<group>.<method>(...) 调用，返回 "group.method"。"""
    calls: list[str] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr = node.func
            # manager.key.create(...) -> attr.value = manager.key
            if isinstance(attr.value, ast.Attribute):
                inner = attr.value
                if (isinstance(inner.value, ast.Name)
                        and inner.value.id == 'manager'):
                    calls.append(f"{inner.attr}.{attr.attr}")
    return calls


# ---------------------------------------------------------------------------
# 3. 解析 manager.py 暴露的分组属性
# ---------------------------------------------------------------------------

def parse_manager_attrs() -> set[str]:
    """从 manager.py 提取 self.<attr> = ... 的属性名集合。"""
    tree = ast.parse(MANAGER_PY.read_text(encoding='utf-8'))
    attrs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name):
                    if t.value.id == 'self':
                        attrs.add(t.attr)
    return attrs


# ---------------------------------------------------------------------------
# 校验
# ---------------------------------------------------------------------------

def main() -> int:
    groups = parse_registry()
    cli = parse_cli()
    manager_attrs = parse_manager_attrs()
    tip_calls = parse_show_tip_calls()
    i18n_keys = parse_i18n_keys()

    problems: list[str] = []

    # 展开 registry 命令为 (group, name) 及 help_key 映射
    registry_commands: set[tuple[str, str]] = set()
    help_key_map: dict[tuple[str, str], str] = {}
    for group, entries in groups.items():
        for name, help_key in entries:
            registry_commands.add((group, name))
            help_key_map[(group, name)] = help_key

    cli_commands: set[tuple[str, str]] = set()
    for (group, name) in cli.keys():
        if name and not name.startswith('_'):  # 排除 callback（无 name）
            cli_commands.add((group, name))

    # 1. registry -> cli 完整性
    for gc in sorted(registry_commands):
        if gc not in cli_commands:
            problems.append(f"[registry->cli] registry has {gc[0]} {gc[1]}, but app.py lacks it")

    # 2. cli -> registry 完整性（cli 有但注册表没有）
    for gc in sorted(cli_commands):
        if gc not in registry_commands:
            problems.append(f"[cli->registry] app.py has {gc[0]} {gc[1]}, but registry lacks it")

    # 3. 三位一体：命令函数体内的 manager.<group>.<method> 与命令名一致
    for (group, name), methods in sorted(cli.items()):
        if not name or name.startswith('_'):
            continue
        for m in methods:
            mg, method = m.split('.', 1)
            if mg != group:
                continue  # 跨组调用（如 repo use 调用 key.switch），仅提示不报错
            if method != name:
                problems.append(
                    f"[trinity] {group} {name} calls manager.{group}.{method}, "
                    f"method should be {name}")

    # 4. manager 属性存在性
    for gc in cli_commands:
        group = gc[0]
        if group not in manager_attrs:
            problems.append(f"[manager-attr] app.py uses manager.{group}, but manager lacks self.{group}")

    # 5. help_key 命名规范：cmd.{group}_{name}（连字符转下划线）
    for (group, name), help_key in sorted(help_key_map.items()):
        if not help_key:
            problems.append(f"[help-key] {group} {name} has no help_key in registry")
            continue
        expected = f"cmd.{group}_{name.replace('-', '_')}"
        if help_key != expected:
            problems.append(
                f"[help-key] {group} {name} help_key='{help_key}', "
                f"expected '{expected}'")

    # 6. _show_tip(group, current) 与命令所属分组/命令名一致
    for g, n in tip_calls:
        if (g, n) not in registry_commands:
            problems.append(f"[tip] _show_tip('{g}', '{n}') has no matching registered command")

    # 7. help_key 引用的 i18n key 必须存在
    for (group, name), help_key in sorted(help_key_map.items()):
        if help_key and help_key not in i18n_keys:
            problems.append(f"[i18n] {group} {name} help_key '{help_key}' missing from KEYS")

    # 输出结果
    if problems:
        print(f"Found {len(problems)} inconsistency(ies):")
        for p in problems:
            print(f"  [X] {p}")
        return 1

    print(f"[OK] Trinity consistency check passed:")
    print(f"  - registry groups: {len(groups)}, commands: {len(registry_commands)}")
    print(f"  - app.py commands: {len(cli_commands)}, all aligned with registry")
    print(f"  - manager group attrs: {sorted(manager_attrs)}")
    print(f"  - tip calls checked: {len(tip_calls)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
