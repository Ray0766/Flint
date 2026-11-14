// P6 发起分析 · POST /projects/{project_id}/analysis —— 真后端写。
//
// 契约要点（analysis.py#submit + schemas.py#AnalysisSubmitRequest）：
//   body = { topic_id?: string, keywords: string[] = [], locale = "zh-CN", budget_cny: number }
//   带 topic_id → 后端由 chosen Topic 派生 keywords；不带 → 用 body.keywords。
//   Header `Idempotency-Key` 可选：同一 (principal, key) 重复提交回同一个 job_id。
// 服务端只取候选主题清单，提交交互在 client 组件里。
import type { Metadata } from "next";
import { fetchCategories, fetchProjectTopics } from "@/lib/api";
import type { Category, TopicsResponse } from "@/lib/types";
import { AppShell } from "@/components/shell/app-shell";
import { AnalysisSubmitForm } from "@/components/analysis/analysis-submit-form";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "发起分析 · Flint",
  description: "POST /projects/{id}/analysis — 选主题、给预算，提交 Gate① 分析作业。",
};

export default async function AnalysisNewPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ topic_id?: string }>;
}) {
  const { id } = await params;
  const { topic_id: preselect } = await searchParams;

  let data: TopicsResponse | null = null;
  let loadError = false;
  try {
    data = await fetchProjectTopics(id);
  } catch {
    loadError = true;
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
      endpoint={`POST /projects/${id}/analysis  ·  主题来源 GET /projects/${id}/topics`}
      categories={categories}
      categoriesError={categoriesError}
    >
      <AnalysisSubmitForm
        projectId={id}
        topics={data?.topics ?? []}
        chosenTopicId={data?.chosen_topic_id ?? null}
        preselectTopicId={preselect ?? null}
        loadError={loadError}
      />
    </AppShell>
  );
}
