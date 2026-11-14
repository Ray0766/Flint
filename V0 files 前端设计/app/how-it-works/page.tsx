import type { Metadata } from "next"
import Link from "next/link"
import { ThemeToggle } from "@/components/theme-toggle"

/* ============================================================
   它怎么工作 · /how-it-works

   由首页迁入（首页原 4100px 过长）：13 步用户旅程 + 本站元素→后端字段对照表。
   这一页是**现状清单**，不是营销页：每步标真实现状（已挂载 / 未挂载 / 接口预留），
   NEVER 把未建的说成已建。视觉走功能屏语言（实用配色，无 glow）。
   ============================================================ */

export const metadata: Metadata = {
  title: "它怎么工作 · Flint",
  description: "13 步用户旅程与每步对应的真实端点、当前挂载现状。",
}

const DATA_LAYERS = [
  {
    tier: "01",
    name: "日更采集层",
    grit: "最粗粝",
    reads: "广场 / 工作台读这层",
    entities: ["Cluster 热点簇", "HeatPoint 单源单日热度", "EvidenceCard 证据卡"],
  },
  {
    tier: "02",
    name: "主题层",
    grit: "半成形",
    reads: "combo 关联假设 → 候选主题",
    entities: [
      "Origin 入口（combo 是其一种）",
      "TopicSeed 种子 · 带 hypothesis",
      "Topic 候选主题 · 带 why_now",
      "Project 项目容器",
    ],
  },
  {
    tier: "03",
    name: "产物层",
    grit: "最完成",
    reads: "报告 / 计划书 / 导出读这层",
    entities: [
      "Job 作业",
      "VerdictResult Gate 裁决",
      "Deliverable 报告 / 计划书 / vibe_pack",
      "Block 树 结构化正文 · 唯一真相",
      "FactsLedger 跨产物事实账本",
    ],
  },
] as const

const BY_SOURCE = [
  { source_id: "arxiv", value: "88.0", color: "var(--src-arxiv)" },
  { source_id: "ghtrend", value: "41.2", color: "var(--src-github)" },
  { source_id: "gtrends", value: "30.5", color: "var(--src-trends)" },
  { source_id: "weibo", value: "22.0", color: "var(--src-weibo)" },
] as const

type StatusKey = "mounted" | "unmounted" | "reserved"

const JOURNEY: {
  n: string
  step: string
  action: string
  endpoint: string
  status: StatusKey
  note?: string
  fork?: string
}[] = [
  { n: "01", step: "热点广场", action: "看当日热点主榜 + 弱信号早期轨", endpoint: "GET /plaza/hot?day=", status: "mounted" },
  { n: "02", step: "点簇进工作台", action: "点一个簇看它的证据卡", endpoint: "GET /clusters/{id}/evidence-cards", status: "mounted" },
  { n: "03", step: "combo 关联假设", action: "跨簇选卡 2~5 张 + 写一句关联假设 → 建项目、生成 N 主题", endpoint: "POST /projects/combo", status: "mounted", fork: "关联假设入口" },
  { n: "04", step: "主题列表 + 选主题", action: "看候选主题、选一个", endpoint: "GET /projects/{id}/topics", status: "mounted" },
  { n: "05", step: "发起分析", action: "对选中主题发起 Gate① 分析", endpoint: "POST /projects/{id}/analysis", status: "mounted" },
  { n: "06", step: "看分析进度", action: "实时看 job 进度（SSE）", endpoint: "GET /jobs/{id}/events", status: "mounted", note: "进度已建，内容渐进 stub" },
  { n: "07", step: "Gate 四分类结果", action: "看 A/B/C/D 判定 + 引用 + 竞品 + 缺口", endpoint: "GET /jobs/{id}/verdict", status: "mounted" },
  { n: "08", step: "生成报告", action: "用分析结果组稿深度报告", endpoint: "POST /projects/{id}/report", status: "unmounted", note: "demo 后端刻意不挂：无 report worker，挂了只会造出永远 queued 的假连通" },
  { n: "09", step: "看报告（L0 渲染）", action: "看结构化 Block 树报告", endpoint: "GET /deliverables/{id}/blocks", status: "mounted" },
  { n: "10", step: "指令改 / 干预（L2）", action: "锁定 / 章节再生成 / 块级重生成 / 争议 / 补证据", endpoint: "POST /interventions/…", status: "unmounted" },
  { n: "11", step: "生成计划书（受众分叉）", action: "单选：human_reader（五模板）/ ai_executor（vibe_pack）", endpoint: "POST /projects/{id}/proposal", status: "reserved", note: "端点已建 · 前端选择器未建", fork: "受众分叉入口" },
  { n: "12", step: "导出", action: "markdown / html / pdf / docx / vibe_pack zip", endpoint: "GET /deliverables/{id}/render?fmt=", status: "mounted", note: "pdf 需 GTK · pack 需 builder，两者如实回 503" },
  { n: "13", step: "支付", action: "免费额度 + 按次", endpoint: "—", status: "reserved", note: "仅 billing_enabled=False flag" },
]

const STATUS_META: Record<StatusKey, { label: string; className: string }> = {
  mounted: { label: "已建·已挂载", className: "border-ink bg-ink text-primary-foreground" },
  unmounted: { label: "已建·未挂载", className: "border-ink-2 text-ink-2" },
  reserved: { label: "未建·接口预留", className: "border-dashed border-rail text-ink-3" },
}

export default function HowItWorksPage() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <header className="border-b border-rule">
        <div className="mx-auto flex max-w-[1180px] items-center justify-between gap-4 px-6 py-5">
          <Link href="/" className="font-display text-[22px] text-ink">
            Flint 燧石
          </Link>
          <div className="flex items-center gap-5">
            <Link href="/" className="text-[14px] text-ink-2 transition-colors hover:text-ink">
              返回首页
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1180px] px-6 py-16">
        <h1 className="font-display text-[34px] font-medium leading-[1.25] text-ink text-balance md:text-[44px]">
          它怎么工作
        </h1>
        <p className="mt-5 max-w-[36em] text-[16px] leading-[1.8] text-ink-2">
          下面是从热点到导出的完整 13 步，每步标出它真正调用的端点，以及此刻的挂载现状。
          标「未挂载」「接口预留」的就是还没建好的——这一页不替产品把话说满。
        </p>
      </div>

      {/* ============ 三层数据 ============ */}
      <section className="border-t border-rule">
        <div className="mx-auto max-w-[1180px] px-6 py-14">
          <header className="mb-8 flex flex-wrap items-baseline justify-between gap-4">
            <h2 className="font-display text-[26px] font-medium text-ink">三个层次的数据</h2>
            <span className="font-mono text-[11px] text-ink-3">采集 · 粗粝 → 产物 · 完成</span>
          </header>

          <div className="grid gap-5 md:grid-cols-3">
            {DATA_LAYERS.map((layer) => (
              <div
                key={layer.tier}
                className="flex flex-col border border-rule bg-surface p-6"
                style={{ borderRadius: "var(--radius-card)" }}
              >
                <div className="flex items-center gap-3">
                  <span className="font-mono text-[12px] text-ink-3">{layer.tier}</span>
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-3">
                    {layer.grit}
                  </span>
                </div>
                <h3 className="mt-2.5 font-display text-[21px] font-medium text-ink">{layer.name}</h3>
                <p className="mt-2 text-[13px] leading-[1.7] text-ink-3">{layer.reads}</p>
                <ul className="mt-5 flex flex-col gap-2">
                  {layer.entities.map((e) => (
                    <li
                      key={e}
                      className="border border-rule bg-raised px-3 py-2 font-mono text-[12px] leading-[1.5] text-ink-2"
                      style={{ borderRadius: "var(--radius)" }}
                    >
                      {e}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          {/* 采集层读数：唯一放数字处，全标出处 */}
          <div
            className="mt-5 border border-rule bg-surface p-6"
            style={{ borderRadius: "var(--radius-card)" }}
          >
            <div className="mb-5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="text-[14px] font-medium text-ink-2">样例响应 · by_source 四源分值</span>
              <code className="text-[11px] text-ink-3">
                GET /plaza/hot?day=2026-07-04 · cluster c-20260704-000
              </code>
            </div>

            <div className="grid gap-x-8 gap-y-3 sm:grid-cols-2 lg:grid-cols-4">
              {BY_SOURCE.map((s) => (
                <div key={s.source_id} className="flex items-center gap-3">
                  <span
                    aria-hidden
                    className="inline-block h-2 w-2 shrink-0 rounded-[1px]"
                    style={{ backgroundColor: s.color }}
                  />
                  <code className="w-[68px] text-[12px] text-ink-2">{s.source_id}</code>
                  <span className="tabular text-[16px] text-ink">{s.value}</span>
                </div>
              ))}
            </div>

            <div className="mt-7 flex flex-wrap gap-x-12 gap-y-4 border-t border-rule pt-5">
              {[
                { v: "87.75", k: "hotness" },
                { v: "159.7", k: "total_heat" },
                { v: "3", k: "hotness_components.cross_count" },
                { v: "1", k: "当日簇数 · clusters.length" },
              ].map((m) => (
                <div key={m.k} className="flex flex-col">
                  <span className="tabular text-[22px] text-ink">{m.v}</span>
                  <code className="mt-1 text-[11px] text-ink-3">{m.k}</code>
                </div>
              ))}
            </div>

            <p className="mt-5 text-[11px] leading-[1.6] text-ink-3">
              以上数值逐字取自说明书 §2.1 样例响应，非实时统计。排序由后端定，前端零计算不重排；
              源色仅作类别识别，方形源印面积恒定，不表强弱。
            </p>
          </div>
        </div>
      </section>

      {/* ============ 13 步旅程 ============ */}
      <section className="border-t border-rule">
        <div className="mx-auto max-w-[1180px] px-6 py-14">
          <header className="mb-8 flex flex-wrap items-baseline justify-between gap-4">
            <h2 className="font-display text-[26px] font-medium text-ink">核心用户旅程 · 13 步</h2>
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 font-mono text-[10px] uppercase tracking-[0.12em]">
              <span className="flex items-center gap-2 text-ink">
                <span className="inline-block h-2.5 w-2.5 bg-ink" aria-hidden /> 已建·已挂载
              </span>
              <span className="flex items-center gap-2 text-ink-2">
                <span className="inline-block h-2.5 w-2.5 border border-ink-2" aria-hidden /> 已建·未挂载
              </span>
              <span className="flex items-center gap-2 text-ink-3">
                <span className="inline-block h-2.5 w-2.5 border border-dashed border-rail" aria-hidden />{" "}
                未建·接口预留
              </span>
            </div>
          </header>

          <ol
            className="overflow-hidden border border-rule bg-surface"
            style={{ borderRadius: "var(--radius-card)" }}
          >
            {JOURNEY.map((s) => {
              const meta = STATUS_META[s.status]
              return (
                <li key={s.n} className="border-b border-rule last:border-b-0">
                  <div className="grid grid-cols-[auto_1fr] gap-x-5 px-5 py-5 md:grid-cols-[auto_1fr_auto] md:gap-x-8 md:px-8">
                    <div className="flex flex-col items-start">
                      <span className="tabular text-[20px] leading-none text-ink">{s.n}</span>
                      {s.fork ? (
                        <span className="mt-2 inline-flex items-center gap-1 rounded-[4px] border border-rail px-1.5 py-0.5 font-mono text-[10px] text-ink-3">
                          ⋔ 分叉
                        </span>
                      ) : null}
                    </div>

                    <div className="min-w-0">
                      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                        <h3 className="text-[16px] font-medium text-ink">{s.step}</h3>
                        {s.fork ? <span className="text-[12px] text-ink-3">分叉点 · {s.fork}</span> : null}
                      </div>
                      <p className="mt-1.5 text-[13px] leading-[1.7] text-ink-2">{s.action}</p>
                      <code className="mt-2 block break-all text-[11px] text-ink-3">{s.endpoint}</code>
                      {s.note ? <p className="mt-1 text-[11px] leading-[1.6] text-ink-3">— {s.note}</p> : null}
                    </div>

                    <div className="col-span-2 mt-2 md:col-span-1 md:mt-0 md:self-start">
                      <span
                        className={[
                          "inline-flex whitespace-nowrap rounded-[4px] border px-2.5 py-1 font-mono text-[10px]",
                          meta.className,
                        ].join(" ")}
                      >
                        {meta.label}
                      </span>
                    </div>
                  </div>
                </li>
              )
            })}
          </ol>
        </div>
      </section>

      {/* ============ 字段对照 ============ */}
      <section className="border-t border-rule bg-raised">
        <div className="mx-auto max-w-[1180px] px-6 py-12">
          <h2 className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-3">
            本站元素 → 后端字段对照
          </h2>
          <div className="mt-6 grid gap-x-10 gap-y-4 text-[12px] leading-[1.7] md:grid-cols-2">
            <p className="text-ink-2">
              首页 hero 判定卡 <code className="text-ink">verdict / gaps[] / competitors[] /
              key_citation_ids / rationale_fact_ids</code> → 录制回放真跑产出{" "}
              <code className="text-ink">snap-job-gate1-live-qwen-verdict</code>（非实时）
            </p>
            <p className="text-ink-2">
              <code className="text-ink">by_source</code> 四源分值（arxiv 88.0 / ghtrend 41.2 / gtrends
              30.5 / weibo 22.0）→ 逐源方形源印 · <code className="text-ink">GET /plaza/hot</code> §2.1
            </p>
            <p className="text-ink-2">
              <code className="text-ink">hotness</code> 87.75 · <code className="text-ink">total_heat</code>{" "}
              159.7 · <code className="text-ink">hotness_components.cross_count</code> 3 → 采集层等宽读数
            </p>
            <p className="text-ink-2">
              三层实体 <code className="text-ink">Cluster / Origin / TopicSeed / Topic / Job /
              Deliverable / Block 树 / FactsLedger</code> → §一「三个层次的数据」
            </p>
            <p className="text-ink-2">
              13 步 <code className="text-ink">step / 主端点 / 现状</code> → §一「核心用户旅程」表格逐字
            </p>
            <p className="text-ink-2">
              分叉点 step 03 <code className="text-ink">POST /projects/combo</code> · step 11{" "}
              <code className="text-ink">POST /projects/{"{id}"}/proposal</code> → §一两个分叉点
            </p>
          </div>
          <p className="mt-8 text-[11px] leading-[1.6] text-ink-3">
            全页无任何无出处统计数；告警色 spark 在本页零出现——它只属于 blocking / 409 / 503。
          </p>
        </div>
      </section>
    </main>
  )
}
