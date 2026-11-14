// 未知 job 态：GET /jobs/{id} 与 GET /jobs/{id}/verdict **双双 404** → notFound() → 本页。
// 「后端没有这个 job」，不是错误、也不是判定结果——沿用 D 判定屏的克制语气，不用 spark。
export default function GateNotFound() {
  return (
    <div className="mx-auto max-w-[42rem] px-5 py-24">
      <div className="rounded-card border border-dashed border-rail bg-base p-8">
        <p className="font-mono text-[11px] text-ink-3">job · not_found · verdict · not_found</p>
        <h1 className="mt-4 font-display text-[25px] font-normal leading-tight text-ink-2">后端没有这个 job</h1>
        <p className="mt-4 max-w-[32em] text-[15px] leading-relaxed text-ink-2">
          <span className="font-mono text-[13px]">GET /jobs/&#123;id&#125;</span> 与
          <span className="font-mono text-[13px]"> /verdict </span>
          都回 404。可能是 job_id 写错，或该 job 属于另一套数据库。界面不替后端造一个判定出来。
        </p>
      </div>
    </div>
  )
}
