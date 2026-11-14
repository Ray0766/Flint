import type { Metadata } from "next"
import type { Block } from "@/lib/types"
import { CertaintyLevel } from "@/components/honesty/certainty-level"
import { SpeculativeTag } from "@/components/honesty/speculative-tag"
import { ReviewBadge } from "@/components/honesty/review-badge"
import { DisputedMark } from "@/components/honesty/disputed-mark"
import { GapNotice } from "@/components/honesty/gap-notice"
import { ProtectedBlock } from "@/components/honesty/protected-block"
import { ChartPlaceholder } from "@/components/honesty/chart-placeholder"
import { ChannelValue } from "@/components/honesty/channel-value"
import { CitationMark } from "@/components/honesty/citation-mark"
import { EvidenceGutter, type GutterMark } from "@/components/honesty/evidence-gutter"

export const metadata: Metadata = {
  title: "Flint · Styleguide",
  description: "Flint 确定度 / 出处 / 判定 的可跑样式基准，消费 components/honesty/。",
}

/* ============================================================
   /styleguide —— 消费 components/honesty/ 的可跑基准（非表格）
   全站唯一强调色 = --spark；全站唯一动效 = .spark-strike
   页面仅保留 SourceMark / EvidenceRow / Section 版式脚手架（出处槽由 EvidenceGutter 承载），
   所有诚实形态均由 honesty 组件呈现，页面内不重复实现。
   ============================================================ */

// —— 源印：2px 方形，仅承担"哪一源"，色不表强弱，尺寸恒定（版式脚手架，非诚实态） ——
const SOURCES = {
  trends: { label: "google trends", cls: "bg-src-trends" },
  weibo: { label: "weibo", cls: "bg-src-weibo" },
  github: { label: "github trend", cls: "bg-src-github" },
  arxiv: { label: "arxiv", cls: "bg-src-arxiv" },
} as const

function SourceMark({ src }: { src: keyof typeof SOURCES }) {
  const s = SOURCES[src]
  return (
    <span className="inline-flex items-center gap-1.5 align-middle">
      <span className={`inline-block h-2.5 w-2.5 rounded-[1px] ${s.cls}`} aria-hidden />
      <span className="font-mono text-[11px] leading-none text-ink-3">{s.label}</span>
    </span>
  )
}

// —— 出处槽演示行：消费正式组件 EvidenceGutter（显式 marks 形态，仅用于词汇表展示）——
// 空态 marks={[]} → 桌面轨线仍在、移动端不占位。
function EvidenceRow({
  marks,
  children,
}: {
  marks: GutterMark[]
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col items-stretch gap-2 border-t border-rule py-3 first:border-t-0 md:flex-row">
      <EvidenceGutter marks={marks} />
      <div className="min-w-0 flex-1 pt-0.5 leading-[1.8]">{children}</div>
    </div>
  )
}

function Section({
  n,
  title,
  field,
  children,
}: {
  n: string
  title: string
  field: string
  children: React.ReactNode
}) {
  return (
    <section className="border-t border-rule pt-10">
      <div className="mb-5 flex items-baseline gap-3">
        <span className="font-mono text-[12px] text-ink-3">{n}</span>
        <h2 className="font-display text-[25px] font-medium leading-[1.3] text-foreground">{title}</h2>
      </div>
      <p className="mb-6 font-mono text-[11px] leading-relaxed text-ink-3">
        <span className="text-ink-2">后端字段</span> · {field}
      </p>
      {children}
    </section>
  )
}

// —— 示例 block：仅用于驱动 ProtectedBlock 的保护判定，字段全部取自 types.ts ——
const systemBlock: Block = {
  block_id: "blk-sys-01",
  deliverable_id: "dlv-01",
  section_id: "sec-01",
  order: 0,
  type: "paragraph",
  content: { kind: "paragraph", spans: [] },
  claim_ids: [],
  fact_ids: [],
  author: "system",
  revision: 1,
  locked: false,
  user_modified: false,
  needs_review: false,
  review_reason: null,
  review_severity: null,
}

const userModifiedBlock: Block = {
  ...systemBlock,
  block_id: "blk-usr-01",
  user_modified: true,
  revision: 2,
}

export default function StyleguidePage() {
  return (
    <main className="noise-overlay min-h-screen bg-background">
      <div className="mx-auto max-w-3xl px-6 py-16">
        {/* 卷宗头 */}
        <header className="mb-4">
          <p className="mb-3 font-mono text-[11px] tracking-wide text-ink-3">FLINT · STYLEGUIDE · L0 只读</p>
          <h1 className="font-display text-[48px] font-semibold leading-[1.1] text-foreground text-balance">
            带出处的卷宗，
            <br />
            不是仪表盘
          </h1>
          <p className="mt-4 max-w-[34em] leading-[1.8] text-ink-2">
            排版本身在执行 <code className="text-[13px] text-ink">validate_channels</code>：凡类型化出处值一律等宽对齐，
            散文里不出现裸数字。判不出来时，界面如实留出切口，不拿漂亮占位填。
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-2">
            <SourceMark src="trends" />
            <SourceMark src="weibo" />
            <SourceMark src="github" />
            <SourceMark src="arxiv" />
          </div>
        </header>

        <div className="mt-14 flex flex-col gap-14">
          {/* 1 · 四级确定度阶梯 —— CertaintyLevel + DisputedMark + SpeculativeTag + CitationMark */}
          <Section
            n="01"
            title="确定度阶梯"
            field="Block.needs_review · ClaimSpan.disputed_mark · GapNoticeContent(kind='gap_notice') / D_insufficient"
          >
            <div className="grid grid-cols-1 gap-px overflow-hidden rounded-card border border-rule bg-rule sm:grid-cols-2">
              <CertaintyLevel kind="cited">
                该品类 30 日搜索热度居前
                <CitationMark citation_id="c-0417" />，且仓库活跃度同步上行
                <CitationMark citation_id="c-0418" />。
              </CertaintyLevel>

              <CertaintyLevel kind="speculative">
                若此趋势延续，
                <SpeculativeTag>下一季度需求或将扩张</SpeculativeTag>
                —— 该判断无直接出处支撑。
              </CertaintyLevel>

              <CertaintyLevel kind="disputed">
                <DisputedMark disputed_mark>该赛道已被头部厂商锁定</DisputedMark>
              </CertaintyLevel>

              <CertaintyLevel kind="insufficient">证据不足以支撑判断</CertaintyLevel>
            </div>
            <p className="mt-3 font-mono text-[11px] text-ink-3">
              D_insufficient 明显比其余三级更轻、更留白——没底气不画成有底气。
            </p>
          </Section>

          {/* 2 · 三通道数值排版 —— ChannelValue */}
          <Section
            n="02"
            title="三通道数值"
            field="TableCell → FactCell.fact_id · PriceCell.price_entry_id + quantity · InlineSpan → ProfileRef.field_path"
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="rounded-card border border-rule bg-card p-5">
                <p className="mb-4 font-mono text-[11px] text-ink-3">fact · 事实值</p>
                <ChannelValue channel="fact" fact_id="fct-9a3f" display="12,480" />
              </div>
              <div className="rounded-card border border-rule bg-card p-5">
                <p className="mb-4 font-mono text-[11px] text-ink-3">price · 价目值</p>
                <ChannelValue channel="price" price_entry_id="pr-1c07" quantity={3} display="2,900" />
              </div>
              <div className="rounded-card border border-rule bg-card p-5">
                <p className="mb-4 font-mono text-[11px] text-ink-3">profile · 档案引用</p>
                <ChannelValue channel="profile" field_path="profile.segment.tam" />
              </div>
            </div>
            <p className="mt-3 font-mono text-[11px] text-ink-3">三通道靠印记（F/¥/P）+ 字体字号区分，同为墨色，不靠颜色。</p>
          </Section>

          {/* 3 · advisory vs blocking —— ReviewBadge */}
          <Section
            n="03"
            title="复核严重度"
            field="Block.review_severity ∈ {advisory, blocking} · 导出闸 EXPORT_BLOCKED(409)"
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="rounded-card border border-rule bg-card p-5">
                <p className="mb-3 font-mono text-[11px] text-ink-3">advisory · 提示</p>
                <p className="leading-[1.8] text-ink-2">此段建议补充一处近月出处，但不影响导出。</p>
                <div className="mt-4 flex items-center gap-3 border-t border-rule pt-4">
                  <ReviewBadge review_severity="advisory" review_reason="建议补充出处" />
                  <span className="rounded-[2px] border border-ink bg-primary px-3 py-1.5 font-mono text-[11px] text-primary-foreground">
                    导出可用
                  </span>
                </div>
              </div>

              <div className="rounded-card border border-spark bg-spark-wash p-5">
                <p className="mb-3 leading-[1.8] text-foreground">存在未解决的争议声明，导出被阻断，须先复核。</p>
                <div className="flex flex-wrap items-center gap-3 border-t border-spark/40 pt-4">
                  <ReviewBadge review_severity="blocking" review_reason="blocking · 阻断" />
                  <span className="rounded-[2px] border border-spark px-3 py-1.5 font-mono text-[11px] text-spark">
                    导出被挡 · 409
                  </span>
                </div>
              </div>
            </div>
            <p className="mt-3 font-mono text-[11px] text-ink-3">
              一眼可辨：advisory 静默且导出可用；blocking 迸出唯一火星色并阻断导出。
            </p>
          </Section>

          {/* 4 · verdict 四档（报告级说明书字段，不在 types.ts 镜像内，页面直呈） */}
          <Section
            n="04"
            title="判定 verdict"
            field="报告级 verdict ∈ {A_infeasible, B_red_ocean, C_opportunity, D_insufficient}（说明书字段，不在 types.ts 镜像内）"
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-card border border-ink bg-primary p-5 text-primary-foreground">
                <p className="font-mono text-[11px] opacity-70">A</p>
                <p className="mt-3 font-display text-[20px] font-semibold leading-tight">不可行</p>
                <p className="mt-2 font-mono text-[11px] opacity-70">A_infeasible</p>
              </div>
              <div className="rounded-card border border-ink bg-card p-5">
                <p className="font-mono text-[11px] text-ink-3">B</p>
                <p className="mt-3 font-display text-[20px] font-semibold leading-tight text-foreground">红海</p>
                <p className="mt-2 font-mono text-[11px] text-ink-3">B_red_ocean</p>
              </div>
              <div className="rounded-card border border-rule bg-card p-5">
                <p className="font-mono text-[11px] text-ink-3">C</p>
                <p className="mt-3 font-display text-[20px] font-medium leading-tight text-ink-2">机会</p>
                <p className="mt-2 font-mono text-[11px] text-ink-3">C_opportunity</p>
              </div>
              <div className="gap-cut rounded-[2px] p-5">
                <p className="font-mono text-[11px] text-ink-3">D</p>
                <p className="mt-3 font-display text-[20px] font-normal leading-tight text-ink-3">数据不足</p>
                <p className="mt-2 font-mono text-[11px] text-ink-3">D_insufficient</p>
              </div>
            </div>
            <p className="mt-3 font-mono text-[11px] text-ink-3">
              重量随底气递减：A 实心墨块最重，D 落到切口最轻。verdict 不使用 spark（非阻断态）。
            </p>
          </Section>

          {/* 5 · 保护块 vs 普通块 —— ProtectedBlock */}
          <Section n="05" title="保护块 vs 普通块" field="isProtected(block) = locked ∨ author=='user' ∨ user_modified">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <ProtectedBlock
                block={systemBlock}
                controls={
                  <>
                    <button className="rounded-[2px] border border-ink px-3 py-1.5 font-mono text-[11px] text-foreground transition-colors hover:bg-secondary">
                      编辑
                    </button>
                    <button className="rounded-[2px] border border-rule px-3 py-1.5 font-mono text-[11px] text-ink-2 transition-colors hover:bg-secondary">
                      请求复核
                    </button>
                  </>
                }
              >
                该品类近月热度上行，建议纳入候选。
              </ProtectedBlock>

              <ProtectedBlock block={userModifiedBlock}>此段由使用者改定，前端强制只读。</ProtectedBlock>
            </div>
            <p className="mt-3 font-mono text-[11px] text-ink-3">保护块整块不渲染任何控件——不是灰掉的禁用按钮，而是根本不存在。</p>
          </Section>

          {/* 6 · 图表占位 与 缺口占位 —— ChartPlaceholder + GapNotice */}
          <Section n="06" title="图表占位 与 缺口占位" field="ChartContent.chart_id（前端零计算）· GapNoticeContent.hints_ref">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="rounded-card border border-rule bg-card p-5">
                <p className="mb-3 font-mono text-[11px] text-ink-3">chart · 待后端渲染</p>
                <ChartPlaceholder chart_id="cht-2b19" derived_from="fct-9a3f" />
              </div>
              <div className="rounded-card border border-rule bg-card p-5">
                <p className="mb-3 font-mono text-[11px] text-ink-3">gap_notice · 数据缺口</p>
                <GapNotice hints_ref="gap-5f0c" />
              </div>
            </div>
          </Section>

          {/* 7 · 出处槽（evidence gutter）空态 + 五种非空态（版式脚手架） */}
          <Section
            n="07"
            title="出处槽 evidence gutter"
            field="需 needs_review · disputed_mark · speculative(派生) · locked · gap_notice —— 槽空即真无附加状态"
          >
            <div className="rounded-card border border-rule bg-card px-5 py-2">
              <EvidenceRow marks={[]}>
                <p className="text-foreground">
                  空态：这段没有任何附加状态，出处槽即空——空槽本身是诚实信号，不是留白装饰。
                </p>
              </EvidenceRow>
              <EvidenceRow marks={[{ kind: "review", severity: "advisory" }]}>
                <p className="text-foreground">复核标：needs_review=true，该段待人工复核。</p>
              </EvidenceRow>
              <EvidenceRow marks={[{ kind: "disputed" }]}>
                <p className="text-foreground">争议标：claim 的 disputed_mark=true，标记而不删除原文。</p>
              </EvidenceRow>
              <EvidenceRow marks={[{ kind: "speculative" }]}>
                <p className="text-ink-2">推测标：无出处支撑的派生判断（span 级 SpeculativeTag），降权呈现。</p>
              </EvidenceRow>
              <EvidenceRow marks={[{ kind: "locked" }]}>
                <p className="text-foreground">保护锁：isProtected=true，整块只读。</p>
              </EvidenceRow>
              <EvidenceRow marks={[{ kind: "gap" }]}>
                <p className="text-ink-2">缺口标：gap_notice，证据链在此中断。</p>
              </EvidenceRow>
            </div>
          </Section>
        </div>

        <footer className="mt-16 border-t border-rule pt-6">
          <p className="font-mono text-[11px] leading-relaxed text-ink-3">
            全站唯一强调色 <span className="text-spark">--spark</span> · 全站唯一动效{" "}
            <span className="text-ink-2">.spark-strike</span>（blocking 出现时一次击打，prefers-reduced-motion 下静默）。
          </p>
        </footer>
      </div>
    </main>
  )
}
