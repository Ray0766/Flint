"use client";

import { useEffect, useState, type JSX } from "react";

import { API_BASE } from "../../../lib/apiBase";
import { ClusterSourceLines } from "../../../components/plaza/ClusterSourceLines";
import { fetchPlazaHot, type PlazaCluster } from "../../../lib/viewsClient";
import { t } from "../../../lib/i18n/t";

/**
 * FIX-18：热点分析屏的**来源分列**（`NAV-02` 卡面 ③④ 欠下的那一样）。
 *
 * ## 为什么单独一个文件、而不是动 `AnalysisView`
 *
 * `AnalysisView` 是 **v0.4 封版件**。`FIX-19` 拿到的许可**只限加类名与样式**，
 * 改它的取数路径不在那条许可里（`worker.md` §9.2 / `DEC-021`）。
 *
 * 卡面写得很清楚：**修法不需要动封版件**——承载屏里把
 * `<AnalysisView/>` 与 `<ClusterSourceLines/>` **并排渲染**即可。
 * 本文件就是那个「并排的另一半」。
 *
 * ## 各源原话是**当天**的事实，所以要一个日期
 *
 * `by_source_text` 只在 `GET /plaza/hot?day=…` 的簇行上（`flint/api/views.py`）——
 * 它记的是**那一天**各源怎么说的。所以本组件按 `?day=` 取；
 * URL 上没带时用与广场同一个默认值。
 *
 * **这不是将就**：「各源当天的原话」本来就是按天的，
 * 一个不带日期的「原话」说不清是哪天说的。
 *
 * ## 四态各自成一态，NEVER 合并
 *
 * | 态 | 记号 | 什么意思 |
 * |---|---|---|
 * | 还在取 | `loading` | 还没查 |
 * | 查到了 | `ready` | 这一天的榜里有它，分列照渲染 |
 * | 这一天的榜里没有它 | `not_on_this_day` | **查过了，它不在这一天**——换一天可能就有 |
 * | 读失败 | `failed` | 没查成 |
 *
 * 第三态与第四态尤其不能合并：前者该换一天，后者该重试。
 * 而两者在「屏上没有分列」这个结果上长得一模一样。
 *
 * ## 缺词面的源：`ClusterSourceLines` 自己会如实说
 *
 * 那一层的文件头写着「NEVER 塞占位串」——有热度、当天原始条目找不回来的源，
 * 它另起一行说「这几个源的原话没查到」。本组件**只搬运，不判断**。
 */

/** 与广场同一个默认日（`web/app/plaza/page.tsx`）。两处都写死同一个值，
 *  是因为它今天是**演示库那一天**；库里换成真实抓取之后（`CN-01`）
 *  两处一起改，而 `?day=` 始终优先。 */
const DEFAULT_DAY = "2026-07-04";

type State =
  | { kind: "loading" }
  | { kind: "ready"; cluster: PlazaCluster }
  | { kind: "not_on_this_day" }
  | { kind: "failed" };

export function ClusterSourceLinesForDay({
  clusterId,
}: {
  clusterId: string;
}): JSX.Element {
  const [day, setDay] = useState<string | null>(null);
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    setDay(new URLSearchParams(window.location.search).get("day") ?? DEFAULT_DAY);
  }, []);

  useEffect(() => {
    if (day === null) return;
    let live = true;
    setState({ kind: "loading" });
    fetchPlazaHot(day, { baseUrl: API_BASE })
      .then((rows) => {
        if (!live) return;
        const found = rows.find((row) => row.cluster_id === clusterId);
        // 找不到**不是失败**：它可能就是不在这一天的榜上。
        setState(found ? { kind: "ready", cluster: found } : { kind: "not_on_this_day" });
      })
      .catch(() => live && setState({ kind: "failed" }));
    return () => {
      live = false;
    };
  }, [day, clusterId]);

  return (
    <section
      className="cluster-source-lines"
      data-testid="cluster-source-lines"
      data-source-lines-state={state.kind}
      data-source-lines-day={day ?? ""}
    >
      <h3>{t("cluster.sources.heading")}</h3>
      {state.kind === "loading" ? (
        <p data-testid="cluster-source-lines-loading">{t("screen.loading")}</p>
      ) : state.kind === "failed" ? (
        <p data-testid="cluster-source-lines-failed">{t("cluster.sources.failed")}</p>
      ) : state.kind === "not_on_this_day" ? (
        // 「查过了，它不在这一天」——**说清是哪一天**，用户才知道该换哪个。
        <p data-testid="cluster-source-lines-absent">
          {t("cluster.sources.not_on_this_day", { day: day ?? "" })}
        </p>
      ) : (
        <ClusterSourceLines
          bySource={state.cluster.by_source}
          bySourceRegion={state.cluster.by_source_region}
          bySourceText={state.cluster.by_source_text}
        />
      )}
    </section>
  );
}
