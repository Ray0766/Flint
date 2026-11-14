# ASSUMPTIONS.md · 附件核实与绕行台账（v0.4 工单配套）

更新时间：2026-08-02（第 4 轮上传、models.py 真件到位后）。

## 附件核实结论

| 附件 | 状态 | 核实要点 |
|---|---|---|
| protocols.py | ✅ 真件 | v0.3.3 修订版；冻结头 + 判别联合 + 审核 1~11 语义在列；§2-J1 协议级影响面据此全量核实 |
| tasks.json | ✅ 真件 | spec 2.0-vibe；实测 232 卡 / Σ270 cycles / 关键路径 53 / review_gate 77 / verify 覆盖率 1.0；J5 重估据此 |
| 技术方案-v1.1.md | ✅ 真件 | 八节齐全；E2 表清单与 E3 端点组为 §2-J2 增量基准 |
| 前端功能说明.md | ✅ 真件 | 667 行 / 12 屏 / 20 端点总表；J4 扩版基准 |
| flint-feature-list-v1.md | ✅ 真件 | A~L 96 项，唯一需求来源 |
| CLAUDE.md | ✅ 真件（第 2 轮到） | vibe_pack v2.0，S1~S9；S2-8 禁用词表、S7 返工环、S8 台账约定已并入 D1/D3（S7 由工单 4.4 显式覆盖）。第 1 轮曾误传 Expo Modules JSI 版 |
| models.py | ✅ 真件（第 4 轮到） | 1030 行 / 30783 B / md5 380d7b5a7daee17111a8961f0e3a41c6；燧石冻结头 + v0.3.3 特征（TaskSpec 双单位/review_gate、Audience、ProposalContext）。前三轮均为项目内 .venv 的 fontTools 同名文件（owner 已确认来源）。字段级核实结论 → docs/schema_reconcile_prefill_v04.md |
| 三份 CLAUDE.md 样例（第 3 轮） | ▣ 已搁置 | owner 已明确：批量上传时顺带、不使用；不作为 ⑧ 推演材料，认定挂起撤销 |
| design_handoff_flint_web/ | ▢ 未上传 | J6 以 [待核实] 登记清单数字；DESIGN-05 对入仓 _ds 副本实测 |
| harness/prod_caliber.py | ▢ 未上传 | J7 只做影响声明，不动 harness |

## models.py 对账收紧（真件到位后已执行）

1. 预填对账表 `docs/schema_reconcile_prefill_v04.md`：I1~I13 + 事件增量逐项落点核实；三处落点修正（I2→Doc、I4→Cluster、事件→models_v04）、两处收敛（I6 date 槽取消、J9 PricingRecord 已含 currency/region）、一处微调（AnalysisContext 增 lang/region、locale 保留兼容）。
2. 工单同步：§2-J1 升级字段级、§2-J9 收敛、不符清单增 #14~#18、§3-B7 执行机制与 §4 风格改「非 frozen dataclass」、§4-I2/I4/I6/I13/events 落点改真名。
3. tasks-v04.json 六卡同步（SCHEMA-02/05/06/13/14、MIGRATE-07），重建复检：103 卡 / Σ122 / 关键路径 18 / errors=[] 不变。
4. **SCHEMA-00 对账门保留**：本表基于 owner 上传副本；worker 在仓库内对工作副本复跑 additive 校验为最终防线（含头部冻结文字滞后项 #18 的登记）。

## 立场与口径决定（本轮沿用）

单 agent（review_gate→self_review、L8 删）；增量冻结（contracts_v04/ 副本、只加不删）；K1~K8 留位绕行 NEVER 编造；三提案不进卡文（proposals 键双路径）；隔离带六卡零下游。
