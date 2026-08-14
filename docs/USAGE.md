# 💼 使用指南

完整的 sshm 使用文档。

---

## 📋 目录

- [命令参考](#-命令参考)
- [实战案例](#-实战案例)
- [两种使用方式](#-两种使用方式)
- [交互模式](#-交互模式)
- [国际化 (i18n)](#-国际化-i18n)
- [安全性](#-安全性)

---

## 🛠️ 命令参考

### 基础命令

#### `list` - 查看所有密钥

```bash
sshm list           # 查看密钥列表
sshm list -a        # 显示公钥内容（方便复制）
```

**输出示例**：

```text
✨ [当前使用] PERSONAL
----------------------------------------------------------------------
  类型: ed25519
  私钥: id_ed25519.personal
  公钥: ✅ id_ed25519.personal.pub
  别名: git@personal:user/repo.git
  大小: 419 bytes
  修改: 2026-08-14 10:00:00
  状态: ⭐ 正在使用（当前默认 ed25519 密钥）
```

---

#### `add` - 创建新密钥

```bash
sshm add <标签> <邮箱> [选项]

选项:
  -H, --host <域名>    自动配置 SSH config Host 别名（推荐）
  -t, --type <类型>    密钥类型：ed25519（默认）| rsa | ecdsa | dsa
  -n, --name <姓名>    作者姓名（自动记录，供 sshm author 使用）

示例:
  sshm add personal me@example.com -H github.com
  sshm add work me@company.com -H gitlab.com -t rsa
  sshm add project dev@gmail.com -H github.com -n "My Name"
```

---

#### `use <标签> --global` - 切换全局默认密钥

```bash
sshm use <标签> --global

# 自动检测密钥类型并切换为全局默认
sshm use personal --global
```

---

#### `use` - 为 Git 仓库配置专用密钥

```bash
sshm use <标签> [选项]

选项:
  -p, --path <路径>    仓库路径（默认当前目录）
  -g, --global         配置为全局默认密钥
  -y, --yes            跳过确认直接执行
  -a, --author         同时设置 Git 作者信息

示例:
  cd ~/my-project
  sshm use personal              # 为当前仓库配置 personal 密钥
  sshm use work -p ~/work/repo   # 为指定仓库配置 work 密钥
  sshm use personal -g           # 配置为全局默认
```

`use` 会自动完成：解析仓库 remote URL → 生成别名 → 更新 SSH Config → 测试连接。

---

#### `author` - 管理 Git 作者信息

```bash
# 查看所有已保存的作者
sshm author list

# 添加/更新作者
sshm author add <标签> [-n 姓名] [-e 邮箱]
# 邮箱省略时自动从公钥注释填充
sshm author add work -n "Zhang San" -e work@company.com

# 为当前仓库/全局设置作者
sshm author use <标签> [-p 路径] [-n 覆盖姓名] [-e 覆盖邮箱] [--global] [-y]

# 清除作者配置（回退到上级配置）
sshm author unset [-p 路径] [--global]

# 移除作者
sshm author remove <标签> [-y]
```

---

#### `info` - 查看当前仓库配置

```bash
sshm info [-p 路径]
```

显示：仓库路径、remote URL、平台/用户解析、当前使用的别名、密钥详情、SSH Config 内容。

---

#### `test` - 测试 SSH 连接

```bash
sshm test                # 测试当前仓库连接
sshm test <标签>         # 测试指定密钥连接
sshm test --all          # 批量测试所有密钥
sshm test -p ~/repo      # 指定仓库路径
```

---

#### `backup / backups / restore` - 安全备份

```bash
sshm backup              # 备份所有密钥到归档（时间戳目录）
sshm backups             # 列出所有备份归档
sshm restore             # 从最近的备份恢复
sshm restore -t rsa      # 按类型恢复
```

所有变更操作前都会自动备份，误删可通过 `restore` 找回。

---

#### `tag` - 保存标签

```bash
sshm tag <新标签> [-t 类型] [-s]
# -s 打标签后立即切换
```

---

#### `rename` - 重命名标签

```bash
sshm rename <旧标签> <新标签> [-t 类型]
# 自动同步更新 SSH Config 别名与状态文件
```

---

#### `remove` - 删除密钥

```bash
sshm remove <标签> [-t 类型]
# 默认删除该标签所有类型的密钥；指定 -t 仅删除对应类型
```

---

#### `lang` - 切换语言

```bash
sshm lang            # 查看当前语言
sshm lang zh         # 切换为中文
sshm lang en         # 切换为英文
```

---

#### `update` - 检查更新

```bash
sshm update              # 检查并更新到最新版本
sshm update --check      # 仅检查更新
sshm update --check --force  # 强制检查（忽略缓存）
```

---

## 🧩 实战案例

### 案例一：同时管理个人 GitHub 与公司 GitLab

```bash
# 1. 创建两个密钥
sshm add personal me@gmail.com -H github.com
sshm add work me@company.com -H gitlab.com

# 2. 个人项目
cd ~/personal-project
sshm use personal

# 3. 公司项目
cd ~/work-project
sshm use work

# 4. 测试
sshm test
```

### 案例二：为历史项目配置密钥

```bash
# 查看当前 remote URL
git remote -v

# 一键配置（自动改写 remote URL 为别名并更新 SSH Config）
cd ~/old-project
sshm use work

# 验证
sshm info
sshm test
```

### 案例三：多账号提交信息管理

```bash
# 保存作者信息
sshm author add personal -n "Me" -e me@gmail.com
sshm author add work -n "Zhang San" -e work@company.com

# 切换项目作者
cd ~/work-project
sshm author use work

# 查看当前生效的配置
sshm author list
```

---

## 🔀 两种使用方式

### 方式一：别名方式（推荐）

通过 `sshm use` 为每个仓库配置专属别名，多账号**同时使用**，互不干扰：

```bash
cd ~/personal-project
sshm use personal
git push    # 自动使用 personal 密钥

cd ~/work-project
sshm use work
git push    # 自动使用 work 密钥
```

### 方式二：全局默认切换

通过 `sshm use <标签> --global` 切换全局默认密钥，适合单账号为主的场景：

```bash
sshm use personal --global
# 所有未配置别名的仓库都使用 personal 密钥
```

> 💡 **建议**：多账号场景优先使用别名方式，避免"忘记切换推错账号"。

---

## 🖥️ 交互模式

**双击可执行文件**（或在终端直接运行 `sshm`）即可进入交互式菜单：

- 可视化菜单列出全部操作
- 逐步引导创建密钥、配置仓库
- 无需记忆命令

**添加到 PATH**

交互菜单中提供"添加到环境变量"选项：
- Windows：自动修改用户环境变量（无需管理员权限）
- Linux/macOS：自动写入 `.bashrc` / `.zshrc` / `config.fish`

---

## 🌐 国际化 (i18n)

SSH Manager 内置中英双语支持：

- 默认语言：英文（`en`）
- 切换命令：`sshm lang zh` / `sshm lang en`
- 环境变量优先：`SSHM_LANG=zh sshm list` 可临时指定语言

语言优先级：`SSHM_LANG` 环境变量 > 状态文件 `lang` 字段 > 默认 `en`

---

## 🛡️ 安全性

- **自动备份**：所有变更操作前自动备份到 `~/.ssh/key_backups/`
- **二次确认**：删除、覆盖等危险操作默认需要确认（`-y` 跳过）
- **目录权限**：`~/.ssh` 目录以 700 权限创建
- **隐私保护**：仅操作 `~/.ssh` 目录，不触碰其他系统配置
