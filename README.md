# 🔑 SSH Key Manager

<div align="center">

**企业级多账号 SSH 密钥管理工具**

[![Python Version](https://img.shields.io/badge/python-3.6%2B-blue)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)](https://github.com/365tools/SSHKeyManager)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.1.1-brightgreen)](https://github.com/365tools/SSHKeyManager/releases)

[快速开始](#-快速开始) • [功能特性](#-功能特性) • [使用文档](#-使用文档) • [常见问题](#-常见问题) • [开发者文档](docs/DEVELOPER.md)

</div>

---

## 📖 简介

**SSH Key Manager** 是一个专业的 SSH 密钥管理工具，专为需要管理多个 Git 账号（如个人 GitHub、公司 GitLab 等）的开发者设计。

它通过**标签化管理**和**自动配置**，解决了多账号 SSH 密钥管理的痛点，让开发者的工作流程更加安全、高效。

### 🎯 核心价值

- ✅ **告别混乱**：清晰管理个人、公司等多个账号的密钥
- ✅ **自动配置**：自动生成 `~/.ssh/config`，无需手动编辑
- ✅ **安全无忧**：操作前自动备份，支持误删恢复
- ✅ **无缝切换**：智能识别环境，自动匹配正确的 SSH 密钥
- ✅ **可视化**：提供 GUI 交互界面，操作更直观

---

## ✨ 功能特性

| 功能模块                | 特性说明                             | 核心优势                 |
| :---------------------- | :----------------------------------- | :----------------------- |
| **🏷️ 标签系统** | 为每个密钥设置语义化标签             | 避免文件名混淆，一目了然 |
| **🧠 智能配置**   | 自动生成 SSH Config 文件             | 将复杂的配置过程自动化   |
| **🛡️ 安全机制** | 操作前自动备份、危险操作二次确认     | 数据零丢失风险           |
| **🔌 插件化**     | 支持 Git 仓库自动识别 (`sshm use`) | 深度集成开发工作流       |
| **🔄 自动更新**   | 启动时自动检查，一键升级             | 始终保持最新版本         |
| **💻 跨平台**     | Windows (自动修复编码), macOS, Linux | 统一的一致性体验         |
| **🖱️ 交互模式** | 支持双击运行进入 TUI 菜单            | 零命令基础也能使用       |

---

## 🛠️ 系统要求

- **操作系统**: Windows / macOS / Linux
- **依赖环境**:
  - 使用可执行文件版本：**无** (无需安装 Python)
  - 使用源码/Pip 版本：Python 3.6+
- **工具依赖**: 系统需预装 `ssh-keygen` (通常系统自带)

---

## 🚀 快速开始

### 1. 安装

建议直接使用预编译的可执行文件，无需配置 Python 环境。

#### 方式 A：一键安装 (推荐)

**Windows (PowerShell)**

```powershell
irm https://raw.githubusercontent.com/365tools/SSHKeyManager/main/scripts/install.ps1 | iex
```

**Linux / macOS**

```bash
curl -fsSL https://raw.githubusercontent.com/365tools/SSHKeyManager/main/scripts/install.sh | bash
```

#### 方式 B：手动下载

如果网络无法连接 GitHub，可前往 [Releases 页面](https://github.com/365tools/SSHKeyManager/releases) 下载对应文件，重命名为 `sshm` 后放入 PATH 路径即可。

#### 方式 C：源码运行

```bash
git clone https://github.com/365tools/SSHKeyManager.git
cd SSHManager
python -m sshm list
```

### 2. ⚡ 30秒上手指南

假设你需要同时使用 **个人 GitHub** 和 **公司 GitHub**：

```bash
# 1️⃣ 创建密钥 (自动配置 Host 别名)
sshm add github-me my@email.com -H github.com
sshm add github-work work@company.com -H github.com

# 2️⃣ 查看状态
sshm list

# 3️⃣ 在项目中使用
# 方法 A: 自动配置当前仓库 (推荐)
cd ~/my-project
sshm use github-me

# 方法 B: 克隆时直接使用别名
git clone git@github-work:company/repo.git
```

✅ **搞定！** 以后推送代码时，系统会自动选择正确的密钥。

---

## 📚 使用文档

### 核心目录结构

SSH Manager 遵循标准且安全的目录结构：

```text
~/.ssh/
├── config                      # ⚙️ 自动维护的 SSH 配置文件
├── id_rsa.github-me            # 🔑 托管的私钥
├── id_rsa.github-me.pub        # 🔓 对应的公钥
└── key_backups/                # 💾 自动备份目录 (按时间戳归档)
```

### 常用命令详解

#### 🔐 密钥管理

| 命令            | 说明                 | 示例                             |
| :-------------- | :------------------- | :------------------------------- |
| `sshm list`   | 列出所有托管的密钥   | `sshm list -a` (显示公钥内容)  |
| `sshm add`    | 添加新密钥           | `sshm add gh-work me@work.com` |
| `sshm remove` | 删除指定密钥         | `sshm remove gh-old`           |
| `sshm tag`    | 给当前默认密钥打标签 | `sshm tag original-key`        |
| `sshm rename` | 重命名密钥标签       | `sshm rename gh-old gh-new`    |

#### 🔧 配置与连接

**`sshm use <tag>` (推荐)**

智能配置当前 Git 仓库使用指定密钥。

```bash
cd ~/project
sshm use github-work
# 系统会自动：
# 1. 识别当前仓库的 Remote URL
# 2. 修改 .git/config 使用 SSH 别名
# 3. 测试连接是否通畅
```

**`sshm test`**

测试 SSH 连接状态。

```bash
sshm test             # 测试当前仓库连接
sshm test github-me   # 测试指定密钥连接
sshm test --all       # 批量测试所有密钥
```

**`sshm info`**

查看当前仓库的密钥配置详情。

#### 💾 备份恢复

所有涉及修改的操作都会自动触发备份。

```bash
sshm back           # 手动触发一次全量备份
sshm backups        # 查看备份历史列表
```

恢复方法：将 `~/.ssh/key_backups/<timestamp>/` 下的文件复制回 `~/.ssh/` 即可。

---

## 🌟 更多高级功能

除了基础的密钥管理，SSH Manager 还提供了许多强大的辅助功能。

### 1. 🔄 自动更新与维护

不再错过任何新功能！SSH Manager 内置了智能更新机制。

- **静默检查**: 每次运行时自动检测新版本（24小时缓存周期，不影响速度）。
- **一键更新**: 发现新版本后，只需运行 `sshm update` 即可自动下载并替换。
- **强制检查**: 使用 `sshm update --check --force` 强制刷新缓存。

### 2. 🏥 健康检查与诊断

确保你的 SSH 环境始终健康。

* **全量连接测试**: `sshm test --all` 可以一次性测试所有已配置密钥的连通性，快速定位过期待续或配置错误的密钥。
* **仓库配置透视**: `sshm info` 可以在 Git 仓库目录下运行，显示当前仓库的 Remote URL、解析出的 Host、实际使用的密钥路径以及 SSH Config 片段，是排查问题的利器。

### 3. 🖱️ 零门槛交互模式

不想记命令行参数？

* **双击运行**: 在 Windows 上直接双击 `sshm.exe`，或者在终端输入 `sshm` (无参数)，即可进入交互式菜单。
* **功能全覆盖**: 菜单涵盖了查看列表、备份、帮助等常用功能。
* **环境配置**: 菜单中包含 `[4] 添加到环境变量` 选项，一键修复“命令未找到”的问题。

### 4. 🪟 Windows 体验优化

专为 Windows 用户做了深度优化：

* **编码修复**: 自动处理 CMD/PowerShell 的 UTF-8 编码，彻底告别中文乱码。
* **Emoji 支持**: 即使在 Windows 终端也能通过 hack 方式正确显示状态图标。

---

## 🎨 交互式模式 (GUI)

不喜欢敲命令？我们提供了基于终端的交互式界面。

**Windows**: 双击运行 `sshm_gui.bat`
**Linux/Mac**: 运行 `sshm gui` (如果已安装) 或 `python -m sshm.cli.interactive`

界面预览：

```text
========================================
   🔑 SSH Key Manager - 交互式菜单
========================================

请选择操作：
  [01] 查看所有密钥 (list)
  [02] 创建新密钥 (add)
  [03] 切换默认密钥 (switch)
  [04] 删除密钥 (remove)
  [05] 备份所有密钥 (backup)
  [06] 查看备份列表 (backups)
  [07] 将默认密钥另存为标签 (tag)
  [08] 重命名标签 (rename)
  [09] 配置仓库密钥 (use)
  [10] 查看当前配置 (info)
  [11] 测试连接 (test)
  [12] 检查更新 (update)
  [13] 添加到环境变量 (PATH)
  [14] 查看完整帮助
  [Q]  退出
```

---

## ❓ 常见问题 (FAQ)

<details>
<summary><b>Q: 为什么生成的 SSH URL 和原来的不一样？</b></summary>
SSH Manager 使用 SSH Config 的 <code>Host</code> 别名机制来区分不同账号。
<br>例如：<code>git@github.com:user/repo.git</code> 会被自动转换为 <code>git@github-personal:user/repo.git</code>。这完全符合 Git 规范，且是管理多账号的最佳实践。
</details>

<details>
<summary><b>Q: 我现有的密钥会被覆盖吗？</b></summary>
<b>不会。</b> 首次运行时，如果你已经有 <code>id_rsa</code> 等默认密钥，SSH Manager 会建议你先使用 <code>sshm tag</code> 将其纳入管理，或者在操作前自动将其备份到 <code>key_backups</code> 目录。
</details>

<details>
<summary><b>Q: 支持哪些加密算法？</b></summary>
支持所有标准算法，推荐顺序：
1. <b>ed25519</b> (更安全、更快，默认推荐)
2. <b>rsa</b> (兼容性好)
3. ecdsa/dsa
</details>

---

## 🤝 贡献与支持

我们欢迎任何形式的贡献！

- **提交 Bug**: 请前往 [Issues](https://github.com/365tools/SSHKeyManager/issues)
- **开发指南**: 请阅读 [DEVELOPER.md](docs/DEVELOPER.md)
- **提交代码**: Fork -> Feature Branch -> Pull Request

---

## 📄 许可证

本项目基于 MIT License 开源。详见 [LICENSE](LICENSE) 文件。

<div align="center">

Made with ❤️ for developers

</div>
