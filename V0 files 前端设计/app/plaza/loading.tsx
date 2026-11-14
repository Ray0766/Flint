// 加载态：真等后端时的骨架。明说"正在读"，NEVER 先渲染任何占位数值。
export default function PlazaLoading() {
  return (
    <main className="noise-overlay min-h-screen bg-background px-6 py-16 md:px-10">
      <div className="mx-auto flex max-w-[720px] flex-col gap-8">
        <p className="font-mono text-[12px] text-ink-3">GET /plaza/hot</p>
        <h1 className="font-display text-[31px] font-medium leading-[1.3] text-foreground">热点广场</h1>
        <div className="border border-rule bg-surface px-6 py-10">
          <p className="font-mono text-[12px] text-ink-2">正在读取当日热点 …</p>
          <p className="mt-2 text-[13px] leading-relaxed text-ink-3">
            尚未拿到后端响应。此处不预渲染任何分值——空白即"还没有数据"，不是"数据为零"。
          </p>
          <div className="mt-6 flex flex-col gap-3" aria-hidden>
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded-[2px] bg-raised" />
            ))}
          </div>
        </div>
      </div>
    </main>
  )
}
