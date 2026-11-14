// REDESIGN-03：一块的摘要 = 它自己文字的开头一段。
//
// 干预页用它让人认出「这一行是哪一块」。改前摘要只认 `content.text`，
// 带 span 的段落与表格没有这个字段，于是屏上只有动作键、没有内容。
//
// ## NEVER 改写
//
// - 标题、声明：原文；
// - 段落：开头连续的、带文字的 span 接起来。遇到第一个没有文字的 span（引用标、画像引用）
//   就停，并以省略号标出后面还有——跳过它把后文接上来，得到的是一句原文里不存在的话；
// - 表格：表头，用间隔号隔开；
// - 图表、质量卡、引用列表、缺口提示：这四类块没有自己的字，摘要为空串。
//   它们的内部引用号 NEVER 上屏（`FB-10` 的 A 类），由调用方用块类型标签认它。

import type { Block } from "./types";

const ELLIPSIS = "…";

function clip(text: string, limit: number, more: boolean): string {
  if (text.length > limit) return `${text.slice(0, limit)}${ELLIPSIS}`;
  return more ? `${text}${ELLIPSIS}` : text;
}

export function blockExcerpt(block: Block, limit: number = 80): string {
  const content = block.content;
  if (content.kind === "heading" || content.kind === "declaration") {
    return clip(content.text, limit, false);
  }
  if (content.kind === "paragraph") {
    let lead = "";
    let stoppedEarly = false;
    for (const span of content.spans) {
      if (span.kind !== "text" && span.kind !== "claim") {
        stoppedEarly = true;
        break;
      }
      lead += span.text;
    }
    return lead === "" ? "" : clip(lead, limit, stoppedEarly);
  }
  if (content.kind === "table") {
    return clip(content.header.join(" · "), limit, false);
  }
  return "";
}
