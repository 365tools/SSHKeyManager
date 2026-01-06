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

作者: Your Name
版本: 2.0.0
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

VERSION = "2.0.0"
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
        return f"""# {label} - Auto-generated by sshm
Host {label}
  HostName {host}
  User git
  IdentityFile {key_file}
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
    
    def remove_key(self, label: str):
        """删除密钥"""
        label_lower = label.lower()
        
        # 保护默认密钥
        if label_lower == 'default':
            if not prompt_confirm("⚠️  即将删除默认密钥，是否继续？"):
                print("❌ 操作已取消")
                return
        
        # 查找并删除密钥文件
        removed_files = []
        for pattern in [f"id_*.{label}", f"id_*.{label}.pub"]:
            for file in self.ssh_dir.glob(pattern):
                if file.is_file():
                    # 备份
                    backup_path = self.backup_keys(silent=True)
                    print(f"💾 已自动备份到: {backup_path}")
                    
                    # 删除
                    file.unlink()
                    removed_files.append(file.name)
        
        if removed_files:
            print(f"✅ 已删除 {len(removed_files)} 个文件:")
            for f in removed_files:
                print(f"   - {f}")
            
            # 清理 SSH config
            self.config_manager.remove_host(label)
            
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
        
        # 更新配置
        self.config_manager.rename_host(old_label, new_label)
        self.state_manager.update_label(old_label, new_label)
        
        print(f"✅ 已重命名: {old_label} -> {new_label}")
    
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
        print("  [4] 查看完整帮助")
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
  sshm add github email@example.com -H github.com     # 创建 github 密钥
  sshm switch github                                  # 切换到 github 密钥
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
            manager.remove_key(args.label)
        
        elif args.command == 'tag':
            manager.tag_key(args.type, args.label, args.switch)
        
        elif args.command == 'rename':
            manager.rename_tag(args.old_label, args.new_label, args.type)
    
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
