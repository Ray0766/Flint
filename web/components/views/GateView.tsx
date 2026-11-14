import type { JSX } from "react";
import type { Verdict } from "../../lib/viewsClient";
import { enumLabel } from "../../lib/i18n/enumLabel";
import { t } from "../../lib/i18n";

// Gate 视图（FE-VIEWS）：Gate① 四分类判定**全引用据实呈现**——verdict/引用/理由/竞品/gaps
// 全取自后端 verdict（snap-{job}-verdict）。**前端 NEVER 自判分类**：只渲染后端 verdict.verdict。
export function GateView({ verdict }: { verdict: Verdict }): JSX.Element {
  return (
    <section data-gate="true">
      <h2>{t("gate.title")}</h2>
      {/* 后端判定，前端不判：verdict 值直取后端 */}
      <p data-verdict={verdict.verdict}>
        {t("gate.verdict")}: {enumLabel("verdict", verdict.verdict)}
      </p>
      <div data-gate-citations="true">
        {t("gate.citations")}:
        {verdict.key_citation_ids.map((cid) => (
          <span key={cid} data-citation-id={cid}>
            {cid}
          </span>
        ))}
      </div>
      <div data-gate-rationale="true">
        {t("gate.rationale")}:
        {verdict.rationale_fact_ids.map((fid) => (
          <span key={fid} data-fact-id={fid}>
            {fid}
          </span>
        ))}
      </div>
      <ul data-gate-competitors="true">
        {verdict.competitors.map((c) => (
          <li key={c.name} data-competitor={c.name}>
            {c.name} · {enumLabel("strength", c.strength)} · {c.url}
          </li>
        ))}
      </ul>
      <ul data-gate-gaps="true">
        {verdict.gaps.map((g, i) => (
          <li key={i} data-gap-cause={g.cause}>
            {g.missing_what}（{g.action}）
          </li>
        ))}
      </ul>
    </section>
  );
}
