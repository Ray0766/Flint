import type { JSX } from "react";
import { useState } from "react";
import type { Block } from "../lib/types";
import {
  availableBlockInterventions,
  lockTarget,
  regenerateSection,
  disputeTarget,
  DisputeConfirmationRequired,
  type ClientOpts,
} from "../lib/interventionClient";
import { openJobStream, type JobStreamState } from "../lib/jobClient";
import { t } from "../lib/i18n/t";

// L2 干预面板（块级）。S2-5：保护块渲染只读态、无任何改写控件。
// regenerate 复用 L1 openJobStream 流式挂载；dispute 走 409 确认流；
// needs_review/stale 语义只反映后端回值（本面板不自判）。
export function BlockInterventionPanel({
  block,
  projectId,
  ledgerVersion,
  onLocked,
  clientOpts,
  eventSourceImpl,
}: {
  block: Block;
  projectId: string;
  ledgerVersion: number;
  onLocked?: (block: Block) => void;
  clientOpts?: { baseUrl?: string; fetchImpl?: typeof fetch };
  eventSourceImpl?: typeof EventSource;
}): JSX.Element {
  const opts: ClientOpts = { userId: "self", ...clientOpts };
  const actions = availableBlockInterventions(block);

  const [regenStatus, setRegenStatus] = useState<JobStreamState | null>(null);
  const [reason, setReason] = useState("");
  const [confirmVersion, setConfirmVersion] = useState<number | null>(null);
  const [disputeLedger, setDisputeLedger] = useState<number | null>(null);

  // S2-5：保护块——只读，NEVER 出改写控件。
  if (actions.length === 0) {
    return <div data-intervention-protected="true">{t("block.protected.readonly")}</div>;
  }

  async function onLock(): Promise<void> {
    await lockTarget(
      { target_id: block.block_id, scope: "block", deliverable_id: block.deliverable_id, project_id: projectId },
      opts,
    );
    onLocked?.({ ...block, locked: true });
  }

  async function onRegenerate(): Promise<void> {
    const jobId = await regenerateSection(
      { deliverable_id: block.deliverable_id, section_id: block.section_id, project_id: projectId },
      opts,
    );
    openJobStream(jobId, setRegenStatus, {
      EventSourceImpl: eventSourceImpl,
      baseUrl: clientOpts?.baseUrl ?? "",
    });
  }

  async function submitDispute(confirmedVersion?: number): Promise<void> {
    try {
      const out = await disputeTarget(
        projectId,
        {
          dispute_id: `dp-${block.block_id}`,
          deliverable_id: block.deliverable_id,
          target_kind: "block",
          target_id: block.block_id,
          reason_text: reason,
          expected_version: ledgerVersion,
          confirmed_version: confirmedVersion,
        },
        opts,
      );
      setConfirmVersion(null);
      setDisputeLedger(out.ledger_version);
    } catch (err) {
      if (err instanceof DisputeConfirmationRequired) {
        setConfirmVersion(err.currentVersion); // 账本前进 → 请用户确认当前版本
        return;
      }
      throw err;
    }
  }

  return (
    <div data-intervention-panel="true" data-block-id={block.block_id}>
      <button data-action="lock" data-testid="lock" onClick={() => void onLock()}>
        {t("block.action.lock")}
      </button>
      <button data-action="regenerate" data-testid="regenerate" onClick={() => void onRegenerate()}>
        {t("block.action.regenerate")}
      </button>
      {regenStatus ? (
        <span data-testid="regenerate-status">{regenStatus.status ?? ""}</span>
      ) : null}

      <textarea
        data-testid="dispute-reason"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
      />
      <button data-action="dispute" data-testid="dispute" onClick={() => void submitDispute()}>
        {t("block.action.dispute")}
      </button>
      {confirmVersion !== null ? (
        <button
          data-testid="dispute-confirm"
          onClick={() => void submitDispute(confirmVersion)}
        >
          {t("block.ledger.advanced", { version: confirmVersion })}
        </button>
      ) : null}
      {disputeLedger !== null ? (
        <span data-testid="dispute-done">{t("block.dispute.done", { version: disputeLedger })}</span>
      ) : null}
    </div>
  );
}
