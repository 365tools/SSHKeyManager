#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一"tip 段"渲染模板 - 复用于命令底部与错误场景，避免到处手写不同的输出格式。

设计动机：
  原代码里"💡 提示 + 列表"以多种形式散落在 _show_tip、单行 tip、
  内联 print 等多处，样式不一致；错误场景更是另起一个红色 Panel，
  风格与正常命令底部脱节。本模块提供唯一渲染入口：

    render_tip_block(lines)
      ───── separator ─────   ← 上下分隔线（与 ui.console.print_separator 一致）
      <line 1>                ← emoji 前缀自动着色（见 ui.output._EMOJI_STYLE）
      <line 2>
      ───── separator ─────

  这样：
    - 常规命令底部：💡 操作提示 + 💡 相关命令列表   → 同一段
    - 未知命令错误：❌ 错误信息 + 💡 你是不是要找     → 同一段
    - 多段堆叠：连续调用即可自动衔接（每段自带上下分隔线）

依赖：ui.console（分隔线）、ui.output（按 emoji 自动着色）。
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional

from .console import print_separator
from .output import print as _print

__all__ = ['render_tip_block', 'command_list_lines', 'ITEM_BULLET']

# 命令/建议列表项统一前缀图标（与 💡 标题形成视觉层级，一处定义全局复用）
ITEM_BULLET = "➖"


def render_tip_block(lines: Iterable[str], *, top: bool = True,
                     style: Optional[str] = None) -> None:
    """渲染统一的 tip 段：可选顶部分隔线 + 内容行。

    设计：每段默认带一个**顶部分隔线**，不带底部分隔线。这样：
    - 单段使用：顶部 ─ + 内容，与底部自然过渡。
    - 多段连续调用：每段顶端各一条 ─，段间不会出现"双线"。
      例如连续两次 render_tip_block([...]) 输出：

        ──── separator ────
        <line 1>
        <line 2>
        ──── separator ────
        <line 3>
        <line 4>

    Args:
        lines: 内容行序列（每个元素一行）。
        top: 是否输出顶部分隔线。设为 False 时该段紧贴前文（如错误场景里
             `❌ 错误消息`作为首行，上方不应有分隔线）。
        style: 整段统一样式（如 'dim' 降亮度）。不传时按行首 emoji 自动着色
             （见 ui.output._EMOJI_STYLE）：💡 → cyan、❌ → bold red 等。

    非 tty 下分隔线降级为纯 ASCII 横线（与 ui.console.print_separator 一致）。
    """
    if top:
        print_separator('─')
    for line in lines:
        if style:
            _print(line, style=style)
        else:
            _print(line)


def command_list_lines(group: Optional[str],
                       cmds: Iterable[Any]) -> List[str]:
    """统一生成"💡 More commands in this group"命令清单行（唯一格式来源）。

    收敛了原先散落在 app._show_tip 与 suggest._group_commands_lines /
    _top_level_lines 的命令行格式化逻辑，避免格式漂移。

    Args:
        group: 分组名（用于拼 `sshm <group> <name>`）；顶层场景传 None。
        cmds: 命令项序列。元素可以是：
          - CommandMeta（含 .name/.help_key）→ `sshm <group> <name>  <desc>`
          - 字符串（顶层分组名，无描述）→ `sshm <name>`

    返回可直接交给 render_tip_block 的行列表（首行为 💡 标题）。
    """
    from ..i18n import _
    from ..language import K
    lines = [f"💡 {_(K.misc.related_tip)}"]
    for item in cmds:
        if isinstance(item, str):
            lines.append(f"{ITEM_BULLET} sshm {item}")
        else:
            desc = _(item.help_key)
            lines.append(f"{ITEM_BULLET} sshm {group} {item.name:<10} {desc}")
    return lines