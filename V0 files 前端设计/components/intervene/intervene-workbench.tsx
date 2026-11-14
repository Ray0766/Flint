// P10 干预工作台（client）· 四动作真打后端
//
// 清单逐条：
// 20 受保护块 **不渲染**任何控件（不是 disabled）。门控唯一真相 availableBlockInterventions。
//    lock 成功（204）后该块**即时转保护、控件消失**（本地把 locked 置 true，与后端一致）。
// 21 advisory 可折叠、不阻断导出；blocking 阻断导出并高亮 —— 两者形态一眼可辨。
// 26 乐观锁：dispute 带 expected_version；409 LEDGER_CONFLICT 取 detail.current_version，
//    提示「账本已前进至版本 N，确认后重提」→ 二次带 confirmed_version。
//    **NEVER 静默重试、NEVER 丢用户已输入的内容**。
// 27 evidence 结果只显后端回值；alignment=="partial" 标「部分支持、未成事实」。
"use client";

import { useState } from "react";
import { CircleAlert, Eye, Lock, RefreshCw, TriangleAlert } from "lucide-react";
import {
  FlintApiError,
  fileDispute,
  injectEvidence,
  lockTarget,
  regenerateSection,
  type InjectResult,
} from "@/lib/api";
import { isProtected, type Block } from "@/lib/types";
import { availableBlockInterventions, protectionReason } from "@/lib/interventions-gate";

type Busy = { block: string; action: string } | null;

// 争议：一次提交的完整输入（409 后原样保留，NEVER 清空）
interface DisputeDraft {
  blockId: string;
  reason: string;
}

export function InterveneWorkbench({
  deliverableId,
  projectId,
  blocks: initialBlocks,
  ledgerVersion,
}: {
  deliverableId: string;
  projectId: string | null;
  blocks: Block[];
  ledgerVersion: number | null;
}) {
  const [blocks, setBlocks] = useState<Block[]>(initialBlocks);
  const [busy, setBusy] = useState<Busy>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [err, setErr] = useState<unknown>(null);

  // —— 争议（含乐观锁确认流） ——
  const [draft, setDraft] = useState<DisputeDraft | null>(null);
  const [conflict, setConflict] = useState<{ current: number | null } | null>(null);
  const [expected, setExpected] = useState<number>(ledgerVersion ?? 0);

  // —— 补证据 ——
  const [evidenceFor, setEvidenceFor] = useState<string | null>(null);
  const [evidenceRef, setEvidenceRef] = useState("");
  const [claimText, setClaimText] = useState("");
  const [injectRes, setInjectRes] = useState<InjectResult | null>(null);

  const protectedCount = blocks.filter(isProtected).length;

  const doLock = async (b: Block) => {
    if (projectId === null) return;
    setBusy({ block: b.block_id, action: "lock" });
    setErr(null);
    try {
      await lockTarget({
        target_id: b.block_id,
        scope: "block",
        deliverable_id: deliverableId,
        project_id: projectId,
      });
      // 204 成功 → 该块**即时转保护**，控件随之消失（门控函数据 locked 判定）
      setBlocks((cur) =>
        cur.map((x) => (x.block_id === b.block_id ? { ...x, locked: true } : x)),
      );
      setNotice(`已锁定 ${b.block_id}（204）· 该块转为保护块，干预控件已撤下`);
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(null);
    }
  };

  const doRegenerate = async (b: Block) => {
    if (projectId === null) return;
    setBusy({ block: b.block_id, action: "regenerate" });
    setErr(null);
    try {
      const res = await regenerateSection(
        deliverableId,
        b.section_id,
        { project_id: projectId, block_id: b.block_id },
      );
      setNotice(`已提交块级重生成作业 job_id · ${res.job_id}（后端派发，前端不预判结果）`);
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(null);
    }
  };

  const submitDispute = async (confirmedVersion?: number) => {
    if (projectId === null || draft === null) return;
    setBusy({ block: draft.blockId, action: "dispute" });
    setErr(null);
    try {
      await fileDispute(projectId, {
        dispute_id: `dsp-${draft.blockId}-${expected}`,
        deliverable_id: deliverableId,
        target_kind: "block",
        target_id: draft.blockId,
        reason_text: draft.reason,
        expected_version: expected,
        ...(confirmedVersion !== undefined ? { confirmed_version: confirmedVersion } : {}),
      });
      setNotice(`争议已登记 · ${draft.blockId}`);
      setDraft(null);
      setConflict(null);
    } catch (e) {
      if (e instanceof FlintApiError && e.status === 409 && e.code === "LEDGER_CONFLICT") {
        // **不静默重试**：把冲突摆给用户，输入原样保留
        setConflict({ current: e.currentVersion });
      } else {
        setErr(e);
      }
    } finally {
      setBusy(null);
    }
  };

  const submitEvidence = async () => {
    if (projectId === null || evidenceFor === null) return;
    setBusy({ block: evidenceFor, action: "evidence" });
    setErr(null);
    setInjectRes(null);
    try {
      const res = await injectEvidence(projectId, {
        evidence_kind: "url",
        content_ref: evidenceRef,
        claim_text: claimText,
        expected_version: expected,
      });
      setInjectRes(res); // 只显后端回值，前端不自判
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {projectId === null ? (
        <p
          className="border border-dashed border-rail bg-raised px-5 py-4 font-mono text-[12px] leading-[1.7] text-ink-2"
          style={{ borderRadius: "var(--radius-card)" }}
        >
          干预端点都需要 project_id（POST /projects/&#123;id&#125;/…），本页 URL 未带
          <span className="text-ink"> ?project_id=</span>。
          此处**不猜**该交付物属于哪个 project，故干预控件不渲染。
        </p>
      ) : null}

      <p className="font-mono text-[11px] text-ink-3">
        blocks · {blocks.length} · 其中受保护 {protectedCount}（这些块不渲染任何控件）
        {ledgerVersion !== null ? ` · ledger_version ${ledgerVersion}` : " · ledger_version 未知"}
      </p>

      {notice !== null ? (
        <p
          role="status"
          className="border border-rule bg-surface px-4 py-3 font-mono text-[12px] text-ink-2"
          style={{ borderRadius: "var(--radius)" }}
        >
          {notice}
        </p>
      ) : null}

      {err !== null ? (
        <div
          role="alert"
          className="border border-rule bg-surface px-4 py-3"
          style={{ borderRadius: "var(--radius)" }}
        >
          <p className="flex items-center gap-2 font-mono text-[12px] text-ink">
            <TriangleAlert className="h-4 w-4" strokeWidth={1.5} aria-hidden />
            {err instanceof FlintApiError ? `HTTP ${err.status} · ${err.code}` : "请求失败"}
          </p>
          <p className="mt-1 text-[13px] leading-[1.7] text-ink-2">
            {err instanceof Error ? err.message : String(err)}
          </p>
        </div>
      ) : null}

      {/* 乐观锁确认流（清单 26） */}
      {conflict !== null ? (
        <div
          role="alert"
          className="border border-rule bg-surface px-5 py-4"
          style={{ borderRadius: "var(--radius-card)" }}
        >
          <p className="font-mono text-[12px] text-ink">409 · LEDGER_CONFLICT</p>
          <p className="mt-2 max-w-[42em] text-[13px] leading-[1.7] text-ink-2">
            账本已前进至版本{" "}
            <span className="tabular font-mono text-ink">
              {conflict.current ?? "（后端未携带 current_version）"}
            </span>
            。你的争议理由**已保留**，未提交也未丢弃。确认后按新版本重提。
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={conflict.current === null}
              onClick={() => {
                if (conflict.current === null) return;
                setExpected(conflict.current);
                void submitDispute(conflict.current);
              }}
              className="border border-ink bg-ink px-4 py-2 font-mono text-[12px] text-primary-foreground disabled:opacity-40"
              style={{ borderRadius: "var(--radius)" }}
            >
              确认并带 confirmed_version 重提
            </button>
            <button
              type="button"
              onClick={() => setConflict(null)}
              className="border border-rule px-4 py-2 font-mono text-[12px] text-ink-2"
              style={{ borderRadius: "var(--radius)" }}
            >
              先不提交（保留输入）
            </button>
          </div>
        </div>
      ) : null}

      {/* 补证据结果（清单 27）：只显后端回值 */}
      {injectRes !== null ? (
        <div
          className={`border px-5 py-4 ${
            injectRes.alignment === "partial"
              ? "border-dashed border-rail bg-raised"
              : "border-rule bg-surface"
          }`}
          style={{ borderRadius: "var(--radius-card)" }}
          role="status"
        >
          <p className="font-mono text-[12px] text-ink">
            alignment · {injectRes.alignment} · fact_added {String(injectRes.fact_added)}
          </p>
          {injectRes.alignment === "partial" ? (
            <p className="mt-2 flex items-start gap-2 text-[13px] leading-[1.7] text-ink-2">
              <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.5} aria-hidden />
              <span>
                <strong className="font-medium text-ink">部分支持、未成事实</strong>
                ——契约上 partial 的 claim NEVER 被提升为 Fact，故本次未入账。
              </span>
            </p>
          ) : null}
          <p className="mt-2 font-mono text-[11px] text-ink-3">
            ledger_version {injectRes.ledger_version} · score_axis {injectRes.score_axis} ·
            attempts {injectRes.attempts} · optin{" "}
            {String(injectRes.user_evidence_verdict_optin)}
          </p>
          <p className="mt-1 font-mono text-[10px] text-ink-3">
            以上逐字取自后端响应，前端不自判对齐结果。
          </p>
        </div>
      ) : null}

      {/* 块列表 */}
      <div className="flex flex-col gap-3">
        {blocks.map((b) => {
          const actions = availableBlockInterventions(b);
          const reason = protectionReason(b);
          const blocking = b.review_severity === "blocking";
          const advisory = b.review_severity === "advisory";
          return (
            <article
              key={b.block_id}
              className={`border p-4 ${
                blocking ? "border-spark bg-spark-wash" : "border-rule bg-surface"
              }`}
              style={{ borderRadius: "var(--radius-card)" }}
            >
              <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
                <span className="break-all font-mono text-[11px] text-ink-2">
                  {b.block_id} · {b.content.kind} · section {b.section_id}
                </span>
                <span className="flex flex-wrap items-center gap-2">
                  {/* 21：两级复核一眼可辨——blocking 实心 spark 方块，advisory 中空 Eye */}
                  {blocking ? (
                    <span className="inline-flex items-center gap-1 font-mono text-[11px] text-spark">
                      <span className="h-2 w-2 rounded-[1px] bg-spark" aria-hidden />
                      阻断 · 挡导出
                    </span>
                  ) : advisory ? (
                    <span className="inline-flex items-center gap-1 font-mono text-[11px] text-ink-2">
                      <Eye className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />
                      提示 · 不挡导出
                    </span>
                  ) : null}
                  {reason !== null ? (
                    <span className="inline-flex items-center gap-1 border border-rail px-2 py-0.5 font-mono text-[10px] text-ink-2"
                      style={{ borderRadius: "var(--radius)" }}>
                      <Lock className="h-3 w-3" strokeWidth={1.5} aria-hidden />
                      保护块 · {reason}
                    </span>
                  ) : null}
                </span>
              </div>

              {/* 20：受保护 → actions 为空 → **整段控件区不渲染**（不是 disabled） */}
              {projectId !== null && actions.length > 0 ? (
                <div className="mt-3 flex flex-wrap gap-2 border-t border-rule pt-3">
                  {actions.includes("lock") ? (
                    <button
                      type="button"
                      disabled={busy !== null}
                      onClick={() => void doLock(b)}
                      className="inline-flex items-center gap-1.5 border border-rule px-3 py-1.5 font-mono text-[11px] text-ink-2 hover:border-rail disabled:opacity-40"
                      style={{ borderRadius: "var(--radius)" }}
                    >
                      <Lock className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />
                      锁定
                    </button>
                  ) : null}
                  {actions.includes("regenerate") ? (
                    <button
                      type="button"
                      disabled={busy !== null}
                      onClick={() => void doRegenerate(b)}
                      className="inline-flex items-center gap-1.5 border border-rule px-3 py-1.5 font-mono text-[11px] text-ink-2 hover:border-rail disabled:opacity-40"
                      style={{ borderRadius: "var(--radius)" }}
                    >
                      <RefreshCw className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />
                      重生成本块
                    </button>
                  ) : null}
                  {actions.includes("dispute") ? (
                    <button
                      type="button"
                      disabled={busy !== null}
                      onClick={() =>
                        setDraft({ blockId: b.block_id, reason: draft?.reason ?? "" })
                      }
                      className="inline-flex items-center gap-1.5 border border-rule px-3 py-1.5 font-mono text-[11px] text-ink-2 hover:border-rail disabled:opacity-40"
                      style={{ borderRadius: "var(--radius)" }}
                    >
                      争议
                    </button>
                  ) : null}
                  <button
                    type="button"
                    disabled={busy !== null}
                    onClick={() => setEvidenceFor(b.block_id)}
                    className="inline-flex items-center gap-1.5 border border-rule px-3 py-1.5 font-mono text-[11px] text-ink-2 hover:border-rail disabled:opacity-40"
                    style={{ borderRadius: "var(--radius)" }}
                  >
                    补证据
                  </button>
                </div>
              ) : projectId !== null ? (
                <p className="mt-3 border-t border-rule pt-3 font-mono text-[11px] text-ink-3">
                  受保护 · 不提供编辑控件（控件未渲染，非置灰）
                </p>
              ) : null}

              {/* 争议输入（输入保留在 draft 里，409 不清空） */}
              {draft?.blockId === b.block_id ? (
                <div className="mt-3 border-t border-rule pt-3">
                  <label className="font-mono text-[11px] text-ink-3" htmlFor={`d-${b.block_id}`}>
                    争议理由 · expected_version {expected}
                  </label>
                  <textarea
                    id={`d-${b.block_id}`}
                    rows={3}
                    value={draft.reason}
                    onChange={(e) => setDraft({ ...draft, reason: e.target.value })}
                    className="mt-2 w-full border border-rule bg-background px-3 py-2 text-[13px] text-ink outline-none focus-visible:border-rail"
                    style={{ borderRadius: "var(--radius)" }}
                  />
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      disabled={draft.reason.trim() === "" || busy !== null}
                      onClick={() => void submitDispute()}
                      className="border border-ink bg-ink px-3 py-1.5 font-mono text-[11px] text-primary-foreground disabled:opacity-40"
                      style={{ borderRadius: "var(--radius)" }}
                    >
                      提交争议
                    </button>
                    <button
                      type="button"
                      onClick={() => setDraft(null)}
                      className="border border-rule px-3 py-1.5 font-mono text-[11px] text-ink-2"
                      style={{ borderRadius: "var(--radius)" }}
                    >
                      取消
                    </button>
                  </div>
                </div>
              ) : null}

              {/* 补证据输入 */}
              {evidenceFor === b.block_id ? (
                <div className="mt-3 border-t border-rule pt-3">
                  <p className="font-mono text-[11px] text-ink-3">
                    补证据 · expected_version {expected} · evidence_kind url
                  </p>
                  <input
                    value={evidenceRef}
                    onChange={(e) => setEvidenceRef(e.target.value)}
                    placeholder="证据 URL"
                    className="mt-2 w-full border border-rule bg-background px-3 py-2 font-mono text-[12px] text-ink outline-none focus-visible:border-rail"
                    style={{ borderRadius: "var(--radius)" }}
                  />
                  <input
                    value={claimText}
                    onChange={(e) => setClaimText(e.target.value)}
                    placeholder="这条证据支持的断言"
                    className="mt-2 w-full border border-rule bg-background px-3 py-2 text-[13px] text-ink outline-none focus-visible:border-rail"
                    style={{ borderRadius: "var(--radius)" }}
                  />
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      disabled={
                        evidenceRef.trim() === "" || claimText.trim() === "" || busy !== null
                      }
                      onClick={() => void submitEvidence()}
                      className="border border-ink bg-ink px-3 py-1.5 font-mono text-[11px] text-primary-foreground disabled:opacity-40"
                      style={{ borderRadius: "var(--radius)" }}
                    >
                      提交证据
                    </button>
                    <button
                      type="button"
                      onClick={() => setEvidenceFor(null)}
                      className="border border-rule px-3 py-1.5 font-mono text-[11px] text-ink-2"
                      style={{ borderRadius: "var(--radius)" }}
                    >
                      取消
                    </button>
                  </div>
                  <p className="mt-2 font-mono text-[10px] leading-[1.6] text-ink-3">
                    对齐由后端判定（stage=verdict）。partial 不入账——界面只如实转述结果。
                  </p>
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
    </div>
  );
}
