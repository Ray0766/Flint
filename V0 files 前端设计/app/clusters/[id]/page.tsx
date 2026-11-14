// P2 工作台 · GET /clusters/{id}/evidence-cards —— 真后端读。
//
// 铁律落到本屏（批次一字段对照表）：
// - flags 三种（novelty / momentum / revival）**各自可辨**，NEVER 合并成一个统一标签。
//   每种同时有**记号形状**与文字，灰度下也分得开（技术约束清单第 4 条）。
// - top_links **可点**（外链，新窗口）。
// - **未知簇后端回 `evidence_cards: []`，那是空态，NEVER 渲染成 404。**
// - keyword_ids 逐条如实列出；卡上不出现任何后端没给的字段。
//
// 视觉：数据屏语言（双主题语义 token）。NEVER glow、NEVER --sulfur。
import type { Metadata } from "next";
import Link from "next/link";
import { fetchEvidenceCards, fetchCategories } from "@/lib/api";
import type { Category, EvidenceCard, EvidenceCardsResponse } from "@/lib/types";
import { AppShell } from "@/components/shell/app-shell";
import { ApiErrorNotice } from "@/components/honesty/api-error";
import { FlagMark } from "@/components/honesty/flag-mark";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "工作台 · Flint",
  description: "GET /clusters/{id}/evidence-cards — 证据卡与旗标，未知簇为空态而非错误。",
};

function Card({ card }: { card: EvidenceCard }) {
  return (
    <article
      className="border border-rule bg-surface p-5"
      style={{ borderRadius: "var(--radius-card)" }}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
        <p className="tabular break-all font-mono text-[12px] text-ink">{card.card_id}</p>
        <p className="break-all font-mono text-[10px] text-ink-3">cluster_id · {card.cluster_id}</p>
      </div>

      {/* flags：三种各自一枚记号，NEVER 合并成统一标签 */}
      <div className="mt-4">
        <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.12em] text-ink-3">flags</p>
        {card.flags.length === 0 ? (
          <p className="font-mono text-[11px] text-ink-3">flags 为空数组（本卡无旗标）</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {card.flags.map((f) => (
              <FlagMark key={f} flag={f} />
            ))}
          </div>
        )}
      </div>

      {/* keyword_ids */}
      <div className="mt-4">
        <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.12em] text-ink-3">
          keyword_ids · {card.keyword_ids.length}
        </p>
        {card.keyword_ids.length === 0 ? (
          <p className="font-mono text-[11px] text-ink-3">keyword_ids 为空数组</p>
        ) : (
          <ul className="flex flex-wrap gap-1.5">
            {card.keyword_ids.map((k) => (
              <li
                key={k}
                className="border border-rule px-2 py-0.5 font-mono text-[11px] text-ink-2"
                style={{ borderRadius: "var(--radius)" }}
              >
                {k}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* top_links：可点外链 */}
      <div className="mt-4">
        <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.12em] text-ink-3">
          top_links · 外链可点
        </p>
        {card.top_links.length === 0 ? (
          <p className="font-mono text-[11px] text-ink-3">top_links 为空数组</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {card.top_links.map((l) => (
              <li key={l} className="min-w-0">
                <a
                  href={l}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="break-all font-mono text-[11px] text-indigo underline underline-offset-2"
                >
                  {l}
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>
    </article>
  );
}

export default async function ClusterWorkbenchPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ cat?: string }>;
}) {
  const { id } = await params;
  await searchParams;

  let data: EvidenceCardsResponse | null = null;
  let error: unknown = null;
  try {
    data = await fetchEvidenceCards(id);
  } catch (err) {
    error = err;
  }

  let categories: Category[] | null = null;
  let categoriesError = false;
  try {
    categories = await fetchCategories();
  } catch {
    categoriesError = true;
  }

  return (
    <AppShell
      active="/plaza"
      endpoint={`GET /clusters/${id}/evidence-cards`}
      categories={categories}
      categoriesError={categoriesError}
    >
      <main className="mx-auto max-w-[1180px] px-5 py-10">
        <header className="mb-8 flex flex-col gap-3">
          <Link href="/plaza" className="font-mono text-[11px] text-ink-2 hover:text-ink">
            ← 热点广场
          </Link>
          <h1 className="font-display text-[31px] font-medium leading-[1.3] text-ink text-balance">
            工作台
          </h1>
          <p className="break-all font-mono text-[11px] text-ink-3">cluster_id · {id}</p>
          <p className="max-w-[42em] text-[14px] leading-[1.8] text-ink-2">
            该簇的证据卡。三种旗标（novelty / momentum / revival）各自一枚记号、互不合并；
            top_links 为真实外链可点。卡上只出现后端返回的字段。
          </p>
        </header>

        {error !== null ? (
          <ApiErrorNotice error={error} what={`簇 ${id} 的证据卡`} />
        ) : data !== null && data.evidence_cards.length === 0 ? (
          // 空态：未知簇 / 该簇暂无卡，后端回 evidence_cards: []。这是空态，NEVER 当 404。
          <div className="gap-cut flex min-h-40 flex-col items-center justify-center gap-2 rounded-[4px] px-6 py-12">
            <p className="font-display text-[20px] text-ink-2">该簇暂无证据卡</p>
            <p className="max-w-[30em] text-center text-[13px] leading-relaxed text-ink-3">
              后端 <span className="font-mono">evidence_cards</span> 为空数组（HTTP 200）。
              未知簇也走这条路径——这是真实空态，不是 404、不是错误。
            </p>
          </div>
        ) : data !== null ? (
          <>
            <p className="mb-4 font-mono text-[11px] text-ink-3">
              evidence_cards · {data.evidence_cards.length} 张
            </p>
            <div className="grid gap-4 lg:grid-cols-2">
              {data.evidence_cards.map((c) => (
                <Card key={c.card_id} card={c} />
              ))}
            </div>
            <p className="mt-8 text-[13px] leading-[1.7] text-ink-2">
              想跨簇把几张卡凑成一个假设？到{" "}
              <Link href="/combo/new" className="text-indigo underline underline-offset-2">
                combo 入口
              </Link>
              （选 2~5 张 + 写一句关联假设）。
            </p>
          </>
        ) : null}
      </main>
    </AppShell>
  );
}
