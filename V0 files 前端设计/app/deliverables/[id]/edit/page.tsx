// P10 可干预页 · /deliverables/[id]/edit —— 真后端写。
//
// 读：GET /deliverables/{id}/blocks（同 P9 报告 L0 的读契约）
// 写：POST /interventions/lock · /deliverables/{id}/sections/{sid}/regenerate ·
//     /projects/{id}/evidence · /projects/{id}/disputes
//
// 视觉：数据屏语言。NEVER glow、NEVER 硫磺；--spark 只用于 blocking 复核标。
import type { Metadata } from "next";
import Link from "next/link";
import { fetchBlocks, fetchCategories, fetchDeliverableMeta } from "@/lib/api";
import type { BlocksResponse, Category, DeliverableMeta } from "@/lib/types";
import { AppShell } from "@/components/shell/app-shell";
import { ApiErrorNotice } from "@/components/honesty/api-error";
import { InterveneWorkbench } from "@/components/intervene/intervene-workbench";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "可干预页 · Flint",
  description: "锁定 / 再生成 / 争议 / 补证据 —— 受保护块不提供任何控件。",
};

export default async function DeliverableEditPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ project_id?: string }>;
}) {
  const { id } = await params;
  const { project_id: projectId } = await searchParams;

  let tree: BlocksResponse | null = null;
  let meta: DeliverableMeta | null = null;
  let error: unknown = null;
  try {
    [meta, tree] = await Promise.all([fetchDeliverableMeta(id), fetchBlocks(id)]);
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
      endpoint={`GET /deliverables/${id}/blocks  ·  写 POST /interventions/*`}
      categories={categories}
      categoriesError={categoriesError}
    >
      <main className="mx-auto max-w-[1180px] px-5 py-10">
        <header className="mb-8 flex flex-col gap-3">
          <Link
            href={`/deliverables/${encodeURIComponent(id)}`}
            className="font-mono text-[11px] text-ink-2 hover:text-ink"
          >
            ← 只读报告
          </Link>
          <h1 className="font-display text-[31px] font-medium leading-[1.3] text-ink text-balance">
            可干预页
          </h1>
          <p className="break-all font-mono text-[11px] text-ink-3">
            deliverable · {id}
            {meta !== null ? ` · ledger_version ${meta.ledger_version}` : ""}
          </p>
          <p className="max-w-[46em] text-[14px] leading-[1.8] text-ink-2">
            受保护的块（<code className="text-[13px] text-ink">locked ∨ author=&quot;user&quot; ∨ user_modified</code>
            ）
            <strong className="font-medium text-ink">不提供任何干预控件</strong>
            ——是不存在，不是置灰。门控唯一真相为{" "}
            <code className="text-[13px] text-ink">availableBlockInterventions(block)</code>。
          </p>
        </header>

        {error !== null ? (
          <ApiErrorNotice error={error} what={`交付物 ${id}`} />
        ) : tree === null ? (
          <div className="gap-cut flex min-h-40 flex-col items-center justify-center gap-2 rounded-[4px] px-6 py-12">
            <p className="font-display text-[20px] text-ink-2">该交付物尚未生成</p>
            <p className="max-w-[32em] text-center text-[13px] leading-relaxed text-ink-3">
              <span className="font-mono">GET /deliverables/{id}/blocks</span> 回 404。
              没有 Block 树就无从干预——这不是错误，是还没有内容。
            </p>
          </div>
        ) : tree.blocks.length === 0 ? (
          <div className="gap-cut flex min-h-40 flex-col items-center justify-center gap-2 rounded-[4px] px-6 py-12">
            <p className="font-display text-[20px] text-ink-2">这份交付物没有任何 block</p>
            <p className="text-[13px] text-ink-3">后端 blocks 为空数组。真实空态，非加载中、非错误。</p>
          </div>
        ) : (
          <InterveneWorkbench
            deliverableId={id}
            projectId={projectId ?? null}
            blocks={tree.blocks}
            ledgerVersion={meta?.ledger_version ?? null}
          />
        )}
      </main>
    </AppShell>
  );
}
