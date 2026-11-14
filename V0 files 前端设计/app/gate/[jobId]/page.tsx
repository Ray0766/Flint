// Gate① 判定屏 · 真后端
//   GET /jobs/{id}/verdict  判定快照（未就绪 → 404 → 「判定尚未就绪」）
//   GET /jobs/{id}          job 快照（越权 → 403 → 如实显「无权查看」）
//   GET /jobs/{id}/events   SSE（非终态时由 GateLive 订阅）
//
// 分派全由**后端事实**决定，NEVER 用 ?demo= 之类前端开关伪造档位。
import type { Metadata } from "next"
import { notFound } from "next/navigation"
import { ArrowUpRight, Lock, Search, Upload, HelpCircle } from "lucide-react"
import { fetchCategories, fetchJobSnapshot, fetchVerdict } from "@/lib/api"
import { TERMINAL_JOB_STATES } from "@/lib/types"
import type {
  Category,
  Competitor,
  Gap,
  JobView,
  PricingRecord,
  VerdictKind,
  VerdictResponse,
} from "@/lib/types"
import { ApiErrorNotice } from "@/components/honesty/api-error"
import { AppShell } from "@/components/shell/app-shell"
import { GateLive } from "@/components/gate/gate-live"

export const dynamic = "force-dynamic"

export const metadata: Metadata = {
  title: "Flint · Gate① 判定",
  description: "把「没底气」画成克制而有分量——D_insufficient 是无法判定，不是失败。",
}

// ── 四档的形态权重：A 最重（实心墨块）→ D 最轻（切口）。verdict 不使用 spark ──
const VERDICT_META: Record<VerdictKind, { label: string; blurb: string; frame: string; head: string }> = {
  A_infeasible: {
    label: "不可行",
    blurb: "已有对齐通过的证伪证据支撑「此路不通」。这是有底气的否定，不是没查到。",
    frame: "rounded-card border border-ink bg-primary p-8 text-primary-foreground",
    head: "text-primary-foreground",
  },
  B_red_ocean: {
    label: "红海",
    blurb: "竞品数量或强度已达红海线。仍可做，但须回答「凭什么是你」。",
    frame: "rounded-card border border-ink bg-card p-8",
    head: "text-foreground",
  },
  C_opportunity: {
    label: "机会",
    blurb: "证伪检索已执行、关键证据对齐通过、无强/未知竞品阻断。判 C 的门槛刻意最高。",
    frame: "rounded-card border border-rule bg-card p-8",
    head: "text-ink-2",
  },
  D_insufficient: {
    label: "暂无法判定",
    blurb:
      "当前证据不足以支撑任一档判定。这不是失败，也不是「不可行」——它是一个诚实的空白：补齐下列缺口后即可重跑判定。",
    frame: "rounded-card border border-dashed border-rail bg-base p-8",
    head: "text-ink-2",
  },
}

// ── gap 动作图标：仅映射 types.ts 的 GapAction，不发明 ──
function gapActionMeta(action: Gap["action"]) {
  switch (action) {
    case "search":
      return { Icon: Search, label: "search · 补采市场源" }
    case "ask_user":
      return { Icon: HelpCircle, label: "ask_user · 向用户询问" }
    case "upload":
      return { Icon: Upload, label: "upload · 上传资料" }
    case "request_permission":
      return { Icon: Lock, label: "request_permission · 请求授权" }
  }
}

// ── 缺资料：展示 suggested_sources + action，绝不说成缺权限 ──
function MissingDataGap({ gap }: { gap: Gap }) {
  const meta = gapActionMeta(gap.action)
  return (
    <div className="rounded-card border border-rule bg-card p-5">
      <div className="flex items-center gap-2">
        <span className="rounded-[1px] border border-rail px-1.5 py-0.5 font-mono text-[10px] text-ink-3">
          missing_data
        </span>
        <span className="font-mono text-[10px] text-ink-3">缺资料</span>
      </div>
      <p className="mt-3 text-[15px] leading-relaxed text-foreground">{gap.missing_what}</p>
      <div className="mt-4 space-y-2">
        <div className="flex items-center gap-2 font-mono text-[12px] text-ink-2">
          <meta.Icon className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />
          {meta.label}
          {gap.target_count !== null ? (
            <span className="text-ink-3">· target_count {gap.target_count}</span>
          ) : null}
        </div>
        {gap.suggested_sources.length > 0 ? (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-mono text-[11px] text-ink-3">suggested_sources:</span>
            {gap.suggested_sources.map((s) => (
              <span
                key={s}
                className="rounded-[1px] border border-rule bg-raised px-1.5 py-0.5 font-mono text-[11px] text-ink-2"
              >
                {s}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}

// ── 缺权限：展示 required_scope +「请 owner 授权」，形态与缺资料明确不同 ──
function MissingPermissionGap({ gap }: { gap: Gap }) {
  return (
    <div className="rounded-card border border-dashed border-rail bg-raised p-5">
      <div className="flex items-center gap-2">
        <Lock className="h-3.5 w-3.5 text-ink-2" strokeWidth={1.5} aria-hidden />
        <span className="rounded-[1px] border border-rail px-1.5 py-0.5 font-mono text-[10px] text-ink-3">
          missing_permission
        </span>
        <span className="font-mono text-[10px] text-ink-3">缺授权</span>
      </div>
      <p className="mt-3 text-[15px] leading-relaxed text-foreground">{gap.missing_what}</p>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {gap.required_scope !== null ? (
          <span className="rounded-[1px] border border-rail px-2 py-0.5 font-mono text-[11px] text-ink-2">
            required_scope · {gap.required_scope}
          </span>
        ) : null}
        <span className="font-mono text-[12px] text-ink-2">请 owner 授权后重跑判定</span>
      </div>
      <p className="mt-3 max-w-[30em] text-[12px] leading-relaxed text-ink-3">
        这是权限缺口，不是数据缺口——授权到位即可复判，无需补采。
      </p>
    </div>
  )
}

function pricingText(pricing: PricingRecord | null): string {
  if (pricing === null) return "—（后端未提供定价记录）"
  const amount = pricing.price === null ? "待确认" : `${pricing.price} ${pricing.currency}`
  return `${pricing.plan} · ${amount} · ${pricing.region} · confidence ${pricing.confidence}`
}

// ── 竞品：unknown 明确标「未知」，形态区别于 weak/moderate/strong ──
function CompetitorRow({ c }: { c: Competitor }) {
  const isUnknown = c.strength === "unknown"
  return (
    <div className="flex items-start justify-between gap-4 border-b border-rule py-3 last:border-b-0">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="truncate text-[14px] text-foreground">{c.name}</span>
          <a
            href={c.url}
            target="_blank"
            rel="noreferrer noopener"
            className="shrink-0 text-ink-3 transition-colors hover:text-foreground"
            aria-label={`打开 ${c.name} 链接`}
          >
            <ArrowUpRight className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />
          </a>
        </div>
        <p className="mt-1 font-mono text-[11px] text-ink-3">pricing · {pricingText(c.pricing ?? null)}</p>
        {c.strength_signals.length > 0 ? (
          <p className="mt-1 font-mono text-[11px] text-ink-3">
            strength_signals · {c.strength_signals.join(", ")}
          </p>
        ) : (
          <p className="mt-1 font-mono text-[11px] text-ink-3">strength_signals · []（无信号命中）</p>
        )}
      </div>
      {isUnknown ? (
        // 未知：虚线中空标记，明示「信息不足」而非「弱」
        <span className="inline-flex shrink-0 items-center gap-1.5 rounded-[1px] border border-dashed border-rail px-2 py-1 font-mono text-[11px] text-ink-3">
          <HelpCircle className="h-3 w-3" strokeWidth={1.5} aria-hidden />
          strength · 未知
        </span>
      ) : (
        <span className="inline-flex shrink-0 items-center rounded-[1px] border border-ink-3 px-2 py-1 font-mono text-[11px] text-ink-2">
          strength · {c.strength}
        </span>
      )}
    </div>
  )
}

// ── 判定依据：constraints_checked 作为可展开对象，不是 boolean ──
function ConstraintsDetail({ v }: { v: VerdictResponse["verdict"] }) {
  const cc = v.constraints_checked
  if (cc === undefined) {
    return (
      <div className="rounded-card border border-dashed border-rail bg-raised px-5 py-4">
        <p className="font-mono text-[12px] text-ink-2">判定依据 · constraints_checked 未记录</p>
        <p className="mt-2 max-w-[34em] text-[13px] leading-relaxed text-ink-3">
          该判定快照没有携带三规则的评估痕迹（早期快照形态）。此处如实留空，不反推、不补默认值。
        </p>
      </div>
    )
  }
  return (
    <details className="group rounded-card border border-rule bg-card">
      <summary className="flex cursor-pointer list-none items-center justify-between rounded-[4px] px-5 py-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2 focus-visible:ring-offset-card">
        <span className="font-mono text-[12px] text-ink-2">
          判定依据 · constraints_checked（gap_count {cc.gap_count}）
        </span>
        <span className="font-mono text-[11px] text-ink-3 transition-transform group-open:rotate-90">›</span>
      </summary>
      <div className="space-y-4 border-t border-rule px-5 py-4 font-mono text-[12px] leading-relaxed">
        <div>
          <p className="text-ink-3">order</p>
          <p className="mt-1 text-ink-2">{cc.order.join(" → ")}</p>
        </div>
        <div>
          <p className="text-ink-3">demoted_by_alignment</p>
          <p className="mt-1 text-ink-2">{String(cc.demoted_by_alignment)}</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-[4px] border border-rule p-3">
            <p className="text-ink-3">rule_a</p>
            <p className="mt-1 text-ink-2">satisfied {String(cc.rule_a.satisfied)}</p>
            <p className="text-ink-2">used_user_evidence_only {String(cc.rule_a.used_user_evidence_only)}</p>
            <p className="text-ink-2">blocked_pending_optin {String(cc.rule_a.blocked_pending_optin)}</p>
          </div>
          <div className="rounded-[4px] border border-rule p-3">
            <p className="text-ink-3">rule_b</p>
            <p className="mt-1 text-ink-2">satisfied {String(cc.rule_b.satisfied)}</p>
            <p className="text-ink-2">by_count {String(cc.rule_b.by_count)}</p>
            <p className="text-ink-2">by_strength {String(cc.rule_b.by_strength)}</p>
            <p className="text-ink-2">reachable_count {cc.rule_b.reachable_count}</p>
            <p className="text-ink-2">
              strong_names {cc.rule_b.strong_names.length > 0 ? cc.rule_b.strong_names.join(", ") : "[]"}
            </p>
          </div>
          <div className="rounded-[4px] border border-rule p-3">
            <p className="text-ink-3">rule_c</p>
            <p className="mt-1 text-ink-2">satisfied {String(cc.rule_c.satisfied)}</p>
            <div className="mt-1">
              <p className="text-ink-2">failed_conditions</p>
              <ul className="mt-0.5 list-inside list-disc text-ink-2">
                {cc.rule_c.failed_conditions.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </div>
            <div className="mt-1">
              <p className="text-ink-2">blocking_competitors</p>
              <ul className="mt-0.5 list-inside list-disc text-ink-2">
                {cc.rule_c.blocking_competitors.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </details>
  )
}

// ── 主判定屏：档位由后端 verdict 决定；D 克制、留白、有分量，不报警不失败 ──
function VerdictView({ res }: { res: VerdictResponse }) {
  const v = res.verdict
  const meta = VERDICT_META[v.verdict] ?? VERDICT_META.D_insufficient
  const gaps = v.gaps ?? []
  const competitors = v.competitors ?? []
  const allSatisfied = v.all_satisfied ?? []
  const keyCitations = v.key_citation_ids ?? []
  const rationaleFacts = v.rationale_fact_ids ?? []
  const missingData = gaps.filter((g) => g.cause === "missing_data")
  const missingPerm = gaps.filter((g) => g.cause === "missing_permission")
  const hasCitations = keyCitations.length > 0 || rationaleFacts.length > 0

  return (
    <div className="mx-auto max-w-[42rem] px-5 py-16">
      <p className="font-mono text-[12px] text-ink-3">job_id · {res.job_id}</p>

      <div className={`mt-4 ${meta.frame}`}>
        <p className="font-mono text-[11px] opacity-70">verdict · {v.verdict}</p>
        <h1 className={`mt-4 text-balance font-display text-[31px] font-normal leading-tight ${meta.head}`}>
          {meta.label}
        </h1>
        <p className="mt-4 max-w-[32em] text-[15px] leading-relaxed opacity-90">{meta.blurb}</p>
        <p className="mt-3 font-mono text-[11px] opacity-70">
          all_satisfied · {allSatisfied.length > 0 ? allSatisfied.join(", ") : "[]（未记录）"}
        </p>
      </div>

      {/* 溯源入口：数组为空就说空 —— 空就是空，不补占位 */}
      <div className="mt-4 font-mono text-[11px] text-ink-3">
        {hasCitations ? (
          <span>
            可溯源 · key_citation_ids [{keyCitations.join(", ") || "—"}] · rationale_fact_ids [
            {rationaleFacts.join(", ") || "—"}]
          </span>
        ) : (
          <span>key_citation_ids · rationale_fact_ids 均为空数组（无可溯源引用）</span>
        )}
      </div>

      {/* 缺口区：两类明确区分。D 档必有缺口；其余档为空则如实说明 */}
      <section className="mt-10">
        <h2 className="font-mono text-[12px] uppercase tracking-wide text-ink-3">
          缺口 · gaps（{gaps.length}）
        </h2>
        {gaps.length === 0 ? (
          <p className="mt-3 font-mono text-[12px] text-ink-3">
            后端未产出缺口清单（该档判定不要求补口）。
          </p>
        ) : (
          <div className="mt-4 space-y-3">
            {missingData.map((g, i) => (
              <MissingDataGap key={`md-${i}`} gap={g} />
            ))}
            {missingPerm.map((g, i) => (
              <MissingPermissionGap key={`mp-${i}`} gap={g} />
            ))}
          </div>
        )}
      </section>

      {/* 竞品：unknown 明确标未知 */}
      <section className="mt-10">
        <h2 className="font-mono text-[12px] uppercase tracking-wide text-ink-3">
          竞品 · competitors（{competitors.length}）
        </h2>
        {competitors.length === 0 ? (
          <p className="mt-3 font-mono text-[12px] text-ink-3">
            competitors 为空数组——后端本次未记录任何竞品，非「无竞品」结论。
          </p>
        ) : (
          <div className="mt-2 rounded-card border border-rule bg-card px-5">
            {competitors.map((c, i) => (
              <CompetitorRow key={`${c.name}-${i}`} c={c} />
            ))}
          </div>
        )}
      </section>

      {/* 判定依据 */}
      <section className="mt-10">
        <ConstraintsDetail v={v} />
      </section>
    </div>
  )
}

// ── 失败态：显示后端 job.error，不编档位 ──
function FailedView({ job }: { job: JobView }) {
  return (
    <div className="mx-auto max-w-[42rem] px-5 py-16">
      <p className="font-mono text-[12px] text-ink-3">job_id · {job.job_id}</p>
      {/* 失败态：坏消息，但非 blocking/409/503——用克制墨色，不动用 spark 火星 */}
      <div className="mt-4 rounded-card border border-dashed border-rail bg-raised/50 p-8">
        <p className="font-mono text-[11px] text-ink-3">job · {job.state}</p>
        <h1 className="mt-4 font-display text-[25px] font-normal leading-tight text-foreground">分析未能完成</h1>
        <p className="mt-4 max-w-[34em] text-[15px] leading-relaxed text-ink-2">
          {job.error ?? "后端未记录失败原因（job.error 为 null）。此处不代为解释。"}
        </p>
        <p className="mt-3 font-mono text-[11px] text-ink-3">
          原因取自后端 job.error，未编造进度或档位。updated_at · {job.updated_at}
        </p>
      </div>
    </div>
  )
}

// ── job 终结但没有判定快照：诚实说明，不降级成任何一档 ──
function VerdictMissingView({ job }: { job: JobView }) {
  return (
    <div className="mx-auto max-w-[42rem] px-5 py-16">
      <p className="font-mono text-[12px] text-ink-3">job_id · {job.job_id}</p>
      <div className="mt-4 gap-cut rounded-[4px] p-8">
        <p className="font-mono text-[11px] text-ink-3">job · {job.state} · verdict · 无快照</p>
        <h1 className="mt-4 font-display text-[25px] font-normal leading-tight text-ink-2">判定尚未就绪</h1>
        <p className="mt-4 max-w-[34em] text-[15px] leading-relaxed text-ink-2">
          该 job 已进入 <span className="font-mono text-[13px]">{job.state}</span>，但
          <span className="font-mono text-[13px]"> GET /jobs/{job.job_id}/verdict </span>
          仍回 404（判定快照不存在）。界面不替后端补一个档位——没有就是没有。
        </p>
      </div>
    </div>
  )
}

export default async function GatePage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params

  let categories: Category[] | null = null
  let categoriesError = false
  try {
    categories = await fetchCategories()
  } catch {
    categoriesError = true
  }

  const shell = (endpoint: string, body: React.ReactNode) => (
    <AppShell
      active="/plaza"
      endpoint={endpoint}
      categories={categories}
      categoriesError={categoriesError}
    >
      {body}
    </AppShell>
  )

  // 两支并发读；各自的失败态互不掩盖。
  const [verdictResult, jobResult] = await Promise.allSettled([
    fetchVerdict(jobId),
    fetchJobSnapshot(jobId),
  ])

  const verdict = verdictResult.status === "fulfilled" ? verdictResult.value : null
  const job = jobResult.status === "fulfilled" ? jobResult.value : null
  const verdictError = verdictResult.status === "rejected" ? verdictResult.reason : null
  const jobError = jobResult.status === "rejected" ? jobResult.reason : null

  // 判定读出错（非 404）→ 如实抬错，NEVER 静默当"未就绪"
  if (verdictError !== null) {
    return shell(
      `GET /jobs/${jobId}/verdict`,
      <div className="mx-auto max-w-[42rem] px-5 py-16">
        <p className="mb-4 font-mono text-[12px] text-ink-3">job_id · {jobId}</p>
        <ApiErrorNotice error={verdictError} what={`Gate 判定 ${jobId}`} />
      </div>,
    )
  }

  // job 快照越权/后端出错，且判定也没有 → 抬错（有判定则判定优先展示）
  if (jobError !== null && verdict === null) {
    return shell(
      `GET /jobs/${jobId}`,
      <div className="mx-auto max-w-[42rem] px-5 py-16">
        <p className="mb-4 font-mono text-[12px] text-ink-3">job_id · {jobId}</p>
        <ApiErrorNotice error={jobError} what={`job 快照 ${jobId}`} />
      </div>,
    )
  }

  // 后端两处都说「没有这个 job」→ 404 页
  if (verdict === null && job === null) notFound()

  if (verdict !== null) {
    return shell(`GET /jobs/${jobId}/verdict`, <VerdictView res={verdict} />)
  }

  // 到此 job 必不为空（verdict 为 null）
  const live = job as JobView
  if (live.state === "failed") {
    return shell(`GET /jobs/${jobId}`, <FailedView job={live} />)
  }
  if (!TERMINAL_JOB_STATES.includes(live.state)) {
    // P7：非终态 → SSE 实时进度（GET /jobs/{id}/events）
    return shell(
      `GET /jobs/${jobId} → SSE GET /jobs/${jobId}/events`,
      <GateLive job={live} />,
    )
  }
  return shell(`GET /jobs/${jobId}`, <VerdictMissingView job={live} />)
}
