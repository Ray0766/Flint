# FIX-11 · 取数层补 `not_found` 态

> v0.4.1 第 6 批第十二张。全量 `pytest -q` **4478 passed / 0 failed**。

## 装载清单

`tasks-v041-b6.json#FIX-11` · `docs/blocked/FETCH-LAYER-HAS-NO-NOT-FOUND-STATE.md` ·
`web/lib/{screenClient.ts,ScreenFetchState.tsx}` ·
`web/components/shell/NotFound404.tsx`（`UIX-02` 建的，一直没人用）·
`web/__tests__/app/ui11.test.tsx`（既有期望）。约 10k tokens，**未超 40k**。

## 一、改前屏上说的是另一件事

后端对未知资源回的形状**是对的**：`404` + `{"code":"NOT_FOUND", …}`
（`BE-09` 的「404 不 403」口径）。而 `Fetched` 的五态里没有一个对应它——
带 `code` 的 404 掉进 `failed`，屏上于是写

> 取数出错 · 后端回了一个错误状态

**「这一条不存在」被说成「系统出错了」。** 两者要用户做的事完全相反：
前者换一个 id 或回上一层，后者等一会儿再试或来找我们。

`NotFound404` 组件 `UIX-02` 就建好了，**因为取数层没有这一态而一直用不上**——
本批反复撞见的「组件建好了没人用」，这一次的机械根因在**取数层**。

## 二、三种「拿不到」，三个 kind、三个标记、三句话

| 后端回什么 | kind | `data-screen-state` | 用户该做什么 |
|---|---|---|---|
| 404 **带** `code` | `not_found` | `not_found`（组件自己标） | 换一个 id / 回上一层 |
| 404 **不带** `code` | `not_provided` | `not_provided` | 等我们去挂路由 |
| 5xx / 其它 | `failed` | `failed` | 等一会儿再试 |

**后端那句说明原样带出**（`not_found` 带 `code` 与 `detail`）：
`BE-09` 把**无权**与**不存在**收进同一条路——分开说等于告诉未授权的人这个 id 存在——
所以那句话得由后端来说，NEVER 在屏上改写成一句自己编的「找不到」。

`what`（「这份交付物」「这个项目」）由**调用方**给；不给时退到一句通用的，
NEVER 编一个具体名词顶上：**编错了的那句话比笼统的那句更难发现**。

## 三、判据分两层，各判各能判的

- **源码层**（pytest，10 条）：联合里六态并列 · `not_found` 带 `code` 与 `detail` ·
  三支各走各的 kind（**阴性对照**：把 `not_found` 做成 `not_provided` 的别名
  也能让「有这一支」为真）· `not_found` 那一支里 NEVER 混进 `not_provided` ·
  组件自己标态、屏这边**不重复标**（两处都标的话，取证只取第一个嵌套值，
  改错哪一处都看不出来）；
- **渲染层**（vitest，7 条）：三种分别构造，断言**三句话互不相同**、
  **三个标记互不相同**、后端原话带得出来、`what` 给与不给两样。

**为什么必须有渲染层那一半**：源码层看不出两个分支渲染出同一句话——
而那正是改前的实况。

## 四、动了一条既有判据（期望值过期，意图没变）

`web/__tests__/app/ui11.test.tsx` 那条「库里没有这个项目 → 后端的 404 带 code，
NEVER 读成『接口未提供』」断言的是 `failed`。

**那正是本卡要修的毛病的另一半**：当时取数层没有 `not_found`，
所以它只能钉住一个不够好的现状。**意图从来没变**（别把应用的 404 读成路由未命中），
改的是期望值 → `not_found`，改因逐字写在判据上方。

## 五、一次返工：判据自己的切法错了

第一版 `union[: union.index(";")]` 切到第一个分号——而 `{ kind: "ready"; data: T }`
里面就有一个，于是只拿到头两行，判据报「联合里没有 not_found」。
**那句话是假的，红在判据上而不是产品上。** 改成切到空行，并把这件事写进那个 helper。

另删掉一处 `assert … or True`（恒真 = 没断言），换成真断言：
屏这边 NEVER 重复标 `not_found`。

## 六、取证：屏上那句话真的变了

`/topics/[id]`（demo 库当日没有主题，样例 id 是占位串——
`docs/blocked/DEMO-TOPIC-SAMPLE-ID-IS-A-PLACEHOLDER.md`）：

```
改前  取数出错 · 后端回了一个错误状态
改后  找不到这一条
      unknown topic: tp-placeholder      ← 后端原话
```

截图 `.ui-probe/topics-id-light-desktop.png`，**我自己看过**。
那一屏的控制台仍有 1 条 404——**那是对的**，是后端如实说「没有这一条」，
额度仍挂在那张活单上。

## 七、verify

```
pytest tests/v041/test_fetch_not_found_state.py -q → 10 passed
pytest -q（全量）                                   → **4478 passed / 0 failed**
cd web && npm test -- --run                         → 812 passed（80 文件）
cd web && npx tsc --noEmit                          → exit 0
ruff / check_line_endings                           → 全绿 / 220 个文件全是 LF
i18n_scan / check_design_constraints                → CJK 0 / 11 条 0 违规
harness/fe_smoke.py                                 → 横向溢出 0；噪声面仍是那两处活单
```

## 八、self_review

① 判据覆盖 acceptance 五条，含两条阴性对照（源码层的「三个 kind 真的不同」+
渲染层的「三句话互不相同」）；② 零冻结件改动；③ 无禁用词；
④ 改动面：`web/lib/` 两处 + `web/messages/` 两个 key + 判据 + 一条既有 vitest 期望，
**全在卡上 outputs**（`web/lib/` · `web/components/` · 测试）；⑤ 装载 ≈10k tokens。

## 九、留给下游

`not_found` 现在是取数层的一等态。**接新屏时**：`what` 记得给一个本屏的名词
（「这份交付物」而不是通用的「这一条」）——不给不会红，但屏上那句话会笼统一档。
