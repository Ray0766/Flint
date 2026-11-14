import type { JSX } from "react";
import type { EvidenceCard } from "../../lib/viewsClient";
import { t } from "../../lib/i18n";

// 工作台（FE-VIEWS）：该簇证据卡只读呈现（引用=top_links 源链接据实，前端零计算）。
// 「关联假设」V1 不含（Q-010，未持久化，留白登记）。
export function WorkbenchView({
  clusterId,
  cards,
}: {
  clusterId: string;
  cards: EvidenceCard[];
}): JSX.Element {
  return (
    <section data-workbench="true" data-cluster-id={clusterId}>
      <h2>{t("workbench.title")}</h2>
      {cards.length === 0 ? (
        <p data-workbench-empty="true">{t("workbench.empty")}</p>
      ) : (
        <ul data-card-list="true">
          {cards.map((card) => (
            <li key={card.card_id} data-card-id={card.card_id}>
              <span data-card-flags>
                {t("workbench.flags")}: {card.flags.join(", ")}
              </span>
              <span data-card-keywords>{card.keyword_ids.join(", ")}</span>
              <span data-card-links>
                {t("workbench.links")}:
                {card.top_links.map((url) => (
                  <a key={url} href={url} data-link={url}>
                    {url}
                  </a>
                ))}
              </span>
            </li>
          ))}
        </ul>
      )}
      <p data-hypothesis-deferred="true">{t("workbench.hypothesis_deferred")}</p>
    </section>
  );
}
