// I18N-05：引文槽（译文呈现时必带原文展开）。
//
// PRINCIPLES#B9/#B10：引文原文不翻译；报告以译文呈现引用时，出处槽 MUST 可展开到原文。
// 展开态渲染的是 source_field 指向的**原文字节**——NEVER 是译文的再加工。
//
// 没有译文数据时只显原文槽：那是如实，而不是「缺了一块」。

import type { JSX } from "react";
import { useState } from "react";

import { t } from "../../lib/i18n/t";

export type QuoteDisplay = {
  text: string;
  translated: boolean;
  translator: string;
  source_field: string;
};

export type QuoteSlotProps = {
  /** 引文原文（Citation.quote_span）。权威字段。 */
  quoteSpan: string;
  /** 机翻派生槽；无则只显原文。 */
  display?: QuoteDisplay | null;
};

export function QuoteSlot({ quoteSpan, display }: QuoteSlotProps): JSX.Element {
  const [expanded, setExpanded] = useState(false);

  // 无译文：只显原文槽。NEVER 显示一个「展开原文」按钮却展开出同一段文字。
  if (!display) {
    return (
      <blockquote data-testid="quote-original-only" data-has-translation="false">
        {quoteSpan}
      </blockquote>
    );
  }

  return (
    <blockquote data-testid="quote-slot" data-has-translation="true">
      <span data-testid="quote-translated" data-translator={display.translator}>
        {display.text}
      </span>
      <button
        type="button"
        data-testid="quote-expand"
        aria-expanded={expanded}
        onClick={() => setExpanded((v) => !v)}
      >
        {t("quote.expand_original")}
      </button>
      {expanded ? (
        <span
          data-testid="quote-original"
          data-source-field={display.source_field}
        >
          {quoteSpan}
        </span>
      ) : null}
    </blockquote>
  );
}
