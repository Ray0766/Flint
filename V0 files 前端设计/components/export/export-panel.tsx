// P13 导出面板（client）
//
// 清单 21/28：
// - 四格式真打 `GET /deliverables/{id}/render?fmt=`；**前端零预判**。
//   按钮**不因为"可能会 409"就提前禁用**——那等于替后端下结论。
// - 409 EXPORT_BLOCKED → 取 detail.blocking_block_ids，**列出并高亮**待处理块，
//   同时明写「导出被后端挡住」。
// - 503（pdf 引擎缺失 / pack builder 未接线）→「该格式暂不可用」，
//   克制中性形态；NEVER 转圈、NEVER 伪装成下载成功。
// - --spark 只在 409 与 5xx 出现（阻断语义），其余态一律墨色。
"use client";

import { useState } from "react";
import { CircleSlash, Download, Loader2, TriangleAlert } from "lucide-react";
import {
  FlintApiError,
  FlintNetworkError,
  renderDeliverable,
  type RenderFmt,
} from "@/lib/api";
import type { Block } from "@/lib/types";

type State =
  | { s: "idle" }
  | { s: "pending"; fmt: RenderFmt }
  | { s: "ok"; fmt: RenderFmt; filename: string }
  | { s: "blocked"; fmt: RenderFmt; ids: string[]; err: FlintApiError }
  | { s: "degraded"; fmt: RenderFmt; err: FlintApiError }
  | { s: "error"; fmt: RenderFmt; err: unknown };

const FMTS: { fmt: RenderFmt; label: string; note: string }[] = [
  { fmt: "markdown", label: "markdown", note: "文本，最稳" },
  { fmt: "html", label: "html", note: "带样式" },
  { fmt: "docx", label: "docx", note: "python-docx" },
  { fmt: "pdf", label: "PDF", note: "需 GTK 运行库" },
  { fmt: "pack", label: "vibe_pack zip", note: "需 pack builder" },
];

const EXT: Record<RenderFmt, string> = {
  markdown: "md",
  html: "html",
  pdf: "pdf",
  docx: "docx",
  pack: "zip",
};

export function ExportPanel({
  deliverableId,
  blocks,
}: {
  deliverableId: string;
  blocks: Block[];
}) {
  const [state, setState] = useState<State>({ s: "idle" });

  const run = async (fmt: RenderFmt) => {
    setState({ s: "pending", fmt });
    try {
      const res = await renderDeliverable(deliverableId, fmt);
      const blob = await res.blob();
      const filename = `${deliverableId}.${EXT[fmt]}`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      setState({ s: "ok", fmt, filename });
    } catch (e) {
      if (e instanceof FlintApiError && e.status === 409) {
        setState({ s: "blocked", fmt, ids: e.blockingBlockIds, err: e });
      } else if (e instanceof FlintApiError && e.status === 503) {
        setState({ s: "degraded", fmt, err: e });
      } else {
        setState({ s: "error", fmt, err: e });
      }
    }
  };

  const blockedIds = state.s === "blocked" ? state.ids : [];
  const busy = state.s === "pending";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap gap-2">
        {FMTS.map(({ fmt, label, note }) => (
          <button
            key={fmt}
            type="button"
            disabled={busy}
            onClick={() => void run(fmt)}
            title={note}
            className="inline-flex items-center gap-2 border border-rule bg-surface px-4 py-2.5 font-mono text-[12px] text-ink-2 transition-colors hover:border-rail disabled:opacity-50"
            style={{ borderRadius: "var(--radius)" }}
          >
            {busy && state.fmt === fmt ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.5} aria-hidden />
            ) : (
              <Download className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />
            )}
            {label}
          </button>
        ))}
      </div>
      <p className="font-mono text-[10px] leading-[1.6] text-ink-3">
        每个按钮都会真的请求后端。此处不预先禁用任何格式——
        某个格式能不能导出，只有后端知道。
      </p>

      {state.s === "ok" ? (
        <div
          role="status"
          className="border border-rule bg-surface px-5 py-4"
          style={{ borderRadius: "var(--radius-card)" }}
        >
          <p className="font-mono text-[12px] text-ink-2">
            200 · {state.fmt} 已由后端渲染并下载 · {state.filename}
          </p>
        </div>
      ) : null}

      {/* 409：阻断导出 + 列出待处理块 */}
      {state.s === "blocked" ? (
        <div
          role="alert"
          className="border border-spark bg-spark-wash px-5 py-4"
          style={{ borderRadius: "var(--radius-card)" }}
        >
          <p className="flex items-center gap-2 font-mono text-[12px] text-spark">
            <TriangleAlert className="h-4 w-4" strokeWidth={1.5} aria-hidden />
            409 · {state.err.code} · 导出被后端挡住
          </p>
          <p className="mt-2 max-w-[42em] text-[13px] leading-[1.7] text-ink-2">
            存在未解决的阻断级复核块，后端拒绝导出 {state.fmt}。先处理下列块再重试。
          </p>
          <p className="mt-3 font-mono text-[11px] text-ink-2">
            blocking_block_ids ={" "}
            {state.ids.length > 0
              ? state.ids.map((id) => (
                  <a
                    key={id}
                    href={`/deliverables/${encodeURIComponent(deliverableId)}/edit#${id}`}
                    className="mr-1.5 underline decoration-spark/60 underline-offset-2"
                  >
                    {id}
                  </a>
                ))
              : "[]（后端未携块清单）"}
          </p>
        </div>
      ) : null}

      {/* 503：克制中性降级，不转圈不伪装 */}
      {state.s === "degraded" ? (
        <div
          role="status"
          className="border border-dashed border-rail bg-raised px-5 py-4"
          style={{ borderRadius: "var(--radius-card)" }}
        >
          <p className="flex items-center gap-2 font-mono text-[12px] text-ink-2">
            <CircleSlash className="h-4 w-4" strokeWidth={1.5} aria-hidden />
            503 · {state.err.code} · 该格式暂不可用
          </p>
          <p className="mt-2 max-w-[42em] text-[13px] leading-[1.7] text-ink-2">
            {state.fmt} 的渲染依赖当前不可用（pdf 需 GTK 运行库；vibe_pack 需 builder 接线）。
            可改用其它格式——报告内容本身不受影响。
          </p>
          <p className="mt-2 font-mono text-[10px] text-ink-3">{state.err.message}</p>
        </div>
      ) : null}

      {state.s === "error" ? (
        <div
          role="alert"
          className="border border-spark bg-spark-wash px-5 py-4"
          style={{ borderRadius: "var(--radius-card)" }}
        >
          <p className="font-mono text-[12px] text-spark">
            {state.err instanceof FlintApiError
              ? `${state.err.status} · ${state.err.code}`
              : state.err instanceof FlintNetworkError
                ? "后端不可达"
                : "导出失败"}
          </p>
          <p className="mt-2 text-[13px] leading-[1.7] text-ink-2">
            {state.err instanceof Error ? state.err.message : String(state.err)}
          </p>
        </div>
      ) : null}

      {/* 块清单：409 命中的块高亮（清单 21 的「高亮 blocking_block_ids」） */}
      <section
        className="border border-rule bg-surface"
        style={{ borderRadius: "var(--radius-card)" }}
      >
        <header className="border-b border-rule px-5 py-3">
          <h2 className="text-[13px] font-medium text-ink">块清单 · {blocks.length}</h2>
          <p className="mt-1 font-mono text-[11px] text-ink-3">
            复核等级取自后端 needs_review + review_severity；blocking 挡导出，advisory 不挡。
          </p>
        </header>
        <ul>
          {blocks.map((b) => {
            const hit = blockedIds.includes(b.block_id);
            const blocking = b.review_severity === "blocking";
            const advisory = b.review_severity === "advisory";
            return (
              <li
                key={b.block_id}
                id={b.block_id}
                className={`flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-rule px-5 py-2.5 last:border-b-0 ${
                  hit ? "bg-spark-wash" : ""
                }`}
              >
                <span className="break-all font-mono text-[11px] text-ink-2">
                  {b.block_id} · {b.content.kind}
                </span>
                <span className="font-mono text-[11px]">
                  {blocking ? (
                    <span className="inline-flex items-center gap-1 text-spark">
                      <span className="h-2 w-2 rounded-[1px] bg-spark" aria-hidden />
                      blocking · 挡导出
                    </span>
                  ) : advisory ? (
                    <span className="text-ink-2">advisory · 不挡导出</span>
                  ) : (
                    <span className="text-ink-3">—</span>
                  )}
                  {hit ? <span className="ml-2 text-spark">← 本次 409 命中</span> : null}
                </span>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
