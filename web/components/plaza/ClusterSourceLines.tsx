// REGION-12：把一条簇的各源原话接给 `SourceColumns`（`PLAZA-02` 缺口二）。
//
// ## 这一层为什么存在
//
// `SourceColumns`（`HOTSPOT-07`）是 **v0.4 已 verified** 的组件，
// `worker.md` §9.2 / `DEC-021`：已 verified 的实现与判据 NEVER 再改。
// 它的契约是三元组 `{ sourceId, region, text }`，其中 `text` 逐字写着「原文；NEVER 是译文」。
//
// 而广场端点给的是三张并行的表：`by_source`（分值）、`by_source_region`（区）、
// `by_source_text`（原话）。本层只做**搬运与配对**，不做任何判断。
//
// ## 缺词面的源：另起一行，NEVER 塞占位串
//
// 有热度、但当天的原始条目找不回来的源，`by_source_text` 里没有它。
// 那时 **NEVER** 给 `text` 塞一个 `—` 或「暂无」——那个槽契约上是原文，
// 塞进去屏上会写着「微博说：暂无」，**而微博没说过这句话**。
//
// 所以缺的那些源由本层另起一行如实说「这几个源的原话没查到」。
// 这与 `DEC-032` 的诚实态是同一条：**「没查到」与「说了一句空话」是两件事。**
//
// ## `global` 与没有区的源，都落进未归区那一列
//
// `SourceColumns` 用空串表示未归区（`UNKNOWN_REGION_KEY`，恒排最后）。
// 本层把 `global` 也映射成空串——**这正是 `DEC-040` 的呈现层合并**：
// `global` 是 `ghtrend` 写死的常量，不是地理事实。
// **库里两者仍然可分辨**，被合并的只是这一屏上的一列。

import type { JSX } from "react";

import { SourceColumns, type SourceStatement } from "../source-columns/SourceColumns";
import { t } from "../../lib/i18n/t";
import { UNASSIGNED_REGION } from "../../lib/regions";

/** 落在 region 位上、但不是地理事实的值。与后端 `SOURCE_CONSTANT_REGIONS` 同一份名单。 */
const NOT_A_GEOGRAPHIC_REGION: readonly string[] = ["global", UNASSIGNED_REGION];

export type ClusterSourceLinesProps = {
  /** `{源: 分值}`。本层**只用它的键**来发现「有热度却没词面」的源。 */
  bySource: Record<string, number>;
  /** `{源: 区}`。缺项 = 这个源没有区，落未归区那一列。 */
  bySourceRegion?: Record<string, string>;
  /** `{源: 原话}`。**缺项 = 没查到**，NEVER 当成空话。 */
  bySourceText?: Record<string, string>;
};

export function statementsFrom(
  bySourceText: Record<string, string>,
  bySourceRegion: Record<string, string>,
): SourceStatement[] {
  // **顺序恒取后端给的**（`PRINCIPLES#B8`：前端不重排）。
  // 第一版在这里 `.sort()` 了一道，`tools/check_design_constraints` 当场抓到——
  // 而它抓得对：`flint/region/source_text.py#as_payload` 已经排好序了
  // （`sorted(wordings.items())`），前端再排一次是**第二个排序口径**，
  // 两处哪天分叉，屏上的顺序与取证里的顺序就对不上，而没有任何报错。
  return Object.keys(bySourceText).map((sourceId) => {
    const region = bySourceRegion[sourceId] ?? "";
    return {
      sourceId,
      region: NOT_A_GEOGRAPHIC_REGION.includes(region) ? "" : region,
      // 原文**原样搬运**：NEVER trim、NEVER 归一化全半角、NEVER 截断。
      // `clean()` 归一化是入库前的事；到了这里再归一一次，
      // 微博那句 `＃脑机接口＃` 就不再是微博说的那句话了。
      text: bySourceText[sourceId],
    };
  });
}

/** 有热度、却没有词面的那些源。**顺序照 `by_source` 给的**，前端不重排（B8）。 */
export function sourcesWithoutWording(
  bySource: Record<string, number>,
  bySourceText: Record<string, string>,
): string[] {
  return Object.keys(bySource).filter((sourceId) => !(sourceId in bySourceText));
}

export function ClusterSourceLines({
  bySource,
  bySourceRegion,
  bySourceText,
}: ClusterSourceLinesProps): JSX.Element | null {
  const texts = bySourceText ?? {};
  const statements = statementsFrom(texts, bySourceRegion ?? {});
  const missing = sourcesWithoutWording(bySource, texts);

  if (statements.length === 0 && missing.length === 0) return null;

  return (
    <div className="cluster-source-lines" data-testid="cluster-source-lines">
      {statements.length > 0 ? <SourceColumns statements={statements} /> : null}
      {missing.length > 0 ? (
        <p
          className="cluster-source-lines__missing"
          data-testid="source-wording-missing"
          data-sources={missing.join(",")}
        >
          {t("source.wording.missing", { sources: missing.join("、") })}
        </p>
      ) : null}
    </div>
  );
}
