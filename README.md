<div align="center">

# 🔑 sshm

**企业级多账号 SSH 密钥管理工具 · 中英双语 · 跨平台**

[![Python Version](https://img.shields.io/badge/python-3.14%2B-blue)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)](https://github.com/Eavelabs/sshm)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.0.1-brightgreen)](https://github.com/Eavelabs/sshm/releases)

[快速开始](#-快速开始) • [功能特性](#-功能特性) • [使用文档](#-使用文档) • [常见问题](docs/FAQ.md) • [开发者文档](docs/DEVELOPER.md)

</div>

---

## 📖 简介

**sshm** 是一款专业的多账号 SSH 密钥管理工具，专为需要同时管理多个 Git 账号（个人 GitHub、公司 GitLab、自建 GitLab 等）的开发者设计。

通过**标签化管理**与**自动配置**，它彻底解决了多账号场景下密钥混乱、配置繁琐、误切账号等痛点，让开发者的日常工作更安全、更高效。

### 🎯 核心价值

- ✅ **告别混乱**：用语义化标签清晰管理个人、公司等多个账号的密钥
- ✅ **自动配置**：自动生成并维护 `~/.ssh/config`，无需手动编辑
- ✅ **安全无忧**：所有操作前自动备份，支持一键恢复
- ✅ **无缝切换**：智能识别 Git 仓库，自动匹配正确的 SSH 密钥
- ✅ **中英双语**：内置 i18n，支持 `en` / `zh` 一键切换
- ✅ **跨平台**：Windows（自动修复编码）、Linux、macOS 一致体验

---

## ✨ 功能特性

| 功能模块 | 特性说明 | 核心优势 |
| :------- | :------- | :------- |
| **🏷️ 标签系统** | 每个密钥拥有独立语义化标签 | 一目了然，避免文件名混淆 |
| **🧠 智能配置** | 自动生成 SSH Config + 别名 URL | 复杂配置全自动化 |
| **🛡️ 安全机制** | 操作前自动备份、危险操作二次确认、`restore` 一键恢复 | 数据零丢失风险 |
| **🔌 仓库集成** | `sshm use` 自动识别 Git 仓库并配置专用密钥 | 深度融入开发工作流 |
| **👤 作者管理** | `sshm author` 管理并自动设置仓库/全局 Git 作者 | 多账号提交信息不乱 |
| **🌐 国际化** | 内置 i18n，`sshm lang` 切换中英文 | 双语输出体验 |
| **🔄 自动更新** | 启动静默检查，`sshm update` 一键升级 | 始终保持最新版本 |
| **💻 跨平台** | Windows / macOS / Linux | 统一一致性体验 |
| **🖱️ 交互模式** | 双击运行进入 TUI 菜单 | 零命令基础也能使用 |

---

## 🛠️ 系统要求

- **操作系统**: Windows / macOS / Linux
- **依赖环境**:
  - 使用可执行文件版本：**无**（无需安装 Python）
  - 使用源码/Pip 版本：**Python 3.14+**
- **工具依赖**: 系统需预装 `ssh-keygen`（通常系统自带）

---

## 🚀 快速开始

### 1. 安装

建议直接使用预编译的可执行文件，无需配置 Python 环境。

#### 方式 A：一键安装（推荐）

**Windows (PowerShell)**

```powershell
irm https://raw.githubusercontent.com/Eavelabs/sshm/main/scripts/install.ps1 | iex
```

**Linux / macOS**

```bash
curl -fsSL https://raw.githubusercontent.com/Eavelabs/sshm/main/scripts/install.sh | bash
```

> 💡 **`sshm` 显示旧版本 / 运行报错？** 通常是 PATH 中残留了旧的 sshm 目录（如本地构建产物）抢先命中。重新运行安装脚本并加清理参数即可：
> 
> **Windows**
> 
> ```powershell
> irm https://raw.githubusercontent.com/Eavelabs/sshm/main/scripts/install.ps1 -OutFile install.ps1
> powershell -ExecutionPolicy Bypass -File .\install.ps1 -CleanPath
> ```
> 
> **Linux / macOS**
> 
> ```bash
> curl -fsSL https://raw.githubusercontent.com/Eavelabs/sshm/main/scripts/install.sh -o install.sh
> bash install.sh --clean-path
> ```
> 
> 清理后请**重新打开终端**再运行 `sshm`。

#### 方式 B：手动下载

前往 [Releases 页面](https://github.com/Eavelabs/sshm/releases) 下载对应平台文件，重命名为 `sshm` 后放入 PATH 路径即可。

#### 方式 C：源码运行

```bash
git clone https://github.com/Eavelabs/sshm.git
cd SSHManager
python -m sshm list
```

### 2. ⚡ 30 秒上手指南

假设你需要同时使用**个人 GitHub** 和**公司 GitLab**：

```bash
# 1️⃣ 创建密钥（自动配置 Host 别名）
sshm add personal my@email.com -H github.com
sshm add work work@company.com -H gitlab.com

# 2️⃣ 查看状态
sshm list

# 3️⃣ 在项目中使用
cd ~/my-project
sshm use personal        # 自动为当前仓库配置 personal 密钥
```

✅ **搞定！** 以后推送代码时，系统会自动选择正确的密钥，无需手动切换。

---

## 📚 使用文档

### 目录结构

sshm 遵循标准且安全的目录结构：

```text
~/.ssh/
├── config                      # ⚙️ 自动维护的 SSH 配置文件
├── id_ed25519.personal         # 🔑 托管的私钥
├── id_ed25519.personal.pub     # 🔓 对应的公钥
├── .sshm_state                 # 📊 状态文件（当前激活的密钥）
└── key_backups/                # 💾 自动备份目录（按时间戳归档）
```

### 命令总览

| 命令 | 说明 |
| :--- | :--- |
| `sshm list [-a]` | 查看所有密钥（`-a` 显示公钥内容） |
| `sshm add <标签> <邮箱> [-H 主机] [-t 类型]` | 创建新密钥 |
| `sshm use <标签> --global` | 切换全局默认密钥（同时自动切换绑定的全局作者） |
| `sshm use <标签> [-p 路径]` | 为 Git 仓库配置专用密钥（同时自动切换绑定的作者） |
| `sshm clone <标签> <git-url> [目录] [-y]` | 用指定密钥克隆仓库，克隆后仓库直接使用该密钥 |
| `sshm auto-author [on|off]` | 查看/开关"凭据-作者"自动联动（默认开启） |
| `sshm author <子命令>` | 管理/设置仓库与全局 Git 作者 |
| `sshm author fix` | 重写所有历史中的作者名/邮箱（改名/改邮箱） |
| `sshm info` | 查看当前仓库配置详情 |
| `sshm test [标签] [--all]` | 测试 SSH 连接 |
| `sshm backup / backups / restore` | 备份、列出、恢复密钥 |
| `sshm tag / rename / remove` | 标签、重命名、删除密钥 |
| `sshm lang` | 切换中英文（i18n） |
| `sshm update [--check]` | 检查并更新到最新版本 |
| `sshm --help` | 查看完整帮助 |

> 📖 完整命令详解与实战案例请见 [使用指南](docs/USAGE.md)

---

## 📁 项目文档

| 文档 | 说明 |
| :--- | :--- |
| [使用指南](docs/USAGE.md) | 完整命令参考与实战案例 |
| [安装脚本说明](docs/INSTALL.md) | 一键安装脚本详细用法 |
| [自动更新说明](docs/UPDATE.md) | 更新机制与用法 |
| [常见问题 FAQ](docs/FAQ.md) | 高频问题解答 |
| [开发者文档](docs/DEVELOPER.md) | 架构设计、开发与构建指南 |
| [更新日志](docs/CHANGELOG.md) | 版本变更记录 |

---

## 📄 许可证

本项目基于 [MIT](LICENSE) 许可证开源。
