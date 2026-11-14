"use client";

import { use, useEffect, useState, type JSX } from "react";

import { fetchClusterVerdictJob } from "../../../lib/viewsClient";
import { API_BASE } from "../../../lib/apiBase";
import { AnalysisView } from "../../../views/analysis/AnalysisView";
import { Screen } from "../../../components/shell/Screen";
import { ClusterSourceLinesForDay } from "./sourceLines";
import { t } from "../../../lib/i18n/t";

// NAV-02：一个热点的分析界面。**承载屏，不是第二个分析视图。**
//
// ## 改前：成品在盘上，没有屏装它
//
// `web/views/analysis/AnalysisView.tsx` 是 `HOTSPOT-03` 建的成品——四态齐全、
// 只读、复用 `viewsClient`。全仓唯一引用它的是 `GraphOpenAnalysis`（一个抽屉组件），
// **而那个抽屉自己也没有任何屏在用**。于是这套分析界面从没在屏上出现过一次。
//
// 广场那边同时是断的：`PlazaCards` 早就有 `onSelectCluster`，
// 而广场屏一直没往里传——点卡片什么都不会发生。
//
// 本屏只做**承载与接线**：`NEVER 为了这一屏再写一遍分析视图`。
// 写第二份的话，两处会各自漂移，而它们展示的是同一份判定。
//
// ## 进入即渲染，**进入不触发**（`DEC-042` ③）
//
// 打开一个热点的分析界面**只是查看**。本屏 NEVER 顺手跑一次分析：
//
// - 用户每点开一次就**付一次钱**；
// - 同一个热点每次可能显示**不同的判定**，判定本身就不再可被引用。
//
// 所以这里一个写请求都不发（`AnalysisView` 文件头原话）。判据用网络层 spy 数请求方法。
//
// ## 判定归属由**调用方**给出（`DEC-012` / `HOTSPOT-03`）
//
// `verdictJobId` 从本屏 URL 的 `?verdictJob=` 读——那正是「调用方持有」的形态。
// 没带就是**未判定**，且一个 verdict 请求都不发。
//
// `NEVER 拿 cluster_id 拼一个 job id 去试`——这条禁令**一字未改**。
//
// ## WIRE-VERDICT：从「猜不得」变成「问得到」
//
// 上面那条禁令的理由是**那时没有持久化真相**（`docs/blocked/HOTSPOT-03.md`）。
// `DEC-044` 之后前提变了：`cluster_verdicts` 就是那个真相，
// `PERSIST-04` 建了 `GET /clusters/{id}/verdict` 把它读出来。
//
// 所以本屏现在**去问**，而不是去猜——两者的差别不是措辞：
// 猜错时用户看到的是另一个热点的判定，而问不到时端点回 404、屏上如实说「未判定」。
//
// ### 两条读法各自什么时候用（`fetchClusterVerdictJob` 文件头有同一张表）
//
// - URL 带 `?verdictJob=` → **用它**。调用方手上那一个是「这一次作业判了什么」，
//   它比「这个热点最近判过什么」更具体，NEVER 被后者覆盖；
// - 没带 → 问 `/clusters/{id}/verdict` 拿 `job_id`；404 = 这个热点没判过。
//
// **封版件一行没动**：`AnalysisView` 的入参仍是 `verdictJobId`，
// 本屏只是把那个 id 的来源从「只有 URL」扩成「URL 优先，其次问端点」。
// 本批 rules 写着「无封版件例外」，所以改它的取数路径不在射程内——
// 而这条路**不需要**改它。
//
// ## 四态归 AnalysisView 自己分
//
// 加载中 / 已判定 / 未判定 / 读失败，四态各自成一态，NEVER 互相冒充。
// 「未判定」（这个热点还没过 Gate①）与「读失败」（我们没读到）尤其不能合并——
// 用户据此做的下一步动作完全不同。本屏不复刻这套分态，只把入参交给它。
export default function ClusterAnalysisPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): JSX.Element {
  const { id: clusterId } = use(params);
  // `undefined` = 还没读 URL；`null` = 读过了，调用方没给。两者 NEVER 共用一个值：
  // 前者时把 `null` 传下去，`AnalysisView` 会先闪一下「未判定」再改口。
  const [verdictJob, setVerdictJob] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    let alive = true;
    const fromUrl = new URLSearchParams(window.location.search).get("verdictJob");
    if (fromUrl) {
      // 调用方给了就用他给的，NEVER 再去问一次把它覆盖掉。
      setVerdictJob(fromUrl);
      return;
    }
    void fetchClusterVerdictJob(clusterId, { baseUrl: API_BASE })
      .then((jobId) => {
        if (alive) setVerdictJob(jobId);
      })
      .catch(() => {
        // 问不到**不等于没判过**。这里落 `null`（AnalysisView 会说「未判定」），
        // 而 `null` 与 `undefined` 的分工没变：`undefined` 是「还没读」。
        // 三态与四态的完整分辨归 `AnalysisView`，本屏 NEVER 复刻一套。
        if (alive) setVerdictJob(null);
      });
    return () => {
      alive = false;
    };
  }, [clusterId]);

  return (
    <Screen
      title={t("cluster.analysis.title")}
      meta={t("cluster.analysis.meta", { cluster: clusterId })}
    >
      {verdictJob === undefined ? (
        <p data-cluster-analysis-loading>{t("cluster.analysis.loading")}</p>
      ) : (
        <>
          <AnalysisView
            clusterId={clusterId}
            verdictJobId={verdictJob}
            baseUrl={API_BASE}
          />
          {/* FIX-18：`NAV-02` 卡面 ③④ 要求这一屏有三样——判定、证据概览、
              **来源分列**。前两样在 `AnalysisView` 里，第三样一直没接。

              **并排渲染，NEVER 动封版件**：`AnalysisView` 是 v0.4 封版件，
              `FIX-19` 拿到的许可只限「加类名与样式」，改它的取数路径不在那条许可里。
              卡面自己写着「修法不需要动封版件」，这里照做。

              复用 `ClusterSourceLines`（`REGION-12` 建的那一层）——
              另写一份的话，广场与这一屏对同一条簇的原话会各自漂移，
              而 `FIX-17` 给它加的可见署名也要再加一遍。 */}
          <ClusterSourceLinesForDay clusterId={clusterId} />
        </>
      )}
    </Screen>
  );
}
