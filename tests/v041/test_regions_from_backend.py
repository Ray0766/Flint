"""LOC-01 · 九区清单在前端还留着一份字面量副本。

## 缺陷

`web/components/region-switch/RegionSwitch.tsx` 里写着：

```ts
export const REGIONS = ["CN", "US", "AU", "SG", "JP", "KR", "GB", "IT", "FR"] as const;
```

而真相在 `contracts_v04.Region`，`BE-07` 的 `GET /settings/locale` 已经把它当
`options.region` 返回，`WIRE-01` 也把那条路由挂上了——**同一份清单存在两处**。

两份清单迟早各说各的（加第十个地区那天，只有一处会跟上），
而**读的人分不出哪份是真的**：两处都写着自己是九区。

## 判据的三条线

1. **前端不再持有副本**：`web/` 全域没有任何文件写着半份以上的九区代码
   （`test_no_file_in_web_holds_half_the_region_list`）。阈值取「一半」，
   因为 `"JP"` 当例子值用不是副本，`["CN","US","AU","SG","JP"]` 才是；
2. **清单来自端点**：装配后的真栈上 `GET /settings/locale` 的 `options.region`
   **逐字等于冻结件** `contracts_v04.Region` 的九项
   （`test_the_endpoint_serves_the_nine_from_the_frozen_contract`）；
3. **端点不可用时说出来**：显示未提供态，**NEVER 悄悄退回硬编码副本**
   （`test_the_fallback_is_a_stated_state_not_a_hidden_copy`）。

第 3 条是这张卡最容易做错的地方：`regions ?? REGIONS` 这一行看起来很稳健，
实际是把「端点挂了」显示成「一切正常」——**用户会照着一份可能过期的清单做选择，
而屏幕上没有任何迹象**。
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from flint.api.app import create_app

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
PAGE = WEB / "app" / "settings" / "locale" / "page.tsx"
SWITCH = WEB / "components" / "region-switch" / "RegionSwitch.tsx"
SETTINGS = WEB / "components" / "locale-settings" / "LocaleSettings.tsx"
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test"
)
#: `DEC-056` 之后是**十**区（清单 A2 九区 + HK）。这份集合在这里只当
#: 「哪些字面量算地区码」的判别用，不是第二份清单——真相仍只在冻结件。
TEN = {"CN", "HK", "US", "AU", "SG", "JP", "KR", "GB", "IT", "FR"}
# 「一半」= 5。低于它的是拿一两个地区当例子值（`"JP"` 之类），那不是副本。
# 改前实测：`RegionSwitch.tsx` 命中 9，其余文件最多 3。
HALF = 5
_LITERAL = re.compile(r"""['"]([A-Z]{2})['"]""")


def _sources() -> list[Path]:
    return [
        p for p in sorted(WEB.rglob("*.ts*"))
        if "node_modules" not in p.parts and ".next" not in p.parts
    ]


def _region_literals(text: str) -> set[str]:
    return {m for m in _LITERAL.findall(text) if m in TEN}


@pytest.fixture(scope="module")
def client() -> Any:
    with TestClient(create_app(DSN)) as test_client:
        yield test_client


# ───────────────────────── acceptance②：副本退役


def test_no_file_in_web_holds_half_the_region_list() -> None:
    """`web/` 全域没有第二份九区清单。

    改前 `RegionSwitch.tsx` 命中 9 项（整份），其余文件最多 3 项（例子值）。
    这条判据不禁止 `"JP"` 当例子——**禁的是把清单再写一遍**。
    """
    copies = {
        p.relative_to(WEB).as_posix(): sorted(_region_literals(
            p.read_text(encoding="utf-8", errors="replace")))
        for p in _sources()
    }
    offenders = {k: v for k, v in copies.items() if len(v) >= HALF}

    assert offenders == {}, f"这些文件里还有半份以上的九区清单：{offenders}"


def test_the_switch_no_longer_exports_a_region_constant() -> None:
    """`RegionSwitch` 不再导出 `REGIONS`，也不再导出九项的联合类型 `Region`。

    联合类型也是副本：`type Region = "CN" | "US" | …` 与那个数组一样，
    加第十个地区那天它同样不会跟上，而 `tsc` 会理直气壮地拦下新地区。
    """
    text = SWITCH.read_text(encoding="utf-8")

    assert "export const REGIONS" not in text
    assert not re.search(r'type\s+Region\s*=.*["\']CN["\']', text)
    assert "REGIONS" not in SETTINGS.read_text(encoding="utf-8"), (
        "LocaleSettings 还在引用那个常量"
    )


def test_the_page_hands_the_list_down_from_the_response() -> None:
    """清单从**响应**里下发：页面把 `options.region` 传给组件。

    页面本来就在取 `/settings/locale`（`useScreenData`），`options` 一直在响应里躺着，
    只是没人往下传。
    """
    text = PAGE.read_text(encoding="utf-8")

    assert "options.region" in text, "页面没有把端点回的地区清单传下去"
    assert "regions=" in text, "组件没有收到 regions"


# ───────────────────────── acceptance①：清单的唯一真相在冻结件


@pytest.mark.compose
def test_the_endpoint_serves_the_ten_from_the_frozen_contract(
    client: TestClient,
) -> None:
    """装配后的真栈上，`options.region` **逐字等于冻结件**的十项。

    这条判据接的是前端**现在真正读的那一份**。
    「清单完整、无 EU」这句断言此前写在组件测试里——那时它判的是一份副本；
    现在它判的是源头。**同一句话，从抄件搬到了正本上。**

    `DEC-056` 加 HK 那天，这一条**只改了一个数字就跟上了**——
    而这正是当初把清单搬到源头要换的东西：副本时代要改的是两处，
    且只有一处会被想起来。
    """
    import sys

    sys.path.insert(0, str(REPO))
    from typing import get_args

    from contracts_v04.models_v04 import Region

    got = client.get("/settings/locale", headers={"x-user-id": "loc01-user"})
    assert got.status_code == 200, got.text
    regions = got.json()["options"]["region"]

    assert regions == sorted(get_args(Region))
    assert len(regions) == 10
    assert "HK" in regions, "DEC-056：HK 是可选区"
    assert "EU" not in regions, "EU 是区域联盟，不是地区"


# ───────────────────────── acceptance③：回落是**说出来的状态**


def test_the_fallback_is_a_stated_state_not_a_hidden_copy() -> None:
    """端点不可用 → 屏上说「接口未提供」，NEVER 悄悄退回硬编码副本。

    `regions ?? REGIONS` 那一行看起来稳健，实际是把「端点挂了」显示成
    「一切正常」——**用户照着一份可能过期的清单做选择，而屏幕上没有任何迹象**。

    页面这一侧由 `ScreenFetchState` 兜住（五态各有说法）；
    组件这一侧自己也要有说法：拿不到清单时 NEVER 渲染一个空的 `<select>`——
    **空下拉读起来是「没有可选地区」，那是一句结论**。
    """
    page = PAGE.read_text(encoding="utf-8")
    switch = SWITCH.read_text(encoding="utf-8")

    assert "ScreenFetchState" in page, "页面没有五态兜底"
    # 组件里不许有任何形状的「取不到就用自带的那份」。
    for hidden in ("?? REGIONS", "|| REGIONS", "regions = [", "regions = REGIONS"):
        assert hidden not in switch, f"组件里藏着回落副本：{hidden}"
    assert 'data-screen-state="not_provided"' in switch, (
        "组件拿不到清单时没有说法——空 <select> 是一句结论"
    )
