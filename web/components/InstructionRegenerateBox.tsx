import type { JSX } from "react";
import { useState } from "react";
import type { Block } from "../lib/types";
import {
  availableBlockInterventions,
  regenerateBlockWithGuidance,
} from "../lib/interventionClient";
import { openJobStream, type JobStreamState } from "../lib/jobClient";
import { t } from "../lib/i18n";

// L2+ 块级指令式重生成框（FE-CORE-007）。非保护块旁写自然语言指令 → 调块级
// guided-regenerate 端点 → 复用 L1 openJobStream 流式挂载重生成块。
// S2-5：保护块（locked∨author=='user'∨user_modified）无框（availableBlockInterventions
// 保护块返回 []，不含 instruct_regenerate → 渲染 null）。新文案走 i18n key（④留缝）。
export function InstructionRegenerateBox({
  block,
  projectId,
  clientOpts,
  eventSourceImpl,
}: {
  block: Block;
  projectId: string;
  clientOpts?: { baseUrl?: string; fetchImpl?: typeof fetch };
  eventSourceImpl?: typeof EventSource;
}): JSX.Element | null {
  const [instruction, setInstruction] = useState("");
  const [stream, setStream] = useState<JobStreamState | null>(null);

  // S2-5 门控（hooks 之后）：保护块不含 instruct_regenerate → 无指令框。
  if (!availableBlockInterventions(block).includes("instruct_regenerate")) {
    return null;
  }

  async function submit(): Promise<void> {
    const jobId = await regenerateBlockWithGuidance(
      {
        deliverable_id: block.deliverable_id, section_id: block.section_id,
        project_id: projectId, block_id: block.block_id, guidance: instruction,
      },
      { userId: "self", ...clientOpts },
    );
    openJobStream(jobId, setStream, {
      EventSourceImpl: eventSourceImpl, baseUrl: clientOpts?.baseUrl ?? "",
    });
  }

  return (
    <div data-instruct-box="true" data-block-id={block.block_id}>
      <textarea
        data-testid="instruct-input"
        placeholder={t("instruct.placeholder")}
        value={instruction}
        onChange={(e) => setInstruction(e.target.value)}
      />
      <button data-testid="instruct-submit" onClick={() => void submit()}>
        {t("instruct.submit")}
      </button>
      {stream ? (
        <span data-testid="instruct-status">
          {stream.failedReason
            ? t("instruct.failed")
            : stream.done
              ? t("instruct.done")
              : t("instruct.streaming")}
        </span>
      ) : null}
    </div>
  );
}
