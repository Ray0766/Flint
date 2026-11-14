# SELFCHECK-V1 — Schema 阶段出口 @2026-08-02

十五张卡（SCHEMA-00~14）全部 verified。

## ① 出口命令输出摘要（工单 §8 的 V1 行，逐条实跑）

| 命令 | 结果 |
|---|---|
| `check_frozen_additive contracts/models.py contracts_v04/models_v04.py` | **exit 0** —— 保留 87 类 / 443 字段 / 1 函数签名 / 31 别名；新增 17 类、13 字段、10 枚举·联合成员 |
| `check_frozen_additive contracts/protocols.py contracts_v04/protocols_v04.py` | **exit 0** —— 保留 24 类 / 40 函数签名；新增 0（零签名改动，仅 docstring 增补） |
| `pytest tests/v04/schema -q` | **95 passed** |

**全局门**：`ruff check --no-cache .` All checks passed · `mypy --strict flint` 224 文件净 ·
`pytest -q` **1445 passed / 0 failed**（V0 出口时 1350 → 本阶段新增 95 条）。

**冻结件零改动复核**：`contracts/models.py` md5 `380d7b5a7dae…`、
`contracts/protocols.py` md5 `eb19b73e176e…`，与 SCHEMA-00 开工时逐字节一致。

## ② 本阶段 DECISIONS 汇总

- **DEC-004**（SCHEMA-00）：`pyproject.toml` 增 `"contracts_v04/*" = ["I"]` ruff 豁免——
  副本逐字继承冻结件的 import 排版，给它排序等于制造差异。

本阶段无新增 DEC（其余判断都落在卡内实现的 docstring 与各卡 trace 里）。

## ③ 未清 blocked

| 单 | 状态 |
|---|---|
| `docs/blocked/SCHEMA-05-FROZEN-WORDING.md` | **未清（非阻塞）**：`tasks-v04.json#SCHEMA-05` acceptance 写「frozen 拒二次赋值」，真件 `Cluster` 是非 frozen dataclass，预填表注记 2 与工单 §3-B7 均已改口径为「写路径校验」。已按 contracts/ 实现为**字段级写一次**并留痕，等 owner 一句话对齐措辞。 |
| `docs/blocked/CLAUDE-S3-LAG.md` | 未清（非阻塞，V0 遗留）：CLAUDE.md S3 目录结构仍是包模板形态。 |

## ④ 下阶段风险（一句话）

V2 起要真写运行期代码（`flint/region/`、`flint/i18n/` 等新子包 + 前端 `web/src/`），
**DEC-003 的触碰边界从此刻开始真正生效**——既有文件只允许注册点的只加不删增量、
每处 trace 留 diff，而 V2 的正交性 harness（18 组合）与 i18n 扫描器是两件全新工具，
它们本身的可靠性要先自证（否则「18 组合全绿」可能只是工具什么都没测）。

## 附：本阶段两件必须记住的事

**① SCHEMA-00 越界，破坏了 test-first 顺序（两张卡）**
建副本时把 I1~I13 的增量一次性落进去，而那些增量各归 SCHEMA-01~14 所有。
后果：**SCHEMA-01 与 SCHEMA-14 首跑即绿**，红态无从制造。
补救是抽掉对应字段跑出红再还原（SCHEMA-01 得 4 failed、SCHEMA-14 得 3 failed），
**这不等价于先红后绿**，只是等价强度的反空转证据。
其余 12 张卡因预落形状与 acceptance 不符，都有真红（最多的一张 7 条）。

**② additive 校验器自身曾有一处空转，被变异体抓出来**
`ast.get_source_segment` 对 `arguments` 结点永远返回 `None`，导致 40 个方法签名
一直在拿 `""=="" ` 比。改用 `ast.unparse` 后 s5 变异体立刻报红。
这条教训写进了 `tools/check_frozen_additive.py` 的 `_src` docstring。
