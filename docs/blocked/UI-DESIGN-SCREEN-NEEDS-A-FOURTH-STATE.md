# UI-DESIGN-SCREEN-NEEDS-A-FOURTH-STATE · 设计屏要显示的那种「没有」，组件里没有对应的位

**状态** closed · 2026-08-08 · `DESIGN-03`

**发现者** worker / `WIRE-12` · 2026-08-06

**性质** 前端组件契约不够用（不是缺陷，是缺一个状态）

## 事实

`WIRE-12` 把 `/design/templates` 从「回一个空表」改成了照实说：

```
200 /design/templates {"status":"not_provided","reason":"模板注册表不可用（迁移里没有 templates 表）：本端点 NEVER 拿一个空列表冒充「你确实没有模板」"}
```

后端这侧干净了。但设计屏**没跟着切成真取数**，原因是组件那侧的位不够：

`DesignWorkbench` 的 `registryAvailable` 是三态——

| 值 | 意思 | 屏上 |
|---|---|---|
| `null` | 还没查过 | `design.solidify.not_checked` |
| `false` | 查过了，注册表**坏了** | `design.solidify.registry_down` |
| `true` | 查过了，可用 | 固化入口放开 |

后端现在给的是**第四种**：「这套部署根本没有模板表」。

## 为什么不能塞进已有的三种里

- 塞进 `false`（坏了）→ 屏上写「注册表不可用，请稍后重试」，
  而真相是**重试一万次也不会有**。这正是本批一路在禁的那件事：
  **「没配后端」与「坏了」NEVER 挤进同一个表示**；
- 塞进 `null`（没查过）→ 我们**明明查过了**，那是另一个方向的谎；
- 留着不切（当前做法）→ 屏上显示的话碰巧是对的（「接口未提供」），
  但它是**写死的**，后端哪天真上了 templates 表，这一屏不会知道。

三条都不干净，所以本卡停在这里登记，而不是挑一个看起来最像的。

## 要做的事

1. `DesignWorkbench` 的 `registryAvailable` 从 `boolean | null` 扩成
   四态（`"not_checked" | "not_provided" | "down" | "available"`）；
2. 补 `design.solidify.not_provided` 的 zh/en 文案；
3. `web/app/design/page.tsx` 切成 `useScreenData("/design/templates")`，
   四种答复各翻各的；
4. `tests/v041/test_ui_wired_live.py` 的 `HELD_BACK` 里删掉 `design/page.tsx`，
   `WIRED` 里加上它（那张表是等值判据，会自己提醒）。

**注意 `preview` 那一侧不在此列**：`POST /design` 仓里**根本没有这条端点**，
它的 `null` 是如实的「没查过」。本单只说注册表这一侧。

## 为什么 `WIRE-12` 不顺手做掉

卡上 outputs 是 `flint/api/` 与 `tests/v041/test_no_fake_empty.py`。
改组件契约 + 加两条文案 + 切屏，改动面大于 outputs——
按第 4 批纪律 §五.1，这种情况停下登记，NEVER 顺手扩面。

收藏那一屏能切，是因为它的组件在 `WIRE-03` 时就**两条路都备好了**
（`null` = 没查过、数组 = 查过了），不需要动契约。


---

## 关闭记录（`DESIGN-03` · 2026-08-08）

四态落地，逐条对上这张单要的三件：

1. `DesignWorkbench` 的 `registryAvailable` 从 `boolean | null` 扩成
   `RegistryState = "not_checked" | "not_provided" | "down" | "ok"`
   （单据当时建议的第四个名字是 `available`，**卡面写的是 `ok`**，按卡面的取）；
2. `design.solidify.not_provided` 的 zh/en 文案已补，且判据钉着它**说得出「重试也不会有」**
   ——「这里没有」与「坏了」的分界就在这一句上；
3. `web/app/design/page.tsx` 进屏真查一次 `/design/templates`（`probeRegistry`），
   四态由**查回来的答复**决定；初值是 `not_checked`，NEVER 初成 `down`。

阴性对照四条在 `web/components/design-workbench/registryStates.test.tsx`：
每一态单独构造，并**逐条断言另外三态的话不在场**。
判据 `tests/v041/test_design_solidify.py::test_the_fourth_state_sheet_is_closed`
**先验四态在位、再验这一行**——关单的条件是事情做完了，不是「那张卡跑完了」。
