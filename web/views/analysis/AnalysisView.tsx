// HOTSPOT-03：分析界面骨架（默认展示 Gate① 既有判定 + 证据概览，零新计算）。
//
// 「进入即渲染」的另一半是「进入不触发」：打开一个热点的分析界面**只是查看**，
// NEVER 顺手跑一次分析——那会让用户每次点开都付一次钱，且同一个热点可能
// 每次显示不同的判定，判定本身就不再可被引用。所以本视图只调既有读端点。
//
// 判定归属由调用方给出（verdictJobId），本视图 NEVER 自己推断：
// contracts 里 Job 无 cluster 字段、jobs 表也无 cluster_id，cluster→判定 的对应关系
// 当前没有持久化真相（已上报 docs/blocked/HOTSPOT-03.md）。缺就是缺——
// 拿 cluster_id 拼一个 job id 去试，等于凭空发明一条溯源链。
//
// 四个状态各自成一态，NEVER 互相冒充：加载中 / 已判定 / 未判定 / 读失败。
// 「未判定」与「读失败」尤其不能合并：前者是这个热点还没过 Gate①，
// 后者是我们没读到——用户据此做的下一步动作完全不同。

import type { JSX } from "react";
import { useEffect, useState } from "react";

import { t } from "../../lib/i18n/t";
import {
  fetchEvidenceCards,
  fetchVerdict,
  VerdictNotReady,
  type EvidenceCard,
  type Verdict,
} from "../../lib/viewsClient";

/** 读端点全部复用既有客户端（viewsClient），本视图不拼 URL、不改请求方法。 */

/* FIX-19（owner 2026-08-09 明确许可动这个 v0.4 封版件）：
 * **加类名与样式，边界只限于此**——
 * NEVER 改判定语义、NEVER 动四态逻辑、NEVER 改任何既有判据。
 *
 * 本次改动逐条就是：15 处元素各加一个 `className`。
 * 判定分支、四态分支、取数、`data-testid` / `data-verdict` / `data-card-id`
 * **一个字都没动**——判据 `test_analysis_view_styled.py` 从两侧量这件事。
 *
 * 样式住在 `web/app/globals.css` 的 `.analysis*` 一段，全部走 `_ds` token，
 * NEVER 写死颜色与字号（`UI-01` 三条判据的射程）。
 */
export type AnalysisViewProps = {
  clusterId: string;
  /** Gate① 判定所在的既有 job；调用方给出，缺省即「未判定」。 */
  verdictJobId?: string | null;
  /** 注入网络层，便于测试断言只读；默认用浏览器的。 */
  fetchImpl?: typeof fetch;
  baseUrl?: string;
};

type ReadState = "loading" | "ready" | "absent" | "failed";

export function AnalysisView({
  clusterId,
  verdictJobId,
  fetchImpl,
  baseUrl,
}: AnalysisViewProps): JSX.Element {
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [verdictState, setVerdictState] = useState<ReadState>(
    verdictJobId ? "loading" : "absent",
  );
  const [cards, setCards] = useState<EvidenceCard[]>([]);
  const [cardsState, setCardsState] = useState<ReadState>("loading");

  useEffect(() => {
    let alive = true;
    const opts = { fetchImpl, baseUrl };

    void (async () => {
      try {
        const found = await fetchEvidenceCards(clusterId, opts);
        if (!alive) return;
        setCards(found);
        setCardsState(found.length > 0 ? "ready" : "absent");
      } catch {
        if (alive) setCardsState("failed");
      }
    })();

    if (!verdictJobId) {
      setVerdict(null);
      setVerdictState("absent");
      return () => {
        alive = false;
      };
    }

    void (async () => {
      try {
        const found = await fetchVerdict(verdictJobId, opts);
        if (!alive) return;
        setVerdict(found);
        setVerdictState("ready");
      } catch (err) {
        if (!alive) return;
        setVerdict(null);
        setVerdictState(err instanceof VerdictNotReady ? "absent" : "failed");
      }
    })();

    return () => {
      alive = false;
    };
  }, [clusterId, verdictJobId, fetchImpl, baseUrl]);

  return (
    <section className="analysis" data-testid="analysis-view" data-cluster-id={clusterId}>
      <h2 className="analysis__heading" data-testid="analysis-verdict-heading">{t("analysis.section.verdict")}</h2>
      {verdictState === "loading" ? (
        <p className="analysis__note" data-testid="analysis-verdict-loading">{t("analysis.verdict.loading")}</p>
      ) : null}
      {verdictState === "ready" && verdict ? (
        <div className="analysis__verdict" data-testid="analysis-verdict" data-verdict={verdict.verdict}>
          <span className="analysis__verdict-code" data-testid="analysis-verdict-code">{verdict.verdict}</span>
          <span className="analysis__verdict-part" data-testid="analysis-verdict-all-satisfied">
            {verdict.all_satisfied.join(" ")}
          </span>
          <span className="analysis__verdict-part" data-testid="analysis-verdict-citations">
            {t("analysis.verdict.citations", { count: verdict.key_citation_ids.length })}
          </span>
        </div>
      ) : null}
      {verdictState === "absent" ? (
        <p className="analysis__note" data-testid="analysis-verdict-unjudged">{t("analysis.verdict.unjudged")}</p>
      ) : null}
      {verdictState === "failed" ? (
        <p className="analysis__note analysis__note--error" data-testid="analysis-verdict-error">{t("analysis.verdict.error")}</p>
      ) : null}

      <h2 className="analysis__heading" data-testid="analysis-evidence-heading">{t("analysis.section.evidence")}</h2>
      {cardsState === "loading" ? (
        <p className="analysis__note" data-testid="analysis-evidence-loading">{t("analysis.evidence.loading")}</p>
      ) : null}
      {cardsState === "ready" ? (
        <ul className="analysis__evidence" data-testid="analysis-evidence">
          {cards.map((card) => (
            <li
              key={card.card_id}
              className="analysis__evidence-card"
              data-testid="analysis-evidence-card"
              data-card-id={card.card_id}
            >
              {t("analysis.evidence.counts", {
                keywords: card.keyword_ids.length,
                flags: card.flags.length,
                links: card.top_links.length,
              })}
            </li>
          ))}
        </ul>
      ) : null}
      {cardsState === "absent" ? (
        <p className="analysis__note" data-testid="analysis-evidence-empty">{t("analysis.evidence.empty")}</p>
      ) : null}
      {cardsState === "failed" ? (
        <p className="analysis__note analysis__note--error" data-testid="analysis-evidence-error">{t("analysis.evidence.error")}</p>
      ) : null}
    </section>
  );
}
