// Gate① 进行中 · 真 SSE（GET /jobs/{id}/events，id=seq，data=JobEventPayload JSON）
//
// 断线语义按后端 M1-034：seq 单调递增，浏览器原生 EventSource 自动带 Last-Event-ID 重连
// 并由后端补发；本组件对 seq <= 已见最大值的事件幂等忽略，避免重复挂载。
// 终态（done/failed/cancelled）→ 关流 + router.refresh() 让服务端重取判定。
// NEVER 编造进度：progress 只显后端给的数；后端没给步骤就空着。
"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { jobEventsUrl } from "@/lib/api"
import { TERMINAL_JOB_STATES, type JobEvent, type JobState, type JobView } from "@/lib/types"

interface SeenEvent {
  seq: number
  payload: JobEvent
}

export function GateLive({ job }: { job: JobView }) {
  const router = useRouter()
  const [events, setEvents] = useState<SeenEvent[]>([])
  const [state, setState] = useState<JobState>(job.state)
  const [streamError, setStreamError] = useState<string | null>(null)
  const lastSeq = useRef<number>(-1)
  const refreshed = useRef(false)
  const [dupIgnored, setDupIgnored] = useState(0)
  // 连接阶段（清单第 16 条要求可见）：snapshot → resubscribe → restored
  const [phase, setPhase] = useState<"snapshot" | "resubscribe" | "restored">("snapshot")

  useEffect(() => {
    const es = new EventSource(jobEventsUrl(job.job_id))

    es.onopen = () => {
      // 首次 open 即「已由快照接上流」；断线后 EventSource 自动重连再次 open = 已恢复
      setPhase((p) => (p === "resubscribe" ? "restored" : p))
    }

    es.onmessage = (e: MessageEvent<string>) => {
      const seq = Number(e.lastEventId)
      if (Number.isFinite(seq) && seq <= lastSeq.current) {
        setDupIgnored((n) => n + 1) // 续订重放：幂等忽略（把去重次数显出来，便于核对）
        return
      }
      if (Number.isFinite(seq)) lastSeq.current = seq
      const payload = JSON.parse(e.data) as JobEvent
      setEvents((prev) => [...prev, { seq, payload }])
      if (payload.kind === "status") setState(payload.state)
      if (payload.kind === "failed") setState("failed")
      const terminal =
        (payload.kind === "status" && TERMINAL_JOB_STATES.includes(payload.state)) ||
        payload.kind === "failed"
      if (terminal) {
        es.close()
        if (!refreshed.current) {
          refreshed.current = true
          router.refresh() // 终态：让服务端重取 verdict，判定由后端说了算
        }
      }
    }

    es.onerror = () => {
      // EventSource 会自行重连；只有彻底关闭才是真断。如实标注，不假装还在跑。
      if (es.readyState === EventSource.CLOSED) {
        setStreamError("事件流已关闭。可能是后端结束了该 job 的流，或链路中断。")
      } else {
        // CONNECTING：浏览器正在带 Last-Event-ID 续订。断线不是服务不可用，NEVER 用 spark。
        setPhase("resubscribe")
      }
    }

    return () => es.close()
  }, [job.job_id, router])

  return (
    <div className="mx-auto max-w-[42rem] px-5 py-16">
      <p className="font-mono text-[12px] text-ink-3">job_id · {job.job_id}</p>
      <h1 className="mt-4 font-display text-[25px] font-normal leading-tight text-foreground">分析进行中</h1>

      <div className="mt-6 rounded-card border border-rule bg-card p-6 font-mono text-[12px] leading-relaxed text-ink-2">
        <p>state · {state}</p>
        <p>progress · {job.progress}</p>
        <p>
          budget · {job.budget}　cost_accum · {job.cost_accum}
        </p>
        <p className="text-ink-3">updated_at · {job.updated_at}</p>
        {job.partial_output_ref !== null ? (
          <p className="text-ink-3">partial_output_ref · {job.partial_output_ref}</p>
        ) : null}
      </div>

      {/* SSE 接线阶段（清单第 16 条）：快照 → 带 Last-Event-ID 续订 → 按 seq 去重 → 终态 close */}
      <div
        className="mt-4 border border-dashed border-rail bg-raised px-4 py-3"
        style={{ borderRadius: "var(--radius)" }}
      >
        <p className="font-mono text-[11px] leading-[1.7] text-ink-2">
          {phase === "snapshot"
            ? `已读 GET /jobs/${job.job_id} 快照 · 已订阅 /events`
            : phase === "resubscribe"
              ? `连接中断 · 正带 Last-Event-ID: ${lastSeq.current >= 0 ? lastSeq.current : "—"} 续订`
              : `已恢复 · 自 seq ${lastSeq.current >= 0 ? lastSeq.current + 1 : "—"} 续传`}
        </p>
        <p className="mt-1 font-mono text-[10px] text-ink-3">
          去重：seq ≤ 已见最大值的事件已忽略 {dupIgnored} 条 · 终态自动 close()
        </p>
      </div>

      <div className="mt-6">
        <p className="font-mono text-[12px] uppercase tracking-wide text-ink-3">
          事件序列 · GET /jobs/{job.job_id}/events（SSE）
        </p>
        {events.length === 0 ? (
          <p className="mt-3 font-mono text-[12px] text-ink-3">
            已订阅，尚未收到事件。空列表即"后端还没发"，不是"没有步骤"。
          </p>
        ) : (
          <ol className="mt-3 space-y-2">
            {events.map((e, i) => (
              <li
                key={`${e.seq}-${i}`}
                className="flex items-baseline gap-3 font-mono text-[12px] text-ink-2"
              >
                <span className="text-ink-3">#{Number.isFinite(e.seq) ? e.seq : "—"}</span>
                <span>{describe(e.payload)}</span>
              </li>
            ))}
          </ol>
        )}
        {streamError !== null ? (
          <p className="mt-4 rounded-[4px] border border-dashed border-rail bg-raised px-4 py-3 font-mono text-[11px] text-ink-2">
            {streamError}
          </p>
        ) : null}
      </div>
    </div>
  )
}

function describe(p: JobEvent): string {
  switch (p.kind) {
    case "status":
      return `status · ${p.state}`
    case "step":
      return `step · ${p.step_name} · ${p.phase}${p.cost !== null ? ` · cost ${p.cost}` : ""}`
    case "partial_block":
      return `partial_block · ${p.block_id}`
    case "failed":
      return `failed · ${p.reason}`
  }
}
