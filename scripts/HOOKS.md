# git 提交前检查（Pre-commit Checks）

每次 `git commit` 前自动运行统一检查，确保改动通过所有必要验证，防止把
有问题的代码提交进仓库。

---

## 📦 组件

| 文件 | 作用 |
|------|------|
| `scripts/check_all.py` | **统一检查调度器**（核心）。按顺序运行所有已注册检查，任一失败即返回非零。 |
| `scripts/hooks/pre-commit` | git 钩子**模板**（被安装到 `.git/hooks/pre-commit`）。 |
| `scripts/hooks/install.py` | 钩子**安装/卸载**脚本。 |

> `.git/hooks/` 属于仓库本地配置，不入版本库。clone 后需运行一次
> `install.py` 才会生效。

---

## 🚀 安装钩子

```bash
# 安装（在项目根目录）
python scripts/hooks/install.py

# 卸载
python scripts/hooks/install.py --remove
```

安装后，每次 `git commit` 都会自动触发检查。

**跳过提交检查（仅本次提交，需显式声明）：**

```bash
git commit --no-verify -m "message"
```

> ⚠️ `--no-verify` 会跳过**所有** git 钩子，不建议常规使用。

---

## 🔧 手动运行检查

```bash
# 完整检查（默认：compile + i18n + pytest + pyright）
python scripts/check_all.py

# 快速检查（仅秒级项：语法编译 + i18n 一致性）
python scripts/check_all.py --fast

# 跳过指定检查
python scripts/check_all.py --skip pytest
python scripts/check_all.py --skip pytest,pyright

# 列出所有已注册检查
python scripts/check_all.py --list
```

钩子默认走完整检查；如需钩子走快速模式，设置环境变量：

```bash
# Windows (PowerShell)
$env:SSHM_COMMIT_FAST='1'; git commit -m "..."; Remove-Item Env:SSHM_COMMIT_FAST

# Linux/macOS
SSHM_COMMIT_FAST=1 git commit -m "..."
```

---

## ⚡ pytest 并行加速（pytest-xdist）

完整 pytest 检查默认启用 **xdist 并行**（`-n 3`），实测对含 git 重写测试的
套件可提速约 **20%~25%**（本机 75 例：串行 ~7.4s → 并行 ~5.6s）。

> ⚠️ 并行度不宜过高。`-n auto`（用满 CPU）反而会因 git 重写的 I/O 密集 +
> 进程调度开销而变慢，`-n 3~4` 是本套件的甜点区间。

**调整并行度**（环境变量 `SSHM_TEST_JOBS`）：

```bash
# Windows (PowerShell)
$env:SSHM_TEST_JOBS='4'; python scripts/check_all.py   # 4 个 worker

# 串行（结果最确定，便于调试/定位失败顺序）
$env:SSHM_TEST_JOBS='0'; python scripts/check_all.py
```

**手动跑 pytest** 时同样可用：

```bash
python -m pytest -n 3     # 并行
python -m pytest -n0      # 串行（-n0 = 禁用 xdist）
```

- 未安装 `pytest-xdist` 时，`check_all.py` 会自动回退串行，不影响结果正确性。
- `pytest-xdist` 已加入 `pyproject.toml` 的 `dev` 可选依赖。

---

## ➕ 如何新增一个检查

`check_all.py` 设计为**可扩展**。新增检查只需两步：

1. **实现检查函数**：返回 `(ok: bool, detail: str)`。

   ```python
   def check_black() -> tuple[bool, str]:
       """代码格式化：black --check。"""
       ok, detail = _run(sys.executable, '-m', 'black', '--check', 'src', 'tests')
       return ok, detail
   ```

2. **注册到 `CHECKS` 表**（第三项为是否快速检查 `True`/`False`），
   并可在 `CHECKS_HELP` 补一行说明。

   ```python
   CHECKS = [
       ('compile', True,  check_compile),
       ('i18n',    True,  check_i18n),
       ('pytest',  False, check_pytest),
       ('pyright', False, check_pyright),
       ('black',   False, check_black),   # 新增
   ]
   ```

   快速检查（`is_fast=True`）应在秒级内完成，适合高频触发；
   慢速检查（`is_fast=False`）仅在完整模式下运行。

不需要改动调度逻辑。新增的检查会自动出现在 `--list`、完整/快速模式
和 `--skip` 中。

---

## ✅ 当前已注册检查

| 名称 | 快速 | 说明 |
|------|------|------|
| `compile` | ✅ | 语法编译检查（所有 `src` 文件可被 `py_compile` 编译） |
| `i18n` | ✅ | i18n key 模版 / EN / ZH 一致性（含占位符匹配，见 `tests/test_i18n.py`） |
| `pytest` | ❌ | 完整单元测试套件（含 i18n 守门测试） |
| `pyright` | ❌ | basedpyright 类型检查（0 error / 0 warning） |

---

## 🎯 设计理念

- **零额外依赖**：不引入 pre-commit 框架，纯 Python + 标准库即可运行，跨平台。
- **集中调度**：所有检查在 `check_all.py` 统一编排，结果汇总、退出码统一。
- **易扩展**：新增检查 = 一个函数 + 一行注册，无需改调度逻辑。
- **快速/完整分档**：高频提交可走 `--fast`（秒级），合入前跑完整检查。
- **可阻断**：任一检查失败，钩子返回非零，git 自动中止提交。
