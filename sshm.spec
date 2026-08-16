# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import copy_metadata

# 打包 sshm 自身分发元数据（供 constants.VERSION 的 importlib.metadata 回退）
# 与 CHANGELOG.md（版本自动解析的第一来源）。两者皆缺失时版本会静默回落
# 0.0.0，导致每次运行都误报“有新版本”。包未安装时 copy_metadata 容错跳过。
try:
    _SSHM_METADATA = copy_metadata('sshm')
except Exception:
    _SSHM_METADATA = []


a = Analysis(
    ['src/run_sshm.py'],
    pathex=['src'],
    binaries=[],
    datas=[('docs/CHANGELOG.md', '.')] + _SSHM_METADATA,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='sshm',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='NONE',
)
