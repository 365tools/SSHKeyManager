# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import copy_metadata

# 打包版本文件（constants.VERSION 的第一来源）与 CHANGELOG.md（回退来源）、
# 以及 sshm 自身分发元数据（importlib.metadata 回退）。三者皆缺失时版本会
# 静默回落 0.0.0，导致每次运行都误报“有新版本”。包未安装时 copy_metadata 容错跳过。
try:
    _SSHM_METADATA = copy_metadata('sshm')
except Exception:
    _SSHM_METADATA = []


# 显式排除的无关重量级库：sshm 及 typer 的运行时根本不使用它们，
# 但 PyInstaller 的 hook（rich/pygments 等）会误把它们收集进包，导致
# 体积从 ~10MB 暴涨到 ~30MB。排除可显著瘦身且不影响功能。
_SSHM_EXCLUDES = [
    'numpy', 'scipy', 'pandas', 'matplotlib',
    'PIL', 'Pillow',
    'IPython', 'jupyter', 'notebook',
    'pytest', 'babel',
]


a = Analysis(
    ['src/run_sshm.py'],
    pathex=['src'],
    binaries=[],
    datas=[('src/sshm/_version.txt', 'sshm'),
           ('docs/CHANGELOG.md', '.')] + _SSHM_METADATA,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_SSHM_EXCLUDES,
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
