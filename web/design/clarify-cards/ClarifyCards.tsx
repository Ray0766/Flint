// DESIGN-07：澄清问题卡（G9）。
//
// **每题都有「由你决定」**：澄清问题里总有几条用户其实无所谓——逼他在无所谓的事上
// 做选择，他要么随便点一个（于是系统拿到一个假答案），要么干脆放弃这一轮。
// 把「你替我定」做成一个正经选项，拿到的是**真实**的授权。
//
// 注意「留空」与「由你决定」是两件事：前者是没答，后者是答了「你定」。
// 所以点它会**明确地**回一个 `{deferred: true}`，而不是什么都不发。
//
// **未答复禁续输**：让他一边留着没答的问题一边继续说，系统就得猜「这句新话是不是
// 在回答刚才那题」——猜错的代价是整轮生成基于一个错误前提。禁用的同时必须说明为什么，
// 一个灰着又不说话的输入框只会让人以为界面坏了（与 GRAPH-08 的置灰同一条纪律）。
//
// **答案由上层持有**：组件内部再存一份会与上层那份漂移——用户看到的与将要发出去的
// 不是同一份。本组件只呈现与回调。

import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

export type ClarifyQuestion = {
  id: string;
  question: string;
  options: string[];
};

export type ClarifyAnswer = {
  /** true = 用户明确说「你替我定」 */
  deferred: boolean;
  choice: string | null;
};

export type ClarifyCardsProps = {
  questions: ClarifyQuestion[];
  answers: Record<string, ClarifyAnswer>;
  onAnswer: (questionId: string, answer: ClarifyAnswer) => void;
  /** 把**剩下未答**的题一起交给系统决定 */
  onDeferAll: (questionIds: string[]) => void;
};

export function ClarifyCards({
  questions,
  answers,
  onAnswer,
  onDeferAll,
}: ClarifyCardsProps): JSX.Element | null {
  if (questions.length === 0) return null;

  const pending = questions.filter((q) => answers[q.id] === undefined);

  return (
    <section data-testid="clarify-cards">
      <p data-testid="clarify-pending-count" data-pending={pending.length}>
        {t("design.clarify.pending", { count: pending.length })}
      </p>
      {pending.length > 0 ? (
        <button
          type="button"
          data-testid="clarify-defer-all"
          onClick={() => onDeferAll(pending.map((q) => q.id))}
        >
          {t("design.clarify.defer_all")}
        </button>
      ) : null}
      <ul>
        {questions.map((q) => (
          <li key={q.id} data-testid="clarify-card" data-question-id={q.id}>
            <p>{q.question}</p>
            {q.options.map((option) => (
              <button
                key={option}
                type="button"
                data-testid="clarify-option"
                onClick={() => onAnswer(q.id, { deferred: false, choice: option })}
              >
                {option}
              </button>
            ))}
            <button
              type="button"
              data-testid="clarify-defer"
              onClick={() => onAnswer(q.id, { deferred: true, choice: null })}
            >
              {t("design.clarify.defer")}
            </button>
          </li>
        ))}
      </ul>
      <input
        data-testid="clarify-blocked-input"
        disabled={pending.length > 0}
        placeholder={t("design.clarify.input_placeholder")}
      />
      {pending.length > 0 ? (
        <p data-testid="clarify-blocked-reason">{t("design.clarify.blocked")}</p>
      ) : null}
    </section>
  );
}
