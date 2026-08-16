# 📋 更新日志

本项目的所有重要变更都会记录在此文件中。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [未发布]

### 规划中

- [ ] SSH Agent 管理
- [ ] 密钥导入/导出
- [ ] 远程备份与云同步
- [ ] 团队协作与密钥安全扫描

---

## [0.0.2] - 2026-08-16

### ✨ 新功能

- **🔗 指定凭据克隆**（`sshm clone`）：直接用某个标签的密钥克隆仓库，无需先 `sshm use`。克隆后仓库 origin 自动指向 sshm 别名，即该仓库直接使用对应凭据。支持 `git@host:user/repo.git`（scp）、`ssh://`（ssh2）、`https://` 三种 URL，可指定目标目录与 `-y` 跳过确认
- **👤 凭据-作者自动联动**（`sshm auto-author`）：新增开关（默认开启）。`sshm use`（局部）/ `sshm use --global`（全局）切换凭据时，自动应用该凭据绑定的作者，实现"换凭据即换人"。无绑定则自动跳过，不影响
- **✏️ 历史作者重写**（`sshm author fix`）：重写所有历史中的作者名/邮箱，支持单独改名、改邮箱，或两者同时处理。底层用 git fast-export/import 纯 Python 实现，不依赖外部工具，兼容打包分发。原 refs 备份到 `refs/original/` 便于回滚

### 🐛 修复

- **`tag` 元数据继承**：`sshm tag` 创建的标签现在继承默认密钥的 host 映射与作者信息，避免私有 Git hostname 错乱、作者信息缺失
- **`clone` 作者推断副作用**：克隆后设置作者时不再从别名 remote URL 推断用户名，避免把组织名错设成 `user.name`

### 📝 文档

- 新增完整架构图 `docs/architecture.mmd`，并嵌入开发者文档
- README 与使用指南补充 `clone`、`auto-author` 命令说明及实战案例

---

## [0.0.1] - 2026-08-14

### 🎉 全新发布

自本项目开始以来，所有功能开发与历史迭代已整合为单一发布版本。首个正式发布包含以下能力：

#### ✨ 核心功能

- **🏷️ 标签化管理**：每个 SSH 密钥拥有独立语义化标签，无限账号轻松管理
- **🔑 多类型密钥**：支持 ed25519（默认）/ rsa / ecdsa / dsa 四种类型
- **🧠 智能仓库配置**（`sshm use`）：自动识别 Git 仓库与 remote URL，生成并维护 SSH 别名配置
- **🔄 一键切换**（`sshm use <标签> --global`）：快速切换全局默认身份，支持自动检测密钥类型
- **👤 作者管理**（`sshm author`）：管理多账号 Git 作者信息，自动设置仓库/全局提交身份
- **⚙️ 自动配置**：自动生成并维护 `~/.ssh/config` 与别名 URL
- **🛡️ 安全备份**：所有操作前自动备份，`sshm restore` 一键恢复
- **🌐 国际化**：内置 i18n，`sshm lang` 切换中英文，支持 `SSHM_LANG` 环境变量
- **🖥️ 交互模式**：双击运行进入 TUI 菜单，零命令基础也可使用
- **🔄 自动更新**：启动静默检查 + `sshm update` 一键升级，24 小时缓存

#### 🔧 工程化与稳定性

- **完全模块化架构**：`core`（业务）/ `cli`（命令行）/ `utils`（工具）三层分离
- **跨平台构建**：GitHub Actions 在 Windows / Linux / macOS 三平台自动打包发布
- **Python 3.14 支持**：基于最新稳定版构建，同时兼容 3.11+ 语法
- **PyInstaller 打包**：单文件可执行，开箱即用，无需 Python 环境
- **CI 稳定性修复**：解决 f-string 跨版本兼容与模块静态分析遗漏问题
- **一键安装脚本**：Windows（PowerShell）与 Linux/macOS（Shell）在线安装
- **Windows 编码修复**：自动设置 UTF-8 控制台，中英文与 emoji 显示无乱码

#### 📚 文档

- 全新项目文档体系：使用指南、安装说明、更新说明、FAQ、开发者文档
- 完整命令参考与实战案例

---

## 版本规范

### 语义化版本号（MAJOR.MINOR.PATCH）

- **MAJOR**：不兼容的 API 变更
- **MINOR**：向下兼容的功能新增
- **PATCH**：向下兼容的问题修复

### 变更类型标签

- `Added` 新增功能
- `Changed` 功能变更
- `Deprecated` 即将废弃的功能
- `Removed` 已删除的功能
- `Fixed` 问题修复
- `Security` 安全性修复
