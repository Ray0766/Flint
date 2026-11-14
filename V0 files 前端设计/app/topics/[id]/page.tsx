// P5 主题详情 · GET /topics/{topic_id} —— 真后端读。
//
// 契约要点（views.py#topic_detail）：外层包 {topic: ...}；**未知 topic → 404 NOT_FOUND**
//   （与 project_topics 的空数组语义不同：单个资源不存在就是 404，此处照实走 404 屏）。
//
// 清单第 13 条：speculative 降权 + 抑制溯源入口（WhyNowPanel 承载）。
// 清单第 3 条：keyword_mapping 的值是关键词字符串本身（非 id），照实呈现；
//   evidences 的 citation_id 解引用端点未建 → 只显引用位并写明。
// 视觉：数据屏语言。NEVER glow、NEVER 硫磺。
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CircleDashed } from "lucide-react";
import { fetchCategories, fetchTopic } from "@/lib/api";
import type { Category, Topic } from "@/lib/types";
import { AppShell } from "@/components/shell/app-shell";
import { ApiErrorNotice } from "@/components/honesty/api-error";
import { WhyNowPanel } from "@/components/topic/why-now";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "主题详情 · Flint",
  description: "GET /topics/{id} — 主题的一句话、受众/形态标签、why_now 与关键词映射。",
};

function KeywordMapping({ topic }: { topic: Topic }) {
  const entries = Object.entries(topic.keyword_mapping);
  return (
    <section
      className="border border-rule bg-surface p-5"
      style={{ borderRadius: "var(--radius-card)" }}
    >
      <h2 className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-3">
        keyword_mapping · {entries.length} 组
      </h2>
      <p className="mt-2 text-[12px] leading-[1.7] text-ink-3">
        左侧为来源簇/卡的名目，右侧为该主题据以检索的关键词。发起分析时后端由此派生
        <span className="font-mono"> keywords</span>（前端不重排、不增删）。
      </p>
      {entries.length === 0 ? (
        <p className="mt-4 font-mono text-[11px] text-ink-3">keyword_mapping 为空对象。</p>
      ) : (
        <dl className="mt-4 flex flex-col gap-4">
          {entries.map(([src, kws]) => (
            <div key={src} className="border-t border-rule pt-3 first:border-t-0 first:pt-0">
              <dt className="text-[13px] font-medium text-ink">{src}</dt>
              <dd className="mt-2 flex flex-wrap gap-1.5">
                {kws.length === 0 ? (
                  <span className="font-mono text-[11px] text-ink-3">（该组无关键词）</span>
                ) : (
                  kws.map((k) => (
                    <span
                      key={k}
                      className="border border-rule px-2 py-0.5 font-mono text-[11px] text-ink-2"
                      style={{ borderRadius: "var(--radius)" }}
                    >
                      {k}
                    </span>
                  ))
                )}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}

export default async function TopicDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ project_id?: string }>;
}) {
  const { id } = await params;
  const { project_id: projectId } = await searchParams;

  let topic: Topic | null = null;
  let error: unknown = null;
  try {
    topic = await fetchTopic(id);
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

  // 未知 topic：后端 404 → fetchTopic 回 null → 走 404 屏（单资源不存在，不是空态）
  if (error === null && topic === null) notFound();

  const spec = topic?.why_now.speculative === true;

  return (
    <AppShell
      active="/plaza"
      endpoint={`GET /topics/${id}`}
      categories={categories}
      categoriesError={categoriesError}
    >
      <main className="mx-auto max-w-[900px] px-5 py-10">
        {projectId !== undefined ? (
          <Link
            href={`/projects/${encodeURIComponent(projectId)}/topics`}
            className="font-mono text-[11px] text-ink-2 hover:text-ink"
          >
            ← 候选主题
          </Link>
        ) : null}

        {error !== null ? (
          <div className="mt-4">
            <ApiErrorNotice error={error} what={`主题 ${id}`} />
          </div>
        ) : topic !== null ? (
          <>
            <header className="mt-4 flex flex-col gap-3">
              {spec ? (
                <span
                  className="inline-flex w-fit items-center gap-1.5 border border-dashed border-rail px-2.5 py-1 font-mono text-[11px] text-ink-3"
                  style={{ borderRadius: "var(--radius)" }}
                >
                  <CircleDashed className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />
                  推测态主题 · 未经证据对齐
                </span>
              ) : null}
              <h1
                className={`font-display text-[28px] font-medium leading-[1.35] text-balance md:text-[34px] ${
                  spec ? "text-ink-2" : "text-ink"
                }`}
              >
                {topic.one_liner}
              </h1>
              <p className="break-all font-mono text-[11px] text-ink-3">
                topic_id · {topic.topic_id} · seed_id · {topic.seed_id}
              </p>
              <div className="flex flex-wrap gap-2">
                <span
                  className="border border-rule px-2.5 py-1 font-mono text-[11px] text-ink-2"
                  style={{ borderRadius: "var(--radius)" }}
                >
                  target_user_tag · {topic.target_user_tag}
                </span>
                <span
                  className="border border-rule px-2.5 py-1 font-mono text-[11px] text-ink-2"
                  style={{ borderRadius: "var(--radius)" }}
                >
                  form_factor_tag · {topic.form_factor_tag}
                </span>
              </div>
            </header>

            <div className="mt-8 flex flex-col gap-5">
              <section>
                <h2 className="mb-3 font-mono text-[10px] uppercase tracking-[0.12em] text-ink-3">
                  why_now · 为什么是现在
                </h2>
                <WhyNowPanel why={topic.why_now} />
              </section>

              <KeywordMapping topic={topic} />
            </div>

            {projectId !== undefined ? (
              <div className="mt-8 flex flex-wrap items-center gap-3 border-t border-rule pt-6">
                <Link
                  href={`/projects/${encodeURIComponent(projectId)}/analysis/new?topic_id=${encodeURIComponent(topic.topic_id)}`}
                  className="border border-ink bg-ink px-4 py-2.5 font-mono text-[12px] text-primary-foreground"
                  style={{ borderRadius: "var(--radius)" }}
                >
                  对它发起 Gate① 分析 →
                </Link>
                <span className="font-mono text-[11px] text-ink-3">
                  POST /projects/{projectId}/analysis
                </span>
              </div>
            ) : (
              <p className="mt-8 border-t border-rule pt-6 font-mono text-[11px] leading-[1.7] text-ink-3">
                发起分析需要 project 上下文（POST /projects/&#123;id&#125;/analysis）。
                从候选主题列表进入本页时此处会出现发起入口；直接按 topic_id 访问时不显示——
                界面不替你猜该主题属于哪个 project。
              </p>
            )}
          </>
        ) : null}
      </main>
    </AppShell>
  );
}
