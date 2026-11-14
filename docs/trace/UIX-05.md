# UIX-05 · trace

**卡**：取数钩子——`useScreenData` 没有 refetch，写完只能整屏重读
**verify_cmd**：`pytest tests/v041/test_screen_data_refetch.py -q` → **9 passed**
**cycles**：1

---

## 装载清单（实际）

`docs/blocked/SCREEN-DATA-HOOK-HAS-NO-REFETCH.md` 全文 ·
`web/lib/useScreenData.ts` 全文 · `web/app/projects/[id]/topics/page.tsx` 全文 ·
`web/lib/screenClient.ts` 的 `fetchScreen` · 全站九处调用点 ·
`web/app/design/page.tsx`（核 `ENTRY-01` 有没有要改的）。约 15k tokens。

---

## 断点与决策日志

### 一、改签名，而不是加第二个钩子

`{ state, refetch }` 是单据 §「修法」逐字提的形状。代价是**九处调用点都要改取值写法**。

否掉的两个替代：
- **加一个 `useRefetchable`** → 两个钩子做一件事，正是本仓反复禁的
  「同一件事有两处定义」；
- **把 `refetch` 挂在返回的状态上** → `Fetched<T>` 是判别联合，
  挂方法要每个成员都挂，联合当场变浑。

八处只读屏的改动是纯取值写法（`const { state } = …`），**行为一字未改**。

### 二、重取靠递增一个计数，**它从不进 URL**

`setAttempt(n => n + 1)` 触发同一个 effect。这与「变化的假 query」的区别是本质的：
后者把状态塞进**请求**，而 `DEC-035` 判死的正是那种形状——
靠 FastAPI 静默忽略未声明 query 去实现副作用，
**哪天参数不再被忽略就当场坏掉**。

运行时判据因此判「两次重取的 URL **逐字相同**」，而不只是判源码里没有 `Date.now()`。

### 三、`refetch` 走 `useCallback`

每渲染新造一个的话，把它放进任何 `useEffect` 的依赖里都会造成**无限重取**——
而那个症状是「屏在疯狂打后端」，看起来像后端被攻击。

### 四、重取时先回到 loading

不回的话，旧数据会在新请求飞行期间留在屏上，而屏上没有任何东西说明它是旧的——
用户按下「选这条」，屏上一秒内显示的还是没选之前的样子，**他会以为自己没点上，
于是再点一次**。运行时判据用一个可控释放的桩后端钉住这一条。

### 五、单据说「两处」，实况是**一处**

`web/app/design/page.tsx`（`ENTRY-01`）**根本不用 `useScreenData`**——
它自己管提交结果，没有要重读的读态。判据
`test_the_sheet_records_that_entry_01_had_nothing_to_convert` 把这个实况钉住，
**并且它会在设计屏哪天真用上这个钩子时红**（那时前提变了，该回来改）。

如实记下来，否则下一个人会去找那处不存在的改动。

---

## 改既有文件

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `web/lib/useScreenData.ts` | 返回 `Fetched<T>`，只在 path 变化时重取 | 返回 `{ state, refetch }`；`attempt` 计数触发重取；重取先回 loading | 卡面 outputs 与单据修法 |
| `web/app/projects/[id]/topics/page.tsx` | `window.location.reload()` | `refetch()`，并把「当时为什么只能 reload」的记录留在注释里 | acceptance②。reload 整屏重来，丢滚动位置与屏内状态 |
| 另八处只读屏 | `const state = useScreenData(...)` | `const { state } = ...` | 签名变了。**行为一字未改** |

---

## self_review

**① 覆盖 acceptance**

| acceptance | 判据 |
|---|---|
| ① 现状（只有 path 一个入口、当前走 reload） | 单据原文 + `test_the_hook_returns_a_refetch_handle` |
| ② 加句柄，两处改用，reload 退役 | `test_the_topics_screen_uses_refetch_instead_of_reload` · `test_no_screen_still_reloads_the_whole_page_to_refresh_data`（全站扫）· `test_the_sheet_records_that_entry_01_had_nothing_to_convert`（第二处**不存在**，如实记） |
| ③ 三条错误做法逐条钉死 | 前端记一份 → `test_the_write_path_still_ignores_the_response_body`；假 query → `test_the_hook_does_not_fake_a_query_to_force_a_refetch` + 运行时判 URL 逐字相同；reload → 全站扫 |
| ④ **阴性对照：不调 refetch 屏上仍是旧值** | `screenDataRefetch.test.tsx` 第三条（等 60ms，值仍是 1、fetch 仍只 1 次） |
| ⑤ 关单 | `test_the_sheet_is_closed` |

test-first：判据先跑 **7 failed / 2 passed**，实现后 9 passed。

**② 无冻结件偏离**：未触碰 `contracts/` 与 `flint/domain/`；后端一行未改。
**③ 无禁用词**：新增/改动文件扫过，无命中。
**④ 复用断言**：钩子仍**只**调 `fetchScreen`（五态口径唯一一处），
NEVER 在钩子里做任何转换或乐观更新。
**⑤ 装载**：约 15k / 40k。

**其它门**：`ruff check . --no-cache` All passed；`npx tsc --noEmit` exit 0；
`npx vitest run` **82 文件 831 通过**（全量）。

---

## 产出文件清单

- `web/lib/useScreenData.ts`（签名 + refetch）
- `web/lib/screenDataRefetch.test.tsx`（新，6 条运行时判据）
- `web/app/projects/[id]/topics/page.tsx`（reload → refetch）
- 另八处只读屏取值写法
- `tests/v041/test_screen_data_refetch.py`（新，9 条）
- `docs/blocked/SCREEN-DATA-HOOK-HAS-NO-REFETCH.md`（closed）
- `docs/trace/UIX-05.md`（本文件）
