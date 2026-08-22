#!/usr/bin/env python3
"""
业务异常层次 - 统一错误协议

CLI 层在入口统一捕获 SSHMError 子类，转换为友好提示与退出码，
避免裸 traceback 抛给用户。

设计原则（core 层两种错误方式的分工）：
- 校验失败 / 无法继续的错误 → 抛 SSHMError 子类（由 CLI 统一转退出码）
- 软错误（提示 + 命令继续/收尾）→ 沿用 `_fail()`（置 _had_error，CLI 用
  `_fail_exit` 检查退出码）。二者互补，`_fail` 不改为抛异常，因为部分调用点
  是"告警但继续"语义（如自动联动作者失败）。
"""

from __future__ import annotations

__all__ = ["SSHMError", "ValidationError"]


class SSHMError(Exception):
    """业务错误基类（CLI 层统一处理）"""

    exit_code = 1

    def __init__(self, message: str, *, exit_code: int | None = None):
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code


class ValidationError(SSHMError, ValueError):
    """参数/标签校验失败。

    同时继承 ValueError，保持对旧调用方与既有测试（pytest.raises(ValueError)）
    的兼容。
    """

    exit_code = 2
