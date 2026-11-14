# REGION-11 · trace

**卡**：地区面④——`global` 与 `NULL` 归入显式的「未归区」（`DEC-040`）
**verify_cmd**：`pytest tests/v041/test_unassigned_region.py -q` → **15 passed**
**cycles**：1（卡面估 2）
**owner_review**：true —— 按 `DEC-000` 事后补审

---

## 装载清单（实际）

| 来源 | 用途 |
|---|---|
| `docs/blocked/REGION-08-GLOBAL-IS-A-SOURCE-CONSTANT-NOT-A-REGION.md` 头部 | 立单缘由 |
| `DECISIONS-v04.md#DEC-040` | 本批刚落的裁决 |
| `flint/api/views.py` 的 `_known_regions` 与 plaza 段 | 改点 |
| `contracts_v04/models_v04.py#Region` | 九区词表（只读） |
| `web/components/region-switch/RegionSwitch.tsx` 全文 | 选项渲染 |
| `web/app/plaza/page.tsx` 全文 | 清单从哪来、传给谁 |
| `web/components/plaza/PlazaCards.tsx` 的 region 用法 | 空态那句「换个区试试」 |
| `tests/v041/test_plaza_region_query.py` 全文 | 第 6 批的种子/取数样式，本卡沿用 |
| `web/messages/{zh,en}.json` 相邻行 | 文案 key 的落法 |

估算约 20k tokens，未超 40k 预算。

---

## 做了什么

**后端**（`flint/api/views.py`）：

- 新增 `UNASSIGNED_REGION = "unassigned"`。记号取一个**撞不上地区码**的词——
  `Region` 那九个全是两位大写字母。
- 新增 `SOURCE_CONSTANT_REGIONS = ("global",)`：落在 `region` 列里、**但不是地理事实**的值。
- 新增 `_selectable_regions()` = 九区 ∪ {未归区}，**与 `_known_regions()` 分开**：
  后者是地理词表（也是 `GET /settings/locale` 的 `options.region`），未归区不属于它。
- plaza 的 WHERE 从两分支改成三分支，逐条对应筛选面上的三种状态：

  ```
  ① 不筛      $3 IS NULL AND NOT $4
  ② 未归区    $4 AND (c.region IS NULL OR c.region = ANY($5))
  ③ 某地理区  $3 IS NOT NULL AND c.region = $3
  ```

**前端**：

- 新建 `web/lib/regions.ts`：`UNASSIGNED_REGION` / `withUnassigned()` / `regionOptionLabel()`。
- `RegionSwitch` 渲染 `regionOptionLabel(r)` 而不是 `r`。
- `web/app/plaza/page.tsx` 用 `withUnassigned(...)` 组出筛选清单，
  同时传给 `RegionSwitch` 与 `PlazaCards`。
- 文案 key `region.unassigned.label` 落 `zh.json` / `en.json`。

---

## 断点与决策日志

### 一、未归区**不进** `options.region`

第一直觉是让 `GET /settings/locale` 直接回十个选项，前端零改动。**否掉了**：
那是 locale 的**地理词表**，`PUT /settings/locale` 拿它校验用户偏好——
塞进去等于允许把「未归区」存成一个人的**常住地**。

所以：九区清单仍然只有一处真相（`LOC-01`），未归区是**筛选面**上的第十个选项，
由广场在取到那九个之后追加。`test_the_plaza_appends_the_option_to_the_nine_from_the_backend`
与 `test_the_locale_vocabulary_is_untouched` 两条一起钉这件事。

### 二、`global` 本身仍然选不了

这不是遗漏，是本卡的立场：**`global` 不是一个地方。**
用户选的是「未归区」——一个承认「我们不知道产地」的选项，而不是一个叫「全球」的地方。
`test_global_is_still_not_a_selectable_region` 钉住 400。

### 三、真正值钱的判据是**闭合**，不是「未归区能选」

acceptance④ 那条。只断言「未归区能选、能回 104 条」的话，
将来多出一种 region 值（某个源写死 `worldwide`）时它照样绿，
**而那批簇会重新变得筛不到**——正是这张单的原病。

所以判的是：`九区之和 ∪ 未归区 == 全量`，**且选项之间互不重叠**。
重叠那条单独判，因为「加起来等于全量」在多算一次、漏算一次时也能成立，
而屏上同一条热点会在两个区里各出现一次。

### 四、`NEVER 回填` 判两遍，一动一静

- **动**（`test_the_database_still_tells_the_two_apart`）：种子进去什么样、读出来什么样，
  `ur-none` 仍是 `NULL`、`ur-gl-1` 仍是 `global`；
- **静**（`test_no_migration_backfills_null_into_global`）：扫 `migrations/versions/`，
  NEVER 出现把区回填成 `global` 的 `UPDATE`。

静态那条是必需的：**回填一旦跑过就再也看不出来了**——
回填过的行与本来就是 `global` 的行长得一模一样。所以它必须在**写进仓库的那一刻**被拦住。

那条判据**剥掉注释再扫**（本仓第九次撞见「把说明问题的那句话当成问题本身」）。

### 五、实测数字：89 / 104 是**全表**的，不是某一天的

卡面 acceptance④ 写「选 CN 拿到 89 条 · 选未归区拿到 104 条」。
**那两个数是全表的**（`clusters` 共 193 行 = 89 + 103 + 1），
而广场是**按天**的。本机 demo 库实测（`FLINT_DEMO_DSN`，新代码在进程内跑）：

```
clusters.region 分布： {'global': 103, 'CN': 89, '<NULL>': 1}     ← 与 steward 实查逐字相同
clusters 总数：193 = 89 + 104                                      ← 全表口径对得上

最新有热度点的日子：2026-07-05
  全量：106
         CN:  18
 unassigned:  88
九区+未归区 覆盖：106 | 漏：[] | 多：[]                            ← 闭合成立
region=global → 400
```

**18 + 88 = 106 闭合**。这里如实记下口径差，NEVER 为了对上卡面那两个数去改判据。

---

## 视觉取证

重启了 demo 后端（`harness.demo_server` 两个进程跑的是改动前的代码，
带 `region=unassigned` 回的是 400——**那不是缺陷，是进程旧**）。重启后：

```
locale=200  unassigned=200  CN=200
```

`scripts/ui_probe.py` + 一段一次性 playwright（`C:\pwenv`，NEVER 装进项目 .venv）：

```json
{"value": "unassigned",
 "label": "未归区（不是一个地理区：源没说产地，或源说的是「全球」）"}
"console_errors": []
{"cards_before": 111, "cards_after_unassigned": 93,
 "url_after": "http://localhost:3000/plaza?day=2026-07-05&region=unassigned"}
```

产物 `.ui-probe/region11-unassigned.png` **已用 Read 看过**：
下拉里那一项文案完整、地区标签在位、卡片堆叠正常、页面无横向溢出。
111 → 93 与 API 侧的 106 → 88 对得上（屏上多出 5 张是「今日精选」堆叠里的重复渲染）。

---

## 改既有文件

### ① `flint/api/views.py`（在 outputs `flint/` 内）

- **改前**：`_known_regions()` 是唯一的合法值来源；WHERE 是
  `($3::text IS NULL OR c.region = $3)`；docstring 末段写着「`global` 筛不出来，
  **那是对的、也是要的**——它让 `REGION-08` 那个问题留在明面上」。
- **改后**：加两个常量与 `_selectable_regions()`；WHERE 改三分支；
  docstring 末段改写成「选 `global` 仍然 400，而那 104 条不再筛不到——
  它们经**未归区**这个显式选项出来」。
- **为什么非改不可**：单据已由 `DEC-040` 裁决关闭，
  那段「让问题留在明面上」的话**前提过期了**——问题已经有答案，
  再留着它会让下一个人以为这件事还悬着。`_known_regions()` 的语义**一字未动**
  （它仍然只回冻结件那九个），新逻辑走的是并列的新函数。

### ② `web/components/region-switch/RegionSwitch.tsx`（在 outputs `web/` 内）

- **改前**：`<option>{r}</option>`，区名原样打印。
- **改后**：`{regionOptionLabel(r)}`。
- **为什么非改不可**：`unassigned` 是内部记号，印在屏上就是 `FB-10` 点名的
  **A 类脚手架：开发要看的东西跑到了产品面**。地区码仍然原样显示，只有未归区走文案。

### ③ `web/app/plaza/page.tsx`（在 outputs `web/` 内）

- **改前**：`regions={locale.data.options?.region ?? null}` 直接传给两个组件。
- **改后**：先 `withUnassigned(...)` 组出 `filterRegions`，两处都用它。
- **为什么非改不可**：未归区必须出现在筛选面上（acceptance③）。
  `PlazaCards` 那一处一并换掉，是因为空态那句「换个区试试」列的是筛选面的其它选项——
  **今天未归区是库里最大的一批（104 条），从「其它去处」里漏掉它，
  等于把最可能有结果的那一项藏起来**。

### ④ `web/messages/{zh,en}.json`（在 outputs `web/` 内）

各加一条 `region.unassigned.label`。文案 MUST 说清**它不是一个地理区**——
只写三个字的话，它排在九个国家代码旁边，读起来像第十个国家。
写入按原文件的键序（字典序）插入，其余键**一字未动**。

### ⑤ `tests/v041/test_plaza_filters.py`（第 6 批交付，**outputs 外——唯一一处**）

- **改前**：`test_the_pending_semantics_sheet_is_still_open` 断言单据**仍然 open**。
- **改后**：改名为 `test_the_global_semantics_were_ruled_on_and_not_renamed_to_worldwide`，
  断言 closed + 点名 `DEC-040`/`REGION-11`，**并接着守那条判据自己 docstring 里写的担心**：
  「关掉它，下一个人会顺手把**「全球」两个字**加上」——
  所以改后逐字判选项文案是「未归区」且**不以「全球」开头**。
- **为什么非改不可**：owner 裁了、单据随之关闭，前提过期。
  **红的是自己描述的那个状态过去了，不是有人偷偷关单。**
  意图一字未改，而且这次把它 docstring 里那句担心**从注释变成了断言**。

**这一处在卡上 outputs 之外**（outputs 是 `flint/` · `web/` ·
`tests/v041/test_unassigned_region.py`）。判断为不必走 `docs/blocked/`：
改动面是一条判据的前提刷新，由本卡的关单动作直接引发——但**在此点名，供 steward 复核**。

### ⑥ `docs/blocked/REGION-08-…md`

状态改 closed，写明裁决、两条错法、交付清单、以及「`global` 本身仍然选不了」这一条立场；
立单原文一字未改地留在下半部分。

---

## self_review（卡上 `self_review=true`）

**① 测试真实覆盖 acceptance**

| acceptance | 判据 |
|---|---|
| ① 分布实况（103/89/1），`global` 是源常量 | trace 实测记录 + `SOURCE_CONSTANT_REGIONS` 的注释；`test_global_is_still_not_a_selectable_region` |
| ② 两条错法都不采（不当第九区、不让它消失） | `test_global_is_still_not_a_selectable_region`（不当区）· `test_the_unassigned_option_returns_both_global_and_null`（不消失） |
| ③ 「未归区」可见可选且**标注不是地理区** | `test_the_option_is_labelled_as_not_a_geographic_region` · `test_the_switch_renders_the_label_instead_of_the_raw_sentinel` · `test_the_plaza_appends_the_option_to_the_nine_from_the_backend` · 视觉取证 |
| ④ 阴性对照三条 + **闭合** | `test_the_unassigned_option_is_a_proper_subset` · `test_the_nine_regions_plus_unassigned_cover_everything` · `test_the_options_do_not_overlap` |
| ⑤ 库里两者可分辨，NEVER 回填 | `test_the_database_still_tells_the_two_apart`（动）· `test_no_migration_backfills_null_into_global`（静） |
| ⑥ 关闭 `REGION-08` 单 | `test_the_sheet_is_closed_and_records_the_ruling` |
| （附）前后端记号不漂移 | `test_the_frontend_and_backend_agree_on_the_sentinel` |

test-first 顺序有据：判据先跑 **11 failed / 4 passed**，实现后 15 passed。

**② 无冻结件偏离**：未触碰 `contracts/` 与 `flint/domain/`。
`contracts_v04.Region` 只被读，`test_the_locale_vocabulary_is_untouched` 断言它仍是那九个。

**③ 无禁用词**：对本卡新增/改动的五个源文件扫 `适当/合理/必要时/大约/尽量/若干`
与列表尾的「等」——无命中。

**④ 复用断言在位**：九区清单仍**只有一处真相**（`GET /settings/locale` → 冻结件 `Region`），
本卡 NEVER 在前端抄第二份（`LOC-01`）；记号在前后端各一处且判据判它们相等。

**⑤ 装载未超预算**：约 20k / 40k。

**其它门**：
`ruff check flint/api/views.py tests/v041/test_unassigned_region.py --no-cache` → All checks passed；
`mypy --strict flint` → 306 files, Success；
`npx tsc --noEmit` → exit 0；
`npx vitest run components/region-switch components/plaza app/plaza lib` → 17 文件 141 通过；
`pytest tests/v041/test_plaza_region_query.py tests/v041/test_plaza_filters.py
tests/v041/test_regions_from_backend.py -q` → 全绿（`test_plaza_filters` 那条前提刷新后）。

---

## 产出文件清单

- `flint/api/views.py`（`UNASSIGNED_REGION` · `SOURCE_CONSTANT_REGIONS` · `_selectable_regions` · 三分支 WHERE）
- `web/lib/regions.ts`（新）
- `web/components/region-switch/RegionSwitch.tsx`（选项文案）
- `web/app/plaza/page.tsx`（`withUnassigned` 组清单）
- `web/messages/zh.json` · `web/messages/en.json`（各 +1 key）
- `tests/v041/test_unassigned_region.py`（新，15 条）
- `tests/v041/test_plaza_filters.py`（一条判据前提刷新，**outputs 外，供复核**）
- `docs/blocked/REGION-08-GLOBAL-IS-A-SOURCE-CONSTANT-NOT-A-REGION.md`（closed）
- `.ui-probe/region11-unassigned.png`（取证）
- `docs/trace/REGION-11.md`（本文件）
