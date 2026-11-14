# NARROW-01 · 章程对齐现在的目标，外围冻结（@2026-11-14）

owner 同日做了一次项目评审（报告在仓外），结论 Narrow（收窄）。本卡只做三件，并为第四件列出触发点：

1. `CLAUDE.md` S1 的目标改成开源自用；同步改掉过期的「本包自身范围」与监工视图里的 M1；
2. 冻结清单写进章程；
3. `docs/owner复核摘要-v041.md` 里仍待看的 28 张统一标「搁置」；
4. 连跑批次：找出它是在哪里被触发的，列给 owner，**owner 确认停法之前不改**。

不在范围：不删任何代码或目录（含三套设计稿）；不改 `flint/` 与 `web/` 下的源码；不接模型、不跑真实采集；不动 CI。
在分支 `narrow/charter-freeze` 上做，**没有推送**。

## 一、装载清单

评审报告的「Verdict」「3. 第一性原理」「建议」第 1、2 条（仓外）· `CLAUDE.md` · `DECISIONS-v04.md`（`DEC-000`、`DEC-029`、`DEC-065` 的写法）·
`docs/owner复核摘要-v041.md` · `worker.md` §7 · `supervisor.md` §11.4 · `docs/steward/` 下的起跑令、常备连跑工单、`连跑-overnight.ps1`、
`上岗提示词-steward.md` · `.claude/settings.json` · 判据 `tests/v041/test_decisions_landed.py`、`test_owner_review_digest.py`、
`tests/m4/test_m4_006.py`、`test_m4_042.py`（这两份读 `CLAUDE.md`）。

## 二、行号先核过

| owner 引用 | 实际 | 对得上 |
|---|---|---|
| `CLAUDE.md:11` 目标句 | 「V1 商用 MVP … 支付」 | 是 |
| `CLAUDE.md:15` | 「本包自身范围：M1 数据与索引层全量 41 任务」 | 是 |
| `CLAUDE.md:131` | 「现在在做什么：M1 数据与索引层，41 个任务」 | 是 |
| `docs/owner复核摘要-v041.md:10` | 「仍待你看 … 28」 | 是；表里状态为待看的行数也是 28（26 整行 + `UI-01`/`UI-02` 两张部分覆盖） |

评审报告正文里有一处写的是 `CLAUDE.md:8`，实际是第 11 行，以 owner 给的行号为准。

## 三、改了什么（四个提交）

| 提交 | 内容 |
|---|---|
| `2fc99f3` | `DEC-066` 追加进 `DECISIONS-v04.md`：代码块里是 owner 的目标与冻结清单原话；写明取代了什么、**没有撤 `DEC-000`**、入口还没关、搁置不是销账。水位判据 65 → 66 |
| `609a575` | `CLAUDE.md`：S1 目标句；非目标之下新增冻结清单；「本包自身范围」改成一条真链路；监工视图的「现在在做什么」「怎么看进度」两行不再提 M1 |
| `6523e92` | 复核摘要：28 行状态换成「搁置（`DEC-066`）」，顶上一段说明；判据新增搁置一类 |
| 本提交 | 本 trace 与台账 |

### 我加的、owner 没逐字给的（可推翻）

- `CLAUDE.md:15` 与监工视图的新措辞是我拟的（计划里给 owner 看过，owner 回「按计划做」）；
- 冻结清单里「五套人类模板」后面括了一句「vibe_pack 执行包那一路不冻结」。依据是新目标的成功信号就是执行包；
- 「连跑批次」那一条后面括了「不开新批；已有授权怎么收回待 owner 定」；
- 监工视图「怎么看进度」那一行删掉了「10 个 review_gate 是质量节点，出口在 M1-041」。这一行 owner 没点名，计划里说了会一起改。

## 四、判据（先红后绿）

| 判据 | 改前 | 改后 |
|---|---|---|
| `test_decisions_landed.py` 水位 | 落了 `DEC-066` 之后旧判据红：「最高编号是 DEC-066，不是 DEC-065」 | 54 passed |
| `test_owner_review_digest.py::test_what_was_left_is_shelved_by_the_narrowing`（新） | 先写、摘要没改：红，「少了」28 张 | 9 passed |
| 同文件 `test_both_covered_and_open_rows_exist` | 改成只看状态一格、要求「搁置」：对着旧摘要红 | 过 |
| 同文件 `test_every_open_row_says_what_the_decision_is` | 原来只看含「待看」的行；摘要一改，这条会**空转全绿** | 改成「待看」或「搁置」的行都要说清定什么 |

新判据只看每行**最后一格**（状态）：`UI-01` 的「要定的点」里本来就写着「仍待看」，`BL-12` 的那一格里本来就有「搁置」两个字，
看整行的话这两张会骗过判据。改完之后做了三次变异，都红：

1. `GAUGE-02` 的状态退回「待看」→ 2 条红；
2. `Z-01` 的状态去掉 `DEC-066` → 1 条红；
3. 已覆盖的 `UI-05` 改成搁置 → 2 条红。

## 五、门禁

| 门 | 结果 |
|---|---|
| `ruff check .` | 零条 |
| `mypy --strict flint eval harness` | 371 份零条 |
| `pytest -q` | `5415 passed, 458 skipped`（308 秒） |

本卡没碰 `web/`，tsc 与 vitest 没跑。

## 六、连跑批次：触发点（没改，停法待 owner 定）

**授权它的规则：**

| 位置 | 说的是什么 |
|---|---|
| `DECISIONS-v04.md:6` `DEC-000` | 无人值守连跑授权：除四项事前必审外 NEVER 停机等待 |
| `DECISIONS-v04.md:42` `DEC-029` | 第 2 批一次性连跑；那一批已跑完 |
| `worker.md:83-89`（§7） | 照 `DEC-000` 执行；停机条件只有「全部收卡」或「全部 blocked」 |
| `supervisor.md:208-214`（§11.4） | 「NEVER 停下问 owner 要不要续」 |
| `docs/steward/上岗提示词-steward.md:112-115` | 给 worker 的提示词一律做成 `/loop` 形态 |
| `CLAUDE.md` 监工视图「什么时候会被叫」 | 「其余时间流水线自转」 |

**实际拉起它的动作（都要人手动，没有自动定时）：**

- 在 worker 终端里 `/loop 10m` 后面粘一段起跑令。范本在 `docs/steward/起跑令-*.md` 与 `常备连跑工单-*.md`；
- `docs/steward/连跑-overnight.ps1`：PowerShell 外层循环，每轮起一个新的 `claude` 会话。只能在 Windows 上跑；
  默认指向第 10 批，那批的 `DONE` 标记已在，现在跑会直接退出。

**本机现状（2026-11-14 查）：** 没有 crontab；`~/Library/LaunchAgents` 里没有相关项；`.claude/settings.json` 没有钩子；
应用里没有定时任务；本会话没有 `/loop` 定时；`docs/WORKER.lock` 不在。

**提给 owner 的停法（未执行）：** 记一条裁决撤销 `DEC-000`（每一批须 owner 当次明确开工，做完一批停下汇报）；
`worker.md` §7、`supervisor.md` §11.4、steward 上岗提示词那一节顶上各加一段「已撤销」并指向新裁决，原文保留；
`CLAUDE.md` 的「其余时间流水线自转」改掉，冻结清单里的连跑写成一条 NEVER；`连跑-overnight.ps1` 开头加一个直接退出的闸。

## 七、没有做的 / 还在的

- **入口没关。** 侧栏七个入口在 `web/components/shell/`，源的启用在 `flint/sources/`，都在本次范围外。章程里写明了「入口今天还开着」；
- **`flint/sources/candidates.py:68` 的一段文字仍写着「本产品是商用 MVP（S1）」**。那是 `flint/` 下的源码，没动；
- `CLAUDE.md` 里还有 M1：S2 第 7 条（M1-008 机制）、S4 未决表两行、S5 任务表整节、S7 全局门（M1-007）、S8 历史台账、S9 人审节点（M1-041 类）。
  这些描述的是机制或历史，S9 那一句由 `tests/m4/test_m4_006.py` 钉着；owner 点名的 `:15` 与 `:131` 已不提 M1；
- 非目标那一行仍写着「V1 边界外」，没动；
- 第 17 批剩下的 `CONTRACT-REV-01`、`CHAIN-UI-01-b`、`GATE1-REAL-02` 在核心链路上，没有搁置。

## 八、更正（同日，`DEC-067`）：连跑照旧

owner 看过第六节之后回「连跑不停」，并在两个选项里点了「连跑照旧，移出冻结清单」。所以：

- 「连跑批次」从 `CLAUDE.md` 冻结清单里拿掉了，冻结清单标题注明由 `DEC-067` 移出；
- `DEC-066` 原文不回改（追加式），读它时以 `DEC-067` 为准；
- `DEC-000` 继续有效；第六节那四步停法**不执行**，`worker.md`、`supervisor.md`、steward 上岗提示词、`连跑-overnight.ps1` 一字未动；
- 第六节的触发点清单留着，作为现状的记录。

连跑照旧之后，冻结清单仍然约束连跑领什么卡（S1 那句「NEVER 为冻结项开新卡或续做旧卡」）。这是我对两条裁决合起来的读法，写进了 `DEC-067`，owner 没有逐字说过。落地卡 `NARROW-02`。
