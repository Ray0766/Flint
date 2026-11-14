# FAV-WRITES · 收藏存得住了，屏上却没有入口按下去

**结论**：三条写操作（取消 / 更新到最新 / 看陈旧）接通，**三条各说各的**；
写完 `refetch` 而不是前端自己改列表。
对账器 `backend_unused_by_frontend` **20 → 17**。`verify_cmd` 9 条全绿。
另开一张单：**内嵌证据快照今天没有提供方**。

装载：`docs/steward/tasks-v041-b10.json#FAV-WRITES` · `flint/api/favorites.py` ·
`web/components/favorites-library/FavoritesLibrary.tsx` · `web/app/favorites/page.tsx` ·
`web/components/plaza/cardActions.ts` · `web/lib/useScreenData.ts`
（实测装载 ≈ 16k tokens，预算 40k）

---

## 1 三条各说各的（acceptance②）

**NEVER 合成一句「操作失败」**——三条失败之后用户该做的事完全不同：

| 操作 | 失败意味着 | 用户该做什么 |
|---|---|---|
| 取消收藏 | 那一条**还在**列表里 | 再点一次，或去查后端 |
| 更新到最新 | 收藏还在，**快照没换** | 稍后再试；内容本身没丢 |
| 看陈旧 | **不知道**它旧没旧 | 什么都不改——NEVER 显示成「最新」 |

合成一句的话，第三条会被读成前两条：用户以为自己刚才那一下没生效，
**而其实是我们没查到**。判据判三条措辞**互不相同**，并逐条钉住关键词。

`404` 单列一档（这一条不在 / 不是你的），与「后端挂了」不是一回事。
`not_checked` 是**一等答案**，`stale?: boolean` 保持可选——
写成必填的话，没查过时只能编一个。

## 2 写完 `refetch`，NEVER 前端自己抹掉那一条

抹掉之后如果后端其实没删成，屏上与库里就分叉了——**而分叉的那一侧看起来完全正常**。
`useScreenData` 的文件头写着同一条：`refetch` 只做「再问一次后端」，
NEVER 接受一个「新值」参数。

## 3 不传回调就**不渲染**那三个入口

渲染一个按不动的按钮，与「这个能力没有」在屏上长得一样，
而用户会以为自己没点到——`LOCALE-SAVE` 治的正是那种形状。

## 4 归属两个方向各判一次（acceptance③）

方向一：本人读得到、删得掉；方向二：陌生人**读不到也删不掉**（回 404 而不是 403）。
只判其中一个方向的话，一个「谁都读得到」的实现在方向一上照样绿。

## 5 acceptance④ 撞出一张新单

`POST /favorites` 的 `evidence_snapshot` 是**必填**，而广场那个动作送的是 **`{}`**。
于是**从广场收的每一条收藏，屏上都会说「内容不在了」**——
**那句话是实话**（快照确实是空的），但它读起来像缺陷，
而真相是**没有人往里面放东西**。

**本卡没有顺手补一个**：广场那一屏手上只有热点卡面（id / 名称 / 热度），
拿它们拼一个「证据快照」就是**编一份证据**——acceptance④ 逐字禁掉。
单据 `FAV-SNAPSHOT-HAS-NO-PROVIDER.md` 给了 owner 三个选项，
worker 倾向「收藏时由后端去取那一刻的证据卡」——**快照是「收藏那一刻的证据」，
而只有后端手上有证据**。

判据钉住现状：广场那条仍送 `{}`，且里面 **NEVER 出现前端编的字段**。

## 6 改前 / 改后 / 为什么非改不可

| 文件 | 改前 | 改后 | 为什么 |
|---|---|---|---|
| `web/lib/favoritesClient.ts` | 不存在 | 三条 + 三态结果 | §1 |
| `FavoritesLibrary.tsx` | 只读列表 | 三个入口（可选回调）+ 那一条自己的错误措辞 | §1 §3 |
| `web/app/favorites/page.tsx` | 只取数 | 接三条 + `refetch` | §2 |
| `web/messages/{zh,en}.json` | — | 各 +7 | 三个按钮 + 四条措辞 |

**后端一行没动**——三条端点 `PERSIST-01` 就建好了，缺的只是屏这一半。

## 7 自审（`self_review=true`）

**① 判据覆盖 acceptance**（五条）：①实况已钉；②三条各说各的（措辞互不相同 + 逐条关键词）；
③归属两个方向；④前端不编快照（且把「谁提供」开成单）；⑤对账器少三条（实跑对账器）。
**先红后绿**：9 条里 3 条在改前红。

**② 无冻结件偏离**：四件未触碰。**③ 无禁用词**：0 命中。
**⑤ 装载未超预算**：≈16k / 40k。

## 8 门

```
pytest tests/v041/test_fav_writes.py -q   9 passed
ruff check . --no-cache                   All checks passed!
npx tsc --noEmit                          0
npm test -- --run                         858 passed
对账器：backend_unused_by_frontend 17（改前 20）
```
