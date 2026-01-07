#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSH 密钥管理器 - 核心业务逻辑
"""

import re
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from ..constants import (
    SUPPORTED_KEY_TYPES,
    DEFAULT_KEY_TYPE,
    BACKUP_DIR_NAME,
    STATE_FILE_NAME
)
from ..utils import (
    get_key_pattern,
    format_timestamp,
    format_size,
    prompt_confirm,
    print_separator,
    print_section_header
)
from .config import SSHConfigManager
from .state import StateManager


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
        
        # 按标签排序显示
        def sort_key(label):
            label_lower = label.lower()
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
        is_active = any(active_keys.get(k['type']) == label.lower() 
                       for k in keys)
        
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
        
        for key in keys:
            print(f"  类型: {key['type']}")
            print(f"  私钥: {key['private'].name}")
            print(f"  公钥: {'✅' if key['has_pub'] else '❌'} {key['private'].name}.pub")
            print(f"  大小: {format_size(key['size'])}")
            print(f"  修改: {format_timestamp(key['mtime'])}")
            
            hostname = self._get_hostname_for_label(label)
            host_alias = f"{hostname.split('.')[0]}-{label}"
            print(f"  别名: git@{host_alias}:user/repo.git")
            
            if active_keys.get(key['type']) == label.lower():
                print(f"  状态: ⭐ 正在使用（当前默认 {key['type']} 密钥）")
            else:
                print(f"  状态: 💤 未使用")
            
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
        
        key_files = list(self.ssh_dir.glob('id_*'))
        backed_up = []
        
        for key_file in key_files:
            if key_file.is_file():
                shutil.copy2(key_file, backup_path / key_file.name)
                backed_up.append(key_file.name)
        
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
        
        key_file = self.ssh_dir / f"id_{key_type}.{label}"
        if key_file.exists():
            print(f"❌ 密钥已存在: {key_file.name}")
            return
        
        print(f"🔨 创建新密钥: {label} ({key_type})")
        print(f"📧 邮箱: {email}")
        
        cmd = [
            'ssh-keygen',
            '-t', key_type,
            '-C', email,
            '-f', str(key_file),
            '-N', ''
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"✅ 密钥创建成功: {key_file.name}")
            
            if host:
                self.config_manager.update_host(label, host, key_file)
                print(f"✅ SSH config 已更新: Host {label} -> {host}")
            
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
        """删除密钥"""
        label_lower = label.lower()
        
        if label_lower == 'default':
            if key_type:
                confirm_msg = f"⚠️  即将删除默认密钥 ({key_type})，是否继续？"
            else:
                confirm_msg = "⚠️  即将删除所有默认密钥，是否继续？"
            
            if not prompt_confirm(confirm_msg):
                print("❌ 操作已取消")
                return
        
        removed_files = []
        
        if label_lower == 'default':
            if key_type:
                patterns = [f"id_{key_type}", f"id_{key_type}.pub"]
            else:
                patterns = ["id_ed25519", "id_ed25519.pub", 
                          "id_rsa", "id_rsa.pub",
                          "id_ecdsa", "id_ecdsa.pub",
                          "id_dsa", "id_dsa.pub"]
            
            for pattern in patterns:
                file = self.ssh_dir / pattern
                if file.exists() and file.is_file():
                    if not removed_files:
                        backup_path = self.backup_keys(silent=True)
                        print(f"💾 已自动备份到: {backup_path}")
                    
                    file.unlink()
                    removed_files.append(file.name)
        else:
            if key_type:
                patterns = [f"id_{key_type}.{label}", f"id_{key_type}.{label}.pub"]
            else:
                patterns = [f"id_*.{label}", f"id_*.{label}.pub"]
            
            for pattern in patterns:
                for file in self.ssh_dir.glob(pattern):
                    if file.is_file():
                        if not removed_files:
                            backup_path = self.backup_keys(silent=True)
                            print(f"💾 已自动备份到: {backup_path}")
                        
                        file.unlink()
                        removed_files.append(file.name)
        
        if removed_files:
            print(f"✅ 已删除 {len(removed_files)} 个文件:")
            for f in removed_files:
                print(f"   - {f}")
            
            self._remove_ssh_config_alias(label)
            
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
        
        if target_file.exists():
            active_keys = self.state_manager.read_active_keys()
            current_label = active_keys.get(key_type, 'original')
            
            original_backup = self.ssh_dir / f"id_{key_type}.original"
            if not original_backup.exists():
                shutil.copy2(target_file, original_backup)
                shutil.copy2(f"{target_file}.pub", f"{original_backup}.pub")
                print(f"💾 原始密钥已备份为: {original_backup.name}")
            
            if current_label != 'original':
                backup_file = self.ssh_dir / f"id_{key_type}.{current_label}"
                if not backup_file.exists():
                    shutil.copy2(target_file, backup_file)
                    shutil.copy2(f"{target_file}.pub", f"{backup_file}.pub")
        
        shutil.copy2(source_file, target_file)
        shutil.copy2(f"{source_file}.pub", f"{target_file}.pub")
        
        self.state_manager.write_active_key(key_type, label)
        
        self._update_ssh_config_alias(label, source_file)
        
        print(f"✅ 已切换到密钥: {label} ({key_type})")
        print(f"📁 文件: {target_file.name}")
    
    def tag_key(self, key_type: str, new_label: str, switch_after: bool = False):
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
        
        shutil.copy2(source_file, target_file)
        shutil.copy2(f"{source_file}.pub", f"{target_file}.pub")
        
        print(f"✅ 已添加标签: {new_label} ({key_type})")
        
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
        
        old_file.rename(new_file)
        Path(f"{old_file}.pub").rename(Path(f"{new_file}.pub"))
        
        self._rename_ssh_config_alias(old_label, new_label, new_file)
        
        self.state_manager.update_label(old_label, new_label)
        
        print(f"✅ 已重命名: {old_label} -> {new_label}")
    
    # ------------------------------------------------------------------------
    # Git 仓库相关操作 (use, info, test)
    # ------------------------------------------------------------------------
    
    def use_key_for_repo(self, label: str, repo_path: str = '.', 
                         skip_confirm: bool = False):
        """为指定 Git 仓库配置使用特定密钥"""
        repo_path = Path(repo_path).resolve()
        
        if not (repo_path / '.git').exists():
            print(f"❌ 不是 Git 仓库: {repo_path}")
            print("   请在 Git 仓库目录下执行此命令")
            return
        
        key_type = self._detect_key_type_for_label(label)
        if not key_type:
            print(f"❌ 未找到标签 '{label}' 的密钥")
            return
        
        print_section_header(f"为 Git 仓库配置密钥: {label}")
        print(f"📂 仓库路径: {repo_path}\n")
        
        try:
            result = subprocess.run(
                ['git', '-C', str(repo_path), 'remote', 'get-url', 'origin'],
                capture_output=True,
                text=True,
                check=True
            )
            current_url = result.stdout.strip()
            print(f"🔗 当前 Remote URL:\n   {current_url}\n")
            
            parsed = self._parse_git_url(current_url)
            if not parsed:
                print("❌ 无法解析 Git URL")
                return
            
            platform, user, repo = parsed
            print(f"📊 解析信息:")
            print(f"   平台: {platform}")
            print(f"   用户/组织: {user}")
            print(f"   仓库: {repo}\n")
            
            hostname = self._get_hostname_for_label(label)
            host_alias = f"{hostname.split('.')[0]}-{label}"
            new_url = f"git@{host_alias}:{user}/{repo}.git"
            
            print(f"🔧 新的 Remote URL:")
            print(f"   {new_url}\n")
            
            if not skip_confirm:
                if not prompt_confirm("是否更新 Remote URL？"):
                    print("❌ 操作已取消")
                    return
            
            subprocess.run(
                ['git', '-C', str(repo_path), 'remote', 'set-url', 'origin', new_url],
                check=True
            )
            print("✅ Remote URL 已更新\n")
            
            print("🧪 测试 SSH 连接...")
            test_result = subprocess.run(
                ['ssh', '-T', f'git@{host_alias}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            output = test_result.stderr + test_result.stdout
            if 'successfully authenticated' in output.lower() or \
               'you\'ve successfully authenticated' in output.lower():
                print("✅ SSH 连接测试成功！")
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
        
        if not (repo_path / '.git').exists():
            print(f"❌ 不是有效的 Git 仓库: {repo_path}")
            return
        
        print(f"📂 仓库路径: {repo_path}")
        
        try:
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            remote_url = result.stdout.strip()
            print(f"🔗 Remote URL: {remote_url}")
            
            parsed = self._parse_git_url(remote_url)
            if parsed:
                platform, user, repo = parsed
                print(f"\n📊 解析信息:")
                print(f"  ├─ 平台: {platform}")
                print(f"  ├─ 用户/组织: {user}")
                print(f"  └─ 仓库: {repo}")
                
                ssh_pattern = r'git@([^:]+):'
                match = re.match(ssh_pattern, remote_url)
                if match:
                    host_alias = match.group(1)
                    if '-' in host_alias:
                        label = host_alias.split('-', 1)[1]
                        print(f"\n🔑 当前使用别名: {host_alias}")
                        
                        key_type = self._detect_key_type_for_label(label)
                        if key_type:
                            key_file = self.ssh_dir / f"id_{key_type}.{label}"
                            pub_file = self.ssh_dir / f"id_{key_type}.{label}.pub"
                            
                            print(f"\n🗝️  密钥信息:")
                            print(f"  ├─ 标签: {label}")
                            print(f"  ├─ 类型: {key_type}")
                            print(f"  ├─ 私钥: {key_file}")
                            print(f"  └─ 公钥: {pub_file}")
                            
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
        """测试 SSH 连接"""
        if test_all:
            print_section_header("测试所有 SSH 密钥连接")
            
            keys_by_label = self._scan_all_keys()
            if not keys_by_label:
                print("❌ 未找到任何密钥")
                return
            
            results = []
            for label, key_infos in keys_by_label.items():
                platform = self._get_hostname_for_label(label).split('.')[0]
                host_alias = f"{platform}-{label}"
                
                result = self._test_ssh_connection(host_alias)
                key_types = ', '.join([k['type'] for k in key_infos])
                results.append((label, host_alias, key_types, result))
            
            print("\n" + "=" * 70)
            print("测试结果汇总:")
            print("=" * 70)
            for label, host_alias, key_types, (success, message) in results:
                status = "✅" if success else "❌"
                print(f"{status} {label:20} ({host_alias:30}) [{key_types}]")
                if not success:
                    print(f"    {message}")
            
        elif label:
            print_section_header(f"测试 SSH 连接: {label}")
            
            key_type = self._detect_key_type_for_label(label)
            if not key_type:
                print(f"❌ 未找到标签 '{label}' 对应的密钥")
                print(f"\n💡 使用 'sshm list' 查看所有可用密钥")
                return
            
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
            print_section_header("测试当前仓库 SSH 连接")
            
            repo_path = Path(repo_path).resolve()
            
            if not (repo_path / '.git').exists():
                print(f"❌ 不是有效的 Git 仓库: {repo_path}")
                return
            
            print(f"📂 仓库路径: {repo_path}")
            
            try:
                result = subprocess.run(
                    ['git', 'remote', 'get-url', 'origin'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=True
                )
                remote_url = result.stdout.strip()
                print(f"🔗 Remote URL: {remote_url}")
                
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
        """测试 SSH 连接"""
        try:
            result = subprocess.run(
                ['ssh', '-T', f'git@{host}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            output = result.stdout + result.stderr
            
            if 'successfully authenticated' in output.lower():
                match = re.search(r'Hi ([^!]+)!', output)
                username = match.group(1) if match else 'User'
                return (True, f"认证成功! (Hi {username}!)")
            elif 'welcome to' in output.lower():
                return (True, "连接成功!")
            elif result.returncode == 1 and 'permission denied' not in output.lower():
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
        """解析 Git URL"""
        ssh_pattern = r'git@([^:]+):([^/]+)/(.+?)(?:\.git)?$'
        match = re.match(ssh_pattern, url)
        if match:
            hostname, user, repo = match.groups()
            if '-' in hostname:
                platform = hostname.split('-')[0]
            else:
                platform = hostname.split('.')[0]
            return (platform, user, repo)
        
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
        return 'github.com'
    
    def _update_ssh_config_alias(self, label: str, key_file: Path):
        """自动更新 SSH config 别名配置"""
        hostname = self._get_hostname_for_label(label)
        host_alias = f"{hostname.split('.')[0]}-{label}"
        
        self.config_manager.update_host(host_alias, hostname, key_file.resolve())
        print(f"📝 SSH 配置别名: {host_alias} → {hostname}")
        print(f"   使用方式: git@{host_alias}:user/repo.git")
    
    def _remove_ssh_config_alias(self, label: str):
        """删除 SSH config 别名配置"""
        hostname = self._get_hostname_for_label(label)
        host_alias = f"{hostname.split('.')[0]}-{label}"
        
        self.config_manager.remove_host(host_alias)
        print(f"🗑️  已删除 SSH 配置别名: {host_alias}")
    
    def _rename_ssh_config_alias(self, old_label: str, new_label: str, new_key_file: Path):
        """重命名 SSH config 别名配置"""
        old_hostname = self._get_hostname_for_label(old_label)
        old_alias = f"{old_hostname.split('.')[0]}-{old_label}"
        self.config_manager.remove_host(old_alias)
        
        new_hostname = self._get_hostname_for_label(new_label)
        new_alias = f"{new_hostname.split('.')[0]}-{new_label}"
        self.config_manager.update_host(new_alias, new_hostname, new_key_file.resolve())
        
        print(f"📝 SSH 配置别名已更新: {old_alias} → {new_alias}")
