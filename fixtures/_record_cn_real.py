"""CN-01：中国区两源的**真实**抓取录制器——**红线卡，默认拒跑**。

## 这个脚本存在的理由

广场上那 193 条来自 `fixtures/weibo/*.json`，里面的 `热搜话题NN` 是
`_generate_4src.py` 按真实响应形态**确定性构造**出来的合成词面
（那个文件自己写着「本环境无法对四个真实站点做在线录制」）。
owner 2026-08-09：「界面上还有很多保留着热点话题字样的没替换成真正的热点内容」。

换成真的 = **真实源抓取**，而那是 `worker.md` §7 事前必审四类之一。

## 所以它默认**拒跑**，而且拒得很吵

`DEC-022`（2026-08-04）授权的是 B 档抓取的**纪律形态**——抓完必录 `fixtures/`。
**欠的是首次实跑需 owner 在场**（`docs/blocked/E2E-REALSOURCE.md` 的原话）。
两者是两件事：把「已授权纪律」读成「可以跑了」，正是这条红线要防的误读。

不带 `--owner-is-here` 时本脚本：打印它**将要**做什么、**不发一个请求**、退出码 2。
带上时才真的联网。**NEVER 把这个开关做成环境变量**——
环境变量会被 `.env`、被 CI 配置、被上一条命令留在 shell 里的值悄悄打开，
而这一次点头必须是**当场、显式、看得见**的。

## 一条命令

```
python fixtures/_record_cn_real.py                 # 干跑：说清要做什么，不联网
python fixtures/_record_cn_real.py --owner-is-here # owner 在场时才跑
```

跑完之后用既有回放路径把当天数据灌进 demo 库（**本脚本不碰库**）。

**整行粘进 PowerShell**（`CN-03` 修好的那一条）：

```
python -c "import asyncio; from datetime import UTC, datetime; from pathlib import Path; from flint.jobs.ingest import build_replay_deps, run_daily_ingest; d = datetime.now(UTC).date(); print(asyncio.run(run_daily_ingest('cn-01-real', d, build_replay_deps('postgresql://flint:flint@localhost:55432/flint', Path('fixtures'), d))))"
```

想灌**某一个既有夹具日**（回放可重来），把日期显式写进去：

```
python -c "import asyncio; from datetime import date; from pathlib import Path; from flint.jobs.ingest import build_replay_deps, run_daily_ingest; d = date.fromisoformat('2026-06-24'); print(asyncio.run(run_daily_ingest('cn-01-real-20260624', d, build_replay_deps('postgresql://flint:flint@localhost:55432/flint', Path('fixtures'), d))))"
```

### `CN-03` 修了这条命令的三处（改前**贴上去跑不了**）

1. **`DAY` 没有定义** —— 改前那条直接 `NameError`；
2. **第二参传成了字典** —— `run_daily_ingest(job_id, day: date, deps)` 第二参要
   `date`，改前传的是 `{'day': …}`。仓里另外三个调用点
   （`harness/replay30.py:139` · `harness/drill7.py:90` ·
   `flint/jobs/worker_main.py:196`）**全传 `date`**，只有这条文档里的例外；
3. **反斜杠续行** —— 那是 POSIX shell 的写法，**在 PowerShell 里当场断句**。
   现在是**一整行**，且内层全用单引号，外层双引号——整行粘贴即可。

`d` 取 `datetime.now(UTC).date()` 而不是 `date.today()`：**与本脚本 `--day` 的默认值同源**
（fixture 布局按 UTC 日期编，见 `main()` 里那段注释）。两处若各取各的，
跨日的那几个小时里录进去的文件名与灌库要的那一天会对不上。

分成两步是刻意的：**录制是不可逆的一次外网动作，灌库是可以重来的**。
合在一起的话，灌库那一步失败会让人想「再跑一次」——而再跑一次就是再抓一次。

## 抓不到的源**如实缺**

三类错误各自记在结果里、**NEVER 编造词面**：

| 情况 | 记什么 | 广场上会怎样 |
|---|---|---|
| 429 限频 | `rate_limited` | 照 `PLAZA-03` 的既有降级态显示 |
| 5xx / 网络失败 | `fetch_failed` | 同上 |
| 页面结构漂移 | `parse_drift` | 同上 |

这三类正是 `flint/jobs/ingest.py` 已经在写 `DegradationNote` 的那三类——
本脚本**不新建一套**，只把录制阶段遇到的同样三件事照实记下来。

## 抓完必录 + 出处可核

每次成功录制都写两样：fixture 本体（`fixtures/{source}/{day}.json`，`E12` 布局）
与出处清单（`flint/sources/provenance.py#write_manifest`，含 url / 抓取时刻 /
内容 sha256）。**没有 manifest 的 fixture 等于没有出处**，
而「产物可复现」是 `S2-2` 第三条铁律。

## 合规状态照实记录，不拿它拦抓取

`K2-01` 的裁决是 `flint/region/legal_policy.py#RECORD_ONLY`（owner 2026-08-04，
`scope="non_commercial"`）：**照实记录、不阻断**。本脚本把它原样打印进结果，
NEVER 在这里重新判一次——重新判就是第二个真相。
上线前的手续见 `docs/上线前合规手续清单.md`。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from flint.region.legal_policy import OWNER_DECISION
from flint.sources.arxiv import ArxivSource
from flint.sources.errors import ParseDrift, RateLimitedError, SourceFetchError
from flint.sources.ghtrend import GitHubTrendingSource
from flint.sources.gtrends import GoogleTrendsSource
from flint.sources.provenance import (
    make_provenance,
    manifest_path_for,
    write_manifest,
)
from flint.sources.registry import FROZEN_SOURCE_IDS
from flint.sources.throttle import SourceThrottle
from flint.sources.weibo import WeiboHotSource
from flint.sources.weibo_visitor import handshake as visitor_handshake
from flint.testing.replay import HttpReplay, fixture_path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent

#: 四源全录（`CN-06`）。全部是免登录路，**不花钱、不用凭据**：
#: `weibo` 走访客握手（`DEC-053`）· `gtrends` 走港区公开 RSS（`DEC-054`）·
#: `ghtrend` 走未认证的 search API · `arxiv` 走公开 Atom API。
#: 本版只做中国区（`DEC-045`）——gtrends 那一源采港区、`region` 落 CN，
#: 屏上署名「Google 趋势（港区）」，三件东西缺一即 `review_failed`。
CN_SOURCES = ("weibo", "gtrends", "ghtrend", "arxiv")

#: 限速：两源各自一个桶（`flint/sources/throttle.py` 的既有件）。
#: 容量 1 是刻意的——**这一次跑总共只该发几个请求**，
#: 桶开大了等于给一次误操作留出重试的空间。
THROTTLE = {src: (1, 0.2) for src in CN_SOURCES}

#: 跑过的痕迹。判据靠它分辨「owner 还没点头」与「点过了但没抓到」——
#: 两者在「库里没有真实热点」这个结果上长得一模一样。
RECEIPT = REPO / "docs" / "cn-01-real-ingest-receipt.json"


def _plan(day: date) -> list[dict[str, str]]:
    """要做的事，逐条摊开——干跑时打印的就是它。"""
    return [
        {
            "source": source,
            "fixture": str(fixture_path(ROOT, source, day).relative_to(REPO)),
            "manifest": str(
                manifest_path_for(fixture_path(ROOT, source, day)).relative_to(REPO)),
        }
        for source in CN_SOURCES
    ]


#: 每一源怎么建。**一处定义**——分派散在 if/else 里时，
#: 加一源忘改它不会报错，只会把新源录成旧源（`CN-06` 实测栽过一次）。
_ADAPTERS: dict[str, Any] = {
    # weibo：真实抓取前先走访客握手（`DEC-053`）。
    "weibo": lambda c: WeiboHotSource(c, before_fetch=visitor_handshake),
    # gtrends：采 `geo=HK`、`region` 落 `CN`（`DEC-054` 港区代理口径）。
    "gtrends": lambda c: GoogleTrendsSource(c, region="CN"),
    "ghtrend": lambda c: GitHubTrendingSource(client=c),
    "arxiv": lambda c: ArxivSource(client=c),
}


def _record_one(source_id: str, day: date, throttle: SourceThrottle) -> dict[str, Any]:
    """录一个源。三类错误各自成一条结果，**NEVER 编造词面**。"""
    path = fixture_path(ROOT, source_id, day)
    if not throttle.try_acquire(source_id):
        return {"source": source_id, "outcome": "rate_limited",
                "detail": "本地限速桶拦下——这一次跑不该发第二个请求"}

    try:
        with (
            HttpReplay(path, mode="record",
                       live_transport=httpx.HTTPTransport()) as session,
            session.client() as client,
        ):
            # **要未压缩的响应**（`CN-06` 实测逼出来的）。
            #
            # 录制传输层拿到的是**已解码**的字节，却带着 `content-encoding: gzip`
            # 重建响应——外层客户端照那个头再解一次，四源同时炸
            # `DecodingError: incorrect header check`。
            #
            # 在这里要 `identity` 而不是去改 `flint/testing/replay.py`：
            # 那个文件不在本卡 outputs 里，而**录下来的夹具本来就该是明文**——
            # 存一份压缩流进仓库，下一个人打开它看到的是一堆二进制。
            client.headers["Accept-Encoding"] = "identity"
            # weibo：**真实抓取前先走访客握手**（`DEC-053`）。
            # 五条免登录路全废（`CN-04` 探测实证），不握手的话上游 302
            # 弹到访客系统，拿回来的是一段 JS。
            # gtrends：`DEC-054` 采 `geo=HK`、`region` 落 `CN`（港区代理口径），
            # 屏上署名「Google 趋势（港区）」。
            # **每一源建自己的适配器**（`CN-06` 实测逼出来的）。
            #
            # 改前这里是「weibo 用 WeiboHotSource，**其余一律 GoogleTrendsSource**」——
            # 两源时代那是对的。扩到四源之后它把 `ghtrend` 与 `arxiv`
            # **都录成了 gtrends 的响应**，而回执报的是 `ok`。
            #
            # **这比失败更坏**：失败会喊，而这一种安安静静地把三份一样的东西
            # 存进三个不同的目录，下一个人打开 `fixtures/arxiv/` 看到的是
            # 一份 Google 趋势的 RSS，且它有 manifest、有 sha256、看起来样样齐全。
            source: Any = _ADAPTERS[source_id](client)
            items = source.fetch_daily(day)
    except RateLimitedError as err:
        return {"source": source_id, "outcome": "rate_limited", "detail": str(err)}
    except SourceFetchError as err:
        return {"source": source_id, "outcome": "fetch_failed", "detail": str(err)}
    except ParseDrift as err:
        return {"source": source_id, "outcome": "parse_drift", "detail": str(err)}
    except httpx.HTTPError as err:
        return {"source": source_id, "outcome": "fetch_failed", "detail": repr(err)}

    # 抓完必录：出处清单与 fixture 同时落盘（没有 manifest 的 fixture 等于没有出处）。
    exchanges = json.loads(path.read_text(encoding="utf-8"))
    now = datetime.now(UTC)
    write_manifest(
        manifest_path_for(path),
        [make_provenance(url=ex["url"], fetched_at=now, content=ex["body_text"])
         for ex in exchanges],
    )
    return {
        "source": source_id,
        "outcome": "ok",
        "items": len(items),
        "exchanges": len(exchanges),
        "fixture": str(path.relative_to(REPO)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--owner-is-here", action="store_true",
        help="owner 当场点头才带这个开关。NEVER 做成环境变量（见模块 docstring）。")
    # `DEC-052` 预授权的那一次运行**用说真话的旗标**。
    #
    # **NEVER 冒用 `--owner-is-here`**：那个旗标的语义是「owner 此刻在场」，
    # 而 `DEC-052` 的窗口是**预授权**、owner 并不在场。
    # 旗标的名字就是它的诚实性——冒用一次之后，
    # 盘上再也分不出「谁点的头」，而那正是这两个旗标存在的全部理由。
    parser.add_argument(
        "--authorized-by", default="",
        help="MUST 是 DEC-052。命令行 NEVER 环境变量。")
    # `datetime.now(UTC).date()` 而不是 `date.today()`：抓取的是**当天那一份榜**，
    # 而 fixture 布局按 UTC 日期编（`E12`）。本机时区与 UTC 跨日的那几个小时里，
    # `today()` 会写出一个与回放路径对不上的文件名。
    parser.add_argument(
        "--day", default=datetime.now(UTC).date().isoformat())
    args = parser.parse_args(argv)
    day = date.fromisoformat(args.day)

    # **两个日期都打**：本机 UTC+10，午夜前后两个日期不同——owner 被单时钟绊过一次。
    # 夹具命名照旧只按 UTC（`E12`），这里打出来的是给人看的。
    # 本机时区那一份： 拿本机偏移，NEVER 用裸 now()（ruff DTZ005）。
    local_day = datetime.now(UTC).astimezone().date()
    print(f"UTC 日期 {datetime.now(UTC).date().isoformat()} · "
          f"本机日期 {local_day.isoformat()} · 抓取日 {day.isoformat()}")

    authorized = args.owner_is_here or args.authorized_by == "DEC-052"
    plan = _plan(day)
    if not authorized:
        print("真实源抓取要一次显式授权。本次**不发任何请求**。")
        print("两条路，各说各的：")
        print("  --owner-is-here          owner 此刻在场（红线卡 CN-01 那一次）")
        print("  --authorized-by=DEC-052  DEC-052 预授权的运行（owner 不在场）")
        print()
        live = [s for s in CN_SOURCES if s not in FROZEN_SOURCE_IDS]
        print(f"将要抓：{', '.join(live)}（日期 {day.isoformat()}）；"
              f"{', '.join(sorted(FROZEN_SOURCE_IDS))} 已冻结（DEC-066），不抓")
        for row in plan:
            print(f"  {row['source']:8s} -> {row['fixture']}  +  {row['manifest']}")
        print(f"\n合规裁决（照实记录、不阻断）：{OWNER_DECISION.scope} "
              f"@ {OWNER_DECISION.decided_on.isoformat()}")
        return 2

    throttle = SourceThrottle()
    for source_id, (capacity, refill) in THROTTLE.items():
        throttle.configure(source_id, capacity=capacity, refill_per_second=refill)

    # `NARROW-05`: the two sources `DEC-066` froze are not fetched, even on an authorised run.
    # They still get a line in the receipt, so "frozen" never reads as "forgot to run".
    results = [
        {"source": source_id, "outcome": "frozen",
         "detail": "DEC-066 froze this source; unfreezing takes a new owner ruling"}
        if source_id in FROZEN_SOURCE_IDS
        else _record_one(source_id, day, throttle)
        for source_id in CN_SOURCES
    ]
    receipt = {
        "schema": "cn-01/1",
        "day": day.isoformat(),
        "ran_at": datetime.now(UTC).isoformat(),
        # **说清是谁点的头**：两个旗标各自的语义不同，回执里 NEVER 混成一个。
        "authorized_by": "owner-present" if args.owner_is_here else args.authorized_by,
        "local_date": local_day.isoformat(),
        "utc_date": datetime.now(UTC).date().isoformat(),
        "legal_decision": {"scope": OWNER_DECISION.scope,
                           "decided_on": OWNER_DECISION.decided_on.isoformat()},
        "results": results,
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=1))

    # 一个源都没抓到时退非零：**「跑过了」与「跑成了」是两件事**。
    return 0 if any(r["outcome"] == "ok" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
