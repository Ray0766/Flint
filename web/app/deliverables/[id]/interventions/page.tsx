"use client";

import { use, type JSX } from "react";

import { API_BASE } from "../../../../lib/apiBase";
import { BlockInterventionPanel } from "../../../../components/BlockInterventionPanel";
import { ScreenFetchState } from "../../../../lib/ScreenFetchState";
import { Screen } from "../../../../components/shell/Screen";
import { isProtected, type Block } from "../../../../lib/types";
import { availableBlockInterventions } from "../../../../lib/interventionClient";
import { t } from "../../../../lib/i18n/t";
import { useScreenData } from "../../../../lib/useScreenData";

// CHAIN-05 / 蓝本 P10：干预页。**改前这一屏不存在**——
// `BlockInterventionPanel` 与 `interventionClient` 的四个动作都建好了，
// 而 `web/app/` 下没有任何屏在用它们（grep 零命中）。
//
// ## 受保护 block NEVER 被 regenerate 改写（`CLAUDE.md#S2-5`）
//
// 三者任一即受保护：`locked` ∨ `author === "user"` ∨ `user_modified`。
// **这条判断只有一处实现**：`lib/types.ts#isProtected`，
// `availableBlockInterventions` 据它给出可用动作（受保护 → 空表）。
// 本屏 NEVER 自己再判一次——判两次的话，两处规则会在某天分叉，
// 而分叉的那天用户会看到一个能点的重生成键，点下去改写了他自己写的段落。
//
// 屏上**明说拒绝原因**（卡面 acceptance②）：三种受保护各说各的话，
// 因为它们要用户做的事不同（解锁 / 这是你写的 / 你改过它）。
type BlocksResponse = { deliverable_id: string; blocks: Block[] };

/** 取这一块的开头一段。**原样截断，NEVER 改写**——改写过的摘要不是它本身。 */
function excerptOf(block: Block): string {
  const text = (block.content as { text?: unknown }).text;
  if (typeof text !== "string") return "";
  return text.length > 80 ? `${text.slice(0, 80)}…` : text;
}

function protectedReason(block: Block): string {
  // 顺序有意：`locked` 先判——一个既锁着又被用户改过的 block，
  // 用户要做的第一件事是解锁。三条 NEVER 合成一句「不可编辑」。
  if (block.locked) return t("intervention.protected.locked");
  if (block.author === "user") return t("intervention.protected.authored");
  return t("intervention.protected.modified");
}

export default function InterventionsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): JSX.Element {
  const { id } = use(params);
  const { state } = useScreenData<BlocksResponse>(`/deliverables/${id}/blocks`);

  return (
    <Screen title={t("intervention.title")} meta={t("intervention.meta")}>
      <ScreenFetchState state={state}>
        {(data) => (
          <ul className="intervention-list" data-intervention-list="true">
            {data.blocks.map((block) => (
              <li
                key={block.block_id}
                className="intervention-row"
                data-block-id={block.block_id}
                data-protected={isProtected(block) ? "true" : "false"}
                data-actions={String(availableBlockInterventions(block).length)}
              >
                {/* **内部 id 不上产品面**（`FB-10` 的 A 类，`no_scaffold_on_screen`
                    当场判红）。它留在 `data-block-id` 上供取证——取证认 id，人看内容。
                    这里显示的是**这一块自己的文字**：用户要判断「该不该重生成这一块」，
                    靠的正是它写了什么，而不是它叫什么。
                    没有文字的块（图表之类）就不显示这一槽（逐槽隐藏）。 */}
                {excerptOf(block) === "" ? null : (
                  <p className="intervention-row__excerpt">{excerptOf(block)}</p>
                )}
                {isProtected(block) ? (
                  // 受保护：**说清是哪一种**，NEVER 只把键灰掉了事。
                  <p
                    className="intervention-row__protected"
                    data-protected-reason={
                      block.locked ? "locked"
                        : block.author === "user" ? "authored" : "modified"
                    }
                  >
                    {protectedReason(block)}
                  </p>
                ) : (
                  <BlockInterventionPanel
                    block={block}
                    projectId={data.deliverable_id}
                    ledgerVersion={block.revision}
                    clientOpts={{ baseUrl: API_BASE }}
                  />
                )}
              </li>
            ))}
          </ul>
        )}
      </ScreenFetchState>
    </Screen>
  );
}
