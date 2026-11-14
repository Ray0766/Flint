# SELFCHECK-V0 — 原则与返工阶段出口 @2026-08-02

九张卡（PRIN-01/02 + MIGRATE-01~07）全部 verified。

## ① 出口命令输出摘要（工单 §8 的 V0 行，逐条实跑）

| 命令 | exit |
|---|---|
| `python tools/check_principles_doc.py docs/PRINCIPLES-v04.md` | **0**（7 条 × 4 段；与工单 §3 逐字一致 sha256 `e025e9fe…`） |
| `python tools/check_grounding_spec.py docs/grounding_spec_v04.md` | **0**（三条增补 A1/A2/A3；伪码含 event/event_date/`GroundingOnTranslationError`） |
| `python tools/check_techplan_delta.py docs/技术方案-v1.2-delta.md` | **0**（八节齐全；E2 七新表、E6 三新降级行在列；21 个类型名均已定义） |
| `python tools/check_fe_doc.py docs/前端功能说明-v2.md --min-screens 16` | **0**（18 屏；六类新屏各带状态呈现规则；i18n key 总表；定名已标 owner_review） |
| `python tools/validate_dag_v04.py --base tasks.json --patch tasks-m1m4-v04-patch.json --merged` | **0**（acyclic / nodes 232 / edges 412 / errors [] / coverage 1.0） |
| `check_impact_doc.py handoff_gap_v04.md --require-sections screens,i18n-hardcode,known-issues` | **0** |
| `check_impact_doc.py prod_caliber_impact_v04.md --require-refs 12` | **0**（14 个引用 id 均在仓库可查） |
| `check_impact_doc.py pricebook_currency_v04.md --require-sections currency,defer` | **0** |
| 另跑 `python tools/validate_dag_v04.py --file tasks-v04.json` | **0** |

**全局门**（V0 文档阶段免 mypy）：`ruff check --no-cache .` → All checks passed；
`pytest -q` → **1350 passed / 0 failed**（1345 基线 + PRIN-02 新增 5 条）。

## ② 本阶段 DECISIONS 汇总

- **DEC-000**（owner）：无人值守连跑授权，事前必审四项之外一律事后补审。
- **DEC-001**（PRIN-01）：工单 §3 正文边界 + 哈希前行尾归一。
- **DEC-002**（owner，方案 A）：`worker.md` 移出 `prompts/` 落仓库根——见 §③ 处置记录。

## ③ 未清 blocked → 已清

`docs/blocked/V0-PROMPTS-LOCK.md` —— **已由 owner 选 A 处置，本阶段无遗留 blocked**。

**处置记录**：`prompts/worker.md` → `./worker.md`；同步自引用 **84 处**
（`tasks-v04.json` 2 · `WORKORDER-v04.md` 2 · `worker.md` 2 · `DECISIONS-v04.md` 1 ·
`tasks-m1m4-v04-patch.json` 77）。owner 点名的是四处，实际有五个文件——
后两个是我自己的产出（DEC-000 的引用与补丁里 77 条 deprecated 说明），一并同步，
残留扫描为空。受影响的 MIGRATE-04 verify_cmd 复跑仍 exit 0。
处置后全局门由 `2 failed / 1348 passed` 转为 **`1350 passed / 0 failed`**。

编号说明：owner 口述记为 DEC-001，但该号已被 PRIN-01 占用且 `docs/trace/PRIN-01.md` 已引用，
改号会让既有 trace 指向错误条目 → 顺延为 **DEC-002**，并在条目里写明来由。

## ④ 下阶段风险（一句话）

V1 起 15 张 SCHEMA 卡要落 `contracts_v04/` 与 `src/`，而**本仓库的 Python 包是 `flint/`、没有 `src/`**
（`worker.md` §5 全局门写的是 `mypy --strict src`）——V1 第一张卡 SCHEMA-00 就会撞上这个落点问题，
届时按 §1.4「以 tasks-v04.json 为准 + 写问题单」处理，NEVER 自行择一后不留痕。

## 附：V0 质量口径自查

- 九张卡**全部先写红再实现**，红态输出各自记在对应 trace；
- 断言反空转：累计 **22 个变异体**，全部被对应校验器抓住（逐卡列在 trace 的自审段）；
- 校验器**三次抓到我自己**：MIGRATE-03 屏数不足与关键词不含包、MIGRATE-02 的「查死名单」假绿；
- 真件核实**推翻一处清单预估**（`PricingRecord` 已含 `currency`/`region`，本轮不加字段）；
- `contracts/`、`tasks.json`、`CLAUDE.md`、`harness/prod_caliber.py` **全程零修改**。
