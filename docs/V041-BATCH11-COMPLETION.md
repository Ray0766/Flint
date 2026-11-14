# v0.4.1 第 11 批 · 完成态报告

**8 / 8 卡 verified · 0 blocked。** 五条全局门全绿，**pytest 零 failed**。

七项核心功能**六项能用**，一项（⑥热点分析）等你开一个网络授权窗口。

---

## 一 七项功能可测状态表

> 与 `docs/怎么测-v041.md` **同源**（那一页是给你对着产品逐条走的详版，
> 含每项的「点哪里 / 该看到什么 / 不能用时缺什么」与四条通用排障）。

| | 功能 | 能不能用 | 怎么测（最短一句） | 不能用时缺什么 |
|---|---|---|---|---|
| ① | 热点搜集 | **能** | 看广场卡片是不是真词面 | 是 `热搜话题NN` → 灌库没跑真源；某源整个不见 → 看当日 `degradation_notes` |
| ② | 广场与卡片 | **能** | `/plaza?region=CN` → 切到 `HK` | HK 回 400 → `Region` 里没 HK；有数据不显示 → `:8000` 跑的是旧进程 |
| ③ | 收藏 | **能** | 广场「收藏」→ `/favorites` | 说「内容不在了」→ 后端取证失败（502）或适配层又读 `has_snapshot` |
| ④ | 入台 | **能** | 广场「入台」→ 回 201 + 读回那张图 | 回**没有 `code` 的 404** → 路由没挂；回 422 → 缺 `seed_cluster_id` |
| ⑤ | AI 设计工作台 | **能生成**（进度条会一直转） | `/design` → 写一句话 → 生成 | 秒挂 `HandlerDepsMissing` → worker 少一条缝；转圈不停 → **已知缺陷，见下** |
| ⑥ | 热点分析 | **等你开窗口** | 选 2 张热点 → 建组合 → 发起分析 | **只缺那一跑**：分析要打真实 github/arxiv，而 `DEC-052` 只授权 CN-07 |
| ⑦ | 本地模型生成计划书 | **能** | 提交 report/proposal → 看 `deliverables` 多一条 | 提交回 503 `family=analysis` → `create_app` 没拿到 `redis_url` |

### ⑥ 要你做的那一件

给一个像 `DEC-052` 那样的窗口（**域名 + 每源上限 + 留痕要求**），我按它跑一次真分析并把结果贴回来。

功能这一侧已经就位：提交端点在（缺字段会 422 点名）、判定读端点在（没判过回 404 并说明）、
「判定落库」那条链已修好并离线验过 13 条判据。**差的只是在真网络上跑一次。**

### ⑤ 的已知缺陷（已开单）

`docs/blocked/DESIGN-JOB-STATE-STUCK-AT-QUEUED.md`——生成真的跑完了、
事件流报 `done`（192 个片段），**而 `jobs.state` 停在 `queued`**。
症状是「点了生成，转圈不停，而内容其实已经出来了」。
`compose`（⑦）那一族是对的，所以不是状态机整体没接。

---

## 二 五条全局门（逐字贴）

```
$ ruff check .
All checks passed!

$ PYTHONIOENCODING=utf-8 python -m mypy --strict flint
Success: no issues found in 321 source files

$ PYTHONIOENCODING=utf-8 python -m pytest -q
5232 passed, 2 skipped, 12 warnings in 424.58s (0:07:04)

$ npx tsc --noEmit
（无输出，退出 0）

$ npm test -- --run
Test Files  85 passed (85)
     Tests  858 passed (858)
```

### pytest 的红：一条都没有

本批一路上红过的每一条，**逐条点名归属**（NEVER 按族小结）：

| 曾经红的 | 归谁 | 现在 |
|---|---|---|
| `test_cn04_source_repair::…region_is_cn_while_the_url…` · `::…display_name_says_it_is_hong_kong` | 前提被 `DEC-056` 推翻（钉着「落 CN」「署名带港区」） | 各翻一面 |
| `test_cn06_e2e_real::…screen_name_says_hong_kong` | 同上 | 翻成「必须不带地区缀」 |
| `test_locale_seam_regions::…all_nine_regions…` · `test_unassigned_region::…vocabulary_is_untouched` | 数目/集合写死在判据里（HK 是第十个） | 改成守它真正要守的：护栏包含 · 未归区没混进词表 |
| `test_cn_only_scope::…machine_readable_record` | `DEC-056` 修订 `DEC-045` 前半 | 跟着改数，三态与反向保留一条没松 |
| `test_regions_from_backend::…serves_the_nine…` | 同上 | 只改了一个数字就跟上了——那正是当初把清单搬到源头换来的 |
| `test_blocked_sheets_state::…declares_its_state…` | **我新开的两张单**格式写错 | 按既有形状改 |
| `test_gauge_map::…disk_copies_are_current` | 我加了新判据文件 | 重跑 `tools/gauge_map.py` |
| `test_line_endings` ×2 | **我的 `write_text` 把 5 个 web 文件整体转成 CRLF** | 按字节改回 LF |
| `test_design_submit::…payload_carries_what_the_consumer_reads` | **这条判据自己就是缺陷**（见 §四） | 翻面，且把消费方那一侧一起读进来 |
| `test_fav_writes::…never_invents_snapshot_content` | `DEC-055` | 从「不出现编的字段」翻成「整格不由前端说」 |
| `test_smoke_seven::…adapter_reads_the_snapshot_itself` | 判据扫字面扫到我自己的解释性注释 | 改成先剥注释再扫 |

ruff 第一轮 5 errors，全是本批新写的判据文件（用不上的 `noqa` · import 未排序 ·
没用到的 `Any` · 两处 `import x as x`）——**逐条改，没有用 `--fix` 盲改**。

---

## 三 八张卡各做了什么

| 卡 | 病 | 现在 |
|---|---|---|
| `DEC-055-056-LANDING` | — | 两条原文一字未改追加，水位 054→056，既有 63907 字节逐字节未动 |
| `CN-07` | ghtrend/arxiv 的窗口**结构上恒回 0 条**，而回执写 `ok` | 各回看 7 天；0 条目落 `empty_result` 降级行 |
| `REGION-CN-HK` | HK 数据顶着「中国大陆」的名字（繁体港区词坐在 CN 屏上） | CN=微博 50 条 · HK=Google 趋势 10 条，两区都可切 |
| `COMPOSE-01` | ⑦提交回 503，被一句过期注释讲成「刻意没做」 | 真跑通：`queued→drafting→done`，22 个 block 的真正文 |
| `VERDICT-01` | 判定成功而**无人记它判了谁**（`cluster_verdicts` 0 行） | 诊断出第三种病因；两处缺缝都接上 |
| `FAV-SNAPSHOT` | 收藏屏每条都说「内容不在了」 | 后端自取到真证据卡与真微博链接 |
| `SMOKE-01` | 七项从没被逐项真跑过 | 七项全打过；抓出五处只有真跑才看得见的缺陷 |
| `SHIP-11` | — | 本报告 |

---

## 四 本批最贵的四次「判据全绿而屏上照旧」

**这一批的主题只有一个**：判据绿不等于用户能用。四次都是打真栈才看见的。

1. **改了一份、漏了另一份，而两份都自称是这一源的名字。**
   `REGION-CN-HK` 改了后端 `SOURCE_DISPLAY_NAME`，HK 区屏上照旧写「Google 趋势（港区）」——
   `web/messages/*.json` 里还有一份。后端那条判据绿着，用户看到的是旧的。

2. **收藏屏读的是一个后端从来不发的字段。**
   适配层读 `row.has_snapshot`，而后端回的是 `evidence_snapshot`，
   `Boolean(undefined)` 恒 `false`——**再完整的快照屏上也说「内容不在了」**。
   `FAV-SNAPSHOT` 那一卡 17 条判据全绿，而屏上一个字没变。

3. **一条名叫「两边对得上」的判据，钉住的正是那个对不上的键。**
   `test_the_payload_carries_what_the_consumer_reads` 断言 `payload["brief"]`，
   而消费方读 `payload["prompt"]`。它一直是绿的，
   而 `design_generate` 这一族**从来没有跑通过一次**。

4. **一句诚实的「未提供」也会挡住视线。**
   ⑤设计屏上写着「设计产物接口未提供」——那句是实话（导出那一半确实没配），
   于是三个批次里没有人往下走过一步。真跑下来，它后面压着**三个**毛病：
   worker 少一条缝 → 键名对不上 → 状态机不一致。

---

## 五 要你定的三件

1. **`Region` 从九个成员加到十个**（`docs/blocked/REGION-CN-HK-COUNT-SAYS-SEVEN.md`）。
   `DEC-056` 说「两区都可切」，而 HK **原本不在清单 A2 的九区里**。
   我核了三件事才动手（原冻结件里根本没有 `Region`、additive 校验器明确允许加 Literal 成员、
   `DEC-056` 是该文件自述的合法改动来源），所以没停。
   但 `DEC-056` 原文写「其余七区」——**实际是八区**，且纸面规格「九地区」今天与代码对不上了。
   **要你确认的只有这一件。**

2. **⑥的网络授权窗口**（见 §一）。

3. **一条簇的成员真的跨了两个区**（`docs/blocked/REGION-CN-HK-ONE-CLUSTER-SPANS-BOTH.md`）。
   `c-20260629-108`（脑机接口）同时来自 ghtrend 与 gtrends。
   既有口径写死「跨区 MUST 停下上报，NEVER 取众数」，所以没给它挑区，留在未归区。
   单据里列了三条处置路，倾向乙（`global` 不参与定区），但那是改判定口径，不由实现者定。

---

## 六 吸收批那 9 条本批不做

`docs/research/对标审阅-2026-08.md` §2 那 9 条要严格化的对象是**判定与引用**。

**推迟理由**：本批之前 `cluster_verdicts` 全库 0 行、compose 提交回 503、
设计生成从来没跑通过——**要严格化的东西基本是空的**。
对着空表做严格化，做出来的判据只会证明「空表符合规范」。

**重启条件**：⑥在真网络上跑通一次之后，库里第一次有真判定与真引用，那 9 条才有检得到的东西。

---

## 七 收工纪律的落地检查

- **顺序**：先写七张 trace 与台账 → 再跑五条门 → 最后只改本报告的数字。
  门跑完之后**没有再动任何被判据读的文件**；
- 台账那一行落下之后**单独重跑了它的读者判据**（`test_ledger_pairing_v041` 11 passed）；
- **每张卡的 `started` 与终态成对**——`SMOKE-01` 走了返工环
  （`started` → `blocked`（⑤那处状态机）→ `verified`），`blocked` 也是一次「开始过」的记号；
- pytest 的红**逐条点名归属**（§二），NEVER 按族小结；
- 真实网络**只在 CN-07 那张卡上发生过**：`VERDICT-01` 与 `SMOKE-01` 都只接线、不实跑，
  两处 trace 各写明了这一点；
- 组稿与判定一律走**免费本地档**（`LocalProvider` → 本机 Ollama），**一个 key 都没读过**。
