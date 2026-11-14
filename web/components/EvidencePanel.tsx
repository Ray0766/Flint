import type { JSX } from "react";
import { useState } from "react";
import {
  injectEvidence,
  LedgerConflict,
  type ClientOpts,
  type EvidenceResult,
} from "../lib/interventionClient";
import { t } from "../lib/i18n/t";

// L2 evidence 动作（项目级 inject）。成功 → 展示后端对齐结果（只反映后端回值，
// NEVER 前端自判 alignment/fact_added）；409 自动重放耗尽 → 冲突提示当前版本。
export function EvidencePanel({
  projectId,
  expectedVersion,
  clientOpts,
}: {
  projectId: string;
  expectedVersion: number;
  clientOpts?: { baseUrl?: string; fetchImpl?: typeof fetch };
}): JSX.Element {
  const opts: ClientOpts = { userId: "self", ...clientOpts };
  const [kind, setKind] = useState<"file" | "url" | "text">("url");
  const [contentRef, setContentRef] = useState("");
  const [note, setNote] = useState("");
  const [claim, setClaim] = useState("");
  const [optin, setOptin] = useState(false);
  const [result, setResult] = useState<EvidenceResult | null>(null);
  const [conflict, setConflict] = useState<number | null>(null);

  async function submit(): Promise<void> {
    setResult(null);
    setConflict(null);
    try {
      const out = await injectEvidence(
        projectId,
        {
          evidence_kind: kind, content_ref: contentRef, note,
          claim_text: claim, expected_version: expectedVersion,
          user_evidence_optin: optin,
        },
        opts,
      );
      setResult(out);
    } catch (err) {
      if (err instanceof LedgerConflict) {
        setConflict(err.currentVersion);
        return;
      }
      throw err;
    }
  }

  return (
    <div data-evidence-panel="true">
      <select data-testid="ev-kind" value={kind}
        onChange={(e) => setKind(e.target.value as "file" | "url" | "text")}>
        <option value="file">file</option>
        <option value="url">url</option>
        <option value="text">text</option>
      </select>
      <input data-testid="ev-content-ref" value={contentRef}
        onChange={(e) => setContentRef(e.target.value)} />
      <input data-testid="ev-note" value={note}
        onChange={(e) => setNote(e.target.value)} />
      <input data-testid="ev-claim" value={claim}
        onChange={(e) => setClaim(e.target.value)} />
      <input data-testid="ev-optin" type="checkbox" checked={optin}
        onChange={(e) => setOptin(e.target.checked)} />
      <button data-testid="ev-submit" onClick={() => void submit()}>{t("evidence.submit")}</button>
      {result ? (
        <div data-testid="ev-result">
          {result.alignment} · fact_added={String(result.fact_added)} ·{" "}
          {t("evidence.ledger_version", {
            version: result.ledger_version,
            attempts: result.attempts,
          })}
        </div>
      ) : null}
      {conflict !== null ? (
        <div data-testid="ev-conflict">{t("evidence.conflict", { version: conflict })}</div>
      ) : null}
    </div>
  );
}
