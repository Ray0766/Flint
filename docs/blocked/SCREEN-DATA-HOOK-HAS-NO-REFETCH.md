# `useScreenData` 没有 refetch 句柄——写完之后只能整屏重读

**状态** closed 2026-08-08（由 `UIX-05` 执行，v0.4.1 第 7 批）

## 修完了什么

签名从 `useScreenData<T>(path): Fetched<T>` 改成
`useScreenData<T>(path): { state, refetch }`，照本单 §「修法」那一行。

| 本单要盯的两点 | 落地 |
|---|---|
| ① `refetch()` 真的重发请求（**判运行时**，不判「函数存在」） | `web/lib/screenDataRefetch.test.tsx` 6 条：桩后端每次回新值，屏上从 1 变 2、`fetch` 调用数从 1 变 2 |
| ② 返回体 NEVER 被用来更新本地状态 | `test_the_write_path_still_ignores_the_response_body` 扫写入路径（无 `res.json()`、无本地记一份） |

**阴性对照**（本卡真正的核心）：不调 `refetch` 时等 60ms，屏上仍是旧值、
`fetch` 仍只被调过一次。没有这一条，一个「碰巧因为别的原因也重取了」的实现
会让正向判据绿——而那时 `refetch` 有没有起作用，谁也说不出来。

### 三条错误做法各自钉了判据

- **前端记一份** → `test_the_write_path_still_ignores_the_response_body`；
- **变化的假 query 骗重取**（`DEC-035` 判死的形状）→ 钩子里禁
  `Date.now()`/`Math.random()`/`_t=`/`cacheBust`/`nonce`，
  运行时另判**两次重取的 URL 逐字相同**；
- **`reload()`** → `test_no_screen_still_reloads_the_whole_page_to_refresh_data`
  扫 `web/app/**/*.tsx` 全站零命中（只判那一屏的话，下一个人在别的屏上又写一次）。

### 重取时先回到 loading

不回的话，旧数据会在新请求飞行期间留在屏上，而屏上没有任何东西说明它是旧的——
用户按下「选这条」，屏上一秒内显示的还是没选之前的样子，**他会以为自己没点上，
于是再点一次**。运行时判据钉住这一条。

### 本单说的「两处」，实况是**一处**

单子写「`ENTRY-02` 与 `ENTRY-01` 两处改用它」。实查：
`web/app/design/page.tsx`（`ENTRY-01`）**根本不用 `useScreenData`**——
它自己管提交结果，没有要重读的读态。**如实记下来**，
否则下一个人会去找那处不存在的改动。
`test_the_sheet_records_that_entry_01_had_nothing_to_convert` 钉住这件事，
且它会在设计屏哪天真用上这个钩子时红（那时前提变了，该回来改）。

顺带：另外八处只读屏改了取值写法（`const { state } = …`），**行为一字未改**。

---

## 以下为立单时的原文（一字未改）

**状态**（原）open

> 发现者：worker，v0.4.1 第 6 批 `ENTRY-02`（选主题的写入口）。
> **不是缺陷，是缺口**：这个钩子建的时候全站只有读屏。

## 现象

`web/lib/useScreenData.ts` 的签名是 `useScreenData<T>(path: string | null)`——
它在 `path` 变化时重取，**没有别的重取入口**。

第 6 批开始出现「写完之后要重读」的屏（`ENTRY-02` 的选主题是第一个，
`ENTRY-01` 的设计提交紧随其后）。今天这些屏只有三条路：

| 做法 | 代价 |
|---|---|
| **前端记一份**（乐观更新） | **NEVER**：刷新一次就没了，而用户以为自己已经选过。屏上那段注释逐字禁止它 |
| 拿一个变化的假 query 骗它重取 | **更坏**：那正是 `DEC-035` 判死的形状——靠 FastAPI 静默忽略未声明 query 去实现一个副作用 |
| `window.location.reload()` | 能用、诚实，但整屏重来（滚动位置、其它屏内状态全丢） |

`ENTRY-02` 走的是第三条，**并在屏上写明了为什么**。

## 修法（一张小卡）

给 `useScreenData` 出一个 `refetch()`：

```ts
const { state, refetch } = useScreenData<T>(path);
```

判据要盯住两点：① `refetch()` 真的重发请求（判运行时，不判「函数存在」）；
② **返回体 NEVER 被用来更新本地状态**——那条纪律是这批屏的根，
加了 refetch 之后最容易顺手破掉的也是它。

outputs 应为 `web/lib/` + 用到它的那几屏 + 判据。

## 为什么本卡没做

`ENTRY-02` 的 outputs 是 `flint/api/` + `web/app/` + 判据。
`web/lib/` 不在其中——按第 6 批工单纪律 5 停下立单。
