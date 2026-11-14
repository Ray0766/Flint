// 状态：后端不可达 / 后端回错误体 → 如实呈现，NEVER 退回 mock、NEVER 显空当没事
//
// 两种态严格分开：
//   FlintNetworkError → 连不上后端（进程没起 / 端口不通）：告诉用户连的是哪个基址。
//   FlintApiError     → 后端按契约回了错：原样显 code + message（+ detail 摘要）。
// 5xx 与 4xx 用同一形态但措辞不同：5xx 是"后端出错"，4xx 是"这个请求不成立"。
import { CircleSlash, PlugZap, TriangleAlert } from "lucide-react";
import { FlintApiError, FlintNetworkError } from "@/lib/api";

function Frame({
  tone,
  icon,
  head,
  children,
}: {
  tone: "neutral" | "alarm";
  icon: React.ReactNode;
  head: string;
  children: React.ReactNode;
}) {
  const alarm = tone === "alarm";
  return (
    <div
      role="alert"
      className={`rounded-card border px-5 py-4 ${
        alarm ? "border-spark bg-spark-wash" : "border-dashed border-rail bg-raised"
      }`}
    >
      <p
        className={`flex items-center gap-2 font-mono text-[12px] ${
          alarm ? "text-spark" : "text-ink-2"
        }`}
      >
        {icon}
        {head}
      </p>
      <div className="mt-2 space-y-1.5 text-[13px] leading-relaxed text-ink-2">{children}</div>
    </div>
  );
}

export function ApiErrorNotice({ error, what }: { error: unknown; what: string }) {
  if (error instanceof FlintNetworkError) {
    return (
      <Frame
        tone="neutral"
        icon={<PlugZap className="h-4 w-4" strokeWidth={1.5} aria-hidden />}
        head="后端不可达"
      >
        <p>
          取「{what}」时连不上后端。这不是空数据，也不是判定结果——是链路断了。
        </p>
        <p className="font-mono text-[11px] text-ink-3">API_BASE · {error.base}</p>
        <p className="font-mono text-[11px] text-ink-3">{error.url}</p>
      </Frame>
    );
  }

  if (error instanceof FlintApiError) {
    const server = error.status >= 500;
    const blocking = error.blockingBlockIds;
    return (
      <Frame
        tone={server ? "alarm" : "neutral"}
        icon={
          server ? (
            <TriangleAlert className="h-4 w-4" strokeWidth={1.5} aria-hidden />
          ) : (
            <CircleSlash className="h-4 w-4" strokeWidth={1.5} aria-hidden />
          )
        }
        head={`${error.status} · ${error.code}`}
      >
        <p>{error.message}</p>
        <p className="text-[12px] text-ink-3">
          {server
            ? `取「${what}」时后端内部出错。内容未生成，界面不猜、不填占位。`
            : `取「${what}」时后端拒绝了该请求。`}
        </p>
        {blocking.length > 0 ? (
          <p className="font-mono text-[11px] text-ink-2">
            blocking_block_ids · {blocking.join(", ")}
          </p>
        ) : null}
        {error.body?.detail?.violations?.length ? (
          <p className="font-mono text-[11px] text-ink-2">
            violations · {error.body.detail.violations.join(", ")}
          </p>
        ) : null}
        <p className="font-mono text-[11px] text-ink-3">{error.url}</p>
      </Frame>
    );
  }

  return (
    <Frame
      tone="alarm"
      icon={<TriangleAlert className="h-4 w-4" strokeWidth={1.5} aria-hidden />}
      head="未预期的错误"
    >
      <p>取「{what}」时抛出未归类异常，如实抛在此处，未被吞掉。</p>
      <p className="font-mono text-[11px] text-ink-3">
        {error instanceof Error ? error.message : String(error)}
      </p>
    </Frame>
  );
}
