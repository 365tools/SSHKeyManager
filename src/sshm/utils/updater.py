#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新管理模块 - 检查更新和自动更新
"""

import os
import sys
import json
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError

from ..constants import VERSION


class UpdateManager:
    """更新管理器"""
    
    GITHUB_API = "https://api.github.com/repos/365tools/SSHKeyManager/releases/latest"
    CACHE_FILE = Path.home() / ".sshm_update_cache"
    CACHE_VALID_HOURS = 24
    
    def __init__(self):
        self.current_version = VERSION
        self.platform = self._detect_platform()
        
    def _detect_platform(self) -> str:
        """检测当前平台"""
        system = platform.system()
        if system == "Windows":
            return "windows"
        elif system == "Linux":
            return "linux"
        elif system == "Darwin":
            return "macos"
        else:
            return "unknown"
    
    def _get_asset_name(self) -> str:
        """获取当前平台的资源文件名"""
        if self.platform == "windows":
            return "sshm-windows-amd64.exe"
        elif self.platform == "linux":
            return "sshm-linux-amd64"
        elif self.platform == "macos":
            return "sshm-macos-amd64"
        else:
            raise RuntimeError(f"不支持的平台: {self.platform}")
    
    def _parse_version(self, version: str) -> Tuple[int, ...]:
        """解析版本号为元组"""
        # 移除 'v' 前缀
        version = version.lstrip('v')
        return tuple(map(int, version.split('.')))
    
    def _is_newer_version(self, latest: str, current: str) -> bool:
        """比较版本号"""
        try:
            latest_parts = self._parse_version(latest)
            current_parts = self._parse_version(current)
            return latest_parts > current_parts
        except:
            return False
    
    def _get_cache(self) -> Optional[dict]:
        """读取缓存的版本信息"""
        if not self.CACHE_FILE.exists():
            return None
        
        try:
            import time
            cache_age = time.time() - self.CACHE_FILE.stat().st_mtime
            if cache_age > self.CACHE_VALID_HOURS * 3600:
                return None
            
            with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
    
    def _save_cache(self, data: dict):
        """保存版本信息到缓存"""
        try:
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except:
            pass
    
    def check_update(self, force: bool = False) -> Optional[dict]:
        """
        检查更新
        
        Args:
            force: 强制检查，忽略缓存
            
        Returns:
            如果有更新，返回 {version, download_url, body}，否则返回 None
        """
        # 尝试从缓存读取
        if not force:
            cache = self._get_cache()
            if cache:
                if self._is_newer_version(cache['version'], self.current_version):
                    return cache
                return None
        
        # 从 GitHub API 获取最新版本
        try:
            req = Request(self.GITHUB_API)
            req.add_header('User-Agent', f'SSHKeyManager/{VERSION}')
            
            with urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            latest_version = data['tag_name']
            
            # 检查是否有更新
            if not self._is_newer_version(latest_version, self.current_version):
                return None
            
            # 查找当前平台的下载链接
            asset_name = self._get_asset_name()
            download_url = None
            
            for asset in data.get('assets', []):
                if asset['name'] == asset_name:
                    download_url = asset['browser_download_url']
                    break
            
            if not download_url:
                return None
            
            result = {
                'version': latest_version,
                'download_url': download_url,
                'body': data.get('body', ''),
                'published_at': data.get('published_at', '')
            }
            
            # 保存到缓存
            self._save_cache(result)
            
            return result
            
        except URLError:
            # 网络错误，静默失败
            return None
        except Exception:
            return None
    
    def download_and_update(self, download_url: str) -> bool:
        """
        下载并更新可执行文件
        
        Args:
            download_url: 下载链接
            
        Returns:
            是否成功
        """
        try:
            print(f"⬇️  正在下载...")
            
            # 下载到临时文件
            req = Request(download_url)
            req.add_header('User-Agent', f'SSHKeyManager/{VERSION}')
            
            with urlopen(req, timeout=300) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                chunk_size = 8192
                
                # 创建临时文件
                temp_fd, temp_path = tempfile.mkstemp(suffix='.exe' if self.platform == 'windows' else '')
                
                with open(temp_path, 'wb') as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # 显示进度
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"\r  下载进度: {percent:.1f}%", end='', flush=True)
                
                print()  # 换行
            
            # 获取当前可执行文件路径
            current_exe = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
            current_exe = os.path.abspath(current_exe)
            
            print(f"📝 正在更新...")
            
            # 根据平台执行不同的更新策略
            if self.platform == "windows":
                # Windows: 创建批处理脚本延迟替换
                batch_script = f"""@echo off
timeout /t 2 /nobreak >nul
move /y "{temp_path}" "{current_exe}"
echo.
echo ✅ 更新完成！
echo 版本已更新，请重新运行 sshm
pause
del "%~f0"
"""
                batch_path = os.path.join(tempfile.gettempdir(), 'sshm_update.bat')
                with open(batch_path, 'w', encoding='gbk') as f:
                    f.write(batch_script)
                
                # 启动批处理脚本
                subprocess.Popen(['cmd', '/c', batch_path], 
                               creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, 'CREATE_NEW_CONSOLE') else 0)
                
                print("\n✅ 更新脚本已启动")
                print("程序将自动退出，更新完成后请重新运行 sshm")
                
            else:
                # Linux/macOS: 直接替换（需要权限）
                os.chmod(temp_path, 0o755)
                
                # 尝试直接替换
                try:
                    import shutil
                    shutil.move(temp_path, current_exe)
                    print("\n✅ 更新完成！")
                    print("请重新运行 sshm")
                except PermissionError:
                    # 需要 sudo
                    print(f"\n⚠️  需要管理员权限更新")
                    print(f"请手动运行: sudo mv {temp_path} {current_exe}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"\n❌ 更新失败: {e}")
            return False
    
    def check_and_notify(self):
        """
        检查更新并通知用户（静默检查）
        在每次运行时调用，不干扰正常使用
        """
        update_info = self.check_update(force=False)
        if update_info:
            print(f"\n💡 有新版本可用: {update_info['version']} (当前: v{self.current_version})")
            print(f"   运行 'sshm update' 更新到最新版本\n")
