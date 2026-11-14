"use client";

import { use, useEffect, useState, type JSX } from "react";

import { GraphWorkbench, type WorkbenchGraph } from
  "../../../components/graph-workbench/GraphWorkbench";
import { Screen } from "../../../components/shell/Screen";
import { t } from "../../../lib/i18n/t";
import { createEdge } from "../../../lib/edgesClient";
import { fetchWorkbench } from "../../../lib/workbenchClient";

// UI-03 / v2 屏 2.16：热点工作台·图谱。
//
// 风格来源：`Claude design Flint 前端设计/Flint 应用 · 20 屏/
// Flint 批次二 · 主题与分析.dc.html` 的工作台一节（节点 + 连线的画布形态）。
//
// ## PERSIST-02-b：这一屏今天有数据了
//
// 改前这里写死 `const graph: WorkbenchGraph | null = null`，并如实标「接口未提供」——
// 那时**没有任何一条端点能把一张图读出来**（只有 `POST /workbenches/{id}/edges`）。
// 那段注释的最后一句是「端点建好之后，这里只要把 `graph` 从 `null` 换成取回来的那张图」，
// `PERSIST-02` 建了 `GET /workbenches/{id}`，**这就是那一步**。
//
// ## 四态各画各的，NEVER 并格
//
// | 状态 | 什么时候 | 屏上 |
// |---|---|---|
// | `loading` | 还在取 | 加载中 |
// | `ok` | 取到了（可能是一张空图） | 画布 / 空图引导 |
// | `not_found` | 服务端说这张图不在 | 「没有这张工作台」 |
// | `unavailable` | 取不到（路由没挂 / 5xx / 网络不通） | 「接口未提供」 |
//
// **本卡先把 `loading` 与 `unavailable` 并进了一格**（都渲染成「接口未提供」），
// 理由写的是「两者都还没有依据画任何一张图」。`tools/check_design_constraints.mjs`
// 的 A6 当场把这一屏报成「缺加载态、错误态」——**那把尺子是对的**：
// 正在取的那一秒屏上说「接口未提供」，那是一句假话，而用户会照着它去找运维。
// 并格省下的是四行代码，代价是屏上写着一件没发生的事。
//
// 空态仍然归 `GraphWorkbench`（它自己分 `not_provided` 与 `empty` 两格），
// 本屏 NEVER 自己画一张空图。
export default function WorkbenchPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): JSX.Element {
  const { id } = use(params);
  const [state, setState] = useState<"loading" | "ok" | "not_found" | "unavailable">(
    "loading");
  const [graph, setGraph] = useState<WorkbenchGraph | null>(null);
  const [connect, setConnect] = useState<
    { phase: "working" | "error"; message?: string } | null>(null);
  const [round, setRound] = useState(0);

  // `EDGES-UI`：连线落盘之后**重取整张图**，NEVER 前端自己把线画上去——
  // 后端其实没存下时，画布上那根线就是一句没有依据的话
  // （与 `LocaleSettings` 那条「NEVER 回滚成旧值假装成功」是同一条纪律的两个方向）。
  async function connectNodes(
    from: string, to: string, hypothesis: string,
  ): Promise<void> {
    setConnect({ phase: "working" });
    const result = await createEdge(id, {
      edgeId: `ge-${from}-${to}-${Date.now()}`,
      fromNodeId: from, toNodeId: to, hypothesis,
    });
    if (result.state === "ok") {
      setConnect(null);
      setRound((n) => n + 1);      // 重取
      return;
    }
    // 三种失败**各说各的**：补一句假设 / 两端选错了 / 没存下。
    setConnect({
      phase: "error",
      message: t(result.state === "empty_hypothesis"
        ? "workbench.connect.error.empty"
        : result.state === "rejected"
          ? "workbench.connect.error.rejected"
          : "workbench.connect.error.failed"),
    });
  }

  useEffect(() => {
    let alive = true;
    setState("loading");
    void fetchWorkbench(id).then((result) => {
      // 组件已经卸载就别再 setState——用户切走之后那次写入没有意义。
      if (!alive) return;
      setGraph(result.state === "ok" ? result.graph : null);
      setState(result.state);
    });
    return () => {
      alive = false;
    };
  }, [id, round]);

  return (
    <Screen title={t("workbench.title")} meta={t("workbench.meta", { id })}>
      {state === "loading" ? (
        <p className="workbench__loading" data-workbench-state="loading">
          {t("workbench.loading")}
        </p>
      ) : state === "not_found" ? (
        // 「这张图不在」与「取不到」**不是一回事**：前者该去问用户手上那个 id，
        // 后者该去问后端。屏上说错了，用户就会去做错的那件事。
        <p className="workbench__error" data-workbench-state="not_found">
          {t("workbench.not_found")}
        </p>
      ) : (
        // `unavailable` → `graph` 是 `null` → `GraphWorkbench` 画「接口未提供」；
        // `ok` → 有图就画布，空图就空图引导（两格都在那个组件里）。
        <GraphWorkbench
          graph={graph}
          connectState={connect}
          onConnect={(from, to, hypothesis) => {
            void connectNodes(from, to, hypothesis);
          }}
        />
      )}
    </Screen>
  );
}
