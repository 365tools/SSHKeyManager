# 开发者文档

> SSH Key Manager v2.0.1 - 开发、构建和维护指南

## 📋 目录

- [项目架构](#项目架构)
- [代码规范](#代码规范)
- [构建指南](#构建指南)
- [使用说明](#使用说明)
- [常见问题](#常见问题)
- [更新日志](#更新日志)

---

## 🏗️ 项目架构

### 核心模块设计

```
ssh_manager.py (890 行)
│
├── 📦 常量定义
│   ├── VERSION = "2.0.1"
│   ├── SUPPORTED_KEY_TYPES = ['ed25519', 'rsa', 'ecdsa', 'dsa']
│   └── 其他配置常量
│
├── 🔧 工具函数
│   ├── setup_windows_console()      # Windows UTF-8 编码修复
│   ├── format_timestamp()           # 时间格式化
│   ├── format_size()                # 文件大小格式化
│   └── print_separator()            # 界面打印工具
│
├── ⚙️ SSHConfigManager
│   ├── update_host()                # 更新 SSH config
│   ├── remove_host()                # 删除配置
│   └── rename_host()                # 重命名配置
│
├── 📊 StateManager
│   ├── read_active_keys()           # 读取状态
│   ├── write_active_key()           # 写入状态
│   └── update_label()               # 更新标签
│
├── 🔑 SSHKeyManager (核心类)
│   ├── list_keys()                  # 查询操作
│   ├── backup_keys()                # 备份操作
│   ├── add_key()                    # 创建密钥
│   ├── switch_key()                 # 切换密钥
│   ├── remove_key()                 # 删除密钥
│   └── rename_tag()                 # 重命名标签
│
├── 🎨 交互式菜单
│   ├── show_interactive_menu()      # 主菜单
│   └── show_help()                  # 帮助信息
│
└── 🚀 主函数
    ├── create_parser()              # 参数解析
    └── main()                       # 程序入口
```

### 设计模式

#### 1. 组合模式 (Composition over Inheritance)
```python
class SSHKeyManager:
    def __init__(self):
        # 组合其他管理器，而非继承
        self.config_manager = SSHConfigManager(self.config_file)
        self.state_manager = StateManager(self.state_file)
```

**优势：**
- 降低耦合度
- 更灵活的功能组合
- 易于测试和 mock

#### 2. 单一职责原则
- `SSHConfigManager` → 只管理 SSH config 文件
- `StateManager` → 只管理状态持久化
- `SSHKeyManager` → 只处理业务逻辑

#### 3. 依赖注入
```python
def __init__(self, ssh_dir: Optional[Path] = None):
    self.ssh_dir = ssh_dir or Path.home() / '.ssh'
```

**优势：**
- 方便单元测试
- 支持自定义 SSH 目录
- 降低硬编码依赖

---

## 📏 代码规范

### PEP 8 合规

```python
# ✅ 好的命名
def list_keys(self, show_content: bool = False) -> None:
    """列出所有密钥"""
    pass

# ❌ 不好的命名
def listKeys(self, showContent: bool = False):
    pass
```

### 类型注解

```python
# ✅ 完整的类型注解
def format_timestamp(dt: datetime) -> str:
    """格式化时间戳"""
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def _scan_all_keys(self) -> Dict[str, List[Dict]]:
    """扫描所有密钥文件"""
    pass
```

### 文档字符串

```python
class SSHKeyManager:
    """SSH 密钥管理器 - 核心业务逻辑
    
    负责管理 SSH 密钥的完整生命周期，包括：
    - 创建和删除密钥
    - 切换默认密钥
    - 标签管理
    - 自动备份
    
    Args:
        ssh_dir: SSH 目录路径，默认为 ~/.ssh
    """
```

---

## 🔨 构建指南

### 本地构建

```bash
# 1. 安装依赖（如需要）
pip install pyinstaller

# 2. 运行构建脚本
python build_local.py

# 3. 输出文件
# dist/sshm.exe        - Windows 可执行文件 (7 MB)
# dist/sshm.bat        - 批处理包装器（自动创建）
```

### GitHub Actions 自动构建

推送标签触发自动构建：

```bash
# 1. 更新版本号（ssh_manager.py）
VERSION = "2.1.0"

# 2. 提交代码
git add .
git commit -m "Release v2.1.0"

# 3. 创建标签
git tag v2.1.0

# 4. 推送（触发 Actions）
git push origin main --tags
```

**构建产物：**
- `sshm-windows-amd64.exe` - Windows 版本
- `sshm-linux-amd64` - Linux 版本
- `sshm-macos-amd64` - macOS 版本

### 构建配置

PyInstaller 参数：
```python
pyinstaller \
  --onefile \              # 单文件打包
  --name sshm \            # 输出文件名
  --console \              # 控制台程序
  --clean \                # 清理缓存
  ssh_manager.py
```

---

## 💡 使用说明

### Windows 编码问题解决方案

#### 问题原因
Windows 控制台默认使用 GBK 编码，导致中文和 emoji 显示乱码。

#### 解决方法

**✅ 正确方式：**

```cmd
# 方式 1: CMD 中直接运行
dist\sshm.exe list

# 方式 2: 使用批处理包装器
dist\sshm.bat list

# 方式 3: PowerShell 中通过 CMD
cmd /c "dist\sshm.exe list"
```

**❌ 错误方式：**

```powershell
# PowerShell 管道会破坏编码
.\dist\sshm.exe list | Select-Object -First 10  # ❌ 乱码
```

#### 技术实现

```python
# Windows 控制台编码修复
if sys.platform == 'win32':
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleOutputCP(65001)  # UTF-8
    kernel32.SetConsoleCP(65001)
    
    # 重新包装 stdout/stderr
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer,
        encoding='utf-8',
        errors='replace',
        line_buffering=True,
        write_through=True
    )
```

### 双击运行（交互式菜单）

#### 功能说明

双击 `sshm.exe` 自动进入交互式菜单：

```
================================================================================
🔑 SSH Key Manager - 交互式菜单
================================================================================

请选择操作：
  [1] 查看当前所有密钥
  [2] 查看密钥详情（含公钥）
  [3] 查看备份列表
  [4] 查看完整帮助
  [Q] 退出
```

#### 技术实现

```python
def main():
    # 检测双击运行（无命令行参数）
    if len(sys.argv) == 1:
        show_interactive_menu()
        return
    
    # 正常命令行模式
    parser = create_parser()
    args = parser.parse_args()
    # ...
```

---

## ❓ 常见问题

### Q1: 构建时提示 "Permission Denied"？

**原因：** exe 文件正在运行

**解决：**
```powershell
# 结束进程后重新构建
taskkill /F /IM sshm.exe
python build_local.py
```

### Q2: PowerShell 中显示乱码？

**原因：** PowerShell 管道会重置编码

**解决：**
```powershell
# 方法 1: 不使用管道
.\dist\sshm.exe list

# 方法 2: 通过 CMD
cmd /c "dist\sshm.exe list"

# 方法 3: 使用批处理
.\dist\sshm.bat list
```

### Q3: 如何添加新功能？

遵循单一职责原则：

1. **新增配置管理** → 创建新的 Manager 类
2. **新增命令** → 在 `create_parser()` 中添加子命令
3. **新增工具函数** → 添加到工具函数区块

### Q4: 如何运行单元测试？

```python
# 使用依赖注入的设计，易于测试
def test_list_keys():
    temp_dir = Path('/tmp/test_ssh')
    manager = SSHKeyManager(ssh_dir=temp_dir)
    manager.list_keys()
```

---

## 📝 更新日志

### v2.0.0 (2026-01-07)

#### 🎉 重大重构
- ✅ 完全模块化重构（从 1094 行优化到 890 行）
- ✅ 引入 3 个独立管理器类（SSHConfigManager、StateManager、SSHKeyManager）
- ✅ 完整的类型注解和文档字符串
- ✅ 应用组合模式和单一职责原则

#### 🚀 新功能
- ✅ 交互式菜单（双击运行）
- ✅ Windows UTF-8 编码自动修复
- ✅ 批处理包装器自动生成
- ✅ 当前使用的密钥置顶显示

#### 🐛 问题修复
- ✅ 修复 Windows 控制台乱码问题
- ✅ 修复 PowerShell 管道编码问题
- ✅ 修复双击闪退问题
- ✅ 修复排序逻辑（当前密钥置顶）

#### 📚 文档改进
- ✅ 整合所有文档到 DEVELOPER.md
- ✅ 专业化 README.md
- ✅ 详细的架构说明

### v1.0.0 (2026-01-06)
- 初始版本
- 基础密钥管理功能

---

## 🎯 最佳实践总结

### 代码质量
1. ✅ 遵循 PEP 8 规范
2. ✅ 完整的类型注解
3. ✅ 详细的文档字符串
4. ✅ 单一职责原则
5. ✅ 组合优于继承

### 架构设计
1. ✅ 模块化设计
2. ✅ 职责分离
3. ✅ 依赖注入
4. ✅ 易于测试
5. ✅ 易于扩展

### 用户体验
1. ✅ 清晰的命令行界面
2. ✅ 交互式菜单支持
3. ✅ 完善的错误提示
4. ✅ 多平台支持
5. ✅ 中文和 emoji 支持

---

## 🔗 相关链接

- [主文档](README.md) - 用户使用手册
- [GitHub Releases](https://github.com/yourusername/SSHManager/releases) - 下载最新版本
- [GitHub Issues](https://github.com/yourusername/SSHManager/issues) - 报告问题
- [GitHub Actions](https://github.com/yourusername/SSHManager/actions) - CI/CD 状态

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件
