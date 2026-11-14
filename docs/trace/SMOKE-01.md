# SMOKE-01 · trace

**卡**：七项核心功能逐项真栈冒烟 + 给 owner 的一页《怎么测》。
**状态**：verified · 2 cycles · 判据 18 条全绿。
**七项全部打过真栈**：①②③④⑤⑦ 绿，⑥ 卡在网络授权（不是功能）。
产出 `docs/怎么测-v041.md`（给 owner 的一页）与 `tests/v041/test_smoke_seven.py`。

真栈：`:8000`（demo API）· `:3000`（web）· worker（`harness/run_worker.py`）·
postgres 55432 · redis 56379 · Ollama 11434（`qwen3.6:35b-a3b`）。

## 七项当前状态

| | 功能 | 状态 | 实测 |
|---|---|---|---|
| ① | 热点搜集 | **绿** | 四源契约齐；CN-07 修好两源恒空的窗口 |
| ② | 广场与卡片 | **绿** | CN 50 张真微博热搜 · HK 3+ 张真港区词（馬國明 / 美食博覽2026 / 鰂魚涌），切区后 URL 与屏上内容一致 |
| ③ | 收藏 | **绿（修了两处）** | 见下 |
| ④ | 入台 | **绿**（又一处过期前提） | `POST /workbenches` 回 201 + 读回带真热点节点的图；前端注释写着「今天没挂（实测 404）」——**假的** |
| ⑤ | AI 设计工作台 | **跑通了**（本轮修了两处）+ 发现第五处 | 见下 |
| ⑥ | 热点分析 | **卡在授权** | 见下 |
| ⑦ | 本地模型生成计划书 | **绿** | 提交 → done → 新产物 22 个 block，正文是真句子 |

## 冒烟抓出来的四处（都是真缺陷，且都只有真跑才看得见）

### 一、屏上的源署名还带着「（港区）」——`REGION-CN-HK` 漏了第二份

`REGION-CN-HK` 改了 `flint/sources/gtrends.py#SOURCE_DISPLAY_NAME`，
**而 HK 区屏上照旧写着「Google 趋势（港区）」**——那个名字在
`web/messages/{zh,en}.json#source.name.gtrends` 还有一份。

> 改了一份、漏了另一份，**而两份都自称是这一源的名字**。
> 后端那条判据绿着，用户看到的还是旧的。

已改（`Google 趋势` / `Google Trends`），并在 `test_region_cn_hk.py` 加了一条
判「地区缀 NEVER 出现在源名字里」的判据——两侧不做逐字相等（英文本来就是另一种语言），
判的是那根线：`PRINCIPLES#A3` 源与地区各是一根轴。

### 二、收藏屏对**任何**快照都说「内容不在了」

`web/lib/screenAdapters.ts` 读的是 **`row.has_snapshot`——一个后端从来不发的字段**
（`favorite_json` 回的是 `evidence_snapshot`）。于是 `Boolean(undefined)` 恒 `false`。

**这是 `FAV-SNAPSHOT-HAS-NO-PROVIDER` 那张单上症状的第二个来源**：
快照真的曾经是空的（`DEC-055` 治的是那一半），
而**即使不空，这一行也照样把它读成空**——`FAV-SNAPSHOT` 那一卡的判据全绿，屏上照旧。

改成读快照本身（`isNonEmptyObject(row.evidence_snapshot)`）：一处真相，
NEVER 要后端多发一个派生字段。改后屏上两条都显示「仍是最新」+ 三个按钮。

### 三、`design_generate` 这一族**从来没有跑通过一次**

第一次真跑，连着撞两个：

1. `HandlerDepsMissing`——`harness/run_worker.py` 没注 `design_generate_deps`
   （与 `VERDICT-01` 修的 gate1 是同一类缺缝）。已注（provider 与组稿共用同一个
   `LocalProvider`，事件流是库，一发外部请求都不发）；
2. `ValueError: 没有 prompt`——**提交端点写 `payload["brief"]`，而作业读
   `payload["prompt"]`**。全仓只有 `flint/api/analysis.py:233` 一处写它，
   已改成 `"prompt": body.brief`（请求体那一格仍叫 `brief`，那是用户那一侧的说法；
   改的只是进 payload 时的键——两个名字说同一件东西，而只有一处能是真相）。

改完之后作业**真的开始跑了**（240 秒内没结束——本地 35B 出图慢，不是失败）。

> 屏上此前只说「设计产物接口未提供」。那句是实话（`create_app` 注的是
> `_unconfigured("design")`），**而它盖住了后面两个更硬的毛病**。

### 四、两个 worker 同时在跑，旧的那个抢走了作业

修完 `design_generate_deps` 重跑，仍报 `HandlerDepsMissing`——
因为上一个 worker 进程还活着，而它是**改动之前**起的。
「起一个就够」那句注释说的是 demo 的意图，**没有任何东西在拦第二个**。
处置：全停、只起一个，再跑才看到新的错误。

## ⑥热点分析：卡在授权，不是卡在功能

提交端点、判定读端点都活着（`POST /projects/{id}/analysis` 回 422 点名缺 `budget_cny`，
说明校验在跑；`GET /clusters/{id}/verdict` 回 404 + `no Gate verdict for cluster …`）。

**但真提交一次会让 worker 走 `build_live_deps`，去打真实 github / arxiv。**
本批的真实网络授权（`DEC-052`）**只覆盖 CN-07**，本卡不在其中——
所以**没有提交**，这一项的端到端留给 owner 开一个窗口。

`VERDICT-01` 已经把「判定落库」那条链修好并离线验过（13 条判据）；
差的只是「在真网络上跑一次」这一下。

## 六、④入台：第三处「今天没挂」也是假的

`web/components/plaza/cardActions.ts` 三处写着入台「今天没挂（实测 404，
且是框架的那种没有 `code` 的 404）」。按本批 `stale_premise` 纪律先核 X：

```
GET  /openapi.json → 工作台四条路由都在
POST /workbenches  → 422（缺 seed_cluster_id），**不是 404**
POST /workbenches {"seed_cluster_id": "c-20260810-000"}
                   → 201 {"graph_id":"wb-87be216d6b64", "created":true}
GET  /workbenches/wb-87be216d6b64
                   → 200，nodes 里一个 source_kind=cluster 的节点指着那条真热点
```

三处都改成实况。函数行为一个字没动（本来就是「照样打它、按答复说话」）——
**变的只是那句会误导下一个人的描述**。

## 判据：18 条，含卡面要的阴性对照

`test_each_smoke_names_its_own_endpoint`：逐项把那条路由从装配面上挖掉，
断言那一项红**且红的话里同时有编号与项名**——
一条只会说「某个端点不见了」的冒烟对排障没有用。

另外五条各钉住冒烟抓出的一处（源署名副本 / 收藏适配层 / worker 三条缝 /
design payload 键 / 状态机那张单），三条守《怎么测》与 trace 不脱节。

> `test_the_favorites_adapter_reads_the_snapshot_itself` 第一版又红在我自己身上：
> 它扫源码字面，而改动旁边那段注释**本来就要把旧字段名引出来**说明它错在哪。
> 改成**先剥注释再扫**——本仓这一坑踩到第七次了，所以这次把「怎么剥」也写进了判据。


## 五、⑤ 跑通了，而**作业表与事件流各说各的**

修完两处之后那一跑：**192 个事件**，末尾是本地模型写的真设计描述
（「…示省略号（...），保持卡片高度整洁。」），事件流的最后一条是
`{"kind":"status","state":"done"}`。

**而 `jobs.state` 那一行还停在 `queued`。**

两处对同一件事说了两句相反的话：订阅 SSE 的屏会看到「done」，
而轮询 `GET /jobs/{id}` 的屏会永远看到「排队中」。

没有在本轮改它——它不在本卡的 outputs 里，且改的是作业状态机那一层
（`DEC` 里 D6 定的东西）。**开单**：`docs/blocked/DESIGN-JOB-STATE-STUCK-AT-QUEUED.md`。

> 这一处配得上单独一条：`⑤` 屏上此前说「设计产物接口未提供」，
> 于是没有人往下走过一步；一路真跑下来，它后面还压着**三个**毛病
> （缺缝 · 键名对不上 · 状态机不一致）。**一句诚实的「未提供」也会挡住视线。**
