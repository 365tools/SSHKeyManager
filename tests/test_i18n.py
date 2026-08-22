"""i18n 一致性检查：保证新增翻译 key 时，key 模版与各语言字典严格匹配。

这些测试是"翻译守门员"：任何新增 key 或修改翻译，若导致
模版(KEYS)、英文(EN)、中文(ZH) 三者不一致，或占位符不匹配，
pytest 会立即失败，防止遗漏翻译或格式化错误。
"""

import re
from pathlib import Path

from sshm.i18n import EN, ZH
from sshm.language import KEY_GROUPS, KEYS, LANGUAGES, LanguageDict

# 提取字符串中的 {placeholder} 占位符
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def _placeholders(text: str) -> frozenset:
    return frozenset(_PLACEHOLDER_RE.findall(text))


def _assert_valid_key_set(d: LanguageDict, name: str) -> None:
    """断言字典 key 集合与权威模版一致（无缺失、无多余）"""
    missing = set(KEYS) - set(d)
    extra = set(d) - set(KEYS)
    assert not missing, f"{name} 缺失以下 key: {sorted(missing)}"
    assert not extra, f"{name} 包含模版未定义的多余 key: {sorted(extra)}"


# --------------------------------------------------------------------------
# 1. key 集合一致性
# --------------------------------------------------------------------------


def test_keys_template_matches_both_languages():
    """KEYS 模版与 EN/ZH 字典 key 集合完全一致（三方同步）"""
    assert set(EN) == set(ZH) == set(KEYS)


def test_en_no_missing_or_extra():
    _assert_valid_key_set(EN, "EN")


def test_zh_no_missing_or_extra():
    _assert_valid_key_set(ZH, "ZH")


def test_keys_are_unique():
    """KEYS 无重复"""
    assert len(KEYS) == len(set(KEYS))


# --------------------------------------------------------------------------
# 2. 翻译非空
# --------------------------------------------------------------------------


def test_no_empty_translations():
    """每个 key 的 EN/ZH 翻译均非空（防占位但忘填文本）"""
    for k in KEYS:
        assert EN.get(k), f"EN['{k}'] 为空"
        assert ZH.get(k), f"ZH['{k}'] 为空"


# --------------------------------------------------------------------------
# 3. 占位符一致性（格式化安全）
# --------------------------------------------------------------------------


def test_placeholder_sets_match_en_zh():
    """同一 key 的 EN 与 ZH 占位符集合必须一致，否则 format 会 KeyError"""
    for k in KEYS:
        en_ph = _placeholders(EN[k])
        zh_ph = _placeholders(ZH[k])
        assert en_ph == zh_ph, f"key '{k}' 占位符不一致: EN={sorted(en_ph)} ZH={sorted(zh_ph)}"


def test_placeholder_keys_valid():
    r"""占位符必须是合法 Python 标识符（\w+，允许下划线），排除 {a.b} / {a-b} 等非法字段"""
    for k in KEYS:
        for text in (EN[k], ZH[k]):
            for ph in _placeholders(text):
                assert ph.isidentifier(), f"key '{k}' 含非法占位符 '{{{ph}}}'"


# --------------------------------------------------------------------------
# 4. key 命名约定
# --------------------------------------------------------------------------


def test_key_prefix_in_known_groups():
    """每个 key 必须属于 KEY_GROUPS 定义的分组前缀之一"""
    prefixes = tuple(sorted(KEY_GROUPS, key=len, reverse=True))
    for k in KEYS:
        assert any(k.startswith(p) for p in prefixes), f"key '{k}' 不属于任何已定义分组前缀"


def test_key_groups_cover_all():
    """KEY_GROUPS 前缀覆盖全部 key（无漏网分组）"""
    for k in KEYS:
        prefix = k.split(".")[0] + "."
        assert prefix in KEY_GROUPS, f"分组 '{prefix}' 未在 KEY_GROUPS 中登记"


# --------------------------------------------------------------------------
# 5. 翻译函数可用性
# --------------------------------------------------------------------------


def test_lookup_returns_text_for_all_keys():
    """默认语言下，每个 key 都能查到非空文本（不落回 key 本身）"""
    from sshm.i18n import _

    for k in KEYS:
        text = _(k)
        assert text != k, f"key '{k}' 未找到翻译，落回 key 本身"


def test_supported_languages():
    """支持语言集合符合预期"""
    assert set(LANGUAGES) == {"en", "zh"}


# --------------------------------------------------------------------------
# 6. 代码实际使用的 key 必须已在 KEYS 模版中
# --------------------------------------------------------------------------

_SRC_ROOT = Path(__file__).resolve().parent.parent / "src"
# 兼容两种写法：_(cmd.list) 字面量 与 _(K.cmd.list) 常量（点号前缀分组）
_STR_RE = re.compile(r"_\(\s*['\"]([^'\"]+)['\"]")
_K_RE = re.compile(r"_\(\s*K\.(\w+)\.(\w+)")


def _used_keys_from_source() -> frozenset:
    """扫描 src/sshm 下所有 `_('...')` / `_(K.group.rest)` 调用，提取用到的翻译 key。"""
    keys = set()
    for path in _SRC_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        keys.update(_STR_RE.findall(text))
        # K.cmd.list -> 'cmd.list'
        keys.update(f"{g}.{r}" for g, r in _K_RE.findall(text))
    return frozenset(keys)


def _walk_k(ns, collected: set):
    """递归收集嵌套 K 命名空间的所有叶子值（完整 key 字符串）"""
    for name, value in vars(ns).items():
        if isinstance(value, str):
            collected.add(value)
        else:
            _walk_k(value, collected)


def test_k_constants_cover_all_keys():
    """嵌套 K 命名空间覆盖 KEYS 模版全部 key，且无多余（防手写漏同步）"""
    from sshm.language import K

    collected: set = set()
    _walk_k(K, collected)
    assert collected == set(KEYS), f"K 与 KEYS 不一致: 缺 {sorted(set(KEYS) - collected)} 多 {sorted(collected - set(KEYS))}"


def test_used_keys_are_all_in_template():
    """代码中实际用到的每个 _() key 都必须已在 KEYS 权威模版中。

    防止有人用了一个模版里不存在的 key（会静默回退 key 本身，造成漏翻译）。
    """
    used = _used_keys_from_source()
    missing = sorted(used - set(KEYS))
    assert not missing, f"以下 key 被代码使用但未在 KEYS 模版中登记: {missing}"
