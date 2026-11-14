# WIRE-12 · 假空态：没有存储面的族 NEVER 回一个空表

**卡** `docs/steward/tasks-v041-b4.json#WIRE-12` · **cycles 2（oneshot=false）** ·
**self_review = true** → §5 · **owner_review = true** → §6 · **依赖** `WIRE-11`

## 1. 装载清单

卡面 WIRE-12 · `docs/blocked/WIRE-03-EMPTY-FROM-A-STORE-THAT-HAS-NO-DATABASE.md` ·
`flint/api/favorites.py` 五个端点 · `flint/api/design.py#/design/templates` ·
`flint/api/billing.py`（照抄形状） · `web/app/favorites/page.tsx` ·
`web/lib/screenAdapters.ts` · `web/components/favorites-library/FavoritesLibrary.tsx` ·
`tests/v041/test_ui05.py` 与 `test_ui_wired_live.py` 的登记面。
约 14k tokens，预算 40k 以内。

## 2. 那句系统没有依据说出口的话

装配之后两条端点回的是 `{"items": []}`——而迁移里 **34 张表没有 `favorites`，
也没有 `templates`**。那个空表与「查过了，你确实一条收藏都没有」**逐字相同**，
前端照契约渲染，屏上就写「还没有收藏」。

**真相是「这个功能还没有库，我们根本没查」。**

照 `/billing` 已经做对的形状改（`status` 一个位、`reason` 一句话）：

```
200 /favorites        {"status":"not_provided","reason":"收藏还没有存储面（迁移里没有 favorites 表）：本端点 NEVER 拿一个空列表冒充「你确实没有收藏」"}
200 /design/templates {"status":"not_provided","reason":"模板注册表不可用（迁移里没有 templates 表）：本端点 NEVER 拿一个空列表冒充「你确实没有模板」"}
```

## 3. 读回 200、写回 503——两种码各说各的事

**读用 200**：「这功能还没上」本身就是一个**成功的回答**。
用 4xx/5xx 会让前端的错误路径接管，屏上写「加载失败，请重试」——重试也不会有。

**写用 503**：调用方那次写**确实没有发生**。回 200 会让它以为存下了，
下一次它来读，读到的是「没有存储面」——那时它已经以为自己存过了。

## 4. 缝的两侧都留了实例

| 情形 | 表示 | 屏上 |
|---|---|---|
| `store=None`（没有存储面） | `{"status":"not_provided","reason":…}` | 「接口未提供」 |
| `store` 真在、里面没东西 | `{"items": []}` | 「还没有收藏」+ 去广场 |

**只改一侧的话，第二种意思就没地方表达了**——而它是一个真实存在的状态。
判据两侧各有一条（`test_a_real_store_still_means_checked_and_empty` 直接建一个
带真 `FavoriteStore` 的 app 来量）。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_no_fake_empty.py -q → 9 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 301 source files
            pytest -q               → 4014 passed（WIRE-11 收卡时 4005，本卡 +9）
前端:       npx tsc --noEmit → 无输出；npm test -- --run → 754 passed（+2）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 两族回的空表是没有依据的话 | `test_a_family_without_storage_never_answers_with_an_empty_list`（两族各一次） |
| ② 照 `/billing` 的形状 | `test_it_says_not_provided_and_says_why`、`test_the_billing_shape_is_the_one_being_copied`（**对照**：被照抄的那个形状还在，否则「照 billing 的形状」是一句没人验证过的话） |
| ③ 两种「没有」不合并 | `test_a_real_store_still_means_checked_and_empty`（另一侧）、`test_a_write_against_no_storage_is_refused_not_accepted`（写回 503） |
| ④ 前端跟着改 | `test_the_favorites_screen_maps_not_provided_to_the_not_checked_view` + `web/__tests__/app/ui05.test.tsx` 四条真取数判据（not_provided / 空表 / 有收藏 / 真发请求） |
| ⑤ 关闭 `WIRE-03` 那张单 | `test_the_ticket_is_closed` |

**② 改既有文件七处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `flint/api/favorites.py` | `store: FavoriteStore` → `FavoriteStore \| None`；加 `_NOT_PROVIDED` / `_read_or_absent` / `_write_or_absent`；五个端点各加一道；`_mine` 改成收 store 参数 | **卡上 outputs**。`_mine` 那处是类型收窄要的：`store` 可空之后，闭包里读它 mypy 不认 |
| `flint/api/design.py` | `/design/templates` 在 `not deps.registry.available` 时回 not_provided 姿态 | **卡上 outputs** |
| `flint/api/app.py` | favorites 传 `store=None` | 不传就是回到假空态 |
| `web/lib/screenAdapters.ts` | 新增 `toFavoritesView`（`not_provided` → `null`；`items` → 数组） | acceptance④ |
| `web/app/favorites/page.tsx` | 写死 `favorites={null}` → `useScreenData` + `toFavoritesView` | acceptance④。**这一屏本来是「假装查过」的另一种形式**：屏上话是对的，但它没问过 |
| `tests/v041/test_ui05.py` · `web/__tests__/app/ui05.test.tsx` | 「一个请求都不发、恒传 null」→ 真取数的四条口径 | 那两条钉的是这一族没挂上时的实情，**红得对**（§7） |
| `tests/v041/test_ui_wired_live.py` | `favorites/page.tsx` 从 `HELD_BACK` 移进 `WIRED`；`design/page.tsx` 换理由 | 等值登记面，切了一屏就得对上 |

`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；**未新增依赖**。

**③ 变异考 6 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 退回缺陷态：favorites 真拿一个 store（回到 `{"items": []}`） | 红 3 条，报「还在拿空表冒充查过了」 |
| ② 理由被抽空（`status` 在、`reason` 空） | 红 |
| ③ design 那条退回空表 | 红 2 条 |
| ④ 写操作回 200（假装存下了） | 红 |
| ⑤ 前端退回写死 `null` | 红 |
| ⑥ 假变异对照：末尾加一行注释 | 全绿 9 passed |

**变异考自己踩了坑**：①②③ 第一次跑「红」得不对——① 是 `FavoriteStore` 没 import
（6 个 collect error），②③ 是字符串拼接把语法弄坏了。**语法坏掉的红与判据咬住的红
在返回码上一模一样**。重跑时给变异器加了一道 `ast.parse` 前置校验，
并把每条的首行 `E` 打出来核对红的**理由**——这才是三条真红。

**④ 判据判注释、本批第五次**：`favorites/page.tsx` 的注释里写着
「`not_provided` → `favorites={null}`」正是为了说明这条映射，
被扫描判成「还写死着 null」。改成剥掉 `//` 行再判。
五次分别在 `AUTH-02` / `AUTH-05` / `WIRE-09` / `WIRE-10` / 本卡。

**⑤ 我自己弄脏了两个文件的行尾**：用 `io.open(..., "w")` 写 `.tsx`/`.ts` 时
Windows 把 `\n` 翻成 `\r\n`，`test_line_endings.py` 当场逮住（**它是对的**——
CRLF 会让别处的注释剥刀失效）。用二进制写回 LF 修好。
**教训与 `WIRE-11` 同族：脚本改文件 MUST 显式定行尾与语法校验。**

**⑥** 装载约 14k tokens；**⑦** 禁用词六词 0 命中。

## 6. owner_review

**设计屏没切成真取数，我停下登记了单子**（`docs/blocked/UI-DESIGN-SCREEN-NEEDS-A-FOURTH-STATE.md`）。

原因是组件的位不够：`DesignWorkbench.registryAvailable` 是三态
（没查过 / 坏了 / 可用），而后端现在给的是**第四种**——「这套部署根本没有模板表」。

- 塞进「坏了」→ 屏上写「请稍后重试」，而**重试一万次也不会有**；
- 塞进「没查过」→ 我们明明查过了；
- 留着写死（当前）→ 话碰巧是对的，但后端哪天真上了表，这一屏不会知道。

三条都不干净。加第四态要改组件契约 + 两条文案 + 切屏，**改动面大于卡上 outputs**，
按 §五.1 停下登记。收藏那一屏能切，是因为它的组件在 `WIRE-03` 时两条路就备好了。

**这件事值不值得单开一张卡，是你的判断。** 我的看法是值得——
它是本批「四类没有分得开」这条纪律在前端的最后一处未兑现。

## 7. 三条被我改红又改绿的等值判据

| 判据 | 它原来钉的 | 现在钉的 |
|---|---|---|
| `test_ui05.py::test_the_page_sends_no_request_and_passes_null` | 一个请求都不发、恒传 `null` | 真取数、两种答复各翻各的、**NEVER 写死任一种** |
| `ui05.test.tsx` 那两条 | 同上（组件级） | 拆成四条：真发请求 / not_provided / 空表 / 有收藏 |
| `test_ui_wired_live.py` 的 `HELD_BACK` | favorites 有意不切 | favorites 已切进 `WIRED`；design 换成真理由 |

**这些红不是坏消息，是记账**——它们就是来提醒「这一屏的取数口径变了」的。
每一条改后都比改前多量了东西（原来只判「不取数」，现在两侧都判）。

## 8. 登记未做

1. **设计屏的第四态**：见 §6 与那张单。
2. **`share` / `graph_edges` 两族仍在 `WIRE-03` 单里登记的名单上**，本卡未动——
   卡面 acceptance 只点名 favorites 与 design/templates。
   `share` 的假否定（「每个 token 都不存在」）性质更重，值得单独一卡。
3. **`prefs` / `share_links` 两张表**（卡面提到的四张表里的另两张）本卡没有落表——
   落表是 `AUTH-01` 那种量级的活，不在本卡 outputs。
4. **收藏的写路径回 503 之后，前端没有对应的提示**——
   屏上现在只显示读那侧的「接口未提供」，而写按钮本来就没渲染出来
   （`not_provided` 态不渲染列表），所以当前不可达。真上存储面时要一起看。
