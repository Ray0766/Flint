# UI-BATCH4-FORK-PACK-OVERVIEW trace — 受众分叉 / vibe_pack / 项目总览 / R1~R4 @2026-08-02

> owner 三批交付的**第三批**（收尾）。

## 0 范围

P11 受众分叉 `/projects/[id]/proposal` · P12 vibe_pack 查看器 `/deliverables/[id]/pack` ·
P14 项目总览 `/projects/[id]` · R1 账户 / R2 额度 / R3 质量卡 / R4 陈旧横幅（占位，均在 P14 内）。

`web/` 一字未动（63 测复跑全绿）；`contracts/` 与 `flint/domain/` 未动；
**后端端点响应形状未动**；**compose 按 owner 裁决刻意未挂**；零联网装包；零付费。

## 1 逐条自检（E 组 29~32 + A 组复查）

| # | 条目 | 结果 | 证据 |
|---|---|---|---|
| 29 | 受众强制单选、**无默认**；ai_executor 锁 vibe_pack | ✅ **已实屏验证** | 两支受众 radio **均未预选**（断言直接扫 `<input type="radio" name="audience">` 确认无 `checked`，不是只看文案）。未选受众时模板区写「此处不预先展示任何默认模板」。选 ai_executor → 模板区只出现一枚**锁定态** `template_id · vibe_pack`，**不给第二个选项**，并写明这是契约规则（`plan_proposal`）而非界面偏好 |
| 30 | 受众混用的 422 如实报错 | ✅ 规则上屏 · ⚠️ **未实机取到 422** | 四种会 422 的情形逐条列明（缺 audience／ai_executor+非 vibe_pack／human_reader 未给模板／模板不在五套内），与 `flint/compose/audience.py#plan_proposal` 的真分支一一对应。并写明「本地预检只是提前提示，判定以后端为准」。**提交端点未挂，故 422 未实机触发** |
| 31 | vibe_pack 排版与报告**明显不同** | ✅ **已实屏验证** | 差异是结构性的：报告屏是阅读版式（34em 正文栏／出处槽／衬线标题／段落流）；P12 是**清单/载荷版式**——整屏等宽、标题不用 `font-display`、S1~S9 规格表、零正文流、零出处槽。断言用 `unseen` 反向确认 P12 **不含**出处槽与报告块类型标记 |
| 32 | R1/R2/R3/R4 明确写「端点未建」 | ✅ **已实屏验证** | 统一走 `UnbuiltEndpoint` 件：虚线边 + `Construction` 记号 +「端点未建」徽记 + 未来端点形状 + 为什么没有 + 「此处不提供任何可点控件、不显示任何数值」。R2 明写现状是 `flint/config.py` 的 `billing_enabled = False` |
| A-1 | 无进度条/百分比/星级/雷达 | ✅ | 三屏各断言 `unseen 可靠度` 与 `unseen ★` |
| A-3 | 解引用端点未建处留取数位并写明 | ✅ | R3 质量卡明写 `GET /quality-cards/{card_ref}` 未建、且报告里只显 `card_ref`；P12 明写 pack 内容端点未建 |
| A-5 | `--spark` 只留给 blocking/409/503 | ✅ | 本批三屏**零 spark**（无告警语义），占位一律墨色 + 虚线 |
| A-6 | 三态齐全 | ✅ | P14 主题区：真实列表／空数组空态（明写「未知 project 也走这条路径——非 404 非错误」）／`ApiErrorNotice` 错误态。P11 为纯表单无远程读；P12 元信息 404 时如实写「元信息端点未回内容」 |
| A-7 | 无专属端点的屏必须标注由哪几支组合 | ✅ **已实屏验证** | P14 顶部专门一块：「这一屏没有专属端点（设计决策）」+ 列出三支来源 + 说明后端**没有**按 project 列 jobs/deliverables 的端点 |

## 2 compose 未挂时怎么做 P11（owner 裁决的落法）

提交路径**不做假按钮**：屏上明写
「所以这里没有可点的提交按钮——界面不做一个点了没反应的按钮，也不造一个永远 queued 的假作业」。
取而代之的是一枚「校验并生成载荷（本地，不发请求）」——它按 `plan_proposal` 的真规则做本地预检，
校验通过就把**将来要发的载荷** JSON 摊在屏上。接线当天把这一步换成真请求即可，表单侧零返工。

断言 `unseen("P11 不造永远 queued 的假作业", "已提交，正在排队")` 把这条钉住。

## 3 P14 的诚实边界（本批最容易做假的地方）

后端**只有**按 id 单查的 `GET /jobs/{job_id}` 与 `GET /deliverables/{id}`，
**没有**「按 project 列作业/交付物」的端点。

所以作业区与交付物区**不列举任何条目**，只写清缺的是哪一支端点。
我一度写了个 `<form action="/gate">` 的 job_id 输入框，**随后删掉了**——
它提交后会去 `/gate?jobId=x`（不是真路由），正是「看起来能用的假功能」。
现在那里是一句话：「已知 job_id 时直接访问 /gate/{job_id}。这里不放输入框——
一个提交后不知道去哪的框，就是看起来能用的假功能。」

## 4 验证（真实数字，全部本人跑）

| 项 | 结果 |
|---|---|
| `npx tsc --noEmit` | **exit 0** |
| `node scripts/check-screens.mjs` | **150 / 150，失败 0，exit 0**（118 → 150，本批新增 **32** 条） |
| `node scripts/check-connectivity.mjs` | **94 / 94，exit 0** |
| `scripts/check_contrast.py` | 两主题 × 22 对 + 硫磺圈地 0 违规，**exit 0** |
| `ui_probe`（P11/P12/P14 × 2 主题 × 桌面/移动） | **12 张，问题计数 0** |
| `ruff check .` | All checks passed |
| `mypy --strict flint` | 224 文件净 |
| `cd web; npm test -- --run` | **63 测全绿** |
| `pytest -q` | **1339 passed in 128.88s，0 failed，exit 0** |

## 5 我真看过的 / 没验证的

**真看过（逐张 Read）**：
- P11 日间桌面：两支受众 radio **都没选中**、模板区「不预先展示任何默认模板」、
  四条 422 规则、提交区「端点未接线」+ 无提交按钮
- P12 夜间桌面：整屏等宽、无衬线大标题、S1~S9 规格表、「端点未建」徽记

**没验证（不背书）**：
- **422 未实机取到**：提交端点未挂，四条混用规则是照 `plan_proposal` 的真分支写的，
  但**没有一次真的 422 响应被渲染过**。
- **P14 的 R1~R4 全部是声明**：它们本来就没有端点，所以「验证」到此为止——
  能验的只是「屏上确实写了端点未建、且没有可点控件」。
- **P12 只呈现结构骨架**：各节正文没有读端点，故**没有任何真实 pack 内容被渲染过**。
  S1~S9 的章节名取自 vibe_pack 口径，**不是**从某个真实 pack 产物里读出来的。
- **P14 的 jobs/deliverables 两区没有真实数据流经**：它们不列举，所以也就没有可验的渲染。
- **P11/P12/P14 的移动端两主题**只有探针「0 溢出 / 0 控制台错误」量测，未逐张看图。
- `next build` 未跑；平板断点未测。

## 6 三批共同的一条运行时摩擦（值得 owner 知道）

**每跑一次完整 `pytest -q`，演示库里的 projects / topics / deliverables / snapshots 就被清空一次。**
本轮三批里我因此重建了 **4 次**：`gate1_live replay-qwen`（判定样本）、
`demo_seed_report`（报告夹具）、`POST /projects/combo`（真 project + 主题，每次约 20~26s 本地 qwen）。

`start-demo.ps1` 已经自愈报告夹具（上一轮加的），但**判定样本与 combo 项目仍需手动重建**。
这不是缺陷，是演示库与测试库共用一个 PG 的既有事实；
若你希望减少这类往返，可考虑给 `start-demo.ps1` 再加这两步（**属产品取舍，我不代拍**）。

顺带：本批为重建数据又跑了两次 combo，`degraded` 分别为 **true / false** ——
即该位确实会在真实运行中两种都出现。

## 7 落盘清单

| 文件 | 改动 |
|---|---|
| `V0 files 前端设计/components/proposal/audience-fork.tsx` | **新建**（P11 交互，照 plan_proposal 真规则） |
| `V0 files 前端设计/app/projects/[id]/proposal/page.tsx` | **新建**（P11） |
| `V0 files 前端设计/app/deliverables/[id]/pack/page.tsx` | **新建**（P12，载荷版式） |
| `V0 files 前端设计/app/projects/[id]/page.tsx` | **新建**（P14 组合屏 + R1~R4） |
| `V0 files 前端设计/components/honesty/unbuilt-endpoint.tsx` | **新建**（R1~R4 共用预留位件） |
| `V0 files 前端设计/scripts/check-screens.mjs` | 新增本批 32 条断言 |

**未动**：`contracts/`、`flint/domain/`、后端端点响应形状、`web/`、`flint/api/**`、`components/ui/**`。
