// DESIGN-12：评论层（G17，前端半）。
//
// **锚会失效，评论不会**。用户写下那句话时页面还长着另一个样子；后来那个元素被改没了，
// 评论就没了着落。此时把它藏起来，用户会以为自己的意见被系统吃掉了——
// 而它其实还在，只是钉不住原来那个位置。所以降级到坐标锚，并**明说**位置可能不准。
//
// 三种锚态：`element`（data-loc 还在）→ `point`（元素没了但有坐标）→ `orphan`
// （两者都没有）。orphan 仍然渲染，但不给「让 AI 处理」——一条指不出地方的意见
// 交给模型，只会让它凭空动手。
//
// **本层不改 HTML**：它只是覆在上面的一层。评论层去动产物，就会出现
// 「我只是写了句话，页面自己变了」。

import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

export type CommentInput = {
  commentId: string;
  text: string;
  /** 写下评论时元素的 data-loc */
  loc: string | null;
  /** 降级坐标（画布坐标系） */
  point: [number, number] | null;
  resolved: boolean;
};

export type ResolvedAnchor = {
  kind: "element" | "point" | "orphan";
  loc: string | null;
  point: [number, number] | null;
  degraded: boolean;
};

export function resolveAnchor(html: string, comment: CommentInput): ResolvedAnchor {
  const alive = comment.loc !== null && html.includes(`data-loc="${comment.loc}"`);
  if (alive) {
    return { kind: "element", loc: comment.loc, point: comment.point, degraded: false };
  }
  if (comment.point !== null) {
    return { kind: "point", loc: null, point: comment.point, degraded: true };
  }
  return { kind: "orphan", loc: null, point: null, degraded: true };
}

export type CommentLayerProps = {
  html: string;
  comments: CommentInput[];
  onRequestAi: (payload: {
    commentId: string;
    loc: string | null;
    point: [number, number] | null;
  }) => void;
};

export function CommentLayer({
  html,
  comments,
  onRequestAi,
}: CommentLayerProps): JSX.Element {
  const live = comments.filter((c) => !c.resolved);

  return (
    <div data-testid="design-comment-layer">
      {live.map((comment) => {
        const anchor = resolveAnchor(html, comment);
        return (
          <article
            key={comment.commentId}
            data-testid="design-comment"
            data-comment-id={comment.commentId}
            data-anchor-kind={anchor.kind}
            data-degraded={String(anchor.degraded)}
          >
            <p>{comment.text}</p>
            {anchor.degraded ? (
              <p data-testid="design-comment-degraded-note">
                {t("design.comment.degraded")}
              </p>
            ) : null}
            {anchor.kind === "orphan" ? null : (
              <button
                type="button"
                data-testid="design-comment-ai"
                onClick={() =>
                  onRequestAi({
                    commentId: comment.commentId,
                    loc: anchor.loc,
                    point: anchor.point,
                  })
                }
              >
                {t("design.comment.ask_ai")}
              </button>
            )}
          </article>
        );
      })}
    </div>
  );
}
