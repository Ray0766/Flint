// P11 受众分叉 · /projects/[id]/proposal
//
// 提交端点 POST /projects/{id}/proposal（flint/api/compose.py）**本轮刻意未挂**
// （owner 裁决）。表单侧的校验与呈现照做；提交路径如实标「端点未接线」。
import type { Metadata } from "next";
import Link from "next/link";
import { fetchCategories } from "@/lib/api";
import type { Category } from "@/lib/types";
import { AppShell } from "@/components/shell/app-shell";
import { AudienceFork } from "@/components/proposal/audience-fork";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "受众分叉 · Flint",
  description: "给人看的五套模板 / 给 AI 执行的 vibe_pack —— 强制单选、无默认。",
};

export default async function ProposalPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

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
      endpoint={`POST /projects/${id}/proposal（未接线）`}
      categories={categories}
      categoriesError={categoriesError}
    >
      <main className="mx-auto max-w-[900px] px-5 py-10">
        <header className="mb-8 flex flex-col gap-3">
          <Link
            href={`/projects/${encodeURIComponent(id)}/topics`}
            className="font-mono text-[11px] text-ink-2 hover:text-ink"
          >
            ← 候选主题
          </Link>
          <h1 className="font-display text-[31px] font-medium leading-[1.3] text-ink text-balance">
            受众分叉
          </h1>
          <p className="break-all font-mono text-[11px] text-ink-3">project_id · {id}</p>
          <p className="max-w-[42em] text-[14px] leading-[1.8] text-ink-2">
            同一份分析，产出两种东西：给人读的计划书，或给 AI 执行的包。
            这不是排版偏好——两条路的产物结构不同，所以受众必须先选，且没有默认。
          </p>
        </header>

        <AudienceFork projectId={id} />
      </main>
    </AppShell>
  );
}
