// P6 发起分析表单（client）· POST /projects/{id}/analysis
//
// 纪律：
// - **主题强制单选、无默认**：不替用户预选（除非用户是从某个主题点进来的，
//   那是用户的显式意图，URL 里带着 ?topic_id=）。chosen_topic_id 只做「后端已选」标注，
//   NEVER 自动当成本次分析的选择。
// - budget_cny 是契约必填项，如实做成输入框并说明它是什么；NEVER 偷偷写死一个数替用户决定。
// - Idempotency-Key：同一 key 重复提交回同一个 job_id。这里在首次挂载时生成一枚并显示出来，
//   让「重复点击不会造出第二个 job」这件事可见。
// - 提交后跳到 job 屏（P7/P8 同一路由），**由后端事实决定看到进度还是判定**。
// - 失败如实抬起，用户已填内容不丢。
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { CircleDashed, Loader2, TriangleAlert } from "lucide-react";
import { submitAnalysis, FlintApiError, FlintNetworkError } from "@/lib/api";
import type { Topic } from "@/lib/types";

type SubmitState =
  | { status: "idle" }
  | { status: "pending" }
  | { status: "error"; err: unknown };

const DEFAULT_BUDGET = 5;

export function AnalysisSubmitForm({
  projectId,
  topics,
  chosenTopicId,
  preselectTopicId,
  loadError,
}: {
  projectId: string;
  topics: Topic[];
  chosenTopicId: string | null;
  preselectTopicId: string | null;
  loadError: boolean;
}) {
  const router = useRouter();
  // 只有用户从某个主题点进来（URL 带 topic_id）才预选；否则**无默认**。
  const [picked, setPicked] = useState<string | null>(
    preselectTopicId !== null && topics.some((t) => t.topic_id === preselectTopicId)
      ? preselectTopicId
      : null,
  );
  const [budget, setBudget] = useState<string>(String(DEFAULT_BUDGET));
  const [state, setState] = useState<SubmitState>({ status: "idle" });

  // 幂等键：一次挂载一枚，重复提交回同一个 job_id（后端 (principal,key) 唯一）。
  // **MUST 在客户端挂载后生成**：随机值若参与 SSR，服务端与客户端会渲染出不同字符串
  // → hydration mismatch（本轮实测踩到，探针的控制台断言抓住了它）。
  const [idemKey, setIdemKey] = useState<string | null>(null);
  useEffect(() => {
    setIdemKey(`p6-${projectId}-${Math.random().toString(36).slice(2, 10)}`);
  }, [projectId]);

  const budgetNum = Number(budget);
  const budgetOk = budget.trim() !== "" && Number.isFinite(budgetNum) && budgetNum > 0;
  const canSubmit =
    picked !== null && budgetOk && idemKey !== null && state.status !== "pending";

  const submit = async () => {
    if (picked === null || idemKey === null) return;
    setState({ status: "pending" });
    try {
      const res = await submitAnalysis(
        projectId,
        { topic_id: picked, budget_cny: budgetNum, locale: "zh-CN" },
        { idempotencyKey: idemKey },
      );
      router.push(`/gate/${encodeURIComponent(res.job_id)}`);
    } catch (err) {
      setState({ status: "error", err });
    }
  };

  if (loadError) {
    return (
      <main className="mx-auto max-w-[900px] px-5 py-10">
        <p className="font-mono text-[12px] text-ink-2">
          主题清单取不到（GET /projects/{projectId}/topics 失败）。此处不代填任何主题。
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-[900px] px-5 py-10">
      <header className="mb-8 flex flex-col gap-3">
        <Link
          href={`/projects/${encodeURIComponent(projectId)}/topics`}
          className="font-mono text-[11px] text-ink-2 hover:text-ink"
        >
          ← 候选主题
        </Link>
        <h1 className="font-display text-[31px] font-medium leading-[1.3] text-ink text-balance">
          发起 Gate① 分析
        </h1>
        <p className="break-all font-mono text-[11px] text-ink-3">project_id · {projectId}</p>
        <p className="max-w-[42em] text-[14px] leading-[1.8] text-ink-2">
          选一个主题并给出预算上限。带 <code className="text-[13px] text-ink">topic_id</code> 提交时，
          关键词由后端从该主题派生（前端不代拼关键词）。
        </p>
      </header>

      {topics.length === 0 ? (
        <div className="gap-cut flex min-h-40 flex-col items-center justify-center gap-2 rounded-[4px] px-6 py-12">
          <p className="font-display text-[20px] text-ink-2">该项目暂无候选主题</p>
          <p className="max-w-[30em] text-center text-[13px] leading-relaxed text-ink-3">
            没有主题就无从发起分析。这是真实空态，不是错误。
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {/* ① 选主题：强制单选、无默认 */}
          <section
            className="border border-rule bg-surface p-5"
            style={{ borderRadius: "var(--radius-card)" }}
          >
            <h2 className="text-[14px] font-medium text-ink">① 选一个主题 · 单选，无默认</h2>
            <p className="mt-1 font-mono text-[11px] text-ink-3">
              后端 chosen_topic_id · {chosenTopicId ?? "null"}
              {chosenTopicId !== null ? "（这是项目里已选的主题，不代表本次分析的选择）" : ""}
            </p>
            <ul className="mt-4 flex flex-col gap-2">
              {topics.map((t) => {
                const on = picked === t.topic_id;
                const spec = t.why_now.speculative;
                return (
                  <li key={t.topic_id}>
                    <label
                      className={`flex cursor-pointer items-start gap-3 border p-3 transition-colors ${
                        on ? "border-ink bg-raised" : "border-rule hover:border-rail"
                      } ${spec ? "border-dashed" : ""}`}
                      style={{ borderRadius: "var(--radius)" }}
                    >
                      <input
                        type="radio"
                        name="topic"
                        value={t.topic_id}
                        checked={on}
                        onChange={() => setPicked(t.topic_id)}
                        className="mt-1 accent-current"
                      />
                      <span className="min-w-0 flex-1">
                        <span className="flex flex-wrap items-center gap-2">
                          {spec ? (
                            <span className="inline-flex items-center gap-1 font-mono text-[10px] text-ink-3">
                              <CircleDashed className="h-3 w-3" strokeWidth={1.5} aria-hidden />
                              推测
                            </span>
                          ) : null}
                          {t.topic_id === chosenTopicId ? (
                            <span className="font-mono text-[10px] text-ink-3">已选主题</span>
                          ) : null}
                        </span>
                        <span
                          className={`mt-1 block text-[14px] leading-[1.6] ${spec ? "text-ink-2" : "text-ink"}`}
                        >
                          {t.one_liner}
                        </span>
                        <span className="mt-1 block break-all font-mono text-[10px] text-ink-3">
                          {t.topic_id}
                        </span>
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </section>

          {/* ② 预算：契约必填，如实要求用户给 */}
          <section
            className="border border-rule bg-surface p-5"
            style={{ borderRadius: "var(--radius-card)" }}
          >
            <label htmlFor="budget" className="text-[14px] font-medium text-ink">
              ② 预算上限 budget_cny · 契约必填
            </label>
            <p className="mt-1 text-[12px] leading-[1.7] text-ink-3">
              作业的成本上限（人民币）。后端按它记账并在超限时停下。
              界面不替你决定这个数，也不显示任何「预计花费」——后端没给预估值。
            </p>
            <input
              id="budget"
              type="number"
              min="0"
              step="0.5"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              className="tabular mt-3 w-40 border border-rule bg-background px-3 py-2 font-mono text-[13px] text-ink outline-none focus-visible:border-rail"
              style={{ borderRadius: "var(--radius)" }}
            />
            {!budgetOk && budget.trim() !== "" ? (
              <p className="mt-2 font-mono text-[11px] text-ink-2">budget_cny 需为大于 0 的数字</p>
            ) : null}
          </section>

          {/* 幂等键：让「重复点不会造第二个 job」可见 */}
          <p className="break-all font-mono text-[10px] leading-[1.7] text-ink-3">
            Idempotency-Key · {idemKey ?? "（客户端挂载后生成）"}
            <br />
            同一把钥匙重复提交，后端回同一个 job_id（不会造出第二个作业）。
          </p>

          {state.status === "error" ? (
            <div
              className="border border-rule bg-surface px-5 py-4"
              style={{ borderRadius: "var(--radius-card)" }}
              role="alert"
            >
              <p className="flex items-center gap-2 font-mono text-[12px] text-ink">
                <TriangleAlert className="h-4 w-4" strokeWidth={1.5} aria-hidden />
                {state.err instanceof FlintApiError
                  ? `HTTP ${state.err.status} · ${state.err.code}`
                  : state.err instanceof FlintNetworkError
                    ? "后端不可达"
                    : "提交失败"}
              </p>
              <p className="mt-2 max-w-[42em] text-[13px] leading-[1.7] text-ink-2">
                {state.err instanceof Error ? state.err.message : String(state.err)}
              </p>
              <p className="mt-2 text-[12px] text-ink-3">你的选择与预算已保留，可直接重试。</p>
            </div>
          ) : null}

          {picked === null ? (
            <p className="font-mono text-[11px] text-ink-2">请先选一个主题</p>
          ) : null}

          <button
            type="button"
            disabled={!canSubmit}
            onClick={() => void submit()}
            className="inline-flex w-fit items-center justify-center gap-2 border border-ink bg-ink px-6 py-3 text-[14px] font-medium text-primary-foreground transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
            style={{ borderRadius: "var(--radius-cta)" }}
          >
            {state.status === "pending" ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.5} aria-hidden />
                提交中 · POST /projects/{projectId}/analysis
              </>
            ) : (
              "提交分析作业"
            )}
          </button>
          <p className="font-mono text-[10px] leading-[1.6] text-ink-3">
            提交后跳到该 job 的页面。看到进度还是判定，由后端当时的状态决定——界面不预判。
          </p>
        </div>
      )}
    </main>
  );
}
