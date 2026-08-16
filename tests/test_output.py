"""Output 抽象测试：验证核心层输出可被替换（静默模式不产生任何输出）"""

import tempfile
from pathlib import Path

from sshm.core.manager import SSHKeyManager
from sshm.ui.output import NullOutput, get_output, set_output


def _manager() -> SSHKeyManager:
    return SSHKeyManager(ssh_dir=Path(tempfile.mkdtemp()))


def test_null_output_silences_core(capsys):
    """设置 NullOutput 后，核心层 list_keys 不应向 stdout 输出任何内容"""
    old = get_output()
    try:
        set_output(NullOutput())
        _manager().list_keys()
        assert capsys.readouterr().out == ''
    finally:
        set_output(old)


def test_console_output_restored_after_set(capsys):
    """set_output 恢复原实现后，核心层应正常输出"""
    old = get_output()
    try:
        set_output(NullOutput())
        _manager().list_keys()
        assert capsys.readouterr().out == ''
    finally:
        set_output(old)

    # 恢复默认后应正常输出
    _manager().list_keys()
    assert capsys.readouterr().out != ''
