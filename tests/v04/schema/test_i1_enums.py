"""SCHEMA-01 验收：I1 四枚举。

acceptance（tasks-v04.json#SCHEMA-01）：
  九区无 EU；语言仅 zh/en；权威度五值含 unknown；**枚举外值构造被拒**。

## 「枚举外值构造被拒」怎么才算真的测到

四枚举是 `Literal[...]` 别名，**Python 运行期不会拦**——`Doc(..., authority_tier="bogus")`
照样构造成功。所以「被拒」的执行者是 **mypy**，不是运行期。
本测试因此真的**起一个 mypy 子进程**去编译一段越界赋值，断言它报错；
再编译一段合法赋值，断言它不报错（阳性/阴性成对，避免「mypy 对什么都报错」式的假绿）。

只断言 `get_args()` 的成员集合是不够的——那只证明「我写的字面量是这几个」，
证明不了「写别的会被挡住」。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import get_args

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"


def _load_module() -> object:
    import importlib.util

    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _load_module()

#: 清单 A2 的九区 + `DEC-056` 增的 HK。
#:
#: **HK 原本不在九区里**——`DEC-056` 判「CN 与 HK 两区分家、两区都可切」时，
#: 库里既有的港区数据正以 `region='CN'` 的代理身份存着（`DEC-054`）。
#: 撤销代理口径就必须让 HK 成为一个**真的可选区**，于是这一别名从九个成员变成十个。
#:
#: 这条判据因此**跟着改数**而不是被删：它守的是「这个清单只有一处真相且逐字对得上」，
#: 那件事一天都没有松动过。
TEN_REGIONS = {"CN", "HK", "US", "AU", "SG", "JP", "KR", "GB", "IT", "FR"}


def test_region_is_ten_and_has_no_eu() -> None:
    values = set(get_args(M.Region))
    assert values == TEN_REGIONS, f"十区不符：{sorted(values)}"
    assert "EU" not in values, "EU 不是地区（清单 A2）——它是区域联盟，混进来会让源选集口径塌掉"


def test_system_language_is_exactly_zh_en() -> None:
    assert set(get_args(M.SystemLanguage)) == {"zh", "en"}


def test_authority_tier_has_five_values_including_unknown() -> None:
    values = set(get_args(M.AuthorityTier))
    assert values == {"official", "mainstream", "industry", "community", "unknown"}
    assert "unknown" in values, "unknown 是缺省态，缺了它就只能给未知源硬派一个等级"


def test_fetch_legal_status_defaults_to_unknown_semantics() -> None:
    assert set(get_args(M.FetchLegalStatus)) == {"allowed", "unknown", "restricted"}


def _mypy(snippet: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    src = tmp_path / "probe.py"
    src.write_text(snippet, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--no-incremental", str(src)],
        cwd=REPO_ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )


_HEADER = """import sys
sys.path.insert(0, r"{root}")
from contracts_v04.models_v04 import Region, SystemLanguage, AuthorityTier, FetchLegalStatus

region: Region = {region!r}
lang: SystemLanguage = {lang!r}
tier: AuthorityTier = {tier!r}
legal: FetchLegalStatus = {legal!r}
"""


@pytest.mark.parametrize(
    ("region", "lang", "tier", "legal", "should_fail"),
    [
        ("CN", "zh", "official", "allowed", False),      # 阴性对照：合法值必须编译过
        ("EU", "zh", "official", "allowed", True),       # 九区无 EU
        ("CN", "ja", "official", "allowed", True),       # 语言仅 zh/en
        ("CN", "zh", "verified", "allowed", True),       # 权威度五值之外
        ("CN", "zh", "official", "maybe", True),         # 合规状态三值之外
    ],
)
def test_out_of_enum_values_are_rejected_by_mypy(
    tmp_path: Path, region: str, lang: str, tier: str, legal: str, should_fail: bool
) -> None:
    """枚举外值 MUST 被 mypy 拒；合法值 MUST 通过（成对断言，防「对什么都报错」）。"""
    snippet = _HEADER.format(
        root=str(REPO_ROOT), region=region, lang=lang, tier=tier, legal=legal)
    result = _mypy(snippet, tmp_path)
    failed = result.returncode != 0
    assert failed is should_fail, (
        f"mypy 结果与预期不符（should_fail={should_fail}）：\n{result.stdout}{result.stderr}"
    )
