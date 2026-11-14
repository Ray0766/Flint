// P3 combo 组装器（client）· POST /projects/combo
//
// 铁律落到本件（批次一字段对照表 + 技术约束清单第 12 条）：
// - **卡数 2~5、假设非空**，不合规 → 提交按钮 disabled，并写明还差什么。
// - **degraded == true → 必须明示「部分主题为降级生成」**。
//   这个字段此前全站没有任何屏能渲染，本批补上（owner 点名项）。
// - 400 / 422 各自成屏，说清「发生了什么 / 怎么办」，且**用户的选卡与假设保留不丢**。
// - 提交中不画百分比进度（后端没有进度数据），只说在等什么。
// - 跨簇是允许的（关联假设 = 跨热点联想），NEVER 限制同簇。
"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { CircleAlert, Loader2, TriangleAlert } from "lucide-react";
import { createCombo, FlintApiError, FlintNetworkError } from "@/lib/api";
import type { ComboCreateResponse, EvidenceCard } from "@/lib/types";

export interface CardGroup {
  id: string;
  name: string;
  cards: EvidenceCard[];
}

type SubmitState =
  | { status: "idle" }
  | { status: "pending" }
  | { status: "ok"; res: ComboCreateResponse }
  | { status: "error"; err: unknown };

const MIN_CARDS = 2;
const MAX_CARDS = 5;

export function ComboComposer({
  groups,
  day,
  totalClusters,
  shownClusters,
  loadError,
}: {
  groups: CardGroup[];
  day: string;
  totalClusters: number;
  shownClusters: number;
  loadError: boolean;
}) {
  const [picked, setPicked] = useState<string[]>([]);
  const [hypothesis, setHypothesis] = useState("");
  const [state, setState] = useState<SubmitState>({ status: "idle" });

  const byId = useMemo(() => {
    const m = new Map<string, { card: EvidenceCard; clusterName: string }>();
    for (const g of groups) for (const c of g.cards) m.set(c.card_id, { card: c, clusterName: g.name });
    return m;
  }, [groups]);

  const countOk = picked.length >= MIN_CARDS && picked.length <= MAX_CARDS;
  const hypoOk = hypothesis.trim().length > 0;
  const canSubmit = countOk && hypoOk && state.status !== "pending";

  const validationMsg = !countOk
    ? picked.length < MIN_CARDS
      ? `还需选 ${MIN_CARDS - picked.length} 张卡（需 ${MIN_CARDS}~${MAX_CARDS} 张）`
      : `已超上限，请取消 ${picked.length - MAX_CARDS} 张（需 ${MIN_CARDS}~${MAX_CARDS} 张）`
    : !hypoOk
      ? "关联假设不能为空"
      : "";

  const toggle = (id: string) =>
    setPicked((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));

  const submit = async () => {
    setState({ status: "pending" });
    try {
      const res = await createCombo(picked, hypothesis.trim());
      setState({ status: "ok", res });
    } catch (err) {
      setState({ status: "error", err });
    }
  };

  // ── 成功屏：响应 200 逐字段呈现，degraded 明示 ──
  if (state.status === "ok") {
    const { res } = state;
    return (
      <main className="mx-auto max-w-[820px] px-5 py-10">
        <h1 className="font-display text-[28px] font-medium text-ink">已生成候选主题</h1>
        <p className="mt-2 font-mono text-[11px] text-ink-3">
          响应 200 · {"{project_id, topic_ids, degraded}"}
        </p>

        <dl
          className="mt-6 border border-rule bg-surface px-5 py-4"
          style={{ borderRadius: "var(--radius-card)" }}
        >
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <dt className="font-mono text-[11px] text-ink-3">project_id</dt>
            <dd className="tabular break-all font-mono text-[12px] text-ink">{res.project_id}</dd>
          </div>
          <div className="mt-4">
            <dt className="font-mono text-[11px] text-ink-3">topic_ids · {res.topic_ids.length}</dt>
            <dd className="mt-2 flex flex-col gap-1">
              {res.topic_ids.map((t) => (
                <span key={t} className="tabular break-all font-mono text-[12px] text-ink-2">
                  {t}
                </span>
              ))}
            </dd>
          </div>
        </dl>

        {/* degraded：本批补上的字段 —— true 时明示，false 时也如实说一句 */}
        {res.degraded ? (
          <div
            className="mt-4 border border-dashed border-rail bg-raised px-5 py-4"
            style={{ borderRadius: "var(--radius-card)" }}
            role="status"
          >
            <p className="flex items-center gap-2 font-mono text-[12px] text-ink-2">
              <CircleAlert className="h-4 w-4" strokeWidth={1.5} aria-hidden />
              degraded: true
            </p>
            <p className="mt-2 text-[13px] leading-[1.7] text-ink-2">
              部分主题为<strong className="font-medium text-ink">降级生成</strong>
              （本地模型降级兜底），完整性可能低于正常水平。这一位来自后端
              <span className="font-mono"> orchestrate_combo</span>，前端只据实标注、不自行判定。
            </p>
          </div>
        ) : (
          <p className="mt-4 font-mono text-[11px] text-ink-3">degraded: false（无降级生成）</p>
        )}

        <p className="mt-6 text-[13px] leading-[1.7] text-ink-3">
          主题列表（GET /projects/{"{id}"}/topics）属批次二，本批不建。
        </p>
        <button
          type="button"
          onClick={() => setState({ status: "idle" })}
          className="mt-6 inline-flex border border-rule px-4 py-2 font-mono text-[12px] text-ink-2 hover:border-rail"
          style={{ borderRadius: "var(--radius)" }}
        >
          返回继续编辑
        </button>
      </main>
    );
  }

  // ── 错误屏：说清发生了什么 / 怎么办；用户输入保留（picked 与 hypothesis 未被清空） ──
  if (state.status === "error") {
    const err = state.err;
    const isApi = err instanceof FlintApiError;
    const status = isApi ? err.status : null;
    const what =
      status === 400
        ? "所选证据卡中有卡不存在，或校验未过。"
        : status === 422
          ? "请求缺少必填字段或 X-User-Id 头，后端未处理。"
          : err instanceof FlintNetworkError
            ? "连不上后端（不是后端回了错，是链路断了）。"
            : "后端返回了一个未预期的错误。";
    return (
      <main className="mx-auto max-w-[820px] px-5 py-10">
        <div
          className="border border-rule bg-surface px-5 py-4"
          style={{ borderRadius: "var(--radius-card)" }}
          role="alert"
        >
          <p className="flex items-center gap-2 font-mono text-[12px] text-ink">
            <TriangleAlert className="h-4 w-4" strokeWidth={1.5} aria-hidden />
            {isApi ? `HTTP ${err.status} · ${err.code}` : "请求失败"}
          </p>
          <p className="mt-2 max-w-[42em] text-[13px] leading-[1.7] text-ink-2">
            发生了什么：{what}
            <br />
            怎么办：你的选卡与假设已保留；检查后重新提交。
          </p>
          {isApi ? (
            <p className="mt-2 break-all font-mono text-[11px] text-ink-3">{err.message}</p>
          ) : null}
          <button
            type="button"
            onClick={() => setState({ status: "idle" })}
            className="mt-4 inline-flex border border-ink bg-ink px-4 py-2 font-mono text-[12px] text-primary-foreground"
            style={{ borderRadius: "var(--radius)" }}
          >
            返回检查选卡
          </button>
        </div>
      </main>
    );
  }

  // ── 组装屏 ──
  return (
    <main className="mx-auto max-w-[1180px] px-5 py-10">
      <header className="mb-8 flex flex-col gap-3">
        <h1 className="font-display text-[31px] font-medium leading-[1.3] text-ink text-balance">
          combo · 跨簇关联
        </h1>
        <p className="max-w-[42em] text-[14px] leading-[1.8] text-ink-2">
          跨热点选 {MIN_CARDS}~{MAX_CARDS} 张证据卡，写一句关联假设。Flint 据此生成候选主题。
          跨簇是本入口的用意，NEVER 限制必须同簇。
        </p>
      </header>

      {loadError ? (
        <p className="font-mono text-[12px] text-ink-2">
          选卡来源取不到（GET /plaza/hot 失败）。此处不代填任何卡片。
        </p>
      ) : groups.length === 0 ? (
        <div className="gap-cut flex min-h-40 flex-col items-center justify-center gap-2 rounded-[4px] px-6 py-12">
          <p className="font-display text-[20px] text-ink-2">当日没有可选的证据卡</p>
          <p className="max-w-[30em] text-center text-[13px] leading-relaxed text-ink-3">
            {day} 的主榜簇里没有带证据卡的簇。这是真实空态，非错误。
          </p>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
          {/* 左：跨簇选卡 */}
          <section
            className="overflow-hidden border border-rule bg-surface"
            style={{ borderRadius: "var(--radius-card)" }}
          >
            <header className="border-b border-rule px-4 py-3">
              <h2 className="text-[14px] font-medium text-ink">跨簇选卡</h2>
              <p className="mt-1 font-mono text-[11px] text-ink-3">
                来源 GET /clusters/{"{id}"}/evidence-cards（样例日 {day}） · 当日主榜共{" "}
                {totalClusters} 簇，此处载入前 {shownClusters} 个有卡的簇
              </p>
            </header>
            <div className="flex flex-col">
              {groups.map((g) => (
                <div key={g.id} className="border-b border-rule px-4 py-4 last:border-b-0">
                  <p className="text-[13px] font-medium text-ink">{g.name}</p>
                  <p className="mt-0.5 break-all font-mono text-[10px] text-ink-3">{g.id}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {g.cards.map((c) => {
                      const on = picked.includes(c.card_id);
                      return (
                        <button
                          key={c.card_id}
                          type="button"
                          onClick={() => toggle(c.card_id)}
                          aria-pressed={on}
                          className={`border px-2.5 py-1.5 text-left font-mono text-[11px] transition-colors ${
                            on
                              ? "border-ink bg-ink text-primary-foreground"
                              : "border-rule text-ink-2 hover:border-rail"
                          }`}
                          style={{ borderRadius: "var(--radius)" }}
                        >
                          {c.card_id}
                          {on ? " · 已选" : ""}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* 右：选卡篮 + 假设 + 提交 */}
          <aside className="flex flex-col gap-4 lg:sticky lg:top-6 lg:self-start">
            <section
              className="border border-rule bg-surface p-4"
              style={{ borderRadius: "var(--radius-card)" }}
            >
              <div className="flex items-baseline justify-between gap-3">
                <h2 className="text-[13px] font-medium text-ink">
                  ① 选卡篮 card_ids · 需 {MIN_CARDS}~{MAX_CARDS} 张
                </h2>
                <span className="tabular font-mono text-[12px] text-ink-2">
                  {picked.length} / {MAX_CARDS}
                </span>
              </div>
              {picked.length === 0 ? (
                <p className="mt-3 text-[12px] leading-[1.7] text-ink-3">
                  选卡篮为空。从左侧跨簇选卡，或先到工作台逐簇挑选。
                </p>
              ) : (
                <ul className="mt-3 flex flex-col gap-1.5">
                  {picked.map((id) => {
                    const hit = byId.get(id);
                    return (
                      <li key={id} className="flex items-start justify-between gap-2">
                        <span className="min-w-0">
                          <span className="block break-all font-mono text-[11px] text-ink">{id}</span>
                          <span className="block text-[11px] text-ink-3">{hit?.clusterName ?? ""}</span>
                        </span>
                        <button
                          type="button"
                          onClick={() => toggle(id)}
                          aria-label={`取消 ${id}`}
                          className="shrink-0 border border-rule px-1.5 font-mono text-[11px] text-ink-3 hover:border-rail"
                          style={{ borderRadius: "var(--radius)" }}
                        >
                          ×
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            <section
              className="border border-rule bg-surface p-4"
              style={{ borderRadius: "var(--radius-card)" }}
            >
              <label htmlFor="hypothesis" className="text-[13px] font-medium text-ink">
                ② 关联假设 hypothesis · 一句话，非空
              </label>
              <textarea
                id="hypothesis"
                value={hypothesis}
                onChange={(e) => setHypothesis(e.target.value)}
                rows={4}
                placeholder="这几张卡放在一起，说明了什么？"
                className="mt-3 w-full resize-y border border-rule bg-background px-3 py-2 text-[13px] leading-[1.7] text-ink outline-none placeholder:text-ink-3 focus-visible:border-rail"
                style={{ borderRadius: "var(--radius)" }}
              />
            </section>

            {validationMsg !== "" ? (
              <p className="font-mono text-[11px] text-ink-2">{validationMsg}</p>
            ) : null}

            <button
              type="button"
              disabled={!canSubmit}
              onClick={() => void submit()}
              className="inline-flex items-center justify-center gap-2 border border-ink bg-ink px-5 py-3 text-[14px] font-medium text-primary-foreground transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
              style={{ borderRadius: "var(--radius-cta)" }}
            >
              {state.status === "pending" ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.5} aria-hidden />
                  生成中 · POST /projects/combo
                </>
              ) : (
                "敲下燧石 · 生成候选主题"
              )}
            </button>
            <p className="font-mono text-[10px] leading-[1.6] text-ink-3">
              本地模型生成，通常数秒到十几秒。此处不画百分比——后端没有进度数据。
            </p>

            <p className="text-[12px] leading-[1.7] text-ink-3">
              也可以先去{" "}
              <Link href="/plaza" className="text-indigo underline underline-offset-2">
                热点广场
              </Link>{" "}
              点簇看卡。
            </p>
          </aside>
        </div>
      )}
    </main>
  );
}
