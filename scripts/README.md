# 安装脚本说明

## 📦 统一安装/卸载脚本

为了简化用户操作，安装和卸载功能已合并到同一个脚本中，用户只需下载一次即可完成所有操作。

---

## ✨ 特性

### 单脚本多功能
- ✅ **安装**：自动下载最新版本并配置环境
- ✅ **卸载**：清理所有文件和配置
- ✅ **无需二次下载**：同一脚本完成所有操作

### 跨平台支持
- Windows (PowerShell)
- Linux (Bash)
- macOS (Bash)

---

## 🚀 使用方法

### Windows (install.ps1)

#### 安装
```powershell
# 方式 1: 在线一键安装
irm https://raw.githubusercontent.com/eavelabs-community/sshm/main/scripts/install.ps1 | iex

# 方式 2: 本地安装
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1

# 方式 3: 指定版本
.\scripts\install.ps1 -Version v0.0.4

# 方式 4: 自定义安装路径
.\scripts\install.ps1 -InstallDir "C:\Tools\sshm"
```

#### 卸载
```powershell
# 方式 1: 在线卸载
irm https://raw.githubusercontent.com/eavelabs-community/sshm/main/scripts/install.ps1 | iex -Args '-Uninstall'

# 方式 2: 本地卸载
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Uninstall

# 方式 3: 指定路径卸载
.\scripts\install.ps1 -Uninstall -InstallDir "C:\Tools\sshm"
```

### Linux/macOS (install.sh)

#### 安装
```bash
# 方式 1: 在线一键安装
curl -fsSL https://raw.githubusercontent.com/eavelabs-community/sshm/main/scripts/install.sh | bash

# 方式 2: 本地安装
bash scripts/install.sh

# 方式 3: 指定版本
bash scripts/install.sh --version v0.0.3

# 方式 4: 自定义安装路径
bash scripts/install.sh --install-dir ~/.local/bin
```

#### 卸载
```bash
# 方式 1: 在线卸载
curl -fsSL https://raw.githubusercontent.com/eavelabs-community/sshm/main/scripts/install.sh | bash -s -- --uninstall

# 方式 2: 本地卸载
bash scripts/install.sh --uninstall
```

---

## 📋 脚本参数

### install.ps1 (Windows)

| 参数 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `-Version` | 安装版本 | `latest` | `-Version v0.0.4` |
| `-InstallDir` | 安装目录 | `$env:LOCALAPPDATA\Programs\sshm` | `-InstallDir "C:\Tools\sshm"` |
| `-NoAddPath` | 不添加到 PATH | `false` | `-NoAddPath` |
| `-CleanPath` | 清理 PATH 中的旧 sshm 残留 | `false` | `-CleanPath` |
| `-Uninstall` | 卸载模式 | `false` | `-Uninstall` |

### install.sh (Linux/macOS)

| 参数 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `--version` | 安装版本 | `latest` | `--version v0.0.4` |
| `--install-dir` | 安装目录 | `/usr/local/bin` | `--install-dir ~/.local/bin` |
| `--no-add-path` | 不添加到 PATH | `false` | `--no-add-path` |
| `--clean-path` | 清理 shell 配置中的旧 sshm 残留 | `false` | `--clean-path` |
| `--uninstall` | 卸载模式 | `false` | `--uninstall` |

---

## 🔧 脚本功能

### 安装功能

1. **版本检测**
   - 从 GitHub API 获取最新版本
   - 支持指定版本号安装
   - 显示文件大小和下载地址

2. **自动下载**
   - 进度显示
   - 断点续传支持
   - 下载失败自动重试

3. **智能安装**
   - 创建安装目录
   - 文件重命名 (platform-amd64 → sshm)
   - 权限设置 (Linux/macOS)

4. **环境配置**
   - 自动添加到 PATH
   - 用户确认机制
   - 支持跳过 PATH 配置

5. **安装验证**
   - 测试可执行性
   - 显示安装位置和版本
   - 提供使用示例

### 卸载功能

1. **文件检测**
   - 自动查找安装位置
   - 支持多路径搜索
   - 友好的未安装提示

2. **清理文件**
   - 删除可执行文件
   - 删除平台标识文件
   - 清理空目录

3. **环境清理**
   - 从 PATH 中移除
   - 清理缓存文件 (~/.sshm_update_cache)
   - 更新环境变量

4. **确认机制**
   - 卸载前二次确认
   - 显示卸载位置
   - 操作状态反馈

---

## ⚠️ 常见问题

### Windows: "禁止运行脚本"

**原因**：PowerShell 执行策略限制

**解决方法**：
```powershell
# 方法 1: 使用 -ExecutionPolicy 参数
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1

# 方法 2: 临时修改策略（仅当前会话）
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process

# 方法 3: 用户级别永久允许（不推荐）
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Linux/macOS: "Permission denied"

**原因**：没有写入 /usr/local/bin 的权限

**解决方法**：
```bash
# 方法 1: 使用 sudo
sudo bash scripts/install.sh

# 方法 2: 安装到用户目录
bash scripts/install.sh --install-dir ~/.local/bin
# 然后添加到 PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### 安装后找不到命令

**原因**：PATH 未刷新

**解决方法**：
```bash
# Windows
重启终端

# Linux/macOS
source ~/.bashrc  # 或 ~/.zshrc
```

---

## 🛠 本地开发/在线统一部署脚本（dev_local.ps1）

面向**开发者 / 想要用本地编译最新代码**的用户。采用「**单一安装目录 + 单一 PATH**」策略：
本地编译版与在线安装版**都写入同一个目录** `%LOCALAPPDATA%\Programs\sshm\sshm.exe`，
PATH 只指向这一个目录，任意位置敲 `sshm xxx` 始终命中同一路径，只是文件被谁覆盖而已。
**无需在多个 PATH 目录间切换，最简单也最不易出错。**

### 用法

```powershell
# 1) 本地打包并部署（覆盖安装目录为本地编译版）
.\scripts\dev_local.ps1 install-local

# 2) 从 GitHub 下载最新在线版并部署（覆盖为 sshm.exe）
.\scripts\dev_local.ps1 install-release

# 3) 查看当前安装的是本地版还是在线版
.\scripts\dev_local.ps1 status

# 4) 从 PATH 移除安装目录（不删文件；完全卸载请用 install.ps1 -Uninstall）
.\scripts\dev_local.ps1 uninstall
```

### 关键机制与回答常见疑问

- **PATH 存的是「目录」，不是文件名**。敲 `sshm` 时系统只在 PATH 目录里找 `sshm.exe` / `sshm.bat` / `sshm.cmd`。因此：
  - **远端下载的 `sshm-windows-amd64.exe` 必须重命名为 `sshm.exe`** 才能通过 `sshm` 简写调用；
  - 环境变量**不能**直接支持 `sshm-windows-amd64.exe`（除非你每次都敲全名）。
- **PATH 只需配置一次**：脚本首次会把安装目录加入 User PATH，之后无论 `install-local` 还是 `install-release` 都只替换 `sshm.exe` 文件，不再动 PATH。
- `status` 通过来源标记文件（`.source_local` / `.source_release`）区分当前是本地编译版还是在线版。
- 本地打包复用 `sshm.spec`，与 CI 线上产物**版本解析行为完全一致**（都打入 `CHANGELOG.md` + metadata），不会出现"本地打包后误报有新版本"。

### 注意事项

- `install-local` 会调用 `scripts\build_local.py` 做 PyInstaller 打包（需已安装 `pyinstaller`）。首次打包约需 1–2 分钟。
- 需要管理员权限？不需要，本脚本只改**用户级** PATH（注册表 `HKCU`）和用户目录下的安装目录。
- 若历史上有多个 PATH 目录都含 `sshm`（如 pip 脚本、旧安装），本脚本保证安装目录在 User PATH 最前；`status` 会提示实际命中情况，必要时重开终端。

---

## 🎯 设计理念

### 为什么合并安装和卸载脚本？

1. **用户体验**
   - 一次下载，终身使用
   - 减少文件数量
   - 降低学习成本

2. **维护便利**
   - 统一代码结构
   - 减少重复代码
   - 降低维护成本

3. **逻辑一致**
   - 安装和卸载是对称操作
   - 使用相同的路径和配置
   - 确保完全清理

### 设计原则

- ✅ **简单至上**：一键完成常见操作
- ✅ **安全第一**：危险操作二次确认
- ✅ **友好提示**：清晰的错误信息和帮助
- ✅ **跨平台**：统一的用户体验
- ✅ **容错性**：优雅处理各种异常情况

---

## 📝 技术实现

### 代码结构

```
install.ps1 / install.sh
├── 参数解析
├── 工具函数
│   ├── Write-ColorText (输出彩色文本)
│   └── 错误处理
├── 卸载函数
│   ├── 查找安装位置
│   ├── 确认操作
│   ├── 删除文件
│   ├── 清理 PATH
│   └── 清理缓存
└── 安装流程
    ├── 获取版本信息
    ├── 下载文件
    ├── 安装文件
    ├── 配置 PATH
    └── 验证安装
```

### 关键特性

1. **智能路径查找**
   ```powershell
   # Windows
   $found = Get-Command sshm -ErrorAction SilentlyContinue
   
   # Linux/macOS
   SSHM_PATH=$(which sshm 2>/dev/null || echo "")
   ```

2. **权限处理**
   ```bash
   # 检测是否需要 sudo
   if [ ! -w "$INSTALL_DIR" ]; then
       SUDO="sudo"
   fi
   ```

3. **PATH 管理**
   ```powershell
   # 添加到 PATH
   [Environment]::SetEnvironmentVariable("Path", "$userPath;$InstallDir", "User")
   
   # 从 PATH 移除
   $newPath = ($userPath -split ';' | Where-Object { $_ -ne $InstallDir }) -join ';'
   ```

---

## 🔄 更新记录

### v0.0.1 (2026-08-14)
- ✅ 合并 install 和 uninstall 脚本
- ✅ 统一命令参数
- ✅ 优化用户体验
- ✅ 完善文档说明

### 之前版本
- v2.1.0: 添加自动更新功能
- v2.0.0: 独立的 install 和 uninstall 脚本

---

## 📚 相关文档

- [README.md](../README.md) - 项目主文档
- [INSTALL.md](../docs/INSTALL.md) - 详细安装文档
- [USAGE.md](../docs/USAGE.md) - 详细使用指南
- [UPDATE.md](../docs/UPDATE.md) - 更新功能文档

---

## 💡 提示

- 推荐使用 **在线一键安装**，最简单快捷
- 遇到执行策略问题，使用 `-ExecutionPolicy Bypass`
- 卸载时会自动清理所有文件和配置
- 安装脚本可以重复执行（会覆盖安装）
- 支持从旧版本无缝升级到新版本
