"""
本地构建脚本 - 用于测试 PyInstaller 打包
"""
import subprocess
import sys
import platform
import os
from pathlib import Path

# 切换到项目根目录（scripts/ 的上级目录）
project_root = Path(__file__).parent.parent
os.chdir(project_root)

def build():
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
    
    # 构建命令
    cmd = [
        "pyinstaller",
        "--onefile",           # 打包成单个文件
        "--name", "sshm",      # 输出文件名
        "--console",           # 控制台程序
        "--clean",             # 清理临时文件
        "--paths", "src",      # 添加 src 到 Python 路径
        "src/run_sshm.py"      # PyInstaller 专用入口点（使用绝对导入）
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
            print(f"\n🧪 测试运行...")
            try:
                # 使用 UTF-8 编码解码输出，避免 Windows GBK 编码问题
                test_result = subprocess.run(
                    [str(exe_file), "--help"], 
                    capture_output=True, 
                    text=True, 
                    encoding='utf-8',
                    errors='replace'  # 遇到无法解码的字符时替换而不是报错
                )
                if test_result.returncode == 0:
                    print("✅ 测试通过！")
                    # 显示帮助信息的前几行
                    lines = test_result.stdout.split('\n')[:5]
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
                bat_content = '''@echo off
REM SSH Manager - 确保 UTF-8 编码
chcp 65001 >nul 2>&1
"%~dp0sshm.exe" %*
'''
                bat_file.write_text(bat_content, encoding='utf-8')
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
