"""工具函数测试：console 输出对齐"""

from sshm.ui.console import (
    format_size,
    format_timestamp,
    get_display_width,
    pad_cell,
)


class TestPadCell:
    def test_none_becomes_blank(self):
        assert pad_cell(None, 5) == "     "

    def test_left_align(self):
        assert pad_cell("ab", 5) == "ab   "

    def test_right_align(self):
        assert pad_cell("ab", 5, align="right") == "   ab"

    def test_truncate_long(self):
        result = pad_cell("abcdefghij", 5)
        assert len(result) >= 4  # 截断 + 省略号
        assert "…" in result or len(result) <= 5


class TestGetDisplayWidth:
    def test_ascii(self):
        assert get_display_width("abc") == 3

    def test_cjk_wide(self):
        # 中文全角字符宽度为 2
        assert get_display_width("中文") == 4


class TestFormat:
    def test_format_size(self):
        assert format_size(0) == "0 B"
        assert "KB" in format_size(2048)

    def test_format_timestamp(self):
        from datetime import datetime

        ts = format_timestamp(datetime(2026, 8, 16, 12, 30, 0))
        assert ts == "2026-08-16 12:30:00"
