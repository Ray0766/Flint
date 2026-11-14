"""PERSIST-04：按热点读**最新一条判定**——读侧那一半。

## 为什么它住在 `flint/repo/` 而不是 `flint/jobs/`

`tests/v04/hotspot/test_analysis_view_api.py#test_read_module_imports_no_generation_channel`
是 v0.4 封版的一把尺子：**读端点模块 NEVER import 生成通道**
（`anthropic` / `flint.gate` / `flint.jobs` / `flint.llm` / `flint.compose`）。

`PERSIST-04` 第一版把 `latest_verdict_job` 放在 `flint/jobs/cluster_verdict.py` 里，
于是 `flint/api/views.py` 为了读判定 import 了 `flint.jobs.*`——**当场违规**，
而那把尺子是对的：**打开一屏去看，NEVER 该牵动生成那一侧**
（`DEC-042` ③「打开分析界面只是查看」是同一条纪律的产品面）。

所以读写两半分开住：

| 半 | 在哪 | 谁用 |
|---|---|---|
| 写（收尾时记下判的是哪几个热点） | `flint/jobs/cluster_verdict.py` | `flint/jobs/gate1.py` |
| **读（按热点取最新一条）** | **本模块** | `flint/api/views.py` |

两半共用一张表，**没有第二套口径**：写那半只写，读这半只读。
"""
from __future__ import annotations

import asyncpg


async def latest_verdict_job(
    conn: asyncpg.Connection, cluster_id: str,
) -> str | None:
    """这个热点**最新一条**判定的 job；没判过回 `None`。

    `None` 是「没判过」这一态的表示，**NEVER 与「读失败」合并**——
    后者由调用方那一层的异常路径表示（`DESIGN-03` 的四态口径）。

    一个热点多次判定时取**最新一条**（`DEC-044` 定的默认），
    按 `created_at` 排——**NEVER 拿 `jobs.created_at` 顶**：
    关系是判定收尾那一刻建立的，作业创建时间是另一回事
    （作业可能排了很久，一个早提交晚完成的作业会被排到前面，
    而屏上显示的就是旧的那次判定）。
    """
    found = await conn.fetchval(
        "SELECT job_id FROM cluster_verdicts WHERE cluster_id = $1 "
        "ORDER BY created_at DESC, job_id DESC LIMIT 1",
        cluster_id,
    )
    # 收窄给类型看：这一列是 text NOT NULL，取不到时 asyncpg 回 None。
    return None if found is None else str(found)
