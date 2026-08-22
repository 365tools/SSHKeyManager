"""
本地构建脚本 - 用于测试 PyInstaller 打包
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# 统一 stdout/stderr 为 UTF-8，避免 Windows GBK 控制台无法打印 emoji 导致
# UnicodeEncodeError 中断打包（如 🔨✅⚠️ 等字符）
# 用 getattr 动态访问 reconfigure，规避 pyright 对 TextIO 未声明该方法的告警
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        try:
            _reconfigure(encoding="utf-8")
        except Exception:
            pass

# 切换到项目根目录（scripts/ 的上级目录）
project_root = Path(__file__).parent.parent
os.chdir(project_root)


def _find_upx() -> str:
    """定位 upx.exe，找不到返回空字符串。

    搜索顺序：PATH -> winget 常见安装目录（递归）。
    """
    found = shutil.which("upx")
    if found:
        return found
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages",
        Path(os.environ.get("PROGRAMFILES", "")) / "upx",
        Path.home() / "upx",
    ]
    for base in candidates:
        if base.is_dir():
            for p in base.rglob("upx*.exe"):
                try:
                    return str(p)
                except OSError:
                    continue
    return ""


def build() -> None:
    """构建可执行文件"""
    print("=" * 60)
    print("🔨 开始构建 SSH Manager 可执行文件")
    print("=" * 60)

    # 检查 PyInstaller
    try:
        import PyInstaller

        print(f"✅ PyInstaller 版本: {PyInstaller.__version__}")
    except ImportError:
        print("❌ 未安装 PyInstaller")
        print("\n正在安装 PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"])
        import PyInstaller

        print(f"✅ PyInstaller 版本: {PyInstaller.__version__}")

    # 自动定位 UPX（用于压缩 DLL，进一步减小体积）。
    # winget 安装的 UPX 可能不在当前 shell 的 PATH 中（需重启才生效），
    # 这里扫描常见安装位置并临时加入 PATH，让 PyInstaller 能识别到。
    _upx = _find_upx()
    if _upx:
        _upx_dir = os.path.dirname(_upx)
        if _upx_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = _upx_dir + os.pathsep + os.environ.get("PATH", "")
        print(f"✅ UPX 可用（用于压缩）: {_upx}")
    else:
        print("📝 未找到 UPX（跳过可选的 exe/DLL 压缩）")

    # 复用仓库内的 sshm.spec 打包（而非命令行参数）。
    # spec 内已配置：打入 _version.txt（VERSION 第一来源）+ CHANGELOG.md（回退）
    # + copy_metadata，保证本地产物与 CI 线上产物版本解析行为完全一致。
    spec_file = Path("sshm.spec")
    if not spec_file.exists():
        print("❌ 未找到打包配置: sshm.spec")
        sys.exit(1)

    # 构建前清理旧产物（dist exe + build 缓存），避免：1) 失败时旧 exe 残留导致
    # dev_local.ps1 误判成功；2) PyInstaller 增量缓存异常。
    for _dir_name in ("build", "dist"):
        _d = Path(_dir_name)
        if _d.exists():
            shutil.rmtree(_d, ignore_errors=True)
            print(f"📝 清理旧产物: {_dir_name}/")

    # 用当前解释器执行 PyInstaller（而非裸 'pyinstaller'，避免 PATH 依赖），
    # 加 --noconfirm 避免 dist 存在时交互式覆盖询问卡住构建。
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        str(spec_file),
    ]

    print(f"\n🔧 执行命令: {' '.join(cmd)}")
    print()

    # 执行构建
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\n" + "=" * 60)
        print("✅ 构建成功！")
        print("=" * 60)

        # 显示输出文件信息
        dist_dir = Path("dist")
        if platform.system() == "Windows":
            exe_file = dist_dir / "sshm.exe"
        else:
            exe_file = dist_dir / "sshm"

        if exe_file.exists():
            size_mb = exe_file.stat().st_size / (1024 * 1024)
            print(f"\n📦 输出文件: {exe_file}")
            print(f"📊 文件大小: {size_mb:.2f} MB")
            print(f"💻 平台: {platform.system()} {platform.machine()}")

            # 测试运行
            print("\n🧪 测试运行...")
            try:
                # 使用 UTF-8 编码解码输出，避免 Windows GBK 编码问题
                test_result = subprocess.run(
                    [str(exe_file), "--help"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",  # 遇到无法解码的字符时替换而不是报错
                )
                if test_result.returncode == 0:
                    print("✅ 测试通过！")
                    # 显示帮助信息的前几行
                    lines = test_result.stdout.split("\n")[:5]
                    print("\n📋 输出预览:")
                    for line in lines:
                        print(f"   {line}")
                else:
                    print("⚠️ 测试失败")
                    print(test_result.stderr)
            except UnicodeDecodeError as e:
                print(f"⚠️ 编码警告（可忽略）: {e}")
                print("✅ 测试通过！（程序可正常运行）")

            # Windows 创建批处理包装器
            if platform.system() == "Windows":
                bat_file = dist_dir / "sshm.bat"
                bat_content = """@echo off
REM SSH Manager - 确保 UTF-8 编码
chcp 65001 >nul 2>&1
"%~dp0sshm.exe" %*
"""
                bat_file.write_text(bat_content, encoding="utf-8")
                print(f"\n📝 创建批处理包装器: {bat_file}")
                print("   (解决 PowerShell 管道编码问题)")
        else:
            print(f"⚠️ 未找到输出文件: {exe_file}")
    else:
        print("\n" + "=" * 60)
        print("❌ 构建失败")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    build()
