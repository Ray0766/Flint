"use client";

import { useState, type JSX } from "react";

import { API_BASE, API_USER_ID } from "../../lib/apiBase";
import {
  availableBlockInterventions,
  regenerateBlockWithGuidance,
} from "../../lib/interventionClient";
import { t } from "../../lib/i18n/t";
import type { Block } from "../../lib/types";

/**
 * `WB-06`：对某一个块提批注 → **只重写那一个块**（蓝本原话）。
 *
 * ## 走既有干预层，NEVER 另开一条生成路
 *
 * 提交走 `interventionClient#regenerateBlockWithGuidance`
 * （`POST /deliverables/{}/sections/{}/regenerate`），保护判定走同一个模块的
 * `availableBlockInterventions`（`S2-5`：locked ∨ author==user ∨ user_modified）。
 * 两条生成路会让「这段文字是怎么来的」有两个答案。
 *
 * ## 三处刻意与既有件/蓝本不同，各有其因
 *
 * **一 · 没有直接用 `InstructionRegenerateBox`**（`FE-CORE-007` 那个既有框）。
 * 它提交完就 `openJobStream` 等终态——而这一族作业**不写任何事件、也不推
 * `jobs.state`**（实测：作业跑完了，`jobs` 仍是 `queued`，`job_events` 0 行；
 * 单 `docs/blocked/REGENERATE-JOB-WRITES-NO-EVENTS.md`）。
 * 照着用的话，屏上会一直转——那正是本仓点名要防的那一族病。
 * **复用的是它复用的那两样**：保护门与端点客户端。
 *
 * **二 · 蓝本把批注按钮放在每一块旁边**，本仓做成「点选一块 + 一个面板」：
 * 块是 `BlockTree`/`BlockView` 渲染的，那是 v0.4 已 verified 的封版件
 * （`DEC-021`），往它里面塞控件要停下报 owner。点选 + 面板不动它一个字。
 *
 * **三 · 提交完就停在「已提交」**，NEVER 假装知道它什么时候好。
 *
 * 我先写的是「轮项目的交付物清单，新出现的那一份就是产物」。**实测那条路不通**：
 * `GET /projects/{id}` 的 `deliverable_ids` 是 `projects` 表里一个**建项时写死的列**，
 * 组稿与重写落库时都不回写它——库里已经有四份交付物，那一列仍只有一条
 * （单 `docs/blocked/PROJECT-DOES-NOT-LIST-ITS-OWN-DELIVERABLES.md`）。
 *
 * 于是今天**没有任何一条路**能从「我提交了重写」走到「产物是哪一份」：
 * 作业不写状态也不写事件、端点不回产物 id、项目总览列不出新产出。
 * 三条都断着，所以屏上只说到「已提交」为止，并把作业 id 留在 `data-*` 上。
 *
 * **NEVER 由 `{原id}-r-{作业id}` 拼一个出来**——那个形状在库里确实成立，
 * 但它是实现细节；拼出来的那天它变了，屏上会去问一个不存在的东西
 * （`DEC-012` 判死过同形的手）。
 */

export type WorkbenchAnnotateProps = {
  /** 点选的那一块。没选就什么都不做。 */
  block: Block | null;
  /** 这份交付物属于哪个项目（链上来的，或地址栏 `?project=`）。 */
  projectId: string | null;
  /**
   * 重写产出新版本时把它交上去，预览换过去。
   *
   * **今天没有调用点**：从「提交了重写」到「产物是哪一份」的三条路全断着
   * （见组件头那三张单）。这条缝留着不删——解阻那天接回来的就是它，
   * 而删掉的话，下一个人会以为这一屏本来就不打算换预览。
   */
  onNewVersion?: (deliverableId: string) => void;
};

type Phase = "idle" | "sending" | "submitted" | "failed";

export function WorkbenchAnnotate({
  block,
  projectId,
  onNewVersion,
}: WorkbenchAnnotateProps): JSX.Element {
  const [guidance, setGuidance] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [note, setNote] = useState("");
  const [jobId, setJobId] = useState("");

  if (!block) {
    return (
      <div className="wb-annotate" data-wb-annotate="none">
        <p className="wb-annotate__hint">{t("wb.annotate.pick_first")}</p>
      </div>
    );
  }

  // `S2-5`：受保护的块**改不动**，且屏上说清为什么——
  // 把控件藏起来而不说的话，用户会以为这一块的批注功能坏了。
  const allowed = availableBlockInterventions(block).includes("instruct_regenerate");
  if (!allowed) {
    return (
      <div className="wb-annotate" data-wb-annotate="protected" data-wb-annotate-block={block.block_id}>
        <p className="wb-annotate__hint" data-wb-annotate-protected="true">
          {t("wb.annotate.protected")}
        </p>
      </div>
    );
  }

  async function submit(): Promise<void> {
    if (!block || !projectId || guidance.trim() === "") return;
    setPhase("sending");
    setNote("");
    try {
      const job = await regenerateBlockWithGuidance(
        {
          deliverable_id: block.deliverable_id, section_id: block.section_id,
          project_id: projectId, block_id: block.block_id, guidance,
        },
        { userId: API_USER_ID, baseUrl: API_BASE },
      );
      setJobId(job);
      setPhase("submitted");
      // 留痕：改了哪一块、批注是什么。**到此为止**——
      // 「好了没有」今天问不出来（见组件头），所以这里一个字都不多说。
      setNote(t("wb.annotate.submitted", { block: block.block_id, guidance }));
    } catch (err: unknown) {
      setPhase("failed");
      setNote(String(err));
    }
  }

  return (
    <div className="wb-annotate" data-wb-annotate="ready" data-wb-annotate-block={block.block_id}>
      <p className="wb-annotate__target" data-wb-annotate-type={block.type}>
        {t("wb.annotate.target", { type: block.type, section: block.section_id })}
      </p>
      <textarea
        className="wb-annotate__input"
        data-wb-annotate-input="true"
        rows={2}
        value={guidance}
        placeholder={t("wb.annotate.placeholder")}
        aria-label={t("wb.annotate.label")}
        onChange={(event) => setGuidance(event.target.value)}
      />
      <button
        type="button"
        className="wb-annotate__send"
        data-wb-annotate-submit="true"
        disabled={guidance.trim() === "" || !projectId || phase === "sending"}
        onClick={() => void submit()}
      >
        {t("wb.annotate.submit")}
      </button>
      {projectId ? null : (
        // 这一份是从地址栏打开的、没带项目：**说清缺的是什么**，
        // NEVER 猜一个项目 id 去提交（`DEC-012` 判死过同形的手）。
        <p className="wb-annotate__hint" data-wb-annotate-no-project="true">
          {t("wb.annotate.no_project")}
        </p>
      )}
      {phase !== "idle" ? (
        <p
          className="wb-annotate__status"
          data-wb-annotate-phase={phase}
          data-wb-annotate-job={jobId}
        >
          {phase === "sending" ? t("wb.annotate.sending") : note}
        </p>
      ) : null}
    </div>
  );
}
