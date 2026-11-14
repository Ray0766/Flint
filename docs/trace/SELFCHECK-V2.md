# SELFCHECK-V2 — 地区 + 语言阶段出口 @2026-08-02

V2 十六张卡（REGION-01~08 + I18N-01~08）全部 verified。

## ① 出口命令输出摘要（工单 §8 的 V2 行，逐条实跑）

| 命令 | 结果 |
|---|---|
| `pytest tests/v04/region tests/v04/i18n -q` | **125 passed** |
| `python tools/orthogonality_check.py --combos all` | **exit 0** —— 自证通过（4 条断言各注入反例后都变红 + 阴性对照不报红）→ 18 组（9 区 × 2 语言）× 4 断言全过 |
| `node tools/i18n_scan.mjs web/components --fail-on-cjk` | **exit 0** —— CJK 字面量 0 / 白名单 **0 项** / B7 违规 0 |

**全局门**：`ruff check --no-cache .` All checks passed · `mypy --strict flint` **249 文件净** ·
`pytest -q` **1631 passed / 0 failed** · 前端 `npm test -- --run` **92 passed / 16 files** ·
`npm run typecheck` 干净。
冻结件零改动：`contracts/models.py` md5 `380d7b5a7dae…`、`protocols.py` `eb19b73e176e…`。

## ② 本阶段 DECISIONS 汇总

| # | 内容 |
|---|---|
| DEC-005 | `flint/grounding.py` 逐字节转包为 `flint/grounding/__init__.py`（为放 `original_only.py`） |
| DEC-006 | **一次性网络授权，仅 next-intl**：装前过 RegistryValidator（实测 `exists=True / latest_stable=4.13.4 / 2026-08-02T13:16:38Z`）、`--save-exact` 钉死、lockfile 带 integrity、记录入 `docs/deps_v04.md`；装完回归离线纪律 |
| DEC-007 | **`web/` 是唯一前端工程根**；`web/src/**` → `web/**` 重映射（tasks-v04.json **126 处** + 两份文档同步），`--run src/x` → `--run x` |
| DEC-008 | i18n 扫描面**排除测试文件**——测试里的中文是断言数据，key 化它们会把测试削弱成同义反复 |
| DEC-009 | 组件文案走 `web/lib/i18n/t.ts` 薄封装而非直接 `useTranslations`——既有 11 个测试直接渲染组件，强依赖 Provider 会逼每个测试包一层只为「跑起来」的壳 |

## ③ 未清 blocked

| 单 | 状态 |
|---|---|
| `I18N-01.md` / `I18N-FRONTEND-GROUP.md` | **已解**（DEC-006/007），可标记关闭 |
| `SCHEMA-05-FROZEN-WORDING.md` | 未清（非阻塞）：acceptance 措辞 vs 真件非 frozen |
| `REGION-06-AXIS-WORDING.md` | 未清（非阻塞）：acceptance 措辞 vs `EvidenceOrigin` 两值 |
| `CLAUDE-S3-LAG.md` | 未清（非阻塞）：CLAUDE.md S3 目录结构文字滞后 |
| `CONCURRENT-WORKER-COLLISION.md` | 已按方案 A 处置完毕，可关闭 |

## ④ 下阶段风险（一句话）

V3 起 HOTSPOT/FAV 链条的**根部是前端卡**（HOTSPOT-01 卡片广场、GRAPH-01 工作台容器），
而前端目前只有组件级测试、没有页面级装配——**先做根部前端卡，后面的纯后端卡才解锁**，
顺序反了就会又一次出现「就绪卡为 0」。

## 附：本阶段两处「工具自证」的落地

V1 出口时点名的风险是「全新工具的可靠性要先自证，否则全绿没有意义」。V2 兑现了两处：
- **正交性 harness**：`self_test()` 是 `main()` 的**前置步骤**，四条断言各注入对应反例
  （locale 跟 region 走 / 源集掺 lang / 热点 hash 随 lang 变 / 产物语言取自 region），
  自证不过直接非零退出，**不进入正式 18 组**；
- **i18n 扫描器**：白名单是**推进机制不是豁免机制**，非空时会打印
  「acceptance 要求收尾时为空——留一条永久豁免就等于没做这张卡」，本阶段收尾时为 0 项。

## 追记（HOTSPOT-03 回合 @2026-08-03，NEVER 回改原文）

本报告第 ① 段那句 `i18n_scan --fail-on-cjk exit 0（CJK 0/白名单 0 项/B7 违规 0）`
**成立的前提是扫描面为组件/视图目录**。整棵 `web/` 树跑则是红的：

```
$ node tools/i18n_scan.mjs web/views --fail-on-cjk       → exit 0
$ node tools/i18n_scan.mjs web/components --fail-on-cjk  → exit 0
$ node tools/i18n_scan.mjs web --fail-on-cjk             → exit 1（7 个文件）
```

7 个里两类：**工具假阳性 3 个**（`lib/i18n/config.ts`、`lib/i18n/t.ts`、`stores/prefs.ts` ——
命中的是 JSDoc **块注释**行，而工具自述「注释行不算」，`cjkLines()` 只剥 `//` 与单行 `/* */`）；
**真命中 4 个**（`app/deliverables/[id]/page.tsx`、`app/jobs/[id]/page.tsx`、`app/layout.tsx` 的
title、`lib/i18n.ts` 这份与 `messages/` 重复的 v0.3 遗留词条表）。

留档口径：V2 出口结论不因此推翻（当时各卡的扫描面都是自己的产出目录，逐卡为真），
但「全 web 树 CJK 为 0」这句更强的话**当时并不成立**，后续 I18N 线收尾时按此处清单收。
