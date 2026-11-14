// DS-03：枚举原值 → 人类标签。
//
// ## 治的病
//
// `D_insufficient` 是**数据库里的值**，不是给人看的话。它上屏之后有三重坏处：
//
// 1. 用户读不懂——「D_insufficient」不告诉任何人「证据不够，判不了」；
// 2. 切英文时它**不变**，于是中英两版看起来一样「已经翻译过了」；
// 3. 它把后端的内部命名钉死在产品面上——改一次枚举值就要动一次界面。
//
// ## 为什么是一张表，不是各组件自己 `t()`
//
// 同一个 `unknown` 会出现在权威度、地区、译名来源三处。各组件自己取文案的话，
// 三处会各写各的话，而它们说的是同一件事。这张表是**唯一的映射**，
// 判据（`tests/v041/test_enum_labels.py`）盯着它对齐冻结件里的判别联合——
// 冻结件多一个成员而这里没给标签，当场红。
//
// ## 「未知」与「没查过」NEVER 用同一个词
//
// 这是本仓一路在守的同一条纪律（`WIRE-12` 把假空态改成 `not_provided` 姿态，
// `UI-09` 把「没查过」从「是 0」里分出来，`GAUGE-11` 把「尺子看不见」从「屏在没接」里分出来）。
// 到了标签这一层它同样成立：
//
// - `unknown`（未知）= **查过了，答案是「不知道」**；
// - `not_checked`（没查过）= **还没查**；
// - `not_provided`（接口未提供）= **这个能力还没接**。
//
// 三者混成一句话，用户会拿一个「还没查」当成「查过了没有」。
// 判据 `test_the_three_kinds_of_absence_never_share_a_word` 逐条比对，中英各比一次。

import { t } from "./t";

/** 一族枚举。`values` 是该族的全部成员，逐字对齐真相源（见每族上方的注释）。 */
export type EnumFamily = {
  /** i18n key 前缀：`enum.<prefix>.<value>` */
  prefix: string;
  values: readonly string[];
  /**
   * 该族的真相源，判据照着它对齐。
   *
   * 写成**点号形态**（`contracts.models::Verdict`）而不是文件路径：
   * `tools/no_scaffold_on_screen.mjs` 把「内部文件路径出现在 web/ 源码里」判成
   * A 类脚手架，而它分不出「渲染到屏上的路径」与「给判据用的元数据」。
   * 尺子看不出的差别，就由写法来避开——NEVER 去改尺子放自己过。
   */
  source: string;
};

export const ENUM_FAMILIES: readonly EnumFamily[] = [
  {
    prefix: "verdict",
    source: "contracts.models::Verdict",
    values: ["A_infeasible", "B_red_ocean", "C_opportunity", "D_insufficient"],
  },
  {
    prefix: "job_state",
    source: "contracts.models::JobState",
    values: ["queued", "retrieving", "judging", "drafting", "validating",
             "done", "failed", "cancelled"],
  },
  {
    prefix: "coverage",
    source: "flint.competitor.coverage::CoverageReason",
    values: ["saturated", "confirmed_empty", "queries_pending",
             "not_saturated", "empty_unconfirmed"],
  },
  {
    prefix: "authority",
    source: "docs/authority-weights-v041 (four tiers + unknown)",
    values: ["tier_a", "tier_b", "tier_c", "tier_d", "unknown"],
  },
  {
    prefix: "strength",
    source: "contracts.models::Competitor.strength",
    values: ["strong", "moderate", "weak", "unknown"],
  },
  {
    prefix: "fact_status",
    source: "contracts.models::FactStatus",
    values: ["frozen", "disputed", "retired"],
  },
  {
    prefix: "alignment",
    source: "contracts.models::Alignment",
    values: ["pending", "supports", "partial", "unsupported"],
  },
  {
    // `UIR-03`：项目总览把作业的 kind 直接印在屏上（`proposal`、`gate1_analysis`）。
    prefix: "job_kind",
    source: "contracts.models::JobKind",
    values: ["gate1_analysis", "report", "proposal", "spec_export",
             "revalidation", "daily_ingest", "pricebook_scan"],
  },
  {
    prefix: "deliverable_type",
    source: "contracts.models::DeliverableType",
    values: ["analysis", "report", "proposal", "vibe_pack", "spec", "chart",
             "revalidation_report"],
  },
  {
    // `REDESIGN-03`：干预页每一行用它说「这一块是什么」。图表、质量卡这几类块没有自己的字，
    // 屏上认得出它们靠的就是这一枚标签。
    prefix: "block_type",
    source: "contracts.models::BlockType",
    values: ["heading", "paragraph", "table", "chart",
             "declaration", "quality_card", "citation_list", "gap_notice"],
  },
  {
    prefix: "availability",
    source: "WIRE-12 three states: checked / not checked / not wired",
    values: ["ok", "not_checked", "not_provided", "down"],
  },
] as const;

const OF_VALUE = new Map<string, string>(
  ENUM_FAMILIES.flatMap((family) =>
    family.values.map((value) => [`${family.prefix}.${value}`, value] as const),
  ).map(([key]) => [key, key]),
);

/**
 * 取一个枚举值的人类标签。
 *
 * 表里没有这个值时**原样返回它并告警**——NEVER 编一句话顶上：
 * 编出来的话与真标签长得一样，而它说的是我们并不知道的事。
 * 原样返回还让判据（屏上不出现下划线小写原值）当场把它抓住。
 */
export function enumLabel(prefix: string, value: string): string {
  const key = `${prefix}.${value}`;
  if (!OF_VALUE.has(key)) {
    console.warn(`[enum] no label registered for ${key}`);
    return value;
  }
  return t(`enum.${key}`);
}
