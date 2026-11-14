// P14 项目总览 · /projects/[id]
//
// **无专属端点**（清单 A 组第 7 条）：本屏由三个已挂端点**组合**而成，
// 屏上必须写清由哪几支组合、哪些是设计决策，NEVER 让人以为存在一个 /projects/{id} 的总览端点。
//   · GET /projects/{id}/topics        —— 主题层（真实）
//   · GET /jobs/{job_id}               —— 作业（**需要 job_id 才能查，本屏没有列表端点**）
//   · GET /deliverables/{id}           —— 交付物（同上，需要 id）
//
// 诚实边界：后端**没有**「按 project 列 jobs / deliverables」的端点。
// 所以本屏的作业区与交付物区**不列举**，只提供按 id 直达的入口 +
// 如实说明缺的是哪一支端点。NEVER 假装列出了这个项目的全部作业。
//
// R1 账户 / R2 额度 / R3 质量卡 / R4 陈旧横幅：端点全未建 → UnbuiltEndpoint 明示。
import type { Metadata } from "next";
import Link from "next/link";
import { fetchCategories, fetchProjectTopics } from "@/lib/api";
import type { Category, TopicsResponse } from "@/lib/types";
import { AppShell } from "@/components/shell/app-shell";
import { ApiErrorNotice } from "@/components/honesty/api-error";
import { UnbuiltEndpoint } from "@/components/honesty/unbuilt-endpoint";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "项目总览 · Flint",
  description: "由 topics / jobs / deliverables 三支端点组合而成——无专属总览端点。",
};

export default async function ProjectOverviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let topics: TopicsResponse | null = null;
  let error: unknown = null;
  try {
    topics = await fetchProjectTopics(id);
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
      endpoint={`组合屏 · GET /projects/${id}/topics ＋ /jobs/{id} ＋ /deliverables/{id}`}
      categories={categories}
      categoriesError={categoriesError}
    >
      <main className="mx-auto max-w-[1180px] px-5 py-10">
        <header className="mb-8 flex flex-col gap-3">
          <h1 className="font-display text-[31px] font-medium leading-[1.3] text-ink text-balance">
            项目总览
          </h1>
          <p className="break-all font-mono text-[11px] text-ink-3">project_id · {id}</p>
          <div
            className="max-w-[46em] border border-dashed border-rail bg-raised px-5 py-4"
            style={{ borderRadius: "var(--radius-card)" }}
          >
            <p className="font-mono text-[11px] text-ink-2">这一屏没有专属端点（设计决策）</p>
            <p className="mt-2 text-[13px] leading-[1.75] text-ink-2">
              它由三支已挂端点组合而成：
              <span className="font-mono"> GET /projects/{id}/topics</span>（真实列表）、
              <span className="font-mono"> GET /jobs/&#123;job_id&#125;</span> 与
              <span className="font-mono"> GET /deliverables/&#123;id&#125;</span>
              （按 id 单查）。后端没有「按 project 列 jobs / deliverables」的端点，
              所以下面两区不列举、只给直达入口——界面不假装知道这个项目有哪些作业。
            </p>
          </div>
        </header>

        <div className="flex flex-col gap-6">
          {/* 主题区：真实数据 */}
          <section
            className="border border-rule bg-surface p-5"
            style={{ borderRadius: "var(--radius-card)" }}
          >
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <h2 className="text-[14px] font-medium text-ink">主题 · 真实数据</h2>
              <code className="text-[11px] text-ink-3">GET /projects/{id}/topics</code>
            </div>
            {error !== null ? (
              <div className="mt-4">
                <ApiErrorNotice error={error} what={`项目 ${id} 的主题`} />
              </div>
            ) : topics === null ? null : topics.topics.length === 0 ? (
              <p className="mt-3 text-[13px] leading-[1.7] text-ink-3">
                topics 为空数组（HTTP 200）。未知 project 也走这条路径——真实空态，非 404、非错误。
              </p>
            ) : (
              <>
                <p className="mt-2 font-mono text-[11px] text-ink-3">
                  {topics.topics.length} 条 · chosen_topic_id ·{" "}
                  {topics.chosen_topic_id ?? "null（尚未选主题）"}
                </p>
                <ul className="mt-3 flex flex-col gap-1.5">
                  {topics.topics.map((t) => (
                    <li key={t.topic_id}>
                      <Link
                        href={`/topics/${encodeURIComponent(t.topic_id)}?project_id=${encodeURIComponent(id)}`}
                        className="text-[13px] leading-[1.6] text-ink-2 underline-offset-4 hover:text-ink hover:underline"
                      >
                        {t.one_liner}
                      </Link>
                    </li>
                  ))}
                </ul>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Link
                    href={`/projects/${encodeURIComponent(id)}/topics`}
                    className="border border-rule px-3 py-1.5 font-mono text-[11px] text-ink-2 hover:border-rail"
                    style={{ borderRadius: "var(--radius)" }}
                  >
                    主题列表
                  </Link>
                  <Link
                    href={`/projects/${encodeURIComponent(id)}/analysis/new`}
                    className="border border-rule px-3 py-1.5 font-mono text-[11px] text-ink-2 hover:border-rail"
                    style={{ borderRadius: "var(--radius)" }}
                  >
                    发起分析
                  </Link>
                  <Link
                    href={`/projects/${encodeURIComponent(id)}/proposal`}
                    className="border border-rule px-3 py-1.5 font-mono text-[11px] text-ink-2 hover:border-rail"
                    style={{ borderRadius: "var(--radius)" }}
                  >
                    受众分叉
                  </Link>
                </div>
              </>
            )}
          </section>

          {/* 作业区：无列表端点 → 只给按 id 直达 */}
          <section
            className="border border-rule bg-surface p-5"
            style={{ borderRadius: "var(--radius-card)" }}
          >
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <h2 className="text-[14px] font-medium text-ink">作业 · 按 id 直达</h2>
              <code className="text-[11px] text-ink-3">GET /jobs/&#123;job_id&#125;</code>
            </div>
            <p className="mt-2 max-w-[42em] text-[13px] leading-[1.7] text-ink-2">
              后端只提供按 job_id 单查，
              <strong className="font-medium text-ink">没有「列出本项目全部作业」的端点</strong>。
              所以这里不列举——列出来就得由前端猜或缓存，那两条路都会造出不真的东西。
            </p>
            <p className="mt-3 font-mono text-[11px] leading-[1.7] text-ink-3">
              已知 job_id 时直接访问 /gate/&#123;job_id&#125;。
              这里不放输入框——一个提交后不知道去哪的框，就是看起来能用的假功能。
            </p>
          </section>

          {/* 交付物区：同上 */}
          <section
            className="border border-rule bg-surface p-5"
            style={{ borderRadius: "var(--radius-card)" }}
          >
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <h2 className="text-[14px] font-medium text-ink">交付物 · 按 id 直达</h2>
              <code className="text-[11px] text-ink-3">GET /deliverables/&#123;id&#125;</code>
            </div>
            <p className="mt-2 max-w-[42em] text-[13px] leading-[1.7] text-ink-2">
              同样只有按 id 单查，没有按 project 列举的端点。已知 deliverable_id 时可直接进
              只读报告 / 可干预页 / 导出面板。
            </p>
          </section>

          {/* R1~R4：端点全未建（清单 32） */}
          <h2 className="mt-2 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-3">
            预留位 · R1 / R2 / R3 / R4（端点全未建）
          </h2>

          <UnbuiltEndpoint
            title="R1 账户"
            endpoint="GET /me（未建）· 现状：X-User-Id 由 demo 中间件注入 demo-user"
            why="没有账户端点，也没有登录态。顶栏的用户位显示的是真实生效的 X-User-Id 常量，旁边已标「账户端点未建」——那是占位，不是一个能点开的账户菜单。"
          />

          <UnbuiltEndpoint
            title="R2 额度"
            endpoint="GET /quota（未建）· 现状：flint/config.py 的 billing_enabled = False"
            why="计费与额度在 M5 前恒关：DEFAULT_FLAGS 里 billing_enabled 写死 False。没有额度端点，也没有任何余额/用量数字可显——这里不画进度条、不显百分比，因为后端没有这类值。"
          />

          <UnbuiltEndpoint
            title="R3 质量卡"
            endpoint="GET /quality-cards/{card_ref}（未建）"
            why="报告里的 quality_card 块只带 card_ref。解引用端点没建，所以那里只显引用位并写明「NEVER 前端代算覆盖率/对齐率」——本屏同理，不给任何质量分。"
          />

          <UnbuiltEndpoint
            title="R4 陈旧横幅"
            endpoint="Revalidator 的 stale 判定读端点（未建）"
            why="「这份产物是否已过期」由后端 Revalidator 的统一 stale 口径决定。没有读端点就无从显示——界面不自己按时间戳推断新鲜度，那是前端替后端判定。"
          />
        </div>
      </main>
    </AppShell>
  );
}
