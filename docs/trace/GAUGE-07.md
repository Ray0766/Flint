# GAUGE-07 · locale 全仓尺加宽到九区代码

**卡** `docs/steward/tasks-v041-b3.json#GAUGE-07` · **cycles 2** ·
**self_review = true** → §5 · **owner_review = true** → §6 · **依赖** 无

## 1. 装载清单

卡面 GAUGE-07 · `docs/blocked/LOCALE-SEAM-RULER-MISSES-REGION-CODES.md` 全文 ·
`tools/check_locale_seam.py` 全文（约 200 行）· `contracts_v04.models_v04.Region` ·
`tools/orthogonality_check.py` 的 `_BROKEN` 段 · `tests/v041/test_locale_seam.py`
的白名单判据。约 10k tokens，预算 40k 以内。

## 2. 这把尺子此前只守住了**一条轴**

`PRINCIPLES#A3` 明写是两条轴：语言与地区。而 `LOCALE_LITERALS` 里
**九区代码一个都没有**，于是两种写法从它下面走得过去：

```python
if region == "CN":            # 分支假设
select_sources(region="CN")   # 调用点写死
```

`BE-07` 的变异考⑳ 就是这么过的——**两种都漏了**。
这把尺子自己的 docstring 写着「一处硬编码今天是一行，V2 全球版时是一处
要回头找的暗坑——**而它不会报错**」。地区那一半此前就在这个状态。

## 3. 九区**从冻结件取**，不手抄

`_frozen_regions()` 读 `contracts_v04.models_v04.Region`（9 个成员）。

手抄的清单不会跟着冻结件变：V2 加一个地区，尺子仍按九个量，
而**新加的那个地区从此不在护栏内**——最需要护栏的恰恰是新地区。

**取不到就 raise**，NEVER 退化成空集合：空集合会让这半条护栏静静地
不再报任何东西，而报告上写的是「0 处违规」——两句话在退出码上一模一样。

判据 `test_the_regions_come_from_the_contract_not_a_hand_copied_list`
判的是**源码**：那九个代码不许以字面量形式出现在集合里。

## 4. 先量再定豁免（卡面 acceptance③ 的顺序）

加宽后先跑一遍全仓（`flint` / `eval` / `harness` / `tools`，359 个文件）：

```
findings: 2   全部 kind=branch   全部在 tools/orthogonality_check.py:137,155
             分支假设：与写死的地区字面量比较 ['JP'] / ['CN']
```

**只有 2 处，且都在同一个文件。** 那两处是
`tools/orthogonality_check.py` 的 `_BROKEN` 字典——**另一把尺子的自证反例**：
它故意写坏四条 A3 接线（`"ja" if region == "JP"`、`"zh" if region == "CN"`），
用来证明自己报得出 A3 违规。

**判它红等于逼那把尺子删掉自己的反例，而那条反例守的正是本尺子同一条纪律。**

所以豁免逐条列名到**文件级**，理由写清它是什么。
判据 `test_every_whitelist_entry_names_a_file_and_gives_a_reason` 守着：
不许是目录、不许有通配、理由不许太短、且文件必须真的存在。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_locale_seam_regions.py -q → 15 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3817 passed（UIX-03 收卡时 3802，本卡 +15）
            python tools/check_locale_seam.py → exit 0；
                「白名单内命中 2 处」+「没有硬编码的地区假设」
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 九区并入、取自冻结件 | `test_all_nine_regions_are_in_the_literal_set`、`test_the_regions_come_from_the_contract_not_a_hand_copied_list`、`test_an_empty_contract_is_loud_not_silently_empty`、`test_the_language_axis_did_not_regress`（`en` 仍不在内） |
| ② 两类豁免写实 | `test_a_type_declaration_is_not_a_violation`（声明支持面）、`test_a_data_table_key_is_not_a_violation`（数据表的键） |
| ③ 先量再定、逐条列名 | `test_the_repository_is_clean_after_the_widening`、`test_the_only_whitelisted_hits_are_the_ones_we_measured`（判**条数与文件**）、`test_every_whitelist_entry_names_a_file_and_gives_a_reason`、`test_the_new_whitelist_entry_explains_it_is_another_rulers_control` |
| ④ 两种写法都报红 | `test_a_branch_that_assumes_a_region_is_reported`、`test_a_call_site_that_hardcodes_a_region_is_reported`（**各一条，NEVER 合成**——`BE-07` 那次两种都漏了）、`test_every_one_of_the_nine_regions_is_caught_not_just_cn`（九个逐个验：只验 CN 的话「集合里少了 SG」照样绿） |
| ⑤ 关闭问题单 | `test_the_ticket_is_closed`（走三选一的**第 1 个**） |

**② 改既有文件三处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `tools/check_locale_seam.py` | `LOCALE_LITERALS` 并入 `_frozen_regions()`；白名单加一条；补 `sys.path.insert`（CLI 跑法） | **卡上 outputs**。`sys.path` 那句是实跑撞出来的：少了它，护栏会崩在**读冻结件**这一步，看起来像「冻结件坏了」（`WIRE-01` 在另一把尺子上撞过同一个坑） |
| `tests/v041/test_locale_seam.py` | 白名单判据从「`findings` 全空」→「**探针那一条**不在 `findings` 里」 | 加宽后 `tools/` 下多了一处真命中（自证反例）。原写法会把那处无关命中算成本条失败——**它判的是「白名单起没起作用」，不是「全仓有没有别的命中」** |
| `docs/gauge_map.json`（`tools/gauge_map.py` 重生成） | 尺子清单随之更新 | 它自带判据「落盘 json 过期就红」，修法就是重跑 |

**③ 变异考 6 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 九区不再并入 | 红 |
| ② 手抄九区（不从冻结件取） | 红 |
| ③ 取不到冻结件时退化成空集合 | 红 |
| ④ 豁免改成整目录通配 | 红 |
| ⑤ CLI 的 `sys.path` 那句被抽掉 | 红 |
| ⑥ 调用点写死不再报（只留分支那一类） | 红 |
| ⑦ 假变异对照：只改一句注释 | 全绿 |

**④** 装载约 10k tokens；**⑤** 禁用词六词 0 命中。

## 6. owner_review

一处要你看：**全仓只红了 2 处**，远少于工单 §8② 的预估（「可能红出几十处」）。

这不是尺子没生效——`test_every_one_of_the_nine_regions_is_caught_not_just_cn`
逐个验过九个地区都报得出。真实原因是**本仓的地区那条轴本来就干净**：
`region` 一直是从 profile / 请求里传下来的，没人在业务代码里写死过它。

**这是个好消息，但值得你知道**：护栏此前是空的，而代码恰好没踩雷。
换句话说，此前那段时间的干净是**没有护栏保护的干净**。

## 7. 登记未做

1. **`web/` 不在扫描面内**。这把尺子只扫 Python（`flint`/`eval`/`harness`/`tools`）。
   前端的地区假设（比如 `RegionSwitch` 里写死一份九区清单）由
   `tools/check_design_constraints.mjs` 的 A3 管——**两把尺子各管一半**，
   但没有一条判据确认「两边的地区清单是同一份」。`LOC-01` 那张卡会碰到这处。
2. **`LOCALE_PARAMS` 仍是四个形参名**（`locale`/`lang`/`region`/`source_id`）。
   哪天有人把地区参数叫 `market` 或 `country`，调用点那一类就看不见了——
   这条边界是原设计，本卡未动。
