import { useState, type JSX } from "react";
import type { EvidenceCard } from "../../lib/viewsClient";
import { COMBO_MAX, COMBO_MIN, comboCountValid } from "../../lib/topicClient";
import { t } from "../../lib/i18n";

// combo 入口（TS-008，纯呈现）：复选证据卡（2~5，允许跨簇）+ 写一句话关联假设 →
// onSubmit(cardIds, hypothesis)。选卡数/假设非空前端硬校验（后端 #2/#3 仍唯一真相）。
export function ComboEntryView({
  cards,
  onSubmit,
}: {
  cards: EvidenceCard[];
  onSubmit: (cardIds: string[], hypothesis: string) => void;
}): JSX.Element {
  const [selected, setSelected] = useState<string[]>([]);
  const [hypothesis, setHypothesis] = useState<string>("");

  const toggle = (cardId: string): void => {
    setSelected((prev) =>
      prev.includes(cardId)
        ? prev.filter((c) => c !== cardId)
        : [...prev, cardId],
    );
  };

  const countOk = comboCountValid(selected.length);
  const canSubmit = countOk && hypothesis.trim() !== "";

  return (
    <section data-combo-entry="true">
      <h2>{t("combo.title")}</h2>
      <p data-combo-hint="true">{t("combo.hint")}</p>
      <ul data-combo-cards="true">
        {cards.map((card) => (
          <li key={card.card_id}>
            <label>
              <input
                type="checkbox"
                data-combo-card={card.card_id}
                checked={selected.includes(card.card_id)}
                onChange={() => toggle(card.card_id)}
              />
              {card.card_id}
            </label>
          </li>
        ))}
      </ul>
      <textarea
        data-combo-hypothesis="true"
        placeholder={t("combo.hypothesis_placeholder")}
        value={hypothesis}
        onChange={(e) => setHypothesis(e.target.value)}
      />
      {!countOk && (
        <p data-combo-count-error="true">{t("combo.count_error")}</p>
      )}
      <button
        type="button"
        data-combo-submit="true"
        disabled={!canSubmit}
        onClick={() => onSubmit(selected, hypothesis)}
      >
        {t("combo.submit")}
      </button>
      <span data-combo-range hidden>
        {COMBO_MIN}~{COMBO_MAX}
      </span>
    </section>
  );
}
