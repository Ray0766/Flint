// P12 vibe_pack 查看器 · /deliverables/[id]/pack
//
// 清单第 31 条：它是**给 AI 执行的包**，排版 MUST 与给人读的报告**明显不同**，
// NEVER 做成报告的换皮版。本屏的区别是结构性的，不是配色差异：
//   - 报告屏（P9）是**阅读版式**：正文栏 34em、出处槽、衬线标题、段落流。
//   - 本屏是**清单/载荷版式**：等宽为主、章节编号为 S1~S9、每节标注机器可读性质，
//     零正文流、零出处槽、零衬线标题——看上去像一份规格文件而不是一篇文章。
//
// 内容端点未接：pack 装配仅离线（fmt=pack 走既有 503）。故本屏只呈现
// **结构骨架 + 未接线声明**，NEVER 编造任何章节正文。
import type { Metadata } from "next";
import Link from "next/link";
import { fetchCategories, fetchDeliverableMeta } from "@/lib/api";
import type { Category, DeliverableMeta } from "@/lib/types";
import { AppShell } from "@/components/shell/app-shell";
import { UnbuiltEndpoint } from "@/components/honesty/unbuilt-endpoint";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "vibe_pack 查看器 · Flint",
  description: "给 AI 执行的包：清单式载荷版式，与给人读的报告结构不同。",
};

// vibe_pack 的章节族（CLAUDE.md S1~S9 口径）。这里只列**结构**，不填任何正文。
const PACK_SECTIONS = [
  { id: "S1", name: "Charter", machine: "目标 / 非目标 / 本包范围" },
  { id: "S2", name: "Invariants", machine: "每 cycle 恒装的硬约束清单" },
  { id: "S3", name: "Contracts", machine: "冻结件路径 + 锁版依赖表" },
  { id: "S4", name: "Decision Log + Open Questions", machine: "已决 / 未决（含初值与状态）" },
  { id: "S5", name: "Task DAG", machine: "机读任务卡：inputs/outputs/acceptance/verify_cmd" },
  { id: "S6", name: "Context Manifest", machine: "恒装 + 按需 context_refs + token 预算" },
  { id: "S7", name: "Verification Harness", machine: "每任务 verify_cmd + 全局门" },
  { id: "S8", name: "Progress Ledger", machine: "append-only JSONL 事件流" },
  { id: "S9", name: "Escalation Rules", machine: "必停条件 + 审核检查单" },
] as const;

export default async function PackViewerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  let meta: DeliverableMeta | null = null;
  try {
    meta = await fetchDeliverableMeta(id);
  } catch {
    meta = null;
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
      endpoint={`GET /deliverables/${id}（元信息）· pack 内容端点未接`}
      categories={categories}
      categoriesError={categoriesError}
    >
      {/* 载荷版式：整屏等宽、无正文栏宽度限制、无出处槽 */}
      <main className="mx-auto max-w-[1180px] px-5 py-10 font-mono">
        <header className="mb-8 flex flex-col gap-2 border-b border-rule pb-6">
          <Link
            href={`/deliverables/${encodeURIComponent(id)}`}
            className="text-[11px] text-ink-2 hover:text-ink"
          >
            ← 只读报告（给人读的那份）
          </Link>
          <p className="text-[10px] uppercase tracking-[0.16em] text-ink-3">
            AUDIENCE · ai_executor · TEMPLATE · vibe_pack
          </p>
          {/* 刻意不用 font-display 衬线大标题——那是报告屏的语言 */}
          <h1 className="text-[22px] font-medium leading-[1.3] text-ink">vibe_pack</h1>
          <p className="break-all text-[11px] text-ink-3">
            deliverable · {id}
            {meta !== null
              ? ` · type ${meta.type} · version ${meta.version} · reproducible ${String(meta.reproducible)}`
              : " · 元信息端点未回内容"}
          </p>
          <p className="mt-2 max-w-[46em] font-sans text-[13px] leading-[1.75] text-ink-2">
            这是给 AI 执行器读的包，不是给人读的文章。它按 S1~S9 章节族组织，
            每节都是机器可直接消费的约束与清单——所以这一屏是清单版式，
            没有正文栏、没有出处槽、没有衬线标题。
          </p>
        </header>

        {/* 结构骨架：只列章节与其机读性质，零正文 */}
        <section>
          <h2 className="text-[11px] uppercase tracking-[0.14em] text-ink-3">
            SECTIONS · {PACK_SECTIONS.length}
          </h2>
          <ol className="mt-4 border border-rule bg-surface" style={{ borderRadius: "var(--radius-card)" }}>
            {PACK_SECTIONS.map((s) => (
              <li
                key={s.id}
                className="grid grid-cols-[3rem_1fr] gap-x-4 border-b border-rule px-4 py-3 last:border-b-0 sm:grid-cols-[3rem_14rem_1fr]"
              >
                <span className="tabular text-[12px] text-ink">{s.id}</span>
                <span className="text-[12px] text-ink-2">{s.name}</span>
                <span className="col-span-2 text-[11px] leading-[1.6] text-ink-3 sm:col-span-1">
                  {s.machine}
                </span>
              </li>
            ))}
          </ol>
          <p className="mt-3 text-[10px] leading-[1.6] text-ink-3">
            以上是章节结构（取自 vibe_pack 的 S1~S9 口径）。各节正文尚未在此呈现——
            见下方未接线说明。界面不替包编造任何一节的内容。
          </p>
        </section>

        <div className="mt-6 font-sans">
          <UnbuiltEndpoint
            title="pack 内容读端点"
            endpoint="GET /deliverables/{id}/pack（未建）· 装配仅离线；GET …/render?fmt=pack 现回 503"
            why="vibe_pack 的装配目前只在离线路径存在，没有可供本屏取正文的读端点。故本屏只呈现结构骨架与元信息；导出面板里 fmt=pack 也如实回 503「该格式暂不可用」。"
          />
        </div>
      </main>
    </AppShell>
  );
}
