#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSH Key Manager CLI - 企业级多账号 SSH 密钥管理工具

功能特性:
- 🏷️ 标签化管理多个 SSH 密钥
- 🔄 一键切换默认密钥
- ⚙️ 自动生成和维护 SSH config
- 💾 智能备份保护
- 📊 状态追踪和可视化

作者: 365tools
版本: 2.0.1
许可: MIT
"""

import os
import sys
import argparse
import shutil
import subprocess
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import io


# ============================================================================
# 常量定义
# ============================================================================

VERSION = "2.1.0"
SUPPORTED_KEY_TYPES = ['ed25519', 'rsa', 'ecdsa', 'dsa']
DEFAULT_KEY_TYPE = 'ed25519'
STATE_FILE_NAME = '.sshm_state'
BACKUP_DIR_NAME = 'key_backups'


# ============================================================================
# Windows 控制台编码修复
# ============================================================================

def setup_windows_console():
    """修复 Windows 控制台 UTF-8 编码问题"""
    if sys.platform != 'win32':
        return
    
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        
        # 设置控制台代码页为 UTF-8 (65001)
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
        
        # 重新包装 stdout/stderr
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer,
                encoding='utf-8',
                errors='replace',
                line_buffering=True,
                write_through=True
            )
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer,
                encoding='utf-8',
                errors='replace',
                line_buffering=True,
                write_through=True
            )
    except Exception:
        pass  # 静默失败


# 初始化 Windows 控制台
setup_windows_console()


# ============================================================================
# 工具函数
# ============================================================================

def get_key_pattern():
    """获取密钥文件名匹配模式"""
    return re.compile(r'^id_(rsa|ed25519|ecdsa|dsa)(\.\w+)?$')


def format_timestamp(dt: datetime) -> str:
    """格式化时间戳"""
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    return f"{size_bytes} bytes"


def prompt_confirm(message: str) -> bool:
    """确认提示"""
    response = input(f"{message} (y/n): ").lower().strip()
    return response in ['y', 'yes']


def print_separator(char='=', length=80):
    """打印分隔线"""
    print(char * length)


def print_section_header(title: str):
    """打印章节标题"""
    print_separator()
    print(title)
    print_separator()


# ============================================================================
# SSH 配置管理器
# ============================================================================

class SSHConfigManager:
    """SSH config 文件管理器"""
    
    def __init__(self, config_file: Path):
        self.config_file = config_file
    
    def update_host(self, label: str, host: str, key_file: Path):
        """更新或添加 Host 配置"""
        config_block = self._generate_config_block(label, host, key_file)
        
        if not self.config_file.exists():
            self.config_file.write_text(config_block, encoding='utf-8')
            return
        
        content = self.config_file.read_text(encoding='utf-8')
        
        # 查找并替换已存在的配置块
        pattern = rf'^# {re.escape(label)} - Auto-generated.*?(?=^#|\Z)'
        if re.search(pattern, content, re.MULTILINE | re.DOTALL):
            content = re.sub(pattern, config_block.rstrip() + '\n\n', 
                           content, flags=re.MULTILINE | re.DOTALL)
        else:
            content += '\n' + config_block
        
        self.config_file.write_text(content, encoding='utf-8')
    
    def remove_host(self, label: str):
        """从 SSH config 中删除指定标签的配置"""
        if not self.config_file.exists():
            return
        
        content = self.config_file.read_text(encoding='utf-8')
        pattern = rf'^# {re.escape(label)} - Auto-generated.*?(?=^#|\Z)'
        content = re.sub(pattern, '', content, flags=re.MULTILINE | re.DOTALL)
        self.config_file.write_text(content, encoding='utf-8')
    
    def rename_host(self, old_label: str, new_label: str):
        """重命名 SSH config 中的 Host"""
        if not self.config_file.exists():
            return
        
        content = self.config_file.read_text(encoding='utf-8')
        pattern = rf'^# {re.escape(old_label)} - Auto-generated.*?(?=^#|\Z)'
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        
        if match:
            old_block = match.group(0)
            new_block = old_block.replace(f"# {old_label} - ", f"# {new_label} - ")
            new_block = re.sub(rf'^Host {re.escape(old_label)}$', 
                             f'Host {new_label}', new_block, flags=re.MULTILINE)
            content = content.replace(old_block, new_block)
            self.config_file.write_text(content, encoding='utf-8')
    
    @staticmethod
    def _generate_config_block(label: str, host: str, key_file: Path) -> str:
        """生成 SSH config 配置块"""
        # 转换为 POSIX 路径格式（SSH config 标准）
        if hasattr(key_file, 'as_posix'):
            key_file_str = key_file.as_posix()
        else:
            key_file_str = str(key_file).replace('\\', '/')
        
        return f"""# {label} - Auto-generated by sshm
Host {label}
  HostName {host}
  User git
  IdentityFile {key_file_str}
  IdentitiesOnly yes

"""


# ============================================================================
# 状态管理器
# ============================================================================

class StateManager:
    """密钥状态管理器"""
    
    def __init__(self, state_file: Path):
        self.state_file = state_file
    
    def read_active_keys(self) -> Dict[str, str]:
        """读取当前激活的密钥状态"""
        if not self.state_file.exists():
            return {}
        
        try:
            data = json.loads(self.state_file.read_text(encoding='utf-8'))
            # 确保标签为小写
            return {k: v.lower() if v else v for k, v in data.items()}
        except (json.JSONDecodeError, IOError):
            return {}
    
    def write_active_key(self, key_type: str, label: str):
        """写入当前激活的密钥状态"""
        state = self.read_active_keys()
        state[key_type] = label.lower()
        self.state_file.write_text(json.dumps(state, indent=2), encoding='utf-8')
    
    def remove_active_key(self, key_type: str):
        """移除指定类型的激活状态"""
        state = self.read_active_keys()
        if key_type in state:
            del state[key_type]
            self.state_file.write_text(json.dumps(state, indent=2), encoding='utf-8')
    
    def update_label(self, old_label: str, new_label: str):
        """更新状态文件中的标签名"""
        state = self.read_active_keys()
        old_label_lower = old_label.lower()
        new_label_lower = new_label.lower()
        
        updated = False
        for key_type, label in state.items():
            if label == old_label_lower:
                state[key_type] = new_label_lower
                updated = True
        
        if updated:
            self.state_file.write_text(json.dumps(state, indent=2), encoding='utf-8')


# ============================================================================
# SSH 密钥管理器（核心类）
# ============================================================================

class SSHKeyManager:
    """SSH 密钥管理器 - 核心业务逻辑"""
    
    def __init__(self, ssh_dir: Optional[Path] = None):
        """初始化管理器
        
        Args:
            ssh_dir: SSH 目录路径，默认为 ~/.ssh
        """
        self.ssh_dir = ssh_dir or Path.home() / '.ssh'
        self.backup_dir = self.ssh_dir / BACKUP_DIR_NAME
        self.config_file = self.ssh_dir / 'config'
        self.state_file = self.ssh_dir / STATE_FILE_NAME
        
        # 初始化子管理器
        self.config_manager = SSHConfigManager(self.config_file)
        self.state_manager = StateManager(self.state_file)
        
        # 确保必要目录存在
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保必要的目录存在"""
        self.ssh_dir.mkdir(mode=0o700, exist_ok=True)
        self.backup_dir.mkdir(mode=0o700, exist_ok=True)
    
    # ------------------------------------------------------------------------
    # 查询操作
    # ------------------------------------------------------------------------
    
    def list_keys(self, show_content: bool = False):
        """列出所有密钥"""
        print_section_header("SSH 密钥管理器 - 密钥列表")
        print(f"\nSSH 目录: {self.ssh_dir}\n")
        
        keys_by_label = self._scan_all_keys()
        active_keys = self.state_manager.read_active_keys()
        
        if not keys_by_label:
            print("⚠️  未找到任何密钥文件")
            print("\n💡 提示: 使用 'sshm add <标签> <邮箱>' 创建新密钥")
            return
        
        # 获取当前激活的标签
        active_labels = set(active_keys.values())
        
        # 按标签排序显示：当前使用 -> default -> 其他（字母序）
        def sort_key(label):
            label_lower = label.lower()
            # 优先级：0=当前使用, 1=default, 2=其他
            if label_lower in active_labels:
                priority = 0
            elif label_lower == 'default':
                priority = 1
            else:
                priority = 2
            return (priority, label_lower)
        
        for label in sorted(keys_by_label.keys(), key=sort_key):
            self._print_key_info(label, keys_by_label[label], 
                               active_keys, show_content)
        
        print_separator()
        print("💡 提示: 使用 'switch <label>' 切换默认密钥")
        print_separator()
    
    def list_backups(self):
        """列出所有备份"""
        print_section_header("备份列表")
        
        backups = sorted(self.backup_dir.glob('backup_*'), 
                        key=lambda x: x.stat().st_mtime, reverse=True)
        
        if not backups:
            print("📭 暂无备份")
            return
        
        for i, backup in enumerate(backups, 1):
            mtime = datetime.fromtimestamp(backup.stat().st_mtime)
            files = list(backup.glob('id_*'))
            print(f"\n[{i}] {backup.name}")
            print(f"    时间: {format_timestamp(mtime)}")
            print(f"    文件数: {len(files)}")
            print(f"    路径: {backup}")
    
    def _scan_all_keys(self) -> Dict[str, List[Dict]]:
        """扫描所有密钥文件"""
        keys_by_label = {}
        key_pattern = get_key_pattern()
        
        for file in self.ssh_dir.glob('id_*'):
            if not file.is_file() or file.name.endswith('.pub'):
                continue
            
            match = key_pattern.match(file.name)
            if not match:
                continue
            
            key_type = match.group(1)
            label = match.group(2)[1:] if match.group(2) else 'default'
            
            pub_file = self.ssh_dir / f"{file.name}.pub"
            key_info = {
                'type': key_type,
                'private': file,
                'public': pub_file,
                'has_pub': pub_file.exists(),
                'size': file.stat().st_size,
                'mtime': datetime.fromtimestamp(file.stat().st_mtime)
            }
            
            if label not in keys_by_label:
                keys_by_label[label] = []
            keys_by_label[label].append(key_info)
        
        return keys_by_label
    
    def _print_key_info(self, label: str, keys: List[Dict], 
                       active_keys: Dict, show_content: bool):
        """打印单个密钥信息"""
        # 判断是否为当前使用的密钥
        is_active = any(active_keys.get(k['type']) == label.lower() 
                       for k in keys)
        
        # 标题
        if is_active:
            icon = "✨"
            status_text = "[当前使用]"
        elif label == 'default':
            icon = "🔑"
            status_text = "[默认]"
        else:
            icon = "🏷️"
            status_text = ""
        
        print(f"\n{icon} {status_text} {label.upper()}")
        print("-" * 70)
        
        # 密钥详情
        for key in keys:
            print(f"  类型: {key['type']}")
            print(f"  私钥: {key['private'].name}")
            print(f"  公钥: {'✅' if key['has_pub'] else '❌'} {key['private'].name}.pub")
            print(f"  大小: {format_size(key['size'])}")
            print(f"  修改: {format_timestamp(key['mtime'])}")
            
            # SSH Config 别名
            hostname = self._get_hostname_for_label(label)
            host_alias = f"{hostname.split('.')[0]}-{label}"
            print(f"  别名: git@{host_alias}:user/repo.git")
            
            # 状态
            if active_keys.get(key['type']) == label.lower():
                print(f"  状态: ⭐ 正在使用（当前默认 {key['type']} 密钥）")
            else:
                print(f"  状态: 💤 未使用")
            
            # 显示公钥内容
            if show_content and key['has_pub']:
                pub_content = key['public'].read_text(encoding='utf-8').strip()
                print(f"\n  📋 公钥内容:\n  {pub_content}\n")
    
    # ------------------------------------------------------------------------
    # 备份操作
    # ------------------------------------------------------------------------
    
    def backup_keys(self, silent: bool = False):
        """备份所有密钥"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f"backup_{timestamp}"
        backup_path.mkdir(mode=0o700, exist_ok=True)
        
        # 备份所有密钥文件
        key_files = list(self.ssh_dir.glob('id_*'))
        backed_up = []
        
        for key_file in key_files:
            if key_file.is_file():
                shutil.copy2(key_file, backup_path / key_file.name)
                backed_up.append(key_file.name)
        
        # 备份状态文件
        if self.state_file.exists():
            shutil.copy2(self.state_file, backup_path / STATE_FILE_NAME)
        
        if not silent:
            print(f"✅ 备份完成: {backup_path}")
            print(f"📦 已备份 {len(backed_up)} 个文件")
        
        return backup_path
    
    # ------------------------------------------------------------------------
    # 密钥创建与删除
    # ------------------------------------------------------------------------
    
    def add_key(self, label: str, email: str, 
                key_type: str = DEFAULT_KEY_TYPE, host: Optional[str] = None):
        """创建新密钥"""
        if key_type not in SUPPORTED_KEY_TYPES:
            print(f"❌ 不支持的密钥类型: {key_type}")
            print(f"   支持的类型: {', '.join(SUPPORTED_KEY_TYPES)}")
            return
        
        # 检查是否已存在
        key_file = self.ssh_dir / f"id_{key_type}.{label}"
        if key_file.exists():
            print(f"❌ 密钥已存在: {key_file.name}")
            return
        
        print(f"🔨 创建新密钥: {label} ({key_type})")
        print(f"📧 邮箱: {email}")
        
        # 生成密钥
        cmd = [
            'ssh-keygen',
            '-t', key_type,
            '-C', email,
            '-f', str(key_file),
            '-N', ''  # 无密码
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"✅ 密钥创建成功: {key_file.name}")
            
            # 更新 SSH config
            if host:
                self.config_manager.update_host(label, host, key_file)
                print(f"✅ SSH config 已更新: Host {label} -> {host}")
            
            # 显示公钥
            pub_file = Path(str(key_file) + '.pub')
            if pub_file.exists():
                pub_key = pub_file.read_text(encoding='utf-8').strip()
                print(f"\n📋 公钥内容:\n{pub_key}\n")
                print("💡 请将公钥添加到 Git 平台（GitHub/GitLab 等）")
        
        except subprocess.CalledProcessError as e:
            print(f"❌ 创建失败: {e}")
        except Exception as e:
            print(f"❌ 错误: {e}")
    
    def remove_key(self, label: str, key_type: Optional[str] = None):
        """删除密钥
        
        Args:
            label: 密钥标签
            key_type: 指定删除的密钥类型，不指定则删除所有类型
        """
        label_lower = label.lower()
        
        # 保护默认密钥
        if label_lower == 'default':
            if key_type:
                confirm_msg = f"⚠️  即将删除默认密钥 ({key_type})，是否继续？"
            else:
                confirm_msg = "⚠️  即将删除所有默认密钥，是否继续？"
            
            if not prompt_confirm(confirm_msg):
                print("❌ 操作已取消")
                return
        
        # 查找并删除密钥文件
        removed_files = []
        
        # 特殊处理 default 标签：删除无后缀的默认密钥
        if label_lower == 'default':
            if key_type:
                # 只删除指定类型的默认密钥
                patterns = [f"id_{key_type}", f"id_{key_type}.pub"]
            else:
                # 删除所有类型的默认密钥
                patterns = ["id_ed25519", "id_ed25519.pub", 
                          "id_rsa", "id_rsa.pub",
                          "id_ecdsa", "id_ecdsa.pub",
                          "id_dsa", "id_dsa.pub"]
            
            for pattern in patterns:
                file = self.ssh_dir / pattern
                if file.exists() and file.is_file():
                    # 备份
                    if not removed_files:  # 只备份一次
                        backup_path = self.backup_keys(silent=True)
                        print(f"💾 已自动备份到: {backup_path}")
                    
                    # 删除
                    file.unlink()
                    removed_files.append(file.name)
        else:
            # 普通标签：删除带后缀的密钥
            if key_type:
                # 只删除指定类型
                patterns = [f"id_{key_type}.{label}", f"id_{key_type}.{label}.pub"]
            else:
                # 删除所有类型
                patterns = [f"id_*.{label}", f"id_*.{label}.pub"]
            
            for pattern in patterns:
                for file in self.ssh_dir.glob(pattern):
                    if file.is_file():
                        # 备份
                        if not removed_files:  # 只备份一次
                            backup_path = self.backup_keys(silent=True)
                            print(f"💾 已自动备份到: {backup_path}")
                        
                        # 删除
                        file.unlink()
                        removed_files.append(file.name)
        
        if removed_files:
            print(f"✅ 已删除 {len(removed_files)} 个文件:")
            for f in removed_files:
                print(f"   - {f}")
            
            # 清理 SSH config 别名（根据标签推断所有可能的别名）
            self._remove_ssh_config_alias(label)
            
            # 清理状态
            key_type = self._detect_key_type_for_label(label)
            if key_type:
                active_keys = self.state_manager.read_active_keys()
                if active_keys.get(key_type) == label_lower:
                    self.state_manager.remove_active_key(key_type)
        else:
            print(f"⚠️  未找到密钥: {label}")
    
    # ------------------------------------------------------------------------
    # 密钥切换
    # ------------------------------------------------------------------------
    
    def switch_key(self, label: str, key_type: Optional[str] = None):
        """切换默认密钥"""
        label_lower = label.lower()
        
        # 自动检测密钥类型
        if not key_type:
            key_type = self._detect_key_type_for_label(label)
            if not key_type:
                print(f"❌ 未找到标签 '{label}' 的密钥")
                return
            print(f"🔍 自动检测到密钥类型: {key_type}")
        
        source_file = self.ssh_dir / f"id_{key_type}.{label}"
        target_file = self.ssh_dir / f"id_{key_type}"
        
        if not source_file.exists():
            print(f"❌ 密钥不存在: {source_file.name}")
            return
        
        # 备份当前默认密钥
        if target_file.exists():
            active_keys = self.state_manager.read_active_keys()
            current_label = active_keys.get(key_type, 'original')
            
            # 如果没有 .original 备份，则创建
            original_backup = self.ssh_dir / f"id_{key_type}.original"
            if not original_backup.exists():
                shutil.copy2(target_file, original_backup)
                shutil.copy2(f"{target_file}.pub", f"{original_backup}.pub")
                print(f"💾 原始密钥已备份为: {original_backup.name}")
            
            # 备份当前密钥（如果不是 original）
            if current_label != 'original':
                backup_file = self.ssh_dir / f"id_{key_type}.{current_label}"
                if not backup_file.exists():
                    shutil.copy2(target_file, backup_file)
                    shutil.copy2(f"{target_file}.pub", f"{backup_file}.pub")
        
        # 切换密钥
        shutil.copy2(source_file, target_file)
        shutil.copy2(f"{source_file}.pub", f"{target_file}.pub")
        
        # 更新状态
        self.state_manager.write_active_key(key_type, label)
        
        # 自动更新 SSH config 别名
        self._update_ssh_config_alias(label, source_file)
        
        print(f"✅ 已切换到密钥: {label} ({key_type})")
        print(f"📁 文件: {target_file.name}")
    
    def tag_key(self, key_type: str, new_label: str, 
                switch_after: bool = False):
        """给默认密钥添加标签"""
        if not key_type:
            key_type = self._detect_default_key_type()
            if not key_type:
                print("❌ 未找到默认密钥")
                return
        
        source_file = self.ssh_dir / f"id_{key_type}"
        target_file = self.ssh_dir / f"id_{key_type}.{new_label}"
        
        if not source_file.exists():
            print(f"❌ 默认密钥不存在: {source_file.name}")
            return
        
        if target_file.exists():
            print(f"⚠️  标签已存在: {new_label}")
            if not prompt_confirm("是否覆盖？"):
                return
        
        # 复制密钥
        shutil.copy2(source_file, target_file)
        shutil.copy2(f"{source_file}.pub", f"{target_file}.pub")
        
        print(f"✅ 已添加标签: {new_label} ({key_type})")
        
        # 是否立即切换
        if switch_after:
            self.switch_key(new_label, key_type)
    
    def rename_tag(self, old_label: str, new_label: str, 
                   key_type: str = DEFAULT_KEY_TYPE):
        """重命名密钥标签"""
        old_label_lower = old_label.lower()
        new_label_lower = new_label.lower()
        
        if old_label_lower == 'default':
            print("❌ 不能重命名 default 标签")
            return
        
        # 检测密钥类型
        detected_type = self._detect_key_type_for_label(old_label)
        if detected_type:
            key_type = detected_type
        
        old_file = self.ssh_dir / f"id_{key_type}.{old_label}"
        new_file = self.ssh_dir / f"id_{key_type}.{new_label}"
        
        if not old_file.exists():
            print(f"❌ 密钥不存在: {old_file.name}")
            return
        
        if new_file.exists():
            print(f"⚠️  目标标签已存在: {new_label}")
            return
        
        # 重命名文件
        old_file.rename(new_file)
        Path(f"{old_file}.pub").rename(Path(f"{new_file}.pub"))
        
        # 更新 SSH config 别名
        self._rename_ssh_config_alias(old_label, new_label, new_file)
        
        # 更新状态
        self.state_manager.update_label(old_label, new_label)
        
        print(f"✅ 已重命名: {old_label} -> {new_label}")
    
    def use_key_for_repo(self, label: str, repo_path: str = '.', 
                         skip_confirm: bool = False):
        """为指定 Git 仓库配置使用特定密钥
        
        Args:
            label: 密钥标签
            repo_path: Git 仓库路径
            skip_confirm: 是否跳过确认
        """
        repo_path = Path(repo_path).resolve()
        
        # 检查是否是 Git 仓库
        git_dir = repo_path / '.git'
        if not git_dir.exists():
            print(f"❌ 不是 Git 仓库: {repo_path}")
            print("   请在 Git 仓库目录下执行此命令")
            return
        
        # 检查密钥是否存在
        key_type = self._detect_key_type_for_label(label)
        if not key_type:
            print(f"❌ 未找到标签 '{label}' 的密钥")
            return
        
        print_section_header(f"为 Git 仓库配置密钥: {label}")
        print(f"📂 仓库路径: {repo_path}\n")
        
        try:
            # 获取当前 remote URL
            result = subprocess.run(
                ['git', '-C', str(repo_path), 'remote', 'get-url', 'origin'],
                capture_output=True,
                text=True,
                check=True
            )
            current_url = result.stdout.strip()
            print(f"🔗 当前 Remote URL:\n   {current_url}\n")
            
            # 解析 URL
            parsed = self._parse_git_url(current_url)
            if not parsed:
                print("❌ 无法解析 Git URL")
                return
            
            platform, user, repo = parsed
            print(f"📊 解析信息:")
            print(f"   平台: {platform}")
            print(f"   用户/组织: {user}")
            print(f"   仓库: {repo}\n")
            
            # 生成新的 SSH URL
            hostname = self._get_hostname_for_label(label)
            host_alias = f"{hostname.split('.')[0]}-{label}"
            new_url = f"git@{host_alias}:{user}/{repo}.git"
            
            print(f"🔧 新的 Remote URL:")
            print(f"   {new_url}\n")
            
            # 确认
            if not skip_confirm:
                if not prompt_confirm("是否更新 Remote URL？"):
                    print("❌ 操作已取消")
                    return
            
            # 更新 remote URL
            subprocess.run(
                ['git', '-C', str(repo_path), 'remote', 'set-url', 'origin', new_url],
                check=True
            )
            print("✅ Remote URL 已更新\n")
            
            # 测试连接
            print("🧪 测试 SSH 连接...")
            test_result = subprocess.run(
                ['ssh', '-T', f'git@{host_alias}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # 显示测试结果
            output = test_result.stderr + test_result.stdout
            if 'successfully authenticated' in output.lower() or \
               'you\'ve successfully authenticated' in output.lower():
                print("✅ SSH 连接测试成功！")
                # 提取认证信息
                for line in output.split('\n'):
                    if 'Hi' in line or 'Welcome' in line:
                        print(f"   {line.strip()}")
            else:
                print("⚠️  SSH 连接测试:")
                print(f"   {output.strip()}")
            
            print("\n" + "=" * 70)
            print("✅ 配置完成！现在可以使用以下命令:")
            print(f"   cd {repo_path}")
            print(f"   git push")
            print("=" * 70)
            
        except subprocess.CalledProcessError as e:
            if 'No such remote' in str(e.stderr):
                print("❌ 未找到 origin remote")
                print("   请先添加 remote: git remote add origin <url>")
            else:
                print(f"❌ Git 命令执行失败: {e}")
        except subprocess.TimeoutExpired:
            print("⚠️  SSH 连接测试超时")
        except Exception as e:
            print(f"❌ 错误: {e}")
    
    def show_repo_info(self, repo_path: str = '.'):
        """显示当前 Git 仓库的 SSH 配置信息"""
        print_section_header("Git 仓库配置信息")
        
        repo_path = Path(repo_path).resolve()
        
        # 检查是否是 Git 仓库
        if not (repo_path / '.git').exists():
            print(f"❌ 不是有效的 Git 仓库: {repo_path}")
            return
        
        print(f"📂 仓库路径: {repo_path}")
        
        try:
            # 获取 remote URL
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            remote_url = result.stdout.strip()
            print(f"🔗 Remote URL: {remote_url}")
            
            # 解析 URL
            parsed = self._parse_git_url(remote_url)
            if parsed:
                platform, user, repo = parsed
                print(f"\n📊 解析信息:")
                print(f"  ├─ 平台: {platform}")
                print(f"  ├─ 用户/组织: {user}")
                print(f"  └─ 仓库: {repo}")
                
                # 检测使用的别名
                ssh_pattern = r'git@([^:]+):'
                match = re.match(ssh_pattern, remote_url)
                if match:
                    host_alias = match.group(1)
                    if '-' in host_alias:  # 是 SSH config 别名
                        label = host_alias.split('-', 1)[1]
                        print(f"\n🔑 当前使用别名: {host_alias}")
                        
                        # 查找对应的密钥信息
                        key_type = self._detect_key_type_for_label(label)
                        if key_type:
                            key_file = self.ssh_dir / f"id_{key_type}.{label}"
                            pub_file = self.ssh_dir / f"id_{key_type}.{label}.pub"
                            
                            print(f"\n🗝️  密钥信息:")
                            print(f"  ├─ 标签: {label}")
                            print(f"  ├─ 类型: {key_type}")
                            print(f"  ├─ 私钥: {key_file}")
                            print(f"  └─ 公钥: {pub_file}")
                            
                            # 显示 SSH config
                            ssh_config = self.config_manager.config_file
                            if ssh_config.exists():
                                with open(ssh_config, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                    if f"Host {host_alias}" in content:
                                        print(f"\n📝 SSH Config:")
                                        lines = content.split('\n')
                                        in_host = False
                                        for line in lines:
                                            if f"Host {host_alias}" in line:
                                                in_host = True
                                            if in_host:
                                                print(f"  {line}")
                                                if line.strip() and not line.startswith(' ') and not line.startswith('\t') and not f"Host {host_alias}" in line:
                                                    break
                        else:
                            print(f"\n⚠️  未找到标签 '{label}' 对应的密钥文件")
                    else:
                        print(f"\n💡 提示: 当前使用标准 SSH URL，未配置 SSH config 别名")
                        print(f"   可以使用 'sshm use <标签>' 配置密钥")
                else:
                    print(f"\n💡 提示: 使用的是 HTTPS URL")
                    print(f"   可以使用 'sshm use <标签>' 转换为 SSH 并配置密钥")
            else:
                print("\n⚠️  无法解析 remote URL")
                
        except subprocess.CalledProcessError as e:
            if 'No such remote' in str(e.stderr):
                print("\n⚠️  未配置 origin remote")
            else:
                print(f"\n❌ Git 命令执行失败: {e}")
        except Exception as e:
            print(f"\n❌ 错误: {e}")
    
    def test_connection(self, label: Optional[str] = None, test_all: bool = False, 
                       repo_path: str = '.'):
        """测试 SSH 连接
        
        Args:
            label: 指定测试的密钥标签（None 表示测试当前仓库配置）
            test_all: 是否测试所有密钥
            repo_path: Git 仓库路径（当 label 为 None 时使用）
        """
        if test_all:
            # 测试所有密钥
            print_section_header("测试所有 SSH 密钥连接")
            
            # 获取所有密钥
            keys_by_label = self._scan_all_keys()
            if not keys_by_label:
                print("❌ 未找到任何密钥")
                return
            
            results = []
            for label, key_infos in keys_by_label.items():
                # 推断平台和主机别名
                platform = self._get_hostname_for_label(label).split('.')[0]
                host_alias = f"{platform}-{label}"
                
                # 测试连接
                result = self._test_ssh_connection(host_alias)
                key_types = ', '.join([k['type'] for k in key_infos])
                results.append((label, host_alias, key_types, result))
            
            # 显示结果
            print("\n" + "=" * 70)
            print("测试结果汇总:")
            print("=" * 70)
            for label, host_alias, key_types, (success, message) in results:
                status = "✅" if success else "❌"
                print(f"{status} {label:20} ({host_alias:30}) [{key_types}]")
                if not success:
                    print(f"    {message}")
            
        elif label:
            # 测试指定标签
            print_section_header(f"测试 SSH 连接: {label}")
            
            # 检查密钥是否存在
            key_type = self._detect_key_type_for_label(label)
            if not key_type:
                print(f"❌ 未找到标签 '{label}' 对应的密钥")
                print(f"\n💡 使用 'sshm list' 查看所有可用密钥")
                return
            
            # 推断平台和主机别名
            platform = self._get_hostname_for_label(label).split('.')[0]
            host_alias = f"{platform}-{label}"
            
            print(f"🔑 密钥: {label}")
            print(f"🌐 主机: {host_alias}")
            print(f"\n🧪 正在测试连接...")
            
            success, message = self._test_ssh_connection(host_alias)
            if success:
                print(f"✅ {message}")
            else:
                print(f"❌ {message}")
        
        else:
            # 测试当前仓库配置
            print_section_header("测试当前仓库 SSH 连接")
            
            repo_path = Path(repo_path).resolve()
            
            # 检查是否是 Git 仓库
            if not (repo_path / '.git').exists():
                print(f"❌ 不是有效的 Git 仓库: {repo_path}")
                return
            
            print(f"📂 仓库路径: {repo_path}")
            
            try:
                # 获取 remote URL
                result = subprocess.run(
                    ['git', 'remote', 'get-url', 'origin'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=True
                )
                remote_url = result.stdout.strip()
                print(f"🔗 Remote URL: {remote_url}")
                
                # 提取主机别名
                ssh_pattern = r'git@([^:]+):'
                match = re.match(ssh_pattern, remote_url)
                if match:
                    host_alias = match.group(1)
                    print(f"\n🧪 正在测试 {host_alias}...")
                    
                    success, message = self._test_ssh_connection(host_alias)
                    if success:
                        print(f"✅ {message}")
                    else:
                        print(f"❌ {message}")
                        print(f"\n💡 提示: 请检查密钥配置是否正确")
                        print(f"   使用 'sshm info' 查看配置详情")
                else:
                    print("\n⚠️  当前使用的不是 SSH URL，无法测试连接")
                    print("   使用 'sshm use <标签>' 转换为 SSH URL")
                    
            except subprocess.CalledProcessError as e:
                if 'No such remote' in str(e.stderr):
                    print("\n⚠️  未配置 origin remote")
                else:
                    print(f"\n❌ Git 命令执行失败: {e}")
            except Exception as e:
                print(f"\n❌ 错误: {e}")
    
    def _test_ssh_connection(self, host: str) -> Tuple[bool, str]:
        """测试 SSH 连接
        
        Args:
            host: SSH 主机（如 github-personal, gitlab-work）
        
        Returns:
            (success, message) - 成功标志和消息
        """
        try:
            result = subprocess.run(
                ['ssh', '-T', f'git@{host}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            output = result.stdout + result.stderr
            
            # GitHub/GitLab 等会返回特定消息
            if 'successfully authenticated' in output.lower():
                # 提取用户名
                match = re.search(r'Hi ([^!]+)!', output)
                username = match.group(1) if match else 'User'
                return (True, f"认证成功! (Hi {username}!)")
            elif 'welcome to' in output.lower():
                return (True, "连接成功!")
            elif result.returncode == 1 and 'permission denied' not in output.lower():
                # 有些服务器会返回退出码 1 但认证成功
                return (True, "连接成功!")
            else:
                return (False, f"连接失败: {output.strip()[:100]}")
                
        except subprocess.TimeoutExpired:
            return (False, "连接超时")
        except FileNotFoundError:
            return (False, "未找到 ssh 命令")
        except Exception as e:
            return (False, f"错误: {str(e)}")
    
    def _parse_git_url(self, url: str) -> Optional[Tuple[str, str, str]]:
        """解析 Git URL
        
        Returns:
            (platform, user, repo) 或 None
        """
        # SSH 格式: git@github.com:user/repo.git 或 git@github-label:user/repo.git
        ssh_pattern = r'git@([^:]+):([^/]+)/(.+?)(?:\.git)?$'
        match = re.match(ssh_pattern, url)
        if match:
            hostname, user, repo = match.groups()
            # 提取平台名称（去除可能的标签后缀）
            # github-365tools -> github
            # github.com -> github
            if '-' in hostname:
                platform = hostname.split('-')[0]
            else:
                platform = hostname.split('.')[0]
            return (platform, user, repo)
        
        # HTTPS 格式: https://github.com/user/repo.git
        https_pattern = r'https?://([^/]+)/([^/]+)/(.+?)(?:\.git)?$'
        match = re.match(https_pattern, url)
        if match:
            hostname, user, repo = match.groups()
            platform = hostname.split('.')[0]
            return (platform, user, repo)
        
        return None
    
    # ------------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------------
    
    def _detect_key_type_for_label(self, label: str) -> Optional[str]:
        """检测指定标签的密钥类型"""
        for key_type in SUPPORTED_KEY_TYPES:
            key_file = self.ssh_dir / f"id_{key_type}.{label}"
            if key_file.exists():
                return key_type
        return None
    
    def _detect_default_key_type(self) -> Optional[str]:
        """检测默认密钥类型"""
        for key_type in SUPPORTED_KEY_TYPES:
            key_file = self.ssh_dir / f"id_{key_type}"
            if key_file.exists():
                return key_type
        return None
    
    def _get_hostname_for_label(self, label: str) -> str:
        """根据标签推断主机名"""
        hostname_map = {
            'github': 'github.com',
            'gitlab': 'gitlab.com',
            'gitee': 'gitee.com',
            'bitbucket': 'bitbucket.org',
        }
        
        label_lower = label.lower()
        for key, host in hostname_map.items():
            if key in label_lower:
                return host
        return 'github.com'  # 默认
    
    def _update_ssh_config_alias(self, label: str, key_file: Path):
        """自动更新 SSH config 别名配置
        
        Args:
            label: 密钥标签（如 github、work）
            key_file: 密钥文件路径（如 id_rsa.github）
        
        示例生成配置：
            Host github-github
                HostName github.com
                User git
                IdentityFile ~/.ssh/id_rsa.github
        """
        hostname = self._get_hostname_for_label(label)
        host_alias = f"{hostname.split('.')[0]}-{label}"
        
        # 更新配置
        self.config_manager.update_host(host_alias, hostname, key_file.resolve())
        print(f"📝 SSH 配置别名: {host_alias} → {hostname}")
        print(f"   使用方式: git@{host_alias}:user/repo.git")
    
    def _remove_ssh_config_alias(self, label: str):
        """删除 SSH config 别名配置
        
        Args:
            label: 密钥标签（如 github、work）
        """
        hostname = self._get_hostname_for_label(label)
        host_alias = f"{hostname.split('.')[0]}-{label}"
        
        # 删除配置
        self.config_manager.remove_host(host_alias)
        print(f"🗑️  已删除 SSH 配置别名: {host_alias}")
    
    def _rename_ssh_config_alias(self, old_label: str, new_label: str, new_key_file: Path):
        """重命名 SSH config 别名配置
        
        Args:
            old_label: 旧标签（如 github）
            new_label: 新标签（如 work）
            new_key_file: 新密钥文件路径
        """
        # 删除旧别名
        old_hostname = self._get_hostname_for_label(old_label)
        old_alias = f"{old_hostname.split('.')[0]}-{old_label}"
        self.config_manager.remove_host(old_alias)
        
        # 创建新别名
        new_hostname = self._get_hostname_for_label(new_label)
        new_alias = f"{new_hostname.split('.')[0]}-{new_label}"
        self.config_manager.update_host(new_alias, new_hostname, new_key_file.resolve())
        
        print(f"📝 SSH 配置别名已更新: {old_alias} → {new_alias}")


# ============================================================================
# 交互式菜单
# ============================================================================

def show_interactive_menu():
    """显示交互式菜单（双击运行时）"""
    print_section_header("🔑 SSH Key Manager - 交互式菜单")
    print("\n欢迎使用 SSH 密钥管理器！\n")
    print("这是一个命令行工具，需要配合命令使用。")
    print("\n常用命令：")
    print("  sshm list              - 查看所有密钥")
    print("  sshm add <标签> <邮箱>  - 创建新密钥")
    print("  sshm switch <标签>     - 切换默认密钥")
    print("  sshm --help            - 查看完整帮助")
    print_separator()
    
    manager = SSHKeyManager()
    
    while True:
        print("\n请选择操作：")
        print("  [1] 查看当前所有密钥")
        print("  [2] 查看密钥详情（含公钥）")
        print("  [3] 查看备份列表")
        print("  [4] 添加到环境变量（PATH）")
        print("  [5] 查看完整帮助")
        print("  [Q] 退出")
        
        print("\n请输入选项: ", end='', flush=True)
        
        # 读取输入
        if sys.platform == 'win32':
            try:
                import msvcrt
                choice = msvcrt.getch().decode('utf-8', errors='ignore').upper()
                print(choice)
            except:
                choice = input().upper()
        else:
            choice = input().upper()
        
        print()
        
        # 处理选项
        if choice == '1':
            manager.list_keys(show_content=False)
            _wait_for_key()
        elif choice == '2':
            manager.list_keys(show_content=True)
            _wait_for_key()
        elif choice == '3':
            manager.list_backups()
            _wait_for_key()
        elif choice == '4':
            add_to_path()
            _wait_for_key()
        elif choice == '5':
            show_help()
            _wait_for_key()
        elif choice == 'Q':
            print("再见！👋")
            break
        else:
            print("⚠️  无效选项，请重新选择")


def _wait_for_key():
    """等待用户按键"""
    print("\n按任意键继续...")
    if sys.platform == 'win32':
        try:
            import msvcrt
            msvcrt.getch()
        except:
            input()
    else:
        input()


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
        exe_path = Path(__file__).resolve()
        exe_dir = exe_path.parent
    
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
        
        # 规范化路径（统一使用正斜杠）
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
            from ctypes import wintypes
            
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
            pass  # 广播失败不影响主要功能


def show_help():
    """显示帮助信息"""
    print(f"""
SSH Key Manager v{VERSION} - 多账号 Git SSH 密钥管理工具

使用方法:
  sshm <command> [options]

命令列表:
  list              查看当前所有 SSH 密钥
  back              备份所有 SSH 密钥
  backups           列出所有备份
  add               创建新的 SSH 密钥（带标签）
  switch            切换默认 SSH 密钥
  remove            删除 SSH 密钥
  tag               给默认密钥添加标签
  rename            重命名密钥标签

示例:
  sshm list                                           # 查看所有密钥
  sshm list -a                                        # 查看所有密钥（含公钥）
  sshm back                                           # 备份所有密钥
  sshm backups                                        # 查看备份列表
  sshm add github email@example.com -H github.com     # 创建 github 密钥
  sshm add work work@company.com -t rsa               # 创建 RSA 密钥
  sshm switch github                                  # 切换到 github 密钥
  sshm tag backup                                     # 备份当前密钥为 backup
  sshm tag original --switch                          # 备份并切换
  sshm rename github gh                               # 重命名标签
  sshm remove oldkey                                  # 删除密钥

详细帮助: sshm <command> --help
项目主页: https://github.com/yourusername/SSHManager
""")


# ============================================================================
# 命令行参数解析
# ============================================================================

def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog='sshm',
        description=f'SSH Key Manager v{VERSION} - 多账号 Git SSH 密钥管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  sshm list                                           # 查看所有密钥
  sshm add github email@example.com                   # 创建 github 密钥
  sshm switch github                                  # 切换到 github 密钥
  sshm use github                                     # 为当前仓库配置使用 github 密钥
  sshm use work -p ~/project                          # 为指定仓库配置使用 work 密钥
  sshm info                                           # 查看当前仓库配置信息
  sshm test                                           # 测试当前仓库 SSH 连接
  sshm test github                                    # 测试指定密钥连接
  sshm test --all                                     # 测试所有密钥连接
  sshm --help                                         # 查看完整帮助
"""
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # list 命令
    list_parser = subparsers.add_parser('list', help='查看当前所有 SSH 密钥')
    list_parser.add_argument('-a', '--all', action='store_true',
                            help='显示公钥内容')
    
    # back 命令
    subparsers.add_parser('back', help='备份所有 SSH 密钥')
    
    # backups 命令
    subparsers.add_parser('backups', help='列出所有备份')
    
    # add 命令
    add_parser = subparsers.add_parser('add', help='创建新的 SSH 密钥')
    add_parser.add_argument('label', help='密钥标签')
    add_parser.add_argument('email', help='邮箱地址')
    add_parser.add_argument('-t', '--type', choices=SUPPORTED_KEY_TYPES,
                          default=DEFAULT_KEY_TYPE, help='密钥类型')
    add_parser.add_argument('-H', '--host', help='主机名（用于 SSH config）')
    
    # switch 命令
    switch_parser = subparsers.add_parser('switch', help='切换默认 SSH 密钥')
    switch_parser.add_argument('label', help='密钥标签')
    switch_parser.add_argument('-t', '--type', choices=SUPPORTED_KEY_TYPES,
                              help='密钥类型（默认自动检测）')
    
    # remove 命令
    remove_parser = subparsers.add_parser('remove', help='删除 SSH 密钥')
    remove_parser.add_argument('label', help='密钥标签')
    remove_parser.add_argument('-t', '--type', choices=SUPPORTED_KEY_TYPES,
                              help='指定删除的密钥类型（默认删除所有类型）')
    
    # tag 命令
    tag_parser = subparsers.add_parser('tag', help='给默认密钥添加标签')
    tag_parser.add_argument('label', help='新标签名')
    tag_parser.add_argument('-t', '--type', choices=SUPPORTED_KEY_TYPES,
                          help='密钥类型（默认自动检测）')
    tag_parser.add_argument('-s', '--switch', action='store_true',
                          help='打标签后立即切换')
    
    # rename 命令
    rename_parser = subparsers.add_parser('rename', help='重命名密钥标签')
    rename_parser.add_argument('old_label', help='旧标签名')
    rename_parser.add_argument('new_label', help='新标签名')
    rename_parser.add_argument('-t', '--type', choices=SUPPORTED_KEY_TYPES,
                             default=DEFAULT_KEY_TYPE, help='密钥类型')
    
    # use 命令
    use_parser = subparsers.add_parser('use', help='为当前 Git 仓库配置指定密钥')
    use_parser.add_argument('label', help='密钥标签')
    use_parser.add_argument('-p', '--path', default='.', 
                          help='Git 仓库路径（默认当前目录）')
    use_parser.add_argument('-y', '--yes', action='store_true',
                          help='跳过确认直接执行')
    
    # info 命令
    info_parser = subparsers.add_parser('info', help='显示 Git 仓库配置信息')
    info_parser.add_argument('-p', '--path', default='.', 
                           help='Git 仓库路径（默认当前目录）')
    
    # test 命令
    test_parser = subparsers.add_parser('test', help='测试 SSH 连接')
    test_parser.add_argument('label', nargs='?', 
                           help='密钥标签（不指定则测试当前仓库配置）')
    test_parser.add_argument('-p', '--path', default='.', 
                           help='Git 仓库路径（默认当前目录）')
    test_parser.add_argument('-a', '--all', action='store_true',
                           help='测试所有密钥')
    
    return parser


# ============================================================================
# 主函数
# ============================================================================

def main():
    """主函数入口"""
    # 检测双击运行（无参数）
    if len(sys.argv) == 1:
        show_interactive_menu()
        return
    
    # 解析命令行参数
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 创建管理器实例
    manager = SSHKeyManager()
    
    # 路由到对应的命令处理函数
    try:
        if args.command == 'list':
            manager.list_keys(show_content=args.all)
        
        elif args.command == 'back':
            manager.backup_keys()
        
        elif args.command == 'backups':
            manager.list_backups()
        
        elif args.command == 'add':
            manager.add_key(args.label, args.email, args.type, args.host)
        
        elif args.command == 'switch':
            manager.switch_key(args.label, args.type)
        
        elif args.command == 'remove':
            manager.remove_key(args.label, args.type)
        
        elif args.command == 'tag':
            manager.tag_key(args.type, args.label, args.switch)
        
        elif args.command == 'rename':
            manager.rename_tag(args.old_label, args.new_label, args.type)
        
        elif args.command == 'use':
            manager.use_key_for_repo(args.label, args.path, args.yes)
        
        elif args.command == 'info':
            manager.show_repo_info(args.path)
        
        elif args.command == 'test':
            manager.test_connection(args.label, args.all, args.path)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)


# ============================================================================
# 程序入口
# ============================================================================

if __name__ == '__main__':
    main()
