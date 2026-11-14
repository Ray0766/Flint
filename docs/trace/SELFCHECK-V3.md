# SELFCHECK-V3 — 广场 + 收藏 + 分享（HOTSPOT-01~09 + FAV-01~06，15 张）@2026-08-03

## ① 出口命令输出摘要

工单 §8 的 V3 出口判据（`src/views` 按 DEC-007 重映射为 `views`）：

```
$ pytest tests/v04/hotspot tests/v04/fav tests/v04/share -q
92 passed in 0.70s

$ cd web && npm test -- --run components views
Test Files  22 passed (22)
Tests  138 passed (138)
```

全局门（`mypy --strict src` 按 DEC-003 重映射为 `flint`）：

```
$ ruff check . --no-cache      → All checks passed!
$ mypy --strict flint          → Success: no issues found in 255 source files
$ pytest -q                    → 1699 passed in 160.84s
$ npm test -- --run            → 178 passed / 28 files
$ npm run typecheck            → 干净
$ node tools/i18n_scan.mjs web/components --fail-on-cjk → exit 0
$ node tools/i18n_scan.mjs web/views --fail-on-cjk      → exit 0
```

冻结件零改动：`contracts/models.py` md5 `380d7b5a7dae…`、
`contracts/protocols.py` md5 `eb19b73e176e…`（与 V2 出口记录逐位一致）。

本阶段本会话新增卡 7 张（HOTSPOT-03/04/05/06/07/09、FAV-02），各 1 cycle；
V3 十五张全部 `verified`，零 blocked、零 skipped_by_owner。

## ② 本阶段 DECISIONS 汇总

| 编号 | 内容 | 触发卡 |
|---|---|---|
| DEC-010 | 分析界面的 cluster→Gate① 判定对应关系由**调用方**给出（`verdictJobId`），视图与端点 NEVER 自行推断 | HOTSPOT-03 |
| DEC-011 | 分析缓存**键**保持 acceptance 四要素，**查表**另在 owner 命名空间内进行（跨租户复用等于把别人的作业交出去）；版本未知时整条缓存路径跳过；指纹对分隔符转义 | HOTSPOT-05 |
| DEC-012 | **owner 裁决**：HOTSPOT-03 选甲，问题单关闭；乙案（真建 `GET /clusters/{id}/verdict` + 对应关系持久化）登记 v0.4.1 候选，与 §9-P1/P3 同批再议 | owner 2026-08-03 |
| DEC-013 | **owner 裁决**：i18n 三项收尾 MUST 在 V5 出口前完成，届时整棵 `web/` 树 `i18n_scan --fail-on-cjk` exit 0 升格为 V5 出口判据；同时落成机读卡 `I18N-09` | owner 2026-08-03 |

## ③ 未清 blocked 清单

- `docs/blocked/HOTSPOT-03.md` — **本阶段关闭**（DEC-012 裁决甲案）。
- `docs/blocked/SCHEMA-05-FROZEN-WORDING.md`、`REGION-06-AXIS-WORDING.md`、
  `CLAUDE-S3-LAG.md` — 三份措辞/滞后登记单，非阻塞，仍待 owner 一句话。
- `docs/blocked/I18N-01.md`、`I18N-FRONTEND-GROUP.md`、`CONCURRENT-WORKER-COLLISION.md`、
  `V0-PROMPTS-LOCK.md` — 根因已消除，可标记关闭（V2 出口已登记，本阶段无变化）。

**登记未做项**：乙案（cluster→判定持久化）已按 owner 指示挂 v0.4.1，NEVER 在 V4/V5 任何卡里
假定该端点存在。

## ④ 下阶段风险一句话

V4 是 GRAPH-01~16 十六张、几乎全在前端，而目前前端只有**组件级**测试、没有页面级装配
——GRAPH-05（双击开分析抽屉）与 GRAPH-15（工作台动态接广场）都要求容器把两块真的拼起来，
若继续按组件粒度做完就打绿灯，V4 出口会出现「每个零件都通过、装到一起没人验过」的状态；
建议在 GRAPH-05 那张卡起，把「容器 + 子组件」的装配断言写进测试而不是只测子组件。

（另一条已知项：DEC-013 的 i18n 三项收尾按 owner 指示落在 V5 出口前，V4 期间不动。）
