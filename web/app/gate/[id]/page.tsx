"use client";

import { use, useEffect, useState, type JSX } from "react";

import { API_BASE } from "../../../lib/apiBase";
import { GateView } from "../../../components/views/GateView";
import { Screen } from "../../../components/shell/Screen";
import { fetchVerdict, VerdictNotReady, type Verdict } from "../../../lib/viewsClient";
import { t } from "../../../lib/i18n/t";

// UI-02 主链路第二屏：Gate① 四分类判定。
//
// 路由参数名叫 `[id]` 而不是 `[jobId]`：仓里既有的两个动态路由都是 `[id]`
// （`/jobs/[id]`、`/deliverables/[id]`），而 `harness/fe_smoke.py` 的样例 id 替换
// 认的也是 `[id]`。换个名字就要同时改探针的替换逻辑——为一个参数名改一把已 verified
// 的尺子，不值。组件内部把它读成 `jobId`，读代码的人照样看得出它是什么。
//
// 风格来源：`Claude design Flint 前端设计/Flint 应用 · 20 屏/Flint 批次二 · 主题与分析.dc.html`
// 的 P8 Gate① 判定一节。呈现层复用既有 `GateView`（FE-VIEWS 已测）。
//
// ## 路由是 /gate/[jobId]，判定归属仍由调用方持有（DEC-012）
//
// 判定按 **job** 键落在 `snapshots['snap-{job}-verdict']`，没有 cluster→判定的持久化真相。
// 把 jobId 放进路由，等于把「这条对应关系谁说了算」写在 URL 上——**调用方持有**，
// 与 `AnalysisView` 的 `verdictJobId` 入参形态一致。
//
// ## 前端 NEVER 自判分类
//
// `verdict.verdict` 直取后端。四分类是 Gate① 引擎的结论，前端复算一遍就等于
// 这套系统里多了一个会和后端说不一样话的判定者。
export default function GatePage({
  params,
}: {
  params: Promise<{ id: string }>;
}): JSX.Element {
  const { id: jobId } = use(params);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "unjudged" | "error">("loading");
  const [deliverableId, setDeliverableId] = useState<string | null>(null);

  useEffect(() => {
    setDeliverableId(new URLSearchParams(window.location.search).get("deliverable"));
    // 缺 jobId 时**一个请求都不发**（acceptance②）：没有 id 还去问，
    // 问到的必然是别人的判定。
    if (!jobId) {
      setState("unjudged");
      return;
    }
    let live = true;
    fetchVerdict(jobId, { baseUrl: API_BASE })
      .then((v) => {
        if (!live) return;
        setVerdict(v);
        setState("ready");
      })
      .catch((err: unknown) => {
        if (!live) return;
        setState(err instanceof VerdictNotReady ? "unjudged" : "error");
      });
    return () => {
      live = false;
    };
  }, [jobId]);

  return (
    <Screen title={t("gate.screen.title")} meta={t("gate.screen.meta")}>
      {state === "loading" ? <p data-gate-loading>{t("gate.screen.loading")}</p> : null}
      {state === "unjudged" ? (
        <p data-gate-unjudged>{t("gate.screen.unjudged")}</p>
      ) : null}
      {state === "error" ? (
        <p className="job-failed" data-gate-error>
          {t("gate.screen.error")}
        </p>
      ) : null}
      {state === "ready" && verdict ? <GateView verdict={verdict} /> : null}
      <p className="data-row" data-report-entry>
        <span className="data-row__label">{t("gate.report_entry.label")}</span>
        {deliverableId ? (
          <a
            className="data-row__value"
            data-report-link
            href={`/deliverables/${deliverableId}`}
          >
            {t("gate.report_entry.open")}
          </a>
        ) : (
          // 判定与交付物之间同样没有持久化对应关系——同 DEC-012，调用方持有。
          <span className="data-row__value" data-report-missing>
            {t("gate.report_entry.missing")}
          </span>
        )}
      </p>
    </Screen>
  );
}
