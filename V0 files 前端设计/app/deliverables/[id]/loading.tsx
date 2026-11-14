// 加载态（技术约束清单第 6 条：每屏空态 / 错误态 / 加载态齐全）。
// 真等后端时的骨架：明说"正在读"，NEVER 先渲染任何 block 正文、版本号或 blocking 结论。
// 骨架条只占位不承载语义（aria-hidden），故灰度下也不会被误读成内容。
//
// 视觉：实用暗色（功能屏语言），NEVER 用首页 glow。
export default function DeliverableLoading() {
  return (
    <main className="min-h-svh bg-background">
      <header className="border-b border-rule">
        <div className="mx-auto max-w-5xl px-5 py-10">
          <p className="font-mono text-[11px] text-ink-3">
            GET /deliverables/&#123;id&#125; · /blocks
          </p>
          <h1 className="mt-3 font-display text-[31px] font-medium leading-[1.3] text-ink">
            深度报告 L0
          </h1>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-5 py-8">
        <div
          className="border border-rule bg-surface px-6 py-10"
          style={{ borderRadius: "var(--radius-card)" }}
        >
          <p className="font-mono text-[12px] text-ink-2">正在读取交付物与 Block 树 …</p>
          <p className="mt-2 max-w-[34em] text-[13px] leading-relaxed text-ink-3">
            尚未拿到后端响应。此处不预渲染任何正文、版本号或复核结论——
            空白即「还没有数据」，不是「没有内容」，也不是「没有阻断」。
          </p>
          <div className="mt-6 flex flex-col gap-3" aria-hidden>
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded-[4px] bg-raised" />
            ))}
          </div>
        </div>
      </div>
    </main>
  )
}
