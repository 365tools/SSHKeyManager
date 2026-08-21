#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui.tip 渲染模板测试 - 验证"统一 tip 段"在非 tty 下行为稳定。
"""

from __future__ import annotations

from conftest import strip_ansi


def test_render_tip_block_single_emits_one_separator_and_lines(capsys):
    """单段调用：顶部分隔线 + 各内容行（无底部分隔线）。"""
    from sshm.ui.tip import render_tip_block

    render_tip_block(["💡 line 1", "  detail"])
    out = strip_ansi(capsys.readouterr().out)

    # 顶部应有分隔线
    assert "────" in out
    # 内容应紧跟其后
    assert "💡 line 1" in out
    assert "  detail" in out
    # 单段底部不应再出现一条分隔线（设计：只顶部分隔，避免双线）。
    # 分隔线宽度随终端/rich 版本变化（非 tty=80、Rule 路径=控制台宽度），
    # 按"整行都是 ─"计数，避免硬编码 80 造成的跨环境脆弱。
    sep_count = sum(
        1 for line in out.splitlines() if line.strip() and set(line.strip()) == {"─"}
    )
    assert sep_count == 1, (
        f"single block should emit exactly one separator, got {sep_count}"
    )


def test_render_tip_block_consecutive_no_double_separator(capsys):
    """连续两段：每段各一条顶部分隔线，段间不会叠成双线。"""
    from sshm.ui.tip import render_tip_block

    render_tip_block(["💡 first"])
    render_tip_block(["💡 second"])
    out = strip_ansi(capsys.readouterr().out)

    # 应有 2 条分隔线（每段一条），不是 4 条；计数方式同宽度无关
    sep_count = sum(
        1 for line in out.splitlines() if line.strip() and set(line.strip()) == {"─"}
    )
    assert sep_count == 2, (
        f"two consecutive blocks should emit 2 separators, got {sep_count}"
    )
    # 两段内容都在
    assert "💡 first" in out
    assert "💡 second" in out


def test_render_tip_block_empty_lines_safe(capsys):
    """空行列表也安全：只输出分隔线。"""
    from sshm.ui.tip import render_tip_block

    render_tip_block([])
    out = strip_ansi(capsys.readouterr().out)

    # 空段：仍有一条顶部分隔线，无内容（计数方式同宽度无关）
    sep_count = sum(
        1 for line in out.splitlines() if line.strip() and set(line.strip()) == {"─"}
    )
    assert sep_count == 1


def test_command_list_lines_with_command_meta():
    """命令元数据 → `💡 标题` + `➖ sshm <group> <name>  <desc>` 对齐行。"""
    from sshm.i18n import _
    from sshm.language import K
    from sshm.cli.registry import commands_in_group
    from sshm.ui.tip import ITEM_BULLET, command_list_lines

    lines = command_list_lines("key", commands_in_group("key"))
    assert lines[0] == f"💡 {_(K.misc.related_tip)}"
    assert f"{ITEM_BULLET} sshm key list" in lines[1]
    assert f"{ITEM_BULLET} sshm key create" in lines[2]


def test_command_list_lines_with_top_level_names():
    """顶层分组名（字符串）→ `➖ sshm <group>`，无描述列。"""
    from sshm.ui.tip import ITEM_BULLET, command_list_lines

    lines = command_list_lines(None, ["key", "repo"])
    assert lines[0].startswith("💡")
    assert f"{ITEM_BULLET} sshm key" in lines
    assert f"{ITEM_BULLET} sshm repo" in lines


def test_render_tip_block_dim_style_forwarded():
    """style='dim' 应被转发给 ui.output.print（'More commands' 区域降亮度）。"""
    from unittest import mock

    from sshm import ui

    with mock.patch.object(ui.tip, "_print") as mprint:
        ui.tip.render_tip_block(["💡 line"], style="dim")
    # 每个内容行都应以 style='dim' 传给底层 print
    for call in mprint.call_args_list:
        assert call.kwargs.get("style") == "dim", call


def test_render_tip_block_no_style_auto_colors():
    """未传 style 时不传 style 参数（走 emoji 自动着色）。"""
    from unittest import mock

    from sshm import ui

    with mock.patch.object(ui.tip, "_print") as mprint:
        ui.tip.render_tip_block(["💡 line"])
    for call in mprint.call_args_list:
        assert "style" not in call.kwargs, call
