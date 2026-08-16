# 👨‍💻 开发者文档

面向开发者的架构说明、开发环境搭建与构建指南。

---

## 📋 目录

- [项目结构](#-项目结构)
- [架构设计](#-架构设计)
- [开发环境搭建](#-开发环境搭建)
- [测试](#-测试)
- [构建可执行文件](#-构建可执行文件)
- [CI/CD](#-cicd)
- [构建注意事项](#-构建注意事项)

---

## 📁 项目结构

```text
SSHManager/
├── src/
│   ├── run_sshm.py              # PyInstaller 入口点（绝对导入）
│   └── sshm/
│       ├── __init__.py          # 包入口（自动初始化 Windows 控制台）
│       ├── __main__.py          # python -m sshm 入口
│       ├── constants.py         # 密钥类型等常量（版本号从 CHANGELOG 自动解析）
│       ├── i18n.py              # 国际化组装（翻译函数 + 语言状态）
│       ├── language/
│       │   ├── i18n_language.py # 通用 key 模版（权威 key 清单 + 分组约定）
│       │   ├── i18n_en.py       # 英文 (EN) 字典
│       │   ├── i18n_zh.py       # 中文 (ZH) 字典
│       │   └── __init__.py      # language 包导出
│       ├── cli/
│       │   ├── cli.py           # Typer 主应用（16 命令 + author 子命令）
│       │   ├── interactive.py   # 交互式 TUI 菜单
│       │   └── __init__.py      # 导出 app + 交互菜单
│       ├── core/
│       │   ├── manager.py       # SSHKeyManager 核心业务
│       │   ├── config.py        # SSHConfigManager Config 管理
│       │   ├── state.py         # StateManager 状态持久化
│       │   └── rewrite.py       # git 历史重写
│       └── utils/
│           ├── console.py       # 输出格式化、Windows 编码修复
│           ├── system.py        # PATH 配置等系统操作
│           └── updater.py       # 自动更新
├── scripts/
│   ├── build_local.py           # 本地构建脚本
│   ├── check_all.py             # 提交前统一检查（compile/i18n/pytest/pyright）
│   ├── hooks/                   # git pre-commit 钩子模板 + 安装脚本
│   ├── install.ps1              # Windows 一键安装
│   └── install.sh               # Linux/macOS 一键安装
├── tests/                       # pytest 测试套件（75 用例，含 i18n 守门测试）
├── .github/workflows/
│   └── build-release.yml        # 三平台打包发布
└── docs/                        # 项目文档
```

---

## 🏗️ 架构设计

### 分层结构

- **core 层**：纯业务逻辑，不依赖 CLI
  - `SSHKeyManager`：核心业务（创建、切换、配置、测试）
  - `SSHConfigManager`：`~/.ssh/config` 读写
  - `StateManager`：状态文件（`.sshm_state`）持久化
- **cli 层**：命令行交互
  - `cli.py`：Typer 框架声明式定义全部命令（`@app.command()`），自动生成 `--help`/参数校验/补全
  - `interactive.py`：交互式 TUI 菜单
- **utils 层**：通用工具（控制台、系统、更新）
- **language 层**：i18n 翻译字典（`i18n_en.py`/`i18n_zh.py` + key 模版），`i18n.py` 组装翻译函数

> 核心采用**组合模式**：`SSHKeyManager` 内部组合 `SSHConfigManager` 与 `StateManager`，而非继承，降低耦合、便于测试。

### 国际化 (i18n)

- **稳定 key 方案**：翻译键为稳定 key（如 `cmd.list` / `opt.label`），英文（`EN`）与中文（`ZH`）两套字典都映射到同一 key，杜绝"改描述要改两处"与废弃键冗余
- 字典按语言拆分为独立文件（`language/i18n_en.py` / `i18n_zh.py`），通用 key 模版（`language/i18n_language.py`）持有权威 `KEYS` 清单
- 语言优先级：`SSHM_LANG` 环境变量 > 状态文件 `lang` 字段 > 默认 `en`
- 翻译函数 `_(key, **kwargs)`：按当前语言查表，支持 `{placeholder}` 格式化；缺失时回退英文，再缺失回退 key 本身便于发现遗漏
- **一致性守门**：`tests/test_i18n.py` 自动校验 key 模版 / EN / ZH 三方同步、翻译非空、占位符一致

### 数据流

```mermaid
flowchart LR
    A[用户输入] --> B[cli/cli.py  Typer]
    B --> D[core/SSHKeyManager]
    D --> E[SSHConfigManager]
    D --> F[StateManager]
    D --> G[~/.ssh 文件系统]
    B --> H[utils/updater]
    D --> I[i18n 输出]
```

### 完整架构图

> 独立文件见 [architecture.mmd](architecture.mmd)，下方为可渲染版本。

```mermaid
flowchart TB
    subgraph User["用户交互层"]
        CLI["CLI 命令行<br/>sshm &lt;command&gt;"]
        GUI["交互菜单<br/>双击运行 sshm_gui.bat<br/>show_interactive_menu()"]
        LANG["语言层 i18n.py<br/>中英文切换"]
    end

    subgraph Cli["CLI 层 (src/sshm/cli/)"]
        CliApp["cli.py<br/>Typer app<br/>声明式命令定义"]
        Interactive["interactive.py<br/>交互菜单"]
    end

    subgraph Core["核心业务层 (src/sshm/core/)"]
        Manager["manager.py<br/>SSHKeyManager<br/>全部业务逻辑"]
        Config["config.py<br/>SSHConfigManager<br/>SSH config 读写"]
        State["state.py<br/>StateManager<br/>状态持久化"]
    end

    subgraph Utils["工具层 (src/sshm/utils/)"]
        Console["console.py<br/>表格/对齐/编码/确认"]
        System["system.py<br/>PATH 管理"]
        Updater["updater.py<br/>版本更新"]
    end

    subgraph External["外部系统"]
        SSH_DIR["~/.ssh/<br/>id_* 密钥文件<br/>config SSH配置"]
        STATE_FILE[".sshm_state<br/>active_keys / hosts / authors / lang / auto_author"]
        GIT["git 命令<br/>clone / remote / config"]
        SSHD["SSH / Git 平台<br/>GitHub / GitLab / 私有"]
    end

    CLI --> CliApp
    GUI --> Interactive
    CLI --> LANG
    GUI --> LANG

    CliApp --> Manager
    Interactive --> Manager

    Manager --> Config
    Manager --> State

    Manager --> Console
    Manager --> System
    Manager --> Updater

    Manager --> SSH_DIR
    Manager --> STATE_FILE
    Manager --> GIT
    Config --> SSH_DIR
    State --> STATE_FILE
    GIT --> SSHD

    Updater --> GIT
    Updater --> SSHD
```

---

## 💻 开发环境搭建

### 前置要求

- **Python 3.14+**（同时兼容 3.11+）
- Git

### 步骤

```bash
git clone https://github.com/Eavelabs/sshm.git
cd SSHManager
pip install -e .            # 安装运行时依赖（typer / wcwidth）
pip install -e ".[dev]"     # 安装开发依赖（pytest / basedpyright / pyinstaller）
```

### 本地运行

```bash
# 命令行方式
PYTHONPATH=src python -m sshm list

# 交互模式
python src/run_sshm.py
```

---

## 🧪 测试

基于 pytest 的统一测试套件（`tests/`，75 用例），包含核心业务、CLI 帮助、i18n 一致性守门测试等。

```bash
# 运行全部测试
python -m pytest

# 并行加速（pytest-xdist，可选）
python -m pytest -n 3

# 提交前统一检查（compile + i18n + pytest + pyright，任一失败阻断提交）
python scripts/check_all.py
```

> git pre-commit 钩子默认会在 `git commit` 前自动运行 `check_all.py`。
> 安装钩子：`python scripts/hooks/install.py`，详见 [HOOKS.md](../scripts/HOOKS.md)。

---

## 🔨 构建可执行文件

### 本地构建

```bash
python scripts/build_local.py
```

等价命令：

```bash
pyinstaller --onefile --name sshm --console --paths src src/run_sshm.py
```

构建产物：`dist/sshm.exe`（Windows）或 `dist/sshm`（Linux/macOS）

### 验证

```bash
./dist/sshm --help
./dist/sshm list
```

---

## 🤖 CI/CD

`.github/workflows/build-release.yml` 会在推送 `v*` 标签时触发：

1. 在 Windows / Linux / macOS 三平台分别构建单文件可执行文件
2. 运行 `--help` 冒烟测试
3. 上传构建产物
4. 自动创建 GitHub Release 并附带三平台安装包

触发方式：

```bash
git tag v0.0.3
git push origin v0.0.3
```

---

## ⚠️ 构建注意事项

1. **入口文件使用绝对导入**：`run_sshm.py` 必须用 `from sshm.xxx import ...` 形式，确保 PyInstaller 静态分析正确。
2. **避免 f-string 跨行/表达式内反斜杠**：此类写法仅 Python 3.12+（PEP 701）支持。项目以 Python 3.14 构建，但为兼容性，建议将复杂表达式先算到变量再放入 f-string。
3. **模块未被打包时的现象**：若 PyInstaller 因模块导入失败将其标记为 `invalid`，运行时会出现 `ModuleNotFoundError`。可检查 `build/sshm/warn-sshm.txt` 中的 `invalid module named ...`。
4. **清理缓存**：修改源码后务必删除 `build/` 目录再重建，否则 PyInstaller 可能复用旧分析结果：
   ```bash
   rm -rf build dist
   pyinstaller --onefile --name sshm --paths src src/run_sshm.py
   ```
