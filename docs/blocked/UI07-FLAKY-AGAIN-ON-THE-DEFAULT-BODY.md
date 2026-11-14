# `UI-07` 那条两拍竞态又红了一次——这次是在**默认回包**那条路上

**状态** open · 2026-08-12 · `SHIP-16`

不阻断。本单登记的是**一次真实观测**与它的机理，NEVER 让它被「重跑一遍就好」抹掉。

## 一、实测（2026-08-12，第 16 批五条门）

```
cd web && npm test -- --run
FAIL  __tests__/app/ui07.test.tsx > UI-07 · 两轴正交（A3） > 屏上改一根轴，另一根原样不动
AssertionError: expected 'CN' to be 'FR'
Test Files  1 failed | 84 passed (85)
     Tests  1 failed | 857 passed (858)

紧接着单独连跑三次：npx vitest run __tests__/app/ui07.test.tsx
run1 / run2 / run3 → 18 passed × 3
```

**那一次红是在「全量 vitest 与全量 pytest 同时在跑」的机器上出现的**——
这一条要写进来：`FIX-04` 的两拍竞态**对调度压力敏感**，压力越大越容易抢到坏的那一拍。

## 二、机理（不是猜，是 `FIX-04` 已经证过的那一条，只是活在另一条路上）

`FIX-04`（2026-08-06，单 `UI07-LOCALE-TEST-IS-FLAKY.md` 已关）证过：
屏上到位要**两拍**——① 数据 ready、下拉渲染出来（此时草稿仍是声明的默认 `zh/CN`）；
② 对齐草稿的 `useEffect` 冲刷，值才变成后端给的那个。

它的修法是让 `renderLoadedPage` **等值而不是等元素**。那条修法对
**非默认回包**（例如 `en/JP`）是有效的：第一拍的值 `zh/CN` ≠ 期望值，等待不会提前返回。

**但对默认回包（`LOCALE_BODY = zh/CN`）它区分不了两拍**：第一拍的值恰好就是期望值，
`waitFor` 当场满足并返回，而那个对齐 effect **还挂在队列里**。今天红的这条用例正是：

```
const { container } = await renderLoadedPage();          // 默认回包 zh/CN → 可能只走到第一拍
fireEvent.change(region, {target:{value:"FR"}});         // 用户改成 FR
expect(region.value).toBe("FR");                         // ← 挂着的那个 effect 冲刷，把 CN 写回去
```

`FIX-04` 的关闭节里写着「默认值那条用例看不出来（zh/CN 恰好就是期望值）」——
**那句话预言的就是今天这一幕**，只是当时它落在另一条用例上。

## 三、为什么本批不修

本批（第 16 批）是停机前收尾，规则 `no_new_fronts` 逐字写着
「碰到别的问题一律开单，NEVER 顺手修」。而这一处要动的是
`web/__tests__/app/ui07.test.tsx` 的等待姿势（或 `LocaleSettingsPage` 的对齐 effect），
两者都在本批三张卡的 outputs 之外。

**更要紧的一条**：`UI07-LOCALE-TEST-IS-FLAKY` 自己写着
「**间歇红比稳定红更坏**：它会训练人『重跑一遍就好』」。所以这次照它的规矩办——
观测如实登记，**NEVER 写成「全绿」了事**。

## 四、修法（我认为是两条之一，但没动）

1. **等到第二拍真的冲刷完**：`renderLoadedPage` 里在 `waitFor` 之后补一次
   `await act(async () => {})`（或改用一个**非默认**的回包做这条用例的夹具，
   让「等值」重新能区分两拍）；
2. **从产品侧去掉那一拍**：`LocaleSettingsPage` 拿到数据时直接用它初始化草稿，
   而不是先渲染默认值再用 effect 对齐。第二条更根治，但它动的是产品代码，
   要先确认「未保存」那一态的语义不受影响（`NEVER 用浏览器语言猜地区`那条）。

**验收姿势**：改完 `npx vitest run --no-file-parallelism` **连跑 20 次**——
`ASM-03` 立过的规矩：**一次绿不算数**。

## 五、需要 owner 的什么

不需要决定，只需要排期（工程面）。下一批可直接领。
