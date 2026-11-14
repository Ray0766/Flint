# PLAZA-03 · 广场③：四条状态规则

> v0.4.1 第 5 批第六张（`PLAZA-02` blocked，按文件卡序取下一张依赖就绪的）。
> 依赖 `PLAZA-01`（verified）。

## 装载清单

`tasks-v041-b5.json#PLAZA-03` · `docs/前端功能说明-v2.md#2.14`（第 101~108 行 + 话术表 164/165 行）·
`web/components/plaza/*`（PLAZA-01 的产物）· `web/components/shell/LoadingSkeleton.tsx` ·
`web/app/settings/locale/page.tsx`（`useScreenData` 的用法）· `web/messages/{zh,en}.json`。
约 9k tokens，**未超 40k**。

## 一、规格四条 ↔ 落点

| 规格 #2.14 原话 | 落点 | `data-plaza-state` |
|---|---|---|
| 加载中 → 骨架卡 | `HotspotCardSkeleton`（堆叠占位 + 网格占位） | `loading` |
| 空结果 →「该区当日无数据」并给出可切换的区，NEVER 回落到别的区假装有数据 | `.plaza-empty` + 区清单 | `empty` |
| 单区源全灭 → 缺数据角标（E6 降级行），其余照常 | `.plaza-badge--outage`，**卡片照渲染** | `source_outage` |
| 译名缺失 → 只显 `name_native` 单行（A7） | 由 `HotspotCard` 的逐槽隐藏持有，本卡只加判据 | `ready` |

## 二、三处「不能照做，只能如实说」

### 2.1 「给出可切换的区」——清单是真的，切换还没通

区清单从 `GET /settings/locale` 取（实测 `{"region":"CN","options":{"region":[9 个]}}`），
**NEVER 在广场再抄一份**（LOC-01）。但**切换本身没有后端**：
`GET /plaza/hot` 至今只收 `day`（`PLAZA-02` 的单子已把这条钉死）。

所以屏上如实说：区在这儿，切换还没接（`plaza.region.switch_not_wired`，
虚线框 + mono 短标签，与 `.not-provided` 同一族形态）。
**NEVER 画一个能点、点了却什么都不筛的控件**——那比没有控件更坏：
用户会把「全国的热点」读成「这个区的热点」。

判据 `test_the_...switch...`（vitest）断言那一段里**没有 button、没有 combobox**。

### 2.2 「单区源全灭」——后端没有这个信号，参数化留位

`GET /plaza/hot` 回的是 `{day, clusters, weak_signals}`，**没有任何一处说「这一区的源挂了」**。
所以 `sourceOutage` 缺省 `false`，行为与今天逐字相同；信号建成后接上即可，屏与判据都不用改。

**NEVER 由前端去猜**：「一条都没有」既可能是源挂了，也可能是这一区当日真的没有热点，
而这两件事该说的话完全相反。判据
`test_the_outage_signal_is_parameterised_not_guessed` 正向盯着缺省值，
反向盯着「NEVER 由 `length === 0` 推出源挂了」。

### 2.3 骨架卡不用 `shell/LoadingSkeleton`

那个画的是**横条**（给行式内容用）。广场是卡片网格与扇形堆叠，横条既占不对位置、
也不告诉人「这里将出现一张卡」。两者不是同一件东西，
**NEVER 为了「复用」把不合的形状套上去**。

骨架借的是**同一个卡壳**（`.hotspot-card` + `__top` + `__foot`），
所以与真卡尺寸逐像素相同——判据实测：骨架 376.0px、网格真卡 376.0px，差 <2px。

## 三、改既有文件（工单纪律 4）

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `web/components/plaza/PlazaCards.tsx` | 只有 ready / 空两条路 | 四态各有各的判别位与各自的话 | 本卡的产物 |
| `web/app/plaza/page.tsx` | `clusters === null` 时画一行「正在读取」文字 | 交给 `PlazaCards` 出骨架；另取 `/settings/locale` | 一行文字占不住卡片的位，数据落地整屏跳一次 |
| `web/app/globals.css` | 无四态样式 | +骨架/空态/角标三段 | 结构与样式成对交付 |
| `web/messages/{zh,en}.json` | 缺规格话术表登记的两句 | +4 键 ×2（两句照规格原话，判据逐字比对） | acceptance②要求文案走 i18n 中英各一份 |
| `web/components/plaza/plazaCards.test.tsx` | 空态断言 `plaza.empty` | 改判 `plaza.empty.no_data_today` | **换的是文案，不是语义**（查过了、这一区当日没有）。判据跟着换文案，NEVER 跟着换语义 |
| `web/__tests__/app/mainchain.test.tsx` | 一个响应体喂给所有 fetch | 按 URL 分派 | 广场屏现在取两条端点；同一份 `{clusters:[…]}` 喂给 `/settings/locale` 会让报错指向广场，而真相是 mock 喂错了 |
| `tests/v041/test_plaza_cards.py` | 排布层零卡面类 | 骨架卡列入准借白名单 + **补偿断言**（它一个数据槽都不许渲染） | 见 2.3；渲染了数据的「骨架」就是第二份卡面 |
| `tests/v041/test_hotspot_card_format.py` | 卡面只写一份 | 同上白名单，指向那条补偿断言 | 同上 |

## 四、判据分两层，各挡各的

- **阴性对照在 vitest**（`plazaStates.test.tsx`，12 条）：四态各构造一次，
  **逐条断言另外三态不在场**——只断言「本态在」的话，一个把四态全渲染出来的实现照样全绿；
- **pytest 14 条**判 vitest 够不着的：判别位互不重复、两句文案与规格逐字一致、
  以及**骨架在真浏览器里真的占了一张卡那么大的位**。

最后那条是重心：骨架的全部意义就是占位。0 像素的骨架与「一行加载中文字」效果一样。

## 五、取证（真栈 `/plaza`，`.ui-probe/plaza_states.json` + `plaza-loading.png`）

```
loading  state=loading · 骨架卡 6 张 · 首张 376×180 · 圆角 8px(--r-card) · 有纸面底色
         deckReserved=true（堆叠那 420px 台面也占住了）· aria-busy=true · 真卡 0 张
ready    state=ready · 网格真卡 376×… · 骨架 0 张
```

截图已看过：屏头下一行「正在读取当日热点」，其下一张居中的卡形占位（对应堆叠当前卡），
再下是三列骨架网格——**与加载完成后的版式逐块对齐，数据落地时屏幅不跳**。

## 六、verify

```
pytest tests/v041/test_plaza_states.py -q     → 14 passed
pytest tests/v041/test_plaza_cards.py -q      → 18 passed（PLAZA-01 的判据未倒，另加两条）
cd web && npm test -- --run                   → 76 files / 774 tests passed（新增 12 条阴性对照）
cd web && npx tsc --noEmit                    → 0
ruff check . --no-cache                       → All checks passed
node tools/i18n_scan.mjs web --fail-on-cjk    → CJK 0
node tools/check_design_constraints.mjs web   → 0 处违规
node tools/no_scaffold_on_screen.mjs web      → 产品面没有 A 类脚手架
```

返工四轮，每轮都是尺子先红：
① 骨架只占了网格的位、没占堆叠那 420px 台面（判据比出骨架 376 / 真卡 535.6 —— 后者其实是
**堆叠里放大过的那张**，两族东西比不出东西）→ 一并修两处：骨架补上台面占位、判据改比同族；
② `mainchain` 三条红：广场屏多取了一条端点而 mock 只有一份响应体；
③ 上一轮用 heredoc 注入判据时 `\b` 被写成了**真的退格符**（ruff `PLE2510` 抓到 5 处）——
正则语义被悄悄改掉而测试照绿，**这类红最值钱**；
④ 两把「卡面只写一份」的尺子咬住骨架卡（它是故意借卡壳的）→ 白名单 + 补偿断言，
NEVER 只加白名单不加补偿。

## 七、self_review（worker.md §4.6）

① **测试覆盖 acceptance**：vitest 12 条阴性对照 + pytest 14 条；
四态判别位互不重复由「四态各渲染一次逐个判等」钉住，不是「本态在场」那种弱断言。
② **无冻结件偏离**：`contracts/` 一字未动。
③ **无禁用词**：本卡产出 grep 零命中。
④ **复用断言在位**：区清单只有一处真相（`test_the_region_list_comes_from_the_locale_endpoint`
正向 + 反向盯着广场里 NEVER 出现区码字面量数组）；骨架借壳配补偿断言。
⑤ **装载未超预算**：≈9k tokens。

## 八、留给下游

- `PLAZA-02` 的两条后端缺口通了之后，本屏要做两件事：把「切换还没接通」那句删掉、
  把 `sourceOutage` 接到真信号上。两处都已经留好位，改动是**接线不是重写**。
- 译名缺失那一条（A7）在广场上是**恒成立**的：`/plaza/hot` 根本没有译名字段。
  等它有了，`HotspotCard` 的次要行会自动出现——判据已经在 `plazaStates.test.tsx` 里钉着。
