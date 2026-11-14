# TYPE-05 · trace

**卡**：契约⑤——尺子看清之后浮出的 7 条 `field_mismatch`
**verify_cmd**：`pytest tests/v041/test_type_gaps_mismatch.py -q` → **10 passed**
**cycles**：2（分析 1 轮 + 实现 1 轮，跨两个回合；断点靠本文件接力）

---

## 装载清单（实际）

**第一轮（分析）**：`tasks-v041-b7.json#TYPE-05/06` ·
`tools/check_fe_be_parity.py` 的 `_frontend_interfaces` / `_field_findings` /
`_best_interface` · 对账器 `--json` 实跑输出。

**第二轮（实现）**：对账器**重跑一次**（trace 里那两张表是上一轮的，
照过期清单建类型与照记忆写没有区别）· `flint/api/deref.py` 的
`fact_json` / `chart_json` / `card_json` / `hints_json` / `citation_json` / `price_json` ·
`flint/api/favorites.py#favorite_json` · `flint/api/share.py#link_json` ·
`flint/api/analysis.py` 的 `design_generate` 段 · `web/lib/{types,derefClient}.ts` ·
`tools/check_fe_be_parity.py#_handler_keys` 与 `#_best_interface`。

两轮合计约 34k tokens（**分两个回合装载**，单轮均未超 40k）。

---

## 断点与决策日志

### 一、卡面那句「真漂移」，七条里只有一条成立

卡面写「建了类型但字段对不上（真漂移）」。逐条摆出实跑输出之后：

| 端点 | 尺子挑中的接口 | 它凭什么挑中 | 真相 |
|---|---|---|---|
| `/charts/{}` | `types.ts#DisputeSubmitEcho` | 共有 `status` / `ledger_version` | 前端**没有** chart 类型 |
| `/facts/{}` | 同上 | 同上 | 前端**没有** fact 类型 |
| `/favorites` | `interventionClient.ts#DisputeInput` | 共有 `target_id` / `target_kind` | 前端**没有** favorite 类型 |
| `/shares` | 同上 | 同上 | 前端**没有** share 类型 |
| `/hints/{}` | `viewsClient.ts#VerdictGap` | 共有 `missing_what`/`cause`/`action` | `VerdictGap` 是 Gate 判定里的缺口，不是 deref 的 hints |
| `/projects/{}/design_generate` | `types.ts#ReportSubmitEcho` | 共有 `job_id` | 见下「三」 |
| `/cards/{}` | `viewsClient.ts#EvidenceCard` | 共有五个真字段 | **这一条是真的部分覆盖** |

`_best_interface` 的门槛是「至少两个字段重合」——它挡住了单字段巧合，
**没挡住双字段巧合**。

**所以本卡做的不是「对齐那些接口」**：那会把 chart 的字段塞进一个争议回执里，
正是 `DEC-034` / `DEC-038` 反复禁的借槽。本卡给它们**各建自己的类型**。

### 二、全 `unknown` 能让尺子归零，而那不是类型

尺子只比字段**名**。十五个 `field: unknown` 铺满就能让计数为 0，
而 `tsc` 从此对这些端点一个字都不检查——**尺子是绿的，类型系统是瞎的**。

所以每个字段的类型都对着后端读出来：`price_low: number`、`citation_ids: string[]`、
`published_at: string | null`（ISO 日或 null）……
`unknown` **只留两格**：`FactDeref.value` 与 `FavoriteRow.evidence_snapshot`——
它们真的是任意 JSON。判据 `test_unknown_is_only_used_where_the_payload_really_is_any_json`
把这份名单钉成闭集，另一条判据要求文里写清为什么。

### 三、`design_generate`：payload 与响应是**两个**类型

`_handler_keys` 把处理函数里**所有字面量 dict 的键**都算作这条路由的键，
于是 `submit(payload={...})` 里那三个键也在其中，而响应其实只有 `{job_id}`。

**编一个带 `brief` 的「响应」类型能让尺子闭嘴，而那种类型描述的东西根本不存在**——
下一个人照它去读 `res.brief`，拿到的永远是 `undefined`。

所以拆成两个：`DesignGeneratePayload`（进队列的那份，真实存在）与
`DesignGenerateAccepted`（`{job_id}`）。判据钉住两者字段不互串。

### 四、`/settings/locale` 中途换了类别

补完前六条之后它从 `frontend_untyped_response` 变成了 `field_mismatch`
（`FieldNotAllowed` 的两个字段落进了它的响应里）。
**要让 `field_mismatch` 归零就得连它一起建**——所以本卡顺带把它做了，
`TYPE-06` 因此从八条降到五条（已在 `test_types_complete` 的清单里改成实况）。

它的类型此前**屏里有、`web/lib/` 里没有**。尺子只扫 `web/lib/`——
而尺子扫不到的类型，**别的屏也 import 不到**：
广场那一屏此前只好自己再写一个 `LocaleForPlaza`。

### 五、两条 deref 顺带一起建

`/citations/{}` 与 `/price-entries/{}` 属 `TYPE-06` 那一类，但它们与本卡那四条
**同住六条解引用通道**。分两处建会让读的人只看到一半，所以一并落进
`web/lib/derefTypes.ts`，并在文件头写明这一点。

---

## 改既有文件

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `web/lib/types.ts` | 无 favorite / share / design_generate / locale 类型 | 各建；`FieldNotAllowed` 两端共用 | 卡面 outputs |
| `docs/前后端对账表-v041.md` | 36 条 | 重跑生成，26 条 | 表是**跑出来**的，不是手写的；判据判「共 N 条」与实跑相等 |
| `tests/v041/test_types_complete.py` | 十五条清单钉死 | 改成剩余五条 + 断言 `field_mismatch` 已零 | 前提第三次过期（清零 → 看见十五条 → 补完十条）。**每一次钉住当时那个值，都会让下一次正常的修复被判成错** |
| `tests/v041/test_fe_be_parity.py` | 断言真仓库里 `field_mismatch` 非空 | 改判**分类能力本身**（合成三例：全覆盖 / 半覆盖 / 不相干） | 同上，这是它第三次换值。彻底不再钉真仓库的取值——那才是这条判据从第一天起就想守的东西 |

后两处**在卡上 outputs 之外**（outputs 是 `web/lib/` + 本卡判据），
均由本卡的修复直接引发，**在此点名，供 steward 复核**。

---

## self_review

**① 覆盖 acceptance**

| acceptance | 判据 |
|---|---|
| ① 七条点名 | `test_each_of_the_seven_named_endpoints_is_clean`（**逐条**，不只判总数——总数为 0 也可能是这七条从此扫不到了） |
| ② 「不是新引入的」 | 本 trace §一 与判据 docstring 逐条记下每条是被**哪个接口**误匹的 |
| ③ 字段以后端真实 payload 为准，NEVER 手抄 | 清单**重跑**取得；`test_the_fields_match_what_the_backend_really_returns`；`test_unknown_is_only_used_where_the_payload_really_is_any_json` |
| ④ `field_mismatch` 归零并接成硬判据 | `test_no_endpoint_is_reported_as_a_field_mismatch` + `test_the_checker_did_not_go_blind`（反向守卫）+ `test_the_checker_would_still_catch_a_missing_field`（阴性对照，直接调比对函数） |

**② 无冻结件偏离**：未触碰 `contracts/` 与 `flint/domain/`；后端一行未改。
**③ 无禁用词**：新增/改动文件扫过，无命中。
**④ 复用断言**：NEVER 重抄 client 里已有的接口（`test_no_type_was_copied_from_a_client_into_types_ts` 仍绿）；
六条解引用通道的形状同住一个文件。
**⑤ 装载**：分两轮，单轮均 < 40k。

**其它门**：`npx tsc --noEmit` exit 0；
`pytest tests/v041/{test_type_gaps_mismatch,test_types_complete,test_fe_be_parity,test_endpoint_triage,test_parity_blind_spots}.py -q` 全绿。

---

## 产出文件清单

- `web/lib/derefTypes.ts`（新：六条解引用通道的响应形状）
- `web/lib/types.ts`（+favorite / share / design_generate 两型 / locale 两型 / FieldNotAllowed）
- `tests/v041/test_type_gaps_mismatch.py`（新，10 条）
- `docs/前后端对账表-v041.md`（重跑生成，**outputs 外**）
- `tests/v041/test_types_complete.py` · `tests/v041/test_fe_be_parity.py`（前提刷新，**outputs 外，供复核**）
- `docs/trace/TYPE-05.md`（本文件）
