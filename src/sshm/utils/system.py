#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统工具模块 - PATH 配置等系统级操作
"""

import os
import sys
from pathlib import Path

from ..i18n import _
from .console import print_section_header, prompt_confirm


def add_to_path():
    """将当前可执行文件路径添加到环境变量"""
    print_section_header(_("Add to PATH"))
    
    # 获取当前可执行文件路径
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的可执行文件
        exe_path = Path(sys.executable).resolve()
        exe_dir = exe_path.parent
    else:
        # 开发环境中的 Python 脚本
        exe_path = Path(__file__).parent.parent.resolve()
        exe_dir = exe_path
    
    print(f"📂 {_('Current executable: {path}', path=exe_path)}")
    print(f"📁 {_('Directory: {dir}', dir=exe_dir)}")
    
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
            print(_("Path already in environment variable: {path}",
                    path=existing_paths[0]))
            
            if existing_paths[0] != exe_dir_str:
                print(_("Current path: {path}", path=exe_dir_str))
                print(_("Existing path: {path}", path=existing_paths[0]))
                
                if prompt_confirm(_("Update to the current path?")):
                    # 移除旧路径
                    path_entries = [p for p in path_entries if p not in existing_paths]
                    # 添加新路径到开头
                    path_entries.insert(0, exe_dir_str)
                    new_path = ';'.join(path_entries)
                    
                    winreg.SetValueEx(key, 'Path', 0, winreg.REG_EXPAND_SZ, new_path)
                    winreg.CloseKey(key)
                    
                    # 广播环境变量更新
                    _broadcast_env_change()
                    
                    print("\n✅ " + _("Environment variable updated!"))
                    print("\n💡 " + _("Tip: restart your terminal for the change to take effect"))
                    print("   " + _("Then you can use the 'sshm' command directly"))
                else:
                    print("\n❌ " + _("operation cancelled"))
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
            
            print("\n✅ " + _("Added to environment variable!"))
            print(f"   {exe_dir_str}")
            print("\n💡 " + _("Tip: restart your terminal for the change to take effect"))
            print("   " + _("Then you can use the 'sshm' command directly"))
    
    except PermissionError:
        print("\n❌ " + _("Permission denied, please run as administrator"))
    except Exception as e:
        print(f"\n❌ {_('Failed to add: {err}', err=e)}")


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
            print(_("Path already in {name}", name=rc_file.name))
            return
    
    print(_("Will add to: {path}", path=rc_file))
    print(_("Command: {cmd}", cmd=export_line))
    
    if prompt_confirm("\n" + _("Continue?")):
        try:
            with rc_file.open('a', encoding='utf-8') as f:
                f.write(f"\n# Added by sshm\n")
                f.write(f"{export_line}\n")
            
            print("\n✅ " + _("Added to config file!"))
            print(f"\n💡 " + _("Run the following to apply:"))
            print(f"   source {rc_file}")
            print("\n   " + _("or restart your terminal"))
        except Exception as e:
            print(f"\n❌ {_('Failed to add: {err}', err=e)}")
    else:
        print("\n❌ " + _("operation cancelled"))


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
