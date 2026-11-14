"use client";

import { useEffect, useState, type JSX } from "react";

import { API_BASE } from "../../lib/apiBase";
import { DesignWorkbench, type RegistryState } from "../../components/design-workbench/DesignWorkbench";
import { Screen } from "../../components/shell/Screen";
import {
  fetchDesignReplay, probeRegistry, solidifyTemplate, submitDesign,
} from "../../components/design-workbench/designSession";
import { openJobStream } from "../../lib/jobClient";
import { t } from "../../lib/i18n/t";
import type { ActionOutcome } from "../../components/plaza/cardActions";

// UI-04 / v2 屏 2.17：AI 设计工作台。**DESIGN-02 把三件补齐了。**
//
// 风格来源：`Claude design Flint 前端设计/Flint 应用 · 20 屏/
// Flint 批次四 · 分叉与收尾.dc.html` 的工作台一节。
//
// ## 改前
//
// 这一屏给 `DesignWorkbench` 传的是**两个 `null`**，并且**一个请求都不发**——
// 当时的理由写在这里：端点没挂，发一个必然 404 的请求只会在控制台留一条假红。
//
// ## 改后为什么改成发请求
//
// 三条端点里**两条已经真通了**（`DESIGN-01` 刚接的）：
//
// - `GET /jobs/{id}/events`：逐块推；
// - `GET /design/sessions/{job_id}/replay`：断线后取回已产出的块
//   （那条端点改前被钉死成 `load_session=None`，一律回 404）。
//
// 只有**提交**那条仍然没有（`POST /projects/{id}/design_generate` 不在 openapi 里，
// 单据 `docs/blocked/DESIGN-GENERATE-HAS-NO-SUBMIT-ENDPOINT.md`）。
// 它照样发——「能不能提交」的真相在服务端，前端自带一份判断会与后端各自漂移：
// 端点哪天挂上了，屏上仍然会显示「没有」。发一次、按答复说话，是唯一不会说错的做法。
//
// ## 中断可续：进屏先取回，**NEVER 重新提交**
//
// 带 `?job=` 进来时，先打一次 replay 拿回已经产出的文字，再从 `seq` 之后续订 SSE。
// 进屏就提交一次的话，用户每刷新一次页面就多开一个作业——
// 而他看到的只是「又从头开始了」。判据盯着进屏的 effect 里 NEVER 出现提交调用。
export default function DesignPage(): JSX.Element {
  const [prompt, setPrompt] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [streamText, setStreamText] = useState("");
  const [generating, setGenerating] = useState(false);
  const [outcome, setOutcome] = useState<ActionOutcome | null>(null);
  // DESIGN-03：注册表四态。初值 `not_checked` = **还没查过**，
  // NEVER 初成 `down`——那是替后端下结论，而我们还没问过。
  const [registry, setRegistry] = useState<RegistryState>("not_checked");

  // 进屏：认 URL 上的 job，取回已产出的块。**只取回，不提交。**
  useEffect(() => {
    const found = new URLSearchParams(window.location.search).get("job");
    if (!found) return;
    setJobId(found);
    let live = true;
    void fetchDesignReplay(found, { baseUrl: API_BASE }).then((replay) => {
      // `null` = 没有这个会话（还没产出过任何块）。NEVER 拿空串冒充「有会话但文字是空的」。
      if (live && replay !== null) setStreamText(replay.text);
    });
    return () => {
      live = false;
    };
  }, []);

  // 进屏查一次注册表：固化能不能点由**查回来的答复**决定，不由前端猜。
  useEffect(() => {
    let live = true;
    void probeRegistry({ baseUrl: API_BASE }).then((state) => {
      if (live) setRegistry(state);
    });
    return () => {
      live = false;
    };
  }, []);

  // 有 job 就续订：逐块拼由 `jobClient` 的 `designText` 做——**拼接只有一处实现**。
  useEffect(() => {
    if (jobId === null) return;
    const close = openJobStream(
      jobId,
      (state) => {
        if (state.designText !== "") setStreamText(state.designText);
        if (state.done) setGenerating(false);
      },
      { baseUrl: API_BASE },
    );
    return close;
  }, [jobId]);

  const generate = (): void => {
    setGenerating(true);
    void submitDesign(prompt, { baseUrl: API_BASE }).then((result) => {
      setOutcome(result);
      if (result.kind === "ok" && typeof result.detail["job_id"] === "string") {
        setJobId(result.detail["job_id"]);
        return;
      }
      // 没开成作业就不是「正在生成」。停在 `true` 的话，那个转着的标记会一直转下去，
      // 而它说的是一件没有发生的事。
      setGenerating(false);
    });
  };

  return (
    <Screen title={t("design.title")} meta={t("design.meta")}>
      {/* DESIGN-03：`registryAvailable` 已经是四态且接了真查询。
          初值 `not_checked` 是**还没查过**——它与「查过了、这里没有」
          （`not_provided`）、「查过了、坏了」（`down`）各说各的话。 */}
      <DesignWorkbench
        preview={null}
        registryAvailable={registry}
        onSolidify={() => {
          // 固化的是**当前预览的那份产物**。今天还没有产物（`preview` 恒 `null`），
          // 所以这里传空串——端点会照实拒（缺水印），而那句拒绝是真的。
          // NEVER 编一份样板送过去：编出来的那份会被固化成一个没人要求过的模板。
          void solidifyTemplate("", { baseUrl: API_BASE }).then(setOutcome);
        }}
        prompt={prompt}
        onPromptChange={setPrompt}
        onGenerate={generate}
        generating={generating}
        streamText={streamText}
        submitOutcome={outcome}
      />
    </Screen>
  );
}
