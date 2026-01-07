#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统工具模块 - PATH 配置等系统级操作
"""

import os
import sys
from pathlib import Path

from .console import print_section_header, prompt_confirm


def add_to_path():
    """将当前可执行文件路径添加到环境变量"""
    print_section_header("添加到环境变量（PATH）")
    
    # 获取当前可执行文件路径
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的可执行文件
        exe_path = Path(sys.executable).resolve()
        exe_dir = exe_path.parent
    else:
        # 开发环境中的 Python 脚本
        exe_path = Path(__file__).parent.parent.resolve()
        exe_dir = exe_path
    
    print(f"📂 当前可执行文件位置: {exe_path}")
    print(f"📁 目录路径: {exe_dir}")
    
    if sys.platform == 'win32':
        _add_to_windows_path(exe_dir)
    else:
        _add_to_unix_path(exe_dir)


def _add_to_windows_path(exe_dir: Path):
    """Windows 环境变量配置"""
    import winreg
    
    try:
        # 读取当前用户的 PATH 环境变量
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'Environment',
            0,
            winreg.KEY_READ | winreg.KEY_WRITE
        )
        
        try:
            current_path, _ = winreg.QueryValueEx(key, 'Path')
        except FileNotFoundError:
            current_path = ''
        
        # 规范化路径
        exe_dir_str = str(exe_dir)
        path_entries = [p.strip() for p in current_path.split(';') if p.strip()]
        
        # 检查路径是否已存在
        existing_paths = [p for p in path_entries 
                         if Path(p).resolve() == exe_dir.resolve()]
        
        if existing_paths:
            print(f"\n✅ 路径已在环境变量中: {existing_paths[0]}")
            
            if existing_paths[0] != exe_dir_str:
                print(f"\n⚠️  当前路径: {exe_dir_str}")
                print(f"   已有路径: {existing_paths[0]}")
                
                if prompt_confirm("是否更新为当前路径？"):
                    # 移除旧路径
                    path_entries = [p for p in path_entries if p not in existing_paths]
                    # 添加新路径到开头
                    path_entries.insert(0, exe_dir_str)
                    new_path = ';'.join(path_entries)
                    
                    winreg.SetValueEx(key, 'Path', 0, winreg.REG_EXPAND_SZ, new_path)
                    winreg.CloseKey(key)
                    
                    # 广播环境变量更新
                    _broadcast_env_change()
                    
                    print("\n✅ 环境变量已更新！")
                    print("\n💡 提示: 请重启命令行窗口使环境变量生效")
                    print("   然后可以直接使用 'sshm' 命令")
                else:
                    print("\n❌ 操作已取消")
                    winreg.CloseKey(key)
            else:
                winreg.CloseKey(key)
        else:
            # 添加新路径到开头
            path_entries.insert(0, exe_dir_str)
            new_path = ';'.join(path_entries)
            
            winreg.SetValueEx(key, 'Path', 0, winreg.REG_EXPAND_SZ, new_path)
            winreg.CloseKey(key)
            
            # 广播环境变量更新
            _broadcast_env_change()
            
            print("\n✅ 已添加到环境变量！")
            print(f"   {exe_dir_str}")
            print("\n💡 提示: 请重启命令行窗口使环境变量生效")
            print("   然后可以直接使用 'sshm' 命令")
    
    except PermissionError:
        print("\n❌ 权限不足，请以管理员身份运行")
    except Exception as e:
        print(f"\n❌ 添加失败: {e}")


def _add_to_unix_path(exe_dir: Path):
    """Unix/Linux/macOS 环境变量配置"""
    home = Path.home()
    exe_dir_str = str(exe_dir)
    
    # 检测 shell 类型
    shell = os.environ.get('SHELL', '/bin/bash')
    if 'zsh' in shell:
        rc_file = home / '.zshrc'
    elif 'fish' in shell:
        rc_file = home / '.config' / 'fish' / 'config.fish'
    else:
        rc_file = home / '.bashrc'
    
    export_line = f'export PATH="{exe_dir_str}:$PATH"'
    
    # 检查是否已添加
    if rc_file.exists():
        content = rc_file.read_text(encoding='utf-8')
        if exe_dir_str in content:
            print(f"\n✅ 路径已在 {rc_file.name} 中")
            return
    
    print(f"\n📝 将添加到: {rc_file}")
    print(f"   命令: {export_line}")
    
    if prompt_confirm("\n是否继续？"):
        try:
            with rc_file.open('a', encoding='utf-8') as f:
                f.write(f"\n# Added by SSH Key Manager\n")
                f.write(f"{export_line}\n")
            
            print("\n✅ 已添加到配置文件！")
            print(f"\n💡 执行以下命令使环境变量生效：")
            print(f"   source {rc_file}")
            print("\n   或重启终端")
        except Exception as e:
            print(f"\n❌ 添加失败: {e}")
    else:
        print("\n❌ 操作已取消")


def _broadcast_env_change():
    """广播 Windows 环境变量更新"""
    if sys.platform == 'win32':
        try:
            import ctypes
            
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            SMTO_ABORTIFHUNG = 0x0002
            
            result = ctypes.c_long()
            SendMessageTimeout = ctypes.windll.user32.SendMessageTimeoutW
            SendMessageTimeout(
                HWND_BROADCAST,
                WM_SETTINGCHANGE,
                0,
                'Environment',
                SMTO_ABORTIFHUNG,
                5000,
                ctypes.byref(result)
            )
        except:
            pass
