// P4 主题列表 · GET /projects/{project_id}/topics —— 真后端读。
//
// 契约要点（views.py#project_topics）：
// - 未知 project **不是 404**：后端显式回 {project_id, chosen_topic_id: null, topics: []}
//   → 屏上必须是**空态**，NEVER 渲染成错误页。
// - chosen_topic_id 可为 null（尚未选主题）。选中标记直取该字段，前端不自行推断。
// - topic_ids 指向的 Topic 缺失时后端会跳过（据实、不造）→ 列表长度可能少于 topic_ids。
//
// 清单第 13 条：speculative 主题在列表里也 MUST 降权并抑制溯源入口（见 WhyNowPanel）。
// 视觉：数据屏语言。NEVER glow、NEVER 硫磺；--spark 不属本屏（无 blocking/409/503 语义）。
import type { Metadata } from "next";
import Link from "next/link";
import { CircleDashed, Check } from "lucide-react";
import { fetchCategories, fetchProjectTopics } from "@/lib/api";
import type { Category, Topic, TopicsResponse } from "@/lib/types";
import { AppShell } from "@/components/shell/app-shell";
import { ApiErrorNotice } from "@/components/honesty/api-error";
import { WhyNowPanel } from "@/components/topic/why-now";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "主题列表 · Flint",
  description: "GET /projects/{id}/topics — 候选主题与已选主题，选中态直取后端 chosen_topic_id。",
};

function TopicRow({
  topic,
  chosen,
  projectId,
}: {
  topic: Topic;
  chosen: boolean;
  projectId: string;
}) {
  const spec = topic.why_now.speculative;
  return (
    <article
      className={`border p-5 ${
        // 降权：推测态虚线边；已选态实线加重边。两者形态不同，灰度可辨。
        spec ? "border-dashed border-rail bg-surface" : "border-rule bg-surface"
      } ${chosen ? "border-ink" : ""}`}
      style={{ borderRadius: "var(--radius-card)" }}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {chosen ? (
              <span
                className="inline-flex items-center gap-1 border border-ink bg-ink px-2 py-0.5 font-mono text-[10px] text-primary-foreground"
                style={{ borderRadius: "var(--radius)" }}
              >
                <Check className="h-3 w-3" strokeWidth={2} aria-hidden />
                chosen_topic_id
              </span>
            ) : null}
            {spec ? (
              <span
                className="inline-flex items-center gap-1 border border-dashed border-rail px-2 py-0.5 font-mono text-[10px] text-ink-3"
                style={{ borderRadius: "var(--radius)" }}
              >
                <CircleDashed className="h-3 w-3" strokeWidth={1.5} aria-hidden />
                推测 · 未经证据对齐
              </span>
            ) : null}
          </div>

          <h3
            className={`mt-2 text-[16px] font-medium leading-[1.5] ${
              spec ? "text-ink-2" : "text-ink"
            }`}
          >
            <Link
              href={`/topics/${encodeURIComponent(topic.topic_id)}`}
              className="underline-offset-4 hover:underline"
            >
              {topic.one_liner}
            </Link>
          </h3>

          <p className="mt-1.5 break-all font-mono text-[10px] text-ink-3">
            {topic.topic_id} · seed {topic.seed_id}
          </p>

          <div className="mt-3 flex flex-wrap gap-2">
            <span
              className="border border-rule px-2 py-0.5 font-mono text-[11px] text-ink-2"
              style={{ borderRadius: "var(--radius)" }}
            >
              target_user · {topic.target_user_tag}
            </span>
            <span
              className="border border-rule px-2 py-0.5 font-mono text-[11px] text-ink-2"
              style={{ borderRadius: "var(--radius)" }}
            >
              form_factor · {topic.form_factor_tag}
            </span>
          </div>
        </div>

        <Link
          href={`/projects/${encodeURIComponent(projectId)}/analysis/new?topic_id=${encodeURIComponent(topic.topic_id)}`}
          className="shrink-0 border border-rule px-3 py-1.5 font-mono text-[12px] text-ink-2 transition-colors hover:border-rail"
          style={{ borderRadius: "var(--radius)" }}
        >
          对它发起分析 →
        </Link>
      </div>

      <div className="mt-4">
        <WhyNowPanel why={topic.why_now} compact />
      </div>
    </article>
  );
}

export default async function ProjectTopicsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let data: TopicsResponse | null = null;
  let error: unknown = null;
  try {
    data = await fetchProjectTopics(id);
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

  const specCount = (data?.topics ?? []).filter((t) => t.why_now.speculative).length;

  return (
    <AppShell
      active="/plaza"
      endpoint={`GET /projects/${id}/topics`}
      categories={categories}
      categoriesError={categoriesError}
    >
      <main className="mx-auto max-w-[1180px] px-5 py-10">
        <header className="mb-8 flex flex-col gap-3">
          <h1 className="font-display text-[31px] font-medium leading-[1.3] text-ink text-balance">
            候选主题
          </h1>
          <p className="break-all font-mono text-[11px] text-ink-3">project_id · {id}</p>
          <p className="max-w-[42em] text-[14px] leading-[1.8] text-ink-2">
            combo 关联假设生成的候选主题。选中态直取后端{" "}
            <code className="text-[13px] text-ink">chosen_topic_id</code>，前端不自行推断；
            标「推测」的主题未经证据对齐，界面对其降权并不提供溯源入口。
          </p>
        </header>

        {error !== null ? (
          <ApiErrorNotice error={error} what={`项目 ${id} 的主题列表`} />
        ) : data !== null && data.topics.length === 0 ? (
          // 空态：未知 project 也走这里（后端回空数组而非 404）。NEVER 渲染成错误。
          <div className="gap-cut flex min-h-40 flex-col items-center justify-center gap-2 rounded-[4px] px-6 py-12">
            <p className="font-display text-[20px] text-ink-2">该项目暂无候选主题</p>
            <p className="max-w-[32em] text-center text-[13px] leading-relaxed text-ink-3">
              后端 <span className="font-mono">topics</span> 为空数组（HTTP 200）。
              未知 project 也走这条路径——这是真实空态，不是 404、不是错误。
              主题由 <span className="font-mono">POST /projects/combo</span> 生成。
            </p>
            <Link
              href="/combo/new"
              className="mt-3 border border-rule px-4 py-2 font-mono text-[12px] text-ink-2 hover:border-rail"
              style={{ borderRadius: "var(--radius)" }}
            >
              去 combo 入口
            </Link>
          </div>
        ) : data !== null ? (
          <>
            <p className="mb-4 font-mono text-[11px] text-ink-3">
              topics · {data.topics.length} 条
              {" · chosen_topic_id · "}
              {data.chosen_topic_id ?? "null（尚未选主题）"}
              {specCount > 0 ? ` · 其中 ${specCount} 条为推测态` : " · 无推测态主题"}
            </p>
            <div className="flex flex-col gap-4">
              {data.topics.map((t) => (
                <TopicRow
                  key={t.topic_id}
                  topic={t}
                  chosen={t.topic_id === data.chosen_topic_id}
                  projectId={id}
                />
              ))}
            </div>
          </>
        ) : null}
      </main>
    </AppShell>
  );
}
