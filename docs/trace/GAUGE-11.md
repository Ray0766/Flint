# GAUGE-11 · 33（实测 35）条端点逐条分诊

**卡** `docs/steward/tasks-v041-b4.json#GAUGE-11` · **cycles 2（oneshot=false）** ·
**self_review = true** → §5 · **owner_review = false** · **依赖** `WIRE-11`

## 1. 装载清单

卡面 GAUGE-11 · `docs/前后端对账表-v041.md` ·
`tools/check_fe_be_parity.py` 的 `frontend_calls` / `_ENDPOINT_LITERAL` /
`_STRING_LITERAL` · `web/lib/derefClient.ts` 与 `interventionClient.ts` ·
`web/app/**/page.tsx` 十六屏的取数状况 · `docs/V041-BATCH3-COMPLETION.md`。
约 17k tokens。

## 2. 分诊的第一条结论推翻了这一类的名字

`backend_unused_by_frontend` 读起来是「后端有、前端没人用」。
**35 条里有 12 条前端真在调**——两个盲区，机制不同：

| 盲区 | 机制 | 条数 |
|---|---|---|
| 首段白名单 | `_ENDPOINT_LITERAL` 写死了一串首段（`plaza\|clusters\|projects\|…`），不在串里的**永远扫不到** | 7 |
| 只扫 `web/lib/` | `frontend_calls` 只看 `web_dir / "lib"`，而 `useScreenData("/account")` 写在 `web/app/**/page.tsx` | 5 |

**两者要人做的事完全相反**：真没人用 → 去接线；尺子没量到 → 去修尺子。
混在一个名字下报出来，就是让人去接一条**已经接好的线**——
接完它照样报「没人用」，那时人会以为自己接错了。

盲区二有一处值得记：`frontend_calls` 的 docstring 解释过「只扫 lib 是因为页面里的
`/plaza` 是 href 导航不是 API 调用」——**那个理由当时是对的**。
`WIRE-03`/`WIRE-12` 把五张屏改成真取数之后前提就不成立了，
而**没有任何东西提醒过它**。

## 3. 四类，不是卡面写的三类

卡面要的是「该上屏但没接 / 本就不上屏 / 该退役」。实跑下来这三类装不下：

| 类 | 意思 | 条数 |
|---|---|---|
| A | 尺子看不见——前端真在调 | 12 |
| B | 屏在，但那一屏还写死或没接这条 | 19 |
| C | **屏还没建** | 4 |
| D | 该退役 | **0** |

- **A 不在卡面那三类里**，而它是最大的一块，且处置方向与另外三类相反；
- **C 与「本就不上屏」NEVER 合并**：`/pricebook*` `/profile*` 缺的是**屏**，
  不是「不需要屏」。差别在于前者要排期、后者不要——写成后者，这四条再也不会被想起来；
- **D 空着，而这是个结论不是省略**。判退役要能指出「被谁取代」或「需求没了」，
  这 35 条一条都证明不了。`/design/render` 与 `/design/explore/render` 看着重复，
  但入参与门禁不同。**把「我看不出它有什么用」写成「该退役」是猜。**

## 4. A 类的举证责任在我这一侧

A 类推翻的是对账器的结论，所以每一条都**指得出调用点**（`文件:行`），
判据逐条验那个文件真的存在、且里面真有那条路径（变异④ 指一个查无此路径的文件 → 当场红）。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_endpoint_triage.py -q → 10 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 301 source files
            pytest -q               → 4088 passed（GAUGE-10 收卡时 4078，本卡 +10）
对账器实跑: backend_unused_by_frontend 35 条（卡面写 33）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 逐条归类 | `test_the_counts_in_the_headings_match_the_rows`、`test_no_endpoint_is_triaged_into_two_classes`（进两类等于没分诊） |
| ② 机读守着不漂移 | `test_the_triage_covers_exactly_what_the_checker_reports`（**判等值**：多一条少一条都红）、`test_the_checker_is_run_live_not_read_from_a_stale_report`（数据源必须是实跑，读旧报告会绿在一份过期的事实上） |
| ③ 逐条写为什么，NEVER 一句概括 | `test_every_row_carries_a_reason_not_a_blanket_phrase`（每行至少三列且无空列，禁「多为内部用途」等五种空话）、`test_the_retire_class_is_empty_and_says_why` |
| ④ 候选清单带屏名与优先级 | `test_the_candidate_list_carries_a_screen_and_a_priority`（优先级要形如 `P1`~`P4`，四列都不许空） |

另有两条钉 A 类：`test_class_a_entries_really_are_called`、
`test_the_two_blind_spots_are_named_and_ticketed`（两个盲区**各有名字**，
挂一张仍 open 的单——只写「尺子看不见」不够，修一处另一处照样漏）。

**② 改既有文件 0 处**：新增 `docs/端点分诊-v041.md`（卡上 outputs）、
`tests/v041/test_endpoint_triage.py`（卡上 outputs）、
`docs/blocked/PARITY-BLIND-TO-PAGES-AND-UNLISTED-PREFIXES.md`（登记盲区）。

`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；`flint/` 与 `web/` 一行未改；未新增依赖。

**③ 变异考 6 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 表里少一条（等价于新增端点没分诊） | 红 2 条，点名是哪一条 |
| ② 用空话概括（「多为内部用途」） | 红 |
| ③ A 类某条不写调用点 | 红 |
| ④ A 类指一个查无此路径的文件 | 红 |
| ⑤ D 类硬填一条 | 红 |
| ⑥ 候选清单去掉优先级 | 红 |
| ⑦ 假变异对照：文末加一行 HTML 注释 | 全绿 10 passed |

**④ 判据判注释，本批第七次——这次在我自己写的判据里**：
`test_the_checker_is_run_live_not_read_from_a_stale_report` 第一版按整行扫
「同时出现 `read_text` 与 `json`」，当场把上面那句解释性注释判成违规。
改成走 `ast`：只看真的把文件内容喂给 json 解析的那种调用。
七次分别在 `AUTH-02` / `AUTH-05` / `WIRE-09` / `WIRE-10` / `WIRE-12` / `FIX-05` / 本处。

**⑤** 装载约 17k tokens；**⑥** 禁用词六词 0 命中。

## 6. 登记未做

1. **对账器那两个盲区没修**：改 `tools/check_fe_be_parity.py` 超出本卡 outputs，
   登记在 `docs/blocked/PARITY-BLIND-TO-PAGES-AND-UNLISTED-PREFIXES.md`，
   并在分诊表末尾写明**它应当排在所有接线之前**——盲区不修，接完线它照样报「没人用」。
2. **B/C 两类一条都没接线**：本卡是分诊，不是接线。候选清单带屏名与优先级，
   供下一批直接开卡。
3. **优先级是排序建议，不是承诺**：分诊表里写了这句。P1 四条的判断依据只有
   「屏在、端点在、无阻塞」，产品上哪条更重要不是 worker 定的。
4. **`/profile/{}/fields/{}` 的敏感度口径没查**：分诊表里引了 D12，
   但那条决策的正文本卡没装载——只标了出处，没有复述它。
