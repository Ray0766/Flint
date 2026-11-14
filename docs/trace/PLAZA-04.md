# PLAZA-04 · 广场④：卡片三独立动作 + 点击排除区

> v0.4.1 第 5 批第七张。依赖 `PLAZA-01`（verified）。oneshot。

## 装载清单

`tasks-v041-b5.json#PLAZA-04` · `web/components/hotspot-card-actions/HotspotCardActions.tsx` ·
`flint/api/favorites.py`（`POST /favorites` 与 `FavoriteCreate`）· `flint/api/share.py`
（`POST /shares`、`TARGET_KINDS`）· `web/lib/interventionClient.ts`（身份头的既有写法）·
`web/lib/apiBase.ts` · 真栈三条 curl。约 8k tokens，**未超 40k**。

## 一、三条动作今天各自走到哪（开工时逐条打过真栈）

| 动作 | 端点 | 实测答复 |
|---|---|---|
| 收藏 | `POST /favorites` | `{"status":"not_provided","reason":"收藏还没有存储面（迁移里没有 favorites 表）…"}` |
| 分享 | `POST /shares` | `422 {"detail":{"allowed":["deliverable","graph","topic"]}}` —— **热点簇不在冻结件允许的三种里** |
| 入台 | `POST /workbenches` | `404`，且是**框架那种没有 `code` 的 404**（路由从没挂过） |

**三条都到不了「成功」——但这不等于本卡做不了。** `DEC-032` 定死了未装配期间的口径：
一律显示「接口未提供」，NEVER 显示空态／未启用／隐藏入口。
所以本卡交付的是**三个真会发请求、并把服务端的答复如实说出来的按钮**，
而不是三个假装能用的按钮，也不是三个被藏起来的入口。

## 二、三种「不成」NEVER 揉成一句

| 结果 | 说的是 | 谁去修 | 屏上形态 |
|---|---|---|---|
| `not_provided` | 这个能力还没接 | 我们去挂存储面／挂路由 | 虚线框 + mono（本仓给「未建」留位的既有形状） |
| `unsupported` | 能力在，但这类目标不在允许清单里 | 要改冻结件的 `target_kind` | 网点底纹 |
| `failed` | 别的失败，**后端自己的说明原样带出来** | 看那句话 | `--rust` 描边（本屏唯一的坏消息） |

揉成一句「暂不可用」，用户与下一个读代码的人都无从知道该做什么——
与本仓「未知 ≠ 没查过 ≠ 没接」是同一条纪律。

**分享照样把请求发出去**：「热点算不算可分享的目标」的真相在服务端（冻结件的判别联合）。
前端自带一份清单去预判，那份清单会与冻结件各自漂移；
422 的 `detail.allowed` 是服务端自己报出来的，用它渲染那句话永远不会说错。
判据 `test_the_allowed_list_comes_from_the_server_not_from_us` 反向盯着
前端源码里 NEVER 出现 `deliverable`/`graph`/`topic` 这三个字面量。

## 三、两处顺手修掉的真缺陷

### 3.1 三个**空按钮**

改前：`<button type="button" data-testid="action-favorite" onClick={onFavorite} />`
——没有文字、没有 `aria-label`、没有样式。读屏软件念不出来，屏上量出来是 0 像素。
**与 `F-09` 那个占 0 像素的争议记号是同一形状**：DOM 里有、用户看不见。

改后：三个按钮各有文案（走 i18n，中英各一份）与边框、hover、`focus-visible`。
判据在真浏览器里量：每个按钮 `width > 20 && height > 10` 且 `textContent` 非空。

### 3.2 `X-User-Id: "self"` 写死

首版把身份头写死在客户端里，`tools/no_scaffold_on_screen.mjs` 当场判红
（`FB-10` 的 A 类里 `X-User-Id` 逐字点名）。**它报得对**。

改成从配置读（`web/lib/apiBase.ts` 里新增 `API_USER_ID`，与 `API_BASE` 同款），
**没配就不发那个头**——发一个编出来的身份会让服务端把别人的数据当成你的。
没配时服务端会照实拒绝，屏上显示服务端自己的说明，而不是我们假装有一个用户。

## 四、改既有文件（工单纪律 4）

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `web/components/hotspot-card-actions/HotspotCardActions.tsx` | 三个空按钮，无结果位 | 三个带文案的按钮 + 一行结果（三种形态各不相同） | 卡面 acceptance①③：**只接线不另写**，而「接线」必须包括把答复说出来 |
| `web/components/plaza/PlazaCards.tsx` | 网格项只有卡面 | 卡面 + 动作区；结果**按卡片各记各的** | 一张卡的答复 NEVER 显示到另一张上 |
| `web/app/globals.css` | `.hotspot-card__actions` 零样式 | +动作区/按钮/三种结果形态 | 结构与样式成对交付 |
| `web/lib/apiBase.ts` | 只有 `API_BASE` | +`API_USER_ID` | 见 3.2；**超出卡面 outputs（`web/components/`），在此登记** |
| `web/messages/{zh,en}.json` | 无动作文案 | +7 键 ×2 | NEVER 在组件里写死中文 |

## 五、取证（真栈 `/plaza`，`.ui-probe/plaza_card_actions.json` + `plaza-card-actions.png`）

```
buttons   收藏 / 入台 / 分享 —— 三个都有字，宽高非零
zones     每张卡各一个动作区（>1）
真按一次「收藏」：
  outcome kind=not_provided · of=favorite · 376×21.2px · 文案「接口未提供」
  navigated 仍停在 /plaza —— **点击排除区在真浏览器里也成立**
```

截图已看过：三列网格里每张卡下方一排三个按钮，被按过的那张卡下面多一行虚线框的
「接口未提供」，其余卡片不受影响。

## 六、verify

```
pytest tests/v041/test_plaza_card_actions.py -q   → 11 passed
cd web && npm test -- --run                       → 77 files / 784 tests passed（新增 10 条交互）
cd web && npx tsc --noEmit                        → 0
ruff check . --no-cache                           → All checks passed
node tools/i18n_scan.mjs web --fail-on-cjk        → CJK 0
node tools/check_design_constraints.mjs web       → 0 处违规
node tools/no_scaffold_on_screen.mjs web          → 产品面没有 A 类脚手架
```

返工一轮：脚手架尺子抓住写死的身份头（见 3.2）。

## 七、self_review（worker.md §4.6）

① **测试覆盖 acceptance**：vitest 10 条 + pytest 11 条。
acceptance② 的「双断言」逐字落成两条 `expect`（点动作 `onSelect` 没被调用 · 点卡面被调用），
并在真浏览器里再验一次（点完仍停在 `/plaza`）。
② **无冻结件偏离**：`contracts/` 一字未动；允许清单不自带、恒取服务端答复。
③ **无禁用词**：本卡产出 grep 零命中。
④ **复用断言在位**：`test_the_actions_component_is_reused_not_rewritten`
扫全仓，除那一个组件外 NEVER 有第二处画动作区。
⑤ **装载未超预算**：≈8k tokens。

## 八、留给下游

三条动作的后端缺口逐条列名（第 5 批完成态报告会带上）：

1. `POST /favorites` 没有存储面（迁移里没有 favorites 表）；
2. 冻结件的 `Favorite.target_kind` 与 `share.TARGET_KINDS` **都不含 `cluster`**——
   热点簇能不能被收藏/分享是**冻结件面的决定**，NEVER 由一张前端卡自决；
3. `POST /workbenches` 从没挂过（`/workbenches/{graph_id}/edges` 挂了，创建那条没有）。

三条都接通之后，本卡的代码**一行都不用改**：`ok` 那一支早已备好。
