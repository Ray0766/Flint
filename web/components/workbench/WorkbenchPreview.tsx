"use client";

import { useEffect, useState, type JSX } from "react";

import { API_BASE } from "../../lib/apiBase";
import { BlockTree } from "../BlockTree";
import { SseDisconnectNotice } from "../shell/SseDisconnectNotice";
import { WorkbenchCitations } from "./WorkbenchCitations";
import { DeliverableNotFound, fetchBlocks } from "../../lib/deliverableClient";
import { useJobStream } from "../../lib/useJobStream";
import { t } from "../../lib/i18n/t";
import type { Block, BlockType } from "../../lib/types";

/**
 * `WB-04`：右栏——计划书实时预览。
 *
 * ## 渲染复用既有那棵树，NEVER 另写一套
 *
 * `BlockTree`（分节 + 按 order 排）与 `BlockView`（八类各一只读组件 + 三通道
 * `DerefValue`）是 `FE-000`/`UI-01` 就在的件，**本卡一个字没改**它们——
 * 它们是 v0.4 已 verified 的实现（`DEC-021` 封版面），要改得停下报 owner。
 *
 * 另写一份的代价不是重复代码：`BlockView` 里写着「争议记号走几何印记
 * NEVER emoji」「图表零计算只引 chart_id」「保护块额外标注」这些**判定面**的
 * 决定，另写一份会把它们悄悄丢掉，而屏上看起来一样。
 *
 * ## 未知块型在**进那棵树之前**挑出来
 *
 * `BlockView` 的兜底是 `assertNever` —— 编译期穷尽保证，运行期**抛**。
 * 抛出去的后果是整屏空白：一个块型没见过，读者连已经写好的那几节都看不到。
 * 所以这里先按冻结件那八枚分一次，未知的**单独说清是哪一种**
 * （工单 acceptance 的阴性对照：NEVER 静默跳过）。
 *
 * ## 这一份预览从哪来
 *
 * 三个来源，按优先级：链刚产出的那一份（`deliverableId` 传进来）→
 * 地址栏 `?deliverable=`（打开一份已有的）→ 都没有就是空态。
 * **NEVER 在这里填一个夹具 id 冒充**：那样屏上写着「你的计划书」，
 * 而画出来的是夹具那一份（同形先例 `DEC-012`：猜一个 id 去问，不是去问真相）。
 *
 * ## 渐进出现走既有那一路
 *
 * `openJobStream` + `applyEvent` 的 `partial_block`（`lib/jobClient.ts`）——
 * 那一路自带 seq 去重与 `Last-Event-ID` 续订。断线用既有 `SseDisconnectNotice`
 * 如实说，**NEVER 静默停住**（停住的话屏上停在半截，而用户以为还在生成）。
 */

/** 冻结件 `BlockContent` 判别联合的八枚（`contracts/models.py`）。 */
const KNOWN: readonly BlockType[] = [
  "heading", "paragraph", "table", "chart", "declaration",
  "quality_card", "citation_list", "gap_notice",
];

export type WorkbenchPreviewProps = {
  /** 链刚产出的那一份。没有就退到地址栏参数。 */
  deliverableId?: string | null;
  /** 正在跑的那个作业：给它就订它的事件流（块一块一块到）。 */
  jobId?: string | null;
  /**
   * 把「现在看的是哪一份、它正文里真有哪些章」回给上面。
   *
   * 章节导航要这两样，而**去取数的是这里**——让导航自己再取一次的话，
   * 同一份文档会被问两遍，两处还会在某一帧显示不同的东西。
   */
  onDoc?: (doc: { deliverableId: string | null; sectionIds: string[] }) => void;
  /** 点选一块（`WB-06` 的批注面板对着它）。 */
  onPick?: (block: Block | null) => void;
  /** 当前点选的那一块的 id：屏上要看得出选中了哪一块。 */
  pickedBlockId?: string | null;
};

type State = "empty" | "loading" | "ready" | "failed" | "not_found";

export function WorkbenchPreview({
  deliverableId,
  jobId,
  onDoc,
  onPick,
  pickedBlockId,
}: WorkbenchPreviewProps): JSX.Element {
  const [wanted, setWanted] = useState<string | null>(deliverableId ?? null);
  const [watching, setWatching] = useState<string | null>(jobId ?? null);
  const [blocks, setBlocks] = useState<Block[] | null>(null);
  const [state, setState] = useState<State>(deliverableId ? "loading" : "empty");
  /* 订阅走既有的 `useJobStream`（`lib/useJobStream.ts`）——它包着
     `openJobStream` + `applyEvent`：seq 去重、`Last-Event-ID` 续订、
     终态自动 close 都在那里。自己再写一遍的话，重连那一段会少掉去重，
     而症状是「续订之后同一块出现两次」——在屏上看不出是重放。 */
  const stream = useJobStream(watching, { baseUrl: API_BASE });

  // 地址栏那一路只在没有链上产物时才看：链给的永远优先。
  useEffect(() => {
    if (deliverableId) {
      setWanted(deliverableId);
      return;
    }
    const fromUrl = new URLSearchParams(window.location.search).get("deliverable");
    if (fromUrl) setWanted(fromUrl);
  }, [deliverableId]);

  useEffect(() => {
    if (!wanted) {
      setState("empty");
      return;
    }
    let live = true;
    setState("loading");
    void fetchBlocks(wanted, API_BASE)
      .then((got) => {
        if (!live) return;
        setBlocks(got);
        setState("ready");
      })
      .catch((err: unknown) => {
        if (!live) return;
        // **「没这一份」与「读失败」分开**：前者该换一个 id，后者该去查后端。
        setState(err instanceof DeliverableNotFound ? "not_found" : "failed");
      });
    return () => { live = false; };
  }, [wanted]);

  // 事件流：作业 id 由上游给；地址栏那一路同样认（取证与「打开一份已有的」走同一条路）。
  useEffect(() => {
    if (jobId) {
      setWatching(jobId);
      return;
    }
    const fromUrl = new URLSearchParams(window.location.search).get("job");
    if (fromUrl) setWatching(fromUrl);
  }, [jobId]);

  const known = (blocks ?? []).filter((b) => KNOWN.includes(b.type));
  const unknown = (blocks ?? []).filter((b) => !KNOWN.includes(b.type));
  const sectionIds = [...new Set(known.map((b) => b.section_id))];

  // 章在**渲染出来的那些块**里数，NEVER 拿模板表当「正文里有这一章」——
  // 那样每一章都恒「有」，而「这一章还没写」正是导航要说的第一件事。
  useEffect(() => {
    onDoc?.({ deliverableId: wanted, sectionIds });
    // 以内容为依赖：`sectionIds` 每渲染都是新数组。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wanted, sectionIds.join(" ")]);

  /* 点选走**事件委托**：从点到的元素往上找最近的 `[data-block-id]`。
     往 `BlockTree` 里塞一个「批注」按钮才是蓝本的样子，但那个组件是
     v0.4 已 verified 的封版件（`DEC-021`）——改它要停下报 owner。
     委托一层不动它一个字，而选中的是**块自己带的那个 id**，不是我算的。 */
  const pick = (event: React.MouseEvent<HTMLDivElement>): void => {
    if (!onPick) return;
    const el = (event.target as HTMLElement).closest?.("[data-block-id]");
    const id = el?.getAttribute("data-block-id");
    onPick(id ? (blocks ?? []).find((b) => b.block_id === id) ?? null : null);
  };

  return (
    <div
      className="wb-doc"
      /* 记号叫 `data-wb-preview` 而不是 `data-wb-doc`：外壳那一层
         （`WorkbenchShell` 的 `.workbench__doc`）**已经**带着 `data-wb-doc="true"`，
         两个同名记号叠在一起时，取证 `querySelector` 拿到的是外面那个，
         于是「右栏现在是什么态」永远读回 null——一条永远量不到东西的判据。
         （`EYE-05` 现场逮到的。） */
      data-wb-preview="true"
      data-wb-doc-state={state}
      data-wb-doc-picked={pickedBlockId ?? ""}
      onClick={pick}
    >
      {/* 块到了几块**照事件流说的数**，NEVER 数屏上渲染了几个——
          后者是我们自己画了几个，不是链上报了几个。 */}
      {stream.arrivedBlockIds.length > 0 ? (
        <p
          className="wb-doc__progress"
          data-wb-doc-progress={stream.arrivedBlockIds.length}
          data-wb-doc-arrived={stream.arrivedBlockIds.join(" ")}
        >
          {t("wb.doc.arriving", { n: stream.arrivedBlockIds.length })}
        </p>
      ) : null}
      {stream.connection === "disconnected" ? <SseDisconnectNotice /> : null}

      {state === "empty" ? (
        <p className="workbench__placeholder" data-wb-doc-note="empty">
          {t("wb.doc.placeholder")}
        </p>
      ) : null}
      {state === "loading" ? (
        <p className="workbench__placeholder" data-wb-doc-note="loading">
          {t("wb.doc.loading")}
        </p>
      ) : null}
      {state === "failed" ? (
        <p className="workbench__placeholder" data-wb-doc-note="failed">
          {t("wb.doc.failed")}
        </p>
      ) : null}
      {state === "not_found" ? (
        <p className="workbench__placeholder" data-wb-doc-note="not_found">
          {t("wb.doc.not_found", { id: wanted ?? "" })}
        </p>
      ) : null}

      {unknown.map((block) => (
        <p
          key={block.block_id}
          className="wb-doc__unknown"
          data-wb-doc-unknown={block.type}
        >
          {t("wb.doc.unknown_type", { type: String(block.type) })}
        </p>
      ))}

      {state === "ready" ? <BlockTree blocks={known} /> : null}
      {state === "ready" ? <WorkbenchCitations blocks={known} /> : null}
    </div>
  );
}
