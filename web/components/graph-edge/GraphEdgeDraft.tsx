// GRAPH-07：连线草稿 + 强制假设（F7/F8，前端这一半）。
//
// 松手先弹假设框、写了才落盘。**空值不发请求**的理由不是省一次往返：
// 让请求飞出去再被 422 弹回来，用户看到的是一次失败，而他其实只是还没写；
// 更糟的是画布上那根线该不该留——发出去了就得处理「服务端拒了但线还在」的中间态。
// 不发，就没有这个中间态。
//
// 服务端那一道是**独立的**一道（`POST /workbenches/{id}/edges` → 422 EMPTY_HYPOTHESIS），
// 不是这一道的回声：curl 一发照样能建空假设边，所以两道都要在。
//
// 有向：from → to 原样送出，两端不可互换（I8）。
//
// 提交失败时**不清空用户写的那句话**：清掉等于让他重写一遍，而他多半只需要改一个词。

import type { JSX } from "react";
import { useState } from "react";

import { t } from "../../lib/i18n/t";
import { pushUndo } from "../../lib/undo/undoStack";

export type EdgeDraftPayload = {
  fromNodeId: string;
  toNodeId: string;
  hypothesis: string;
};

export type GraphEdgeDraftProps = {
  fromNodeId: string;
  toNodeId: string;
  onCreate: (payload: EdgeDraftPayload) => Promise<unknown>;
  onCancel?: () => void;
  /**
   * 撤销这次建边（把边删掉）。**没给就不入 undo 栈**：
   * 删不掉的边，撤销只能失败——而入了栈就等于向用户承诺这一步撤得掉。
   */
  onUndoCreate?: (payload: EdgeDraftPayload) => Promise<void>;
};

export function GraphEdgeDraft({
  fromNodeId,
  toNodeId,
  onCreate,
  onCancel,
  onUndoCreate,
}: GraphEdgeDraftProps): JSX.Element {
  const [hypothesis, setHypothesis] = useState("");
  const [missing, setMissing] = useState(false);
  const [failed, setFailed] = useState(false);
  const [sending, setSending] = useState(false);

  const submit = (): void => {
    if (hypothesis.trim() === "") {
      setMissing(true);              // 本地拦下：一个请求都不发
      return;
    }
    if (sending) return;             // 连点两下只发一次
    setMissing(false);
    setSending(true);
    const payload: EdgeDraftPayload = { fromNodeId, toNodeId, hypothesis };
    void onCreate(payload)
      .then(() => {
        setFailed(false);
        // 建**成功**才入栈。空假设被本地拦下时连请求都没发，更没有东西要撤。
        if (onUndoCreate === undefined) return;
        pushUndo({
          view: "graph",
          label: "add-edge",
          undo: () => onUndoCreate(payload),
        });
      })
      .catch(() => {
        setFailed(true);             // 草稿留着：改一个词就能再提交
      })
      .finally(() => {
        setSending(false);
      });
  };

  return (
    <div data-testid="graph-edge-draft" data-from={fromNodeId} data-to={toNodeId}>
      <label>
        {t("graph.edge.hypothesis.label")}
        <input
          data-testid="graph-edge-hypothesis-input"
          value={hypothesis}
          onChange={(e) => setHypothesis(e.target.value)}
        />
      </label>
      {missing ? (
        <p data-testid="graph-edge-hypothesis-required">
          {t("graph.edge.hypothesis.required")}
        </p>
      ) : null}
      {failed ? (
        <p data-testid="graph-edge-error">{t("graph.edge.create_failed")}</p>
      ) : null}
      <button type="button" data-testid="graph-edge-submit" onClick={submit}>
        {t("graph.edge.submit")}
      </button>
      <button type="button" data-testid="graph-edge-cancel" onClick={() => onCancel?.()}>
        {t("graph.edge.cancel")}
      </button>
    </div>
  );
}
