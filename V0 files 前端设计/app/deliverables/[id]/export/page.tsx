// P13 导出面板 · /deliverables/[id]/export
//
// 四个格式**真打** GET /deliverables/{id}/render?fmt=——**能不能导由后端说了算**，
// 前端 NEVER 自己预判 409/503（这是上一轮修掉的老毛病，勿回退）。
// 409 EXPORT_BLOCKED → 用 detail.blocking_block_ids 高亮待处理块并挡住导出；
// pdf 503（GTK 缺失）/ pack 503（builder 未接线）→「该格式暂不可用」，NEVER 转圈、NEVER 伪装下载。
import type { Metadata } from "next";
import Link from "next/link";
import { fetchBlocks, fetchCategories, fetchDeliverableMeta } from "@/lib/api";
import type { BlocksResponse, Category, DeliverableMeta } from "@/lib/types";
import { AppShell } from "@/components/shell/app-shell";
import { ApiErrorNotice } from "@/components/honesty/api-error";
import { ExportPanel } from "@/components/export/export-panel";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "导出面板 · Flint",
  description: "四格式真打后端 render；能不能导由后端说了算。",
};

export default async function DeliverableExportPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

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
      endpoint={`GET /deliverables/${id}/render?fmt=`}
      categories={categories}
      categoriesError={categoriesError}
    >
      <main className="mx-auto max-w-[900px] px-5 py-10">
        <header className="mb-8 flex flex-col gap-3">
          <Link
            href={`/deliverables/${encodeURIComponent(id)}`}
            className="font-mono text-[11px] text-ink-2 hover:text-ink"
          >
            ← 只读报告
          </Link>
          <h1 className="font-display text-[31px] font-medium leading-[1.3] text-ink text-balance">
            导出
          </h1>
          <p className="break-all font-mono text-[11px] text-ink-3">
            deliverable · {id}
            {meta !== null ? ` · version ${meta.version} · reproducible ${String(meta.reproducible)}` : ""}
          </p>
          <p className="max-w-[42em] text-[14px] leading-[1.8] text-ink-2">
            四个格式都真打后端。
            <strong className="font-medium text-ink">能不能导出由后端说了算</strong>
            ——界面不预判、不提前灰掉按钮伪装「没有问题」。
          </p>
        </header>

        {error !== null ? (
          <ApiErrorNotice error={error} what={`交付物 ${id}`} />
        ) : tree === null ? (
          <div className="gap-cut flex min-h-40 flex-col items-center justify-center gap-2 rounded-[4px] px-6 py-12">
            <p className="font-display text-[20px] text-ink-2">该交付物尚未生成</p>
            <p className="text-[13px] text-ink-3">没有 Block 树就没有可导出的内容。</p>
          </div>
        ) : (
          <ExportPanel deliverableId={id} blocks={tree.blocks} />
        )}
      </main>
    </AppShell>
  );
}
