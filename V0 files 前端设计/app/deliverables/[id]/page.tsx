// 深度报告 L0（皇冠屏）· /deliverables/[id] —— 真后端
//   GET /deliverables/{id}         元信息（type/version/ledger_version/reproducible）
//   GET /deliverables/{id}/blocks  结构化 Block 树（L0 只读渲染器的读契约）
//   GET /deliverables/{id}/render  导出（下沉到 client 的 ReportShell 真打）
//
// 未生成 → 后端 404 → 如实显「尚未生成」，NEVER 退回 mock、NEVER 编造正文。
//
// 视觉：数据屏语言（日夜双主题，颜色全部走语义 token，本文件不写死任何颜色）——
// 底三阶 --base / --surface / --raised、1px 实线 --rule、4~6px 圆角。
// NEVER 用首页专属的 glow（渐变描边 / 光晕 / 40px 圆角，已圈在 .dark 作用域）；
// NEVER 用 --sulfur（黄底 CTA 只属营销屏，数据屏用它会稀释告警色的唯一性）。
import type { Metadata } from "next"
import { fetchBlocks, fetchDeliverableMeta } from "@/lib/api"
import type { BlocksResponse, DeliverableMeta } from "@/lib/types"
import { BlockRenderer } from "@/components/report/block-renderer"
import { ReportShell } from "@/components/report/report-shell"
import { ApiErrorNotice } from "@/components/honesty/api-error"

export const dynamic = "force-dynamic"

export const metadata: Metadata = {
  title: "深度报告 L0 · Flint",
  description: "带出处的报告卷宗：每个结论以引用为准，未引用处如实标注为推测或缺口。",
}

// 报告页头：交付物元信息逐字取自 GET /deliverables/{id}，等宽 + tabular-nums。
function ReportHeader({ id, meta }: { id: string; meta: DeliverableMeta | null }) {
  return (
    <header className="border-b border-rule">
      <div className="mx-auto max-w-5xl px-5 py-10">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <p className="font-mono text-[11px] text-ink-3">deliverable</p>
          <p className="tabular font-mono text-[11px] text-ink-2">{id}</p>
        </div>
        <h1 className="mt-3 font-display text-[31px] font-medium leading-[1.3] text-ink text-balance">
          深度报告 L0
        </h1>

        {meta !== null ? (
          <dl
            className="mt-6 flex flex-wrap gap-x-8 gap-y-3 border border-rule bg-raised px-5 py-4 font-mono text-[11px]"
            style={{ borderRadius: "var(--radius-card)" }}
          >
            {[
              { k: "type", v: meta.type },
              { k: "version", v: String(meta.version) },
              { k: "ledger_version", v: String(meta.ledger_version) },
              { k: "reproducible", v: String(meta.reproducible) },
            ].map((f) => (
              <div key={f.k} className="flex flex-col gap-1">
                <dt className="text-ink-3">{f.k}</dt>
                <dd className="tabular text-ink">{f.v}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p
            className="mt-6 border border-dashed border-rail bg-raised px-5 py-4 font-mono text-[11px] leading-[1.7] text-ink-2"
            style={{ borderRadius: "var(--radius-card)" }}
          >
            元信息端点未回内容（GET /deliverables/{id} → 404）；Block 树仍在，故正文照常呈现。
          </p>
        )}
      </div>
    </header>
  )
}

function Shell({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <main className="min-h-svh bg-background">
      <ReportHeader id={id} meta={null} />
      <div className="mx-auto max-w-5xl px-5 py-8">{children}</div>
    </main>
  )
}

// 尚未生成：后端 404。说清「为什么现在没有」，不拿占位正文填满。
function NotGenerated({ id }: { id: string }) {
  return (
    <div className="gap-cut flex min-h-64 flex-col items-center justify-center gap-3 rounded-[4px] px-6 py-16">
      <p className="font-mono text-[11px] text-ink-3">404 · NOT_FOUND</p>
      <p className="font-display text-[25px] text-ink-2">该交付物尚未生成</p>
      <p className="max-w-[34em] text-center text-[13px] leading-relaxed text-ink-3">
        <span className="font-mono">GET /deliverables/{id}/blocks</span> 回 404——后端没有这份 Block 树。
        报告由 report 组稿作业产出；作业未跑完（或本环境未接组稿线）时，此处就是空的。
        界面不替后端编一份正文出来。
      </p>
    </div>
  )
}

export default async function DeliverablePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params

  let meta: DeliverableMeta | null = null
  let tree: BlocksResponse | null = null
  let error: unknown = null
  try {
    ;[meta, tree] = await Promise.all([fetchDeliverableMeta(id), fetchBlocks(id)])
  } catch (err) {
    error = err
  }

  if (error !== null) {
    return (
      <Shell id={id}>
        <ApiErrorNotice error={error} what={`交付物 ${id}`} />
      </Shell>
    )
  }

  if (tree === null) {
    return (
      <Shell id={id}>
        <NotGenerated id={id} />
      </Shell>
    )
  }

  const blocks = tree.blocks

  // 服务端预渲染每个 block；高亮由 client shell 依真实导出响应套加。
  const renderedBlocks = blocks.map((b) => ({
    id: b.block_id,
    node: <BlockRenderer key={b.block_id} block={b} />,
  }))

  return (
    <main className="min-h-svh bg-background">
      <ReportHeader id={tree.deliverable_id} meta={meta} />

      <div className="mx-auto max-w-5xl px-5 py-8">
        {blocks.length === 0 ? (
          <div className="gap-cut flex min-h-40 flex-col items-center justify-center gap-2 rounded-[4px] px-6 py-10">
            <p className="font-display text-[20px] text-ink-2">这份交付物没有任何 block</p>
            <p className="max-w-[30em] text-center text-[13px] leading-relaxed text-ink-3">
              后端 blocks 为空数组。这是真实空态，非加载中、非错误。
            </p>
          </div>
        ) : (
          <ReportShell deliverableId={id} blocks={blocks} renderedBlocks={renderedBlocks} />
        )}
      </div>

      {/* 字段清单：屏上每处指回真端点 */}
      <footer className="border-t border-rule">
        <div className="mx-auto max-w-5xl px-5 py-10">
          <h2 className="mb-4 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-3">
            字段清单 · 屏上每处指回真端点
          </h2>
          <ul
            className="max-w-[46em] space-y-2 border border-rule bg-surface px-5 py-4 font-mono text-[11px] leading-relaxed text-ink-2"
            style={{ borderRadius: "var(--radius-card)" }}
          >
            <li>正文 · GET /deliverables/{id}/blocks（8 类 BlockType 全覆盖，逐块原生渲染）</li>
            <li>保护块 · locked ∨ author==user ∨ user_modified → isProtected → 整块不渲染控件</li>
            <li>复核 · needs_review + review_severity（advisory 可折叠 / blocking 挡导出）</li>
            <li>争议 · ClaimSpan.disputed_mark → 标记不删原文</li>
            <li>三通道 · FactCell.fact_id / PriceCell.price_entry_id+quantity / ProfileRef.field_path</li>
            <li>缺口 · GapNoticeContent.hints_ref → 物理切口，不以生成文字填满</li>
            <li>导出 409 · GET …/render?fmt= → EXPORT_BLOCKED.detail.blocking_block_ids 高亮</li>
            <li>导出 503 · pdf 引擎缺失 / pack builder 未接线 → SERVICE_UNAVAILABLE 降级态</li>
            <li>右侧缩略带 · 编码 位置+类别，无强度渐变/热力图</li>
          </ul>
        </div>
      </footer>
    </main>
  )
}
