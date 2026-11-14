# v0.4 增量 · 完成态报告（worker.md §7 停机条件 ①）

**停机时间** 2026-08-03
**停机依据**：§7 停机条件①——**全部卡 verified**（零 blocked、零 skipped_by_owner）。

> 这份报告替代 `docs/blocked/SUMMARY.md`（那份写于 2026-08-02 的停机，
> 依据是条件②「剩余卡全 blocked」；两个 blocked 根因已由 owner 的 DEC-006/007 裁决消除，
> 那份汇总从此只作历史留存，**NEVER 当作当前状态引用**）。

## 一、进度

| 里程碑 | 卡数 | verified | 出口报告 |
|---|---|---|---|
| V0 原则与返工 | 9 | 9 | `docs/trace/SELFCHECK-V0.md` |
| V1 Schema | 15 | 15 | `SELFCHECK-V1.md` |
| V2 地区 + 语言 | 16 | 16 | `SELFCHECK-V2.md`（含追记：整树扫描当时并不成立） |
| V3 广场 + 收藏 + 分享 | 15 | 15 | `SELFCHECK-V3.md` |
| V4 图谱工作台 | 16 | 16 | `SELFCHECK-V4.md` |
| V5 设计工作台 | 33 | 33 | `SELFCHECK-V5.md` |
| **合计** | **104** | **104** | — |

台账 `cycles_used` 合计 **121**（DAG 估算 123）。104 张卡逐张有 trace，
`docs/progress-v04.jsonl` append-only、无回改。

## 二、收工时的全局门（全部实测）

```
ruff check . --no-cache                     → All checks passed!
mypy --strict flint                         → 269 source files, no issues
pytest -q                                   → 1840 passed (138.33s)
cd web && npm test -- --run                 → 524 passed / 58 files
cd web && npm run typecheck                 → 干净
python tools/validate_dag_v04.py --file tasks-v04.json → acyclic / nodes 104 / errors []
python tools/check_frozen_additive.py ×2    → 双通过
contracts/models.py     md5 380d7b5a7dae…   （与 V2/V3/V4 出口逐位一致）
contracts/protocols.py  md5 eb19b73e176e…   （同上）
```

**六把守门工具**（本增量新增五把 + 既有 orthogonality）全部 exit 0，且每把都带
**阴性对照**——证明它认得出违规、也不误伤：

| 工具 | 守什么 |
|---|---|
| `i18n_scan.mjs` | 界面文案 key 化；内建**自证五条**（含「块注释后行号不偏移」这条真 bug 用例） |
| `scan_ds_assets.mjs` | 数字容器 tabular-nums；emoji NEVER 当图标 |
| `no_hardcoded_models.mjs` | 代码里零硬编码模型名 |
| `no_external_fonts.mjs` | 产物不向外要字体 |
| `lint_no_confidence_viz.mjs` | 禁置信度可视化；图标纪律 |
| `orthogonality_check.py` | 语言与地区正交（18 组合，工具先自证再干活） |

## 三、四条铁律在代码里的落点（本增量新增）

| 铁律 | 落点 |
|---|---|
| 结论必有引用 | 导出闸门三判据（DESIGN-16/32）：`fact_removed` blocking、空假设边、模板未固化 |
| 数字必有出处 | 样板三件套（DESIGN-27）+ 固化管道拦示例数字（DESIGN-28）+ 校验器四判据（DESIGN-29）+ 禁置信度可视化（DESIGN-23） |
| 产物可复现 | 模板 checksum 与内容绑定（G5/G6 两处共用契约那一份指纹）+ 检查点 VFS+图谱同快照、历史只增不改（DESIGN-11） |
| 不确定 NEVER 伪装成确定 | `unreported ≠ passed`（DESIGN-13）、用量未记 ≠ 没花钱（DESIGN-18）、失锚仍可见（DESIGN-12）、缺失逐槽隐藏（HOTSPOT-01）、未判定态（HOTSPOT-03） |

## 四、留给 owner 的四件事（**四件均已于 2026-08-03 裁决 · DEC-018~021**）

1. **`docs/blocked/DESIGN-21-FONTS.md`（非阻塞）**：品牌字体现走系统回落栈。
   二选一——给三种 woff2 二进制放进 `web/public/_ds/…/fonts/`（我按同源 `@font-face` 接上），
   或明确接受回落字体、关掉该单。
2. **三份措辞/滞后登记单**（`SCHEMA-05` / `REGION-06` / `CLAUDE-S3-LAG`）：各需一句话。
3. **v0.4.1 候选**：乙案 cluster→判定持久化（DEC-012）、§9-P1 收藏快照 pin、
   §9-P2 判据注册表、§9-P3 delta ephemeral——四项均已登记风险与改动面。
4. **undo 链三处接线**（GRAPH-04/07/09）：缝 `pushUndo` 已留，接线归后续卡。

## 五、下一步该做什么（我的判断）

护栏已成体系，但**它们只在 CI 与本地跑过，没有一次真实用户流量**。
本增量交付的多是模块与判据：`flint/api/` 只新增两条路由，前端也没有页面级端到端跑通。

所以进 v0.4.1 的第一件事应是**端到端接线 + 一次真实 demo 跑通**，而不是继续加判据——
判据再多，没接上就一条都不生效。


## 六、封版（owner 2026-08-03 · DEC-021）

**v0.4 增量封版**，进入 supervisor **终检与异见复审**。

| 裁决 | 内容 | 落点 |
|---|---|---|
| DEC-018 | 字体：接受系统回落；woff2 自托管移入 v0.4.1 | `docs/blocked/DESIGN-21-FONTS.md` 关闭 |
| DEC-019 | 三份措辞/滞后单：认可登记结论、照登记关闭 | 三单关闭；`tasks-v04.json` 3 处 + `WORKORDER-v04.md` 2 行措辞对齐真件 |
| DEC-020 | v0.4.1 候选清单与次序确认（端到端接线居首） | `docs/v0.4.1-候选清单.md` |
| DEC-021 | 封版，进终检与异见复审 | `docs/异见清单-v04.md`（22 处异见 + 1 处观察项） |

**封版后的纪律**：执行侧对 v0.4 范围内的实现与判据 **NEVER 再改**。
终检期间发现的问题只有两条出路——属实现缺陷走既有 `review_failed` 通道（回对应卡 + trace 写意见），
属范围外走 v0.4.1 候选清单；**NEVER 就地打补丁而不留卡**。
（本条已被实际执行过一次：终检准备时发现 `scan_ds_assets.mjs` 缺 `node_modules`/`.next` 跳过——
一行就能改，仍按规矩登记为 E1 而没有就地改。）

**封版当天动过的文件**（全部为措辞对齐与登记，**零实现改动**）：
`tasks-v04.json`（3 处 acceptance/卡名措辞）、`WORKORDER-v04.md`（L39、L390，均在 §3 正文 112~166 之外，
PRIN-01 哈希测试 5 passed 为证）、`DECISIONS-v04.md`（DEC-018~021）、
`docs/blocked/` 四单关闭横幅、新增 `docs/v0.4.1-候选清单.md` 与 `docs/异见清单-v04.md`。
复跑为证：`validate_dag_v04 --file` acyclic / nodes 104 / errors [] / coverage 1.0；
`test_i4_names.py` + `test_scorer_axis.py` 17 passed；`tests/v04/principles` 5 passed；
`no_external_fonts.mjs web` exit 0。
