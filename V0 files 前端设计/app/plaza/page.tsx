// P1 热点广场 · GET /plaza/hot?day=YYYY-MM-DD —— 真后端读。
//
// 铁律落到本屏（批次一字段对照表）：
// - **主榜行序 = clusters[] 返回顺序**（后端 compute_hotness 已排）。前端零重排、**无排序控件**。
// - **by_source 四源各自独立一列**，NEVER 合成一个数、NEVER 堆叠图。
//   后端只回当日实际有热度点的源 → 缺的源如实标「该源当日无数据」，**NEVER 补 0**。
// - **weak_signals 单列一轨**，与主榜分开，NEVER 并入综合分。
// - 大类筛选**仅隐藏行**：rank 号沿用后端次序里的原始位次，隐藏后不重编号。
// - day 非法 → 后端 400 VALIDATION_FAILED，如实抬起并给可点的修正路径（NEVER 前端预判格式）。
// - clusters 与 weak_signals 均空 → 「该日无热点」空态，NEVER 渲染成错误。
//
// 视觉：数据屏语言（双主题语义 token）。NEVER glow、NEVER --sulfur。
import type { Metadata } from "next";
import Link from "next/link";
import { fetchPlazaHot, fetchCategories, FlintApiError } from "@/lib/api";
import type { Category, PlazaCluster, PlazaHotResponse, SourceKey, WeakSignal } from "@/lib/types";
import { AppShell } from "@/components/shell/app-shell";
import { ApiErrorNotice } from "@/components/honesty/api-error";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "热点广场 · Flint",
  description: "GET /plaza/hot?day= — 四源日更热点，排序由后端给定，前端零重排。",
};

// demo 数据最全的一天（与 start-demo.ps1 同口径）。仅作 ?day= 缺省值，不参与任何计算。
const DEFAULT_DAY = "2026-07-04";

// 四源列顺序固定（仅为表头稳定，非按分值排序）
const SOURCE_COLS: SourceKey[] = ["gtrends", "weibo", "ghtrend", "arxiv"];

const COMPONENT_LABEL: Record<string, string> = {
  velocity: "velocity · 速度",
  accel: "accel · 加速度",
  cross_count: "cross_count · 跨源计数",
  multi_boost: "multi_boost · 多源加成",
  novelty_factor: "novelty_factor · 新颖因子",
  decay: "decay · 衰减",
};

function SourceCell({ score }: { score: number | undefined }) {
  if (score === undefined) {
    // 缺源：如实标注，NEVER 补 0（0 是「测到了但为零」，缺失是「当日没测到」，两回事）
    return (
      <span className="inline-flex items-center gap-1.5">
        <span
          className="inline-block h-2 w-2 shrink-0 rounded-[1px] border border-dashed border-rail"
          aria-hidden
        />
        <span className="font-mono text-[11px] text-ink-3">该源当日无数据</span>
      </span>
    );
  }
  return <span className="tabular font-mono text-[13px] text-ink">{score}</span>;
}

// 一簇一行：桌面成表、窄屏堆叠成卡（同一份 DOM，靠 display 切换，NEVER 横向滚动硬挤）
function ClusterRow({ cluster, rank }: { cluster: PlazaCluster; rank: number }) {
  return (
    // 用 details/summary 而非真 <table>：行要能就地展开 hotness_components，
    // 而 <tr> 上无法承载展开态；列对齐由 flex/grid 承担，语义不受损。
    <details className="group block border-b border-rule last:border-b-0">
      <summary className="flex cursor-pointer list-none flex-col gap-2 px-4 py-3 hover:bg-raised md:flex-row md:items-center md:gap-4">
        <span className="tabular w-8 shrink-0 font-mono text-[12px] text-ink-3">{rank}</span>

        <span className="min-w-0 flex-1 md:max-w-[26%]">
          <Link
            href={`/clusters/${encodeURIComponent(cluster.cluster_id)}`}
            className="text-[15px] font-medium leading-[1.4] text-ink underline-offset-4 hover:underline"
          >
            {cluster.canonical_name}
          </Link>
          <span className="mt-0.5 block break-all font-mono text-[10px] text-ink-3">
            {cluster.cluster_id} · {cluster.category_id} · status {cluster.status}
          </span>
        </span>

        {/* 四源各自独立一列，互不合成 */}
        <span className="grid flex-1 grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-4">
          {SOURCE_COLS.map((s) => (
            <span key={s} className="flex flex-col gap-0.5">
              <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3 md:hidden">
                {s}
              </span>
              <SourceCell score={cluster.by_source[s]} />
            </span>
          ))}
        </span>

        <span className="flex shrink-0 items-baseline gap-2 md:w-[7rem] md:justify-end">
          <span className="font-mono text-[10px] text-ink-3 md:hidden">hotness</span>
          <span className="tabular text-[17px] font-medium text-ink">{cluster.hotness}</span>
          <span className="font-mono text-[11px] text-ink-3 transition-transform group-open:rotate-90" aria-hidden>
            ›
          </span>
        </span>
      </summary>

      {/* 展开：hotness_components 各分量独立列出 + total_heat，NEVER 合成显示 */}
      <div className="border-t border-rule bg-raised px-4 py-4">
        <p className="mb-3 font-mono text-[10px] text-ink-3">
          hotness_components（后端分解 · 各分量独立 · 前端零计算）
        </p>
        <dl className="grid grid-cols-1 gap-x-8 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(cluster.hotness_components).map(([k, v]) => (
            <div key={k} className="flex items-baseline justify-between gap-3 border-b border-rule/60 pb-1">
              <dt className="font-mono text-[11px] text-ink-3">{COMPONENT_LABEL[k] ?? k}</dt>
              <dd className="tabular font-mono text-[12px] text-ink">{v}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 font-mono text-[11px] text-ink-3">
          total_heat · <span className="tabular text-ink-2">{cluster.total_heat}</span>
        </p>
      </div>
    </details>
  );
}

function WeakSignalRow({ signal }: { signal: WeakSignal }) {
  const fields: [string, number | string][] = [
    ["weak_score", signal.weak_score],
    ["agg", signal.agg],
    ["velocity", signal.velocity],
    ["drift", signal.drift],
    ["burst_weight", signal.burst_weight],
  ];
  return (
    <li className="border-b border-rule px-4 py-3 last:border-b-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <Link
          href={`/clusters/${encodeURIComponent(signal.cluster_id)}`}
          className="text-[14px] font-medium text-ink underline-offset-4 hover:underline"
        >
          {signal.canonical_name}
        </Link>
        <span className="break-all font-mono text-[10px] text-ink-3">
          {signal.cluster_id} · {signal.category_id} · status {signal.status}
        </span>
      </div>
      <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1">
        {fields.map(([k, v]) => (
          <div key={k} className="flex items-baseline gap-1.5">
            <dt className="font-mono text-[10px] text-ink-3">{k}</dt>
            <dd className="tabular font-mono text-[12px] text-ink">{v}</dd>
          </div>
        ))}
      </dl>
    </li>
  );
}

export default async function PlazaPage({
  searchParams,
}: {
  searchParams: Promise<{ day?: string; cat?: string }>;
}) {
  const { day: dayParam, cat } = await searchParams;
  const day = dayParam ?? DEFAULT_DAY;

  let data: PlazaHotResponse | null = null;
  let error: unknown = null;
  try {
    data = await fetchPlazaHot(day);
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

  const endpoint = `GET /plaza/hot?day=${day}${cat !== undefined ? `  ·  前端筛选 cat=${cat}（仅隐藏行，不重排）` : ""}`;

  // 筛选：只隐藏，不重排。rank 取**后端原序**里的位次，隐藏后不重编号。
  const ranked = (data?.clusters ?? []).map((c, i) => ({ c, rank: i + 1 }));
  const shownClusters =
    cat === undefined ? ranked : ranked.filter((r) => r.c.category_id === cat);
  const allWeak = data?.weak_signals ?? [];
  const shownWeak = cat === undefined ? allWeak : allWeak.filter((w) => w.category_id === cat);

  const dayEmpty =
    data !== null && data.clusters.length === 0 && data.weak_signals.length === 0;
  const is400 = error instanceof FlintApiError && error.status === 400;

  return (
    <AppShell
      active="/plaza"
      endpoint={endpoint}
      categories={categories}
      categoriesError={categoriesError}
    >
      <main className="mx-auto max-w-[1180px] px-5 py-10">
        <header className="mb-8 flex flex-col gap-3">
          <h1 className="font-display text-[31px] font-medium leading-[1.3] text-ink text-balance">
            热点广场
          </h1>
          <p className="max-w-[42em] text-[14px] leading-[1.8] text-ink-2">
            当日四源热点。排序由后端 <code className="text-[13px] text-ink">compute_hotness</code>{" "}
            给定，前端零重排、无排序控件；四源分值各自独立呈现，NEVER 合成一个数；
            弱信号单列一轨，NEVER 并入综合分。
          </p>
          <p className="font-mono text-[11px] text-ink-3">
            换日期：地址后加 <span className="text-ink-2">?day=YYYY-MM-DD</span>
          </p>
        </header>

        {/* 400：说清发生了什么 + 怎么办 + 给一条可点的修正路径 */}
        {is400 ? (
          <div
            className="border border-rule bg-surface px-5 py-4"
            style={{ borderRadius: "var(--radius-card)" }}
            role="alert"
          >
            <p className="font-mono text-[12px] text-ink">
              HTTP 400 · {(error as FlintApiError).code}
            </p>
            <p className="mt-2 max-w-[42em] text-[13px] leading-[1.7] text-ink-2">
              发生了什么：day 参数「{day}」不是 YYYY-MM-DD 格式，后端拒绝了请求。
              <br />
              怎么办：修正日期格式后重新查询；也可以直接改查样例日。
            </p>
            <Link
              href={`/plaza?day=${DEFAULT_DAY}`}
              className="mt-4 inline-flex border border-ink bg-ink px-4 py-2 font-mono text-[12px] text-primary-foreground"
              style={{ borderRadius: "var(--radius)" }}
            >
              改查 {DEFAULT_DAY}
            </Link>
          </div>
        ) : error !== null ? (
          <ApiErrorNotice error={error} what={`热点广场 ${day}`} />
        ) : dayEmpty ? (
          <div className="gap-cut flex min-h-40 flex-col items-center justify-center gap-2 rounded-[4px] px-6 py-12">
            <p className="font-display text-[20px] text-ink-2">该日无热点</p>
            <p className="max-w-[28em] text-center text-[13px] leading-relaxed text-ink-3">
              后端 clusters 与 weak_signals 均为空数组。这是 {data?.day} 的真实空态，非加载中、非错误。
            </p>
          </div>
        ) : data !== null ? (
          <div className="flex flex-col gap-10">
            {/* 主榜 */}
            <section
              className="overflow-hidden border border-rule bg-surface"
              style={{ borderRadius: "var(--radius-card)" }}
            >
              <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-rule px-4 py-3">
                <h2 className="text-[14px] font-medium text-ink">
                  主榜 clusters · 按 hotness 综合分（后端已排）
                </h2>
                <p className="font-mono text-[11px] text-ink-3">
                  day {data.day} · 共 {data.clusters.length} 簇
                  {cat !== undefined ? ` · 本大类显示 ${shownClusters.length} 行` : ""}
                </p>
              </header>

              {/* 桌面表头（窄屏每格自带列名） */}
              <div className="hidden items-center gap-4 border-b border-rule px-4 py-2 md:flex">
                <span className="w-8 shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">#</span>
                <span className="min-w-0 flex-1 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3 md:max-w-[26%]">
                  簇 CLUSTER
                </span>
                <span className="grid flex-1 grid-cols-4 gap-x-4">
                  {SOURCE_COLS.map((s) => (
                    <span key={s} className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
                      {s}
                    </span>
                  ))}
                </span>
                <span className="w-[7rem] shrink-0 text-right font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
                  HOTNESS 综合
                </span>
              </div>

              {shownClusters.length === 0 ? (
                <p className="px-4 py-8 text-center text-[13px] text-ink-3">
                  该大类下无主榜簇。四源分值仍按簇独立呈现，不合成。
                </p>
              ) : (
                shownClusters.map(({ c, rank }) => (
                  <ClusterRow key={c.cluster_id} cluster={c} rank={rank} />
                ))
              )}
            </section>

            {/* 弱信号轨：单列一轨，与主榜分开 */}
            <section
              className="overflow-hidden border border-rule bg-surface"
              style={{ borderRadius: "var(--radius-card)" }}
            >
              <header className="border-b border-rule px-4 py-3">
                <h2 className="text-[14px] font-medium text-ink">弱信号轨 weak_signals</h2>
                <p className="mt-1 font-mono text-[11px] text-ink-3">
                  早期语义新趋势 · 单列一轨，与主榜分开，不并入综合分 · 共 {allWeak.length} 条
                </p>
              </header>
              {shownWeak.length === 0 ? (
                <p className="px-4 py-8 text-center text-[13px] text-ink-3">
                  {allWeak.length === 0 ? "该日无弱信号。" : "该大类下无弱信号。"}
                </p>
              ) : (
                <ul>
                  {shownWeak.map((w) => (
                    <WeakSignalRow key={w.cluster_id} signal={w} />
                  ))}
                </ul>
              )}
            </section>
          </div>
        ) : null}
      </main>
    </AppShell>
  );
}
