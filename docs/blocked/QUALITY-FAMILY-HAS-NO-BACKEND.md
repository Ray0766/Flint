# `GET /deliverables/{id}/quality` 是 503：逐章检查项因此永远显示「还没有判定」

**状态** open · 2026-08-12 · `WB-05`

不阻断（**当前行为是对的**：端点如实回 503，屏上如实说「还没有判定」）。
本单登记的是**那条 503 为什么在**，以及它什么时候该消失。

## 一、实测（2026-08-12，真栈）

```
GET /deliverables/del-demo-fixture-report/quality
→ 503 {"code":"FAMILY_NOT_CONFIGURED","family":"quality", …}
```

装配面（`flint/api/app.py:661-663`）：

```python
assembler.add(create_quality_app(QualityApiDeps(
    load_blocks=_unconfigured("quality"),
    deliverable_owner=_unconfigured("quality"), ref_resolver=None)))
```

路由挂着（`WIRE-01` 把它挂上了），**三个依赖全是占位**：一调用就 503 并点名是哪一族。

## 二、屏上的样子（`WB-05`）

章节导航每一章旁边都有一句检查问句与「是否满足」。
判定只能从后端来——拿不到时显示**「还没有判定」**，
**NEVER 显示「通过」**（工单原话）。今天七章全是「还没有判定」，那是实话。

判据两个方向各钉一次：屏上那句话在 · **请求真的发出去过**——
只判前者的话，一个从不去问的实现也会绿。

## 三、什么时候撤掉这条登记

`quality` 那三个依赖接上真存储那天。届时：

- 这条 404/503 从取证的报错面上消失（`tests/v041/test_wb_preview.py#KNOWN_404` 少一行）；
- 章节旁边开始出现真的「通过 / 没通过」，
  而 `WB-05` 那条「未判 7 · 通过 0」的判据会当场红——**那是好事**：
  它是提醒来这里销账的闹钟。

## 四、需要 owner 的什么

不需要决定，只需要知道：**这一族没配后端不是本批引入的**，
本批只是第一次把它显示在屏上（此前没有任何一屏问过它）。
