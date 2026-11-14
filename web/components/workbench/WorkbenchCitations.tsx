"use client";

import { useEffect, useState, type JSX } from "react";

import { API_BASE } from "../../lib/apiBase";
import { QuoteSlot } from "../quote-slot/QuoteSlot";
import { deref } from "../../lib/derefClient";
import { t } from "../../lib/i18n/t";
import type { Block } from "../../lib/types";

/**
 * `WB-04`：预览底下那一节出处——**引用到得了原文**（`PRINCIPLES#B10`）。
 *
 * ## 为什么要单独一节，而不是改 `BlockView`
 *
 * `BlockView` 里的 `citation_list` 走 `DerefValue`，屏上给的是
 * 「文献标题 + 定位符」（`FB-09` 定的：NEVER 把 `cit-…` 甩给读者）。
 * 那是**正文里**该有的样子——一行引用注不该展开成一整段原文。
 *
 * `B10` 要的是「出处槽 MUST 可展开到原文」，那是**出处这一节**的事。
 * 所以这里加一节，而 `BlockView` 一个字没改（它是 v0.4 已 verified 的件）。
 *
 * ## 原文槽复用既有 `QuoteSlot`（`I18N-05`）
 *
 * 它自己的规矩照旧生效：**没有译文数据时只显原文槽**，
 * NEVER 摆一个「展开原文」按钮却展开出同一段文字。
 * 今天这批引用没有译文槽（后端 `GET /citations/{id}` 回的是
 * `quote_span` + `doc`），所以屏上就是原文本身——那是如实。
 *
 * ## 引用 id 从**块里取**，NEVER 另外去问一遍
 *
 * `citation_list` 块自己带着 `citation_ids`；正文里的 `cite` span 也带。
 * 两处合起来去重，就是这一份产物真正引到的那些。
 */

type Loaded = {
  citationId: string;
  quoteSpan: string;
  title: string;
  locator: string | null;
  /** 取不回来时如实说：`B10` 要的是原文到得了屏上，到不了就得看得出来。 */
  unavailable: boolean;
};

function citationIdsOf(blocks: Block[]): string[] {
  const out: string[] = [];
  const push = (id: string): void => {
    if (id && !out.includes(id)) out.push(id);
  };
  for (const block of blocks) {
    const content = block.content;
    if (content.kind === "citation_list") {
      content.citation_ids.forEach(push);
    }
    if (content.kind === "paragraph") {
      for (const span of content.spans) {
        if (span.kind === "cite") push(span.citation_id);
      }
    }
  }
  return out;
}

export function WorkbenchCitations({ blocks }: { blocks: Block[] }): JSX.Element | null {
  const ids = citationIdsOf(blocks);
  const [rows, setRows] = useState<Loaded[]>([]);

  useEffect(() => {
    if (ids.length === 0) {
      setRows([]);
      return;
    }
    let live = true;
    void Promise.all(
      ids.map(async (citationId): Promise<Loaded> => {
        const got = await deref("citation", citationId, { baseUrl: API_BASE });
        if (got.state !== "resolved") {
          return { citationId, quoteSpan: "", title: "", locator: null, unavailable: true };
        }
        const data = got.data as {
          quote_span: string; locator: string | null; doc: { title: string };
        };
        return {
          citationId,
          quoteSpan: data.quote_span,
          title: data.doc.title,
          locator: data.locator,
          unavailable: false,
        };
      }),
    ).then((loaded) => { if (live) setRows(loaded); });
    return () => { live = false; };
    // id 清单由块算得出来；以它的内容为依赖，NEVER 以数组身份（每渲染都是新数组）。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids.join(" ")]);

  if (ids.length === 0) return null;

  return (
    <section className="wb-cites" data-wb-cites="true" data-wb-cites-count={ids.length}>
      <h2 className="wb-cites__title">{t("wb.cites.title")}</h2>
      <ul className="wb-cites__list">
        {rows.map((row) => (
          <li key={row.citationId} className="wb-cites__item" data-wb-cite={row.citationId}>
            {row.unavailable ? (
              // 取不回来**如实说**并留下 id：空白读起来是「这条本来就没有原文」。
              <span data-wb-cite-unavailable="true">
                {t("deref.unavailable")} {row.citationId}
              </span>
            ) : (
              <>
                <span className="wb-cites__doc">
                  {row.locator ? `${row.title} ${row.locator}` : row.title}
                </span>
                <QuoteSlot quoteSpan={row.quoteSpan} />
              </>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
