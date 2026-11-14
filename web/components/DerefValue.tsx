"use client";

import type { JSX, ReactNode } from "react";
import { useEffect, useState } from "react";

import { API_BASE } from "../lib/apiBase";
import { deref, type DerefKind, type DerefResult } from "../lib/derefClient";
import { t } from "../lib/i18n/t";

// FB-09：把正文里的一个 id 换成它的内容。
//
// 三种态各有各的规矩，而**规矩本身就是这张卡的产品需求**：
//
//   resolved    → 显示内容（读者要看的是「向量库托管月成本 12.5 美元」，
//                 不是 `fact-demo-vecdb-cost`）；
//   unavailable → 显示「接口未提供」**并把原 id 留在屏上**。
//                 NEVER 空白（空白读起来是「这里本来就没东西」）、
//                 NEVER 编造（编出来的内容没有出处）；
//   loading     → 先显示原 id。读者至少看得到「这里引的是哪一条」，
//                 而不是盯着一片空白等。
//
// 管道细节（`GET /facts/…`、HTTP 状态码）**不进产品面**：那是开发要看的，
// 留在 `data-*` 上供取证与调试即可。而「这个数字有出处」「这块被阻断导出」
// 那类是产品需求，照旧显示——两者的分界是本卡 acceptance③。

export interface DerefValueProps {
  kind: DerefKind;
  id: string;
  quantity?: number;
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}

// 每条通道怎么显示，**写在这一个地方**。
//
// 首版把它做成 `render` 函数 prop，由 BlockView 传进来——单测全绿，
// 真页面当场 500：`BlockView` 是 Server Component，
// **函数不能跨 Server→Client 边界传**（React 的硬规矩）。
// 浏览器抓住了单测抓不到的东西（vitest 里一切都在客户端，那条边界根本不存在）。
// 改成按 kind 内部格式化之后，props 全部可序列化，边界问题从根上没有了。
function present(kind: DerefKind, data: unknown): ReactNode {
  switch (kind) {
    case "fact": {
      const f = data as { statement: string; value: unknown; unit: string | null };
      const num = f.value === null ? "" : ` ${String(f.value)}${f.unit ?? ""}`;
      return `${f.statement}${num}`;
    }
    case "price": {
      const p = data as {
        amount_low: number; amount_high: number; currency: string;
        stale: boolean; price_data_note: string | null;
      };
      const amount = p.amount_low === p.amount_high
        ? `${p.amount_low} ${p.currency}`
        : `${p.amount_low}-${p.amount_high} ${p.currency}`;
      // 过期单价照实带注记（D13：NEVER 静默用旧价）。
      return p.stale && p.price_data_note ? `${amount} (${p.price_data_note})` : amount;
    }
    case "citation": {
      const c = data as { doc: { title: string }; locator: string | null };
      return c.locator ? `${c.doc.title} ${c.locator}` : c.doc.title;
    }
    case "chart": {
      const c = data as {
        points: Array<{ statement: string; value: unknown; unit: string | null }>;
      };
      return c.points
        .map((pt) => `${pt.statement} ${String(pt.value)}${pt.unit ?? ""}`)
        .join(", ");
    }
    case "card": {
      const c = data as { cluster: { canonical_name: string } };
      return c.cluster.canonical_name;
    }
    case "hints": {
      const h = data as { hints: Array<{ missing_what: string; why: string }> };
      return (
        <ul data-gap-hints="true">
          {h.hints.map((hint) => (
            <li key={hint.missing_what}>{`${hint.missing_what} - ${hint.why}`}</li>
          ))}
        </ul>
      );
    }
  }
}

export function DerefValue({
  kind,
  id,
  quantity,
  baseUrl,
  fetchImpl,
}: DerefValueProps): JSX.Element {
  const [result, setResult] = useState<DerefResult | null>(null);

  useEffect(() => {
    let alive = true;
    void deref(kind, id, {
      baseUrl: baseUrl ?? API_BASE,
      fetchImpl,
      quantity,
    }).then((got) => {
      if (alive) setResult(got);
    });
    return () => {
      alive = false;
    };
  }, [kind, id, quantity, baseUrl, fetchImpl]);

  if (result === null) {
    return (
      <span data-testid="deref-loading" data-deref-kind={kind} data-deref-id={id}>
        {id}
      </span>
    );
  }

  if (result.state === "unavailable") {
    return (
      <span
        data-testid="deref-unavailable"
        data-deref-kind={kind}
        data-deref-id={id}
        data-deref-status={result.status ?? "offline"}
      >
        {t("deref.unavailable")} {id}
      </span>
    );
  }

  return (
    <span data-testid="deref-resolved" data-deref-kind={kind} data-deref-id={id}>
      {present(kind, result.data)}
    </span>
  );
}
