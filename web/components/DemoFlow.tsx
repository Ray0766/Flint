"use client";

import { useState, type JSX } from "react";

import { ErrorState } from "./shell/ErrorState";
import { LoadingSkeleton } from "./shell/LoadingSkeleton";
import { PlazaCards } from "./plaza/PlazaCards";
import { WorkbenchView } from "./views/WorkbenchView";
import { ComboEntryView } from "./views/ComboEntryView";
import { TopicListView } from "./views/TopicListView";
import { t } from "../lib/i18n";
import {
  fetchPlazaHot,
  fetchEvidenceCards,
  type PlazaCluster,
  type EvidenceCard,
  type ViewOpts,
} from "../lib/viewsClient";
import {
  createCombo,
  fetchProjectTopics,
  submitTopicAnalysis,
  type Topic,
} from "../lib/topicClient";

// TS-012：可点击 demo 流——广场→点簇→工作台→combo→主题→选主题→Gate。
// 纯呈现 + 客户端接线（fetchImpl 注入，离线测）；report 步路由到既有 L1 进度页
// /jobs/{id}（L0/L1/L2 + 指令重生成已建），不在此重嵌。
type Step = "plaza" | "workbench" | "topics" | "gate";

export function DemoFlow({
  day,
  opts = {},
  budgetCny = 10,
}: {
  day: string;
  opts?: ViewOpts;
  budgetCny?: number;
}): JSX.Element {
  const [step, setStep] = useState<Step>("plaza");
  const [clusters, setClusters] = useState<PlazaCluster[]>([]);
  // `REDESIGN-03`：广场取没取过。**「还没查」与「查过了，没有」是两句话**——
  // 改前 `clusters` 初值是空数组，一进屏就画出广场的空态「该区当日无数据」，
  // 而那时一个请求都还没发。
  const [plazaLoaded, setPlazaLoaded] = useState<boolean>(false);
  const [clusterId, setClusterId] = useState<string>("");
  const [cards, setCards] = useState<EvidenceCard[]>([]);
  const [projectId, setProjectId] = useState<string>("");
  const [topics, setTopics] = useState<Topic[]>([]);
  const [chosenTopicId, setChosenTopicId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string>("");
  const [busy, setBusy] = useState<boolean>(false);
  // UIX-01：**每一处 await 此前都没有 catch**。请求失败时 `setBusy(false)`
  // 永远执行不到——屏幕永久停在忙碌态，而且一个字都不说。
  // 这不是「少了个错误提示」，是**一次失败会把整屏卡死**。
  const [failure, setFailure] = useState<string | null>(null);

  /** 包住一次取数：忙碌标志与失败理由**成对**维护，NEVER 只管其中一个。 */
  async function run(task: () => Promise<void>): Promise<void> {
    setBusy(true);
    setFailure(null);
    try {
      await task();
    } catch (err) {
      // 后端/网络给的原话**原样留下**，NEVER 改写成一句通用的「失败」。
      setFailure(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function loadPlaza(): Promise<void> {
    await run(async () => {
      setClusters(await fetchPlazaHot(day, opts));
      setPlazaLoaded(true);
    });
  }

  async function onSelectCluster(cid: string): Promise<void> {
    await run(async () => {
      setClusterId(cid);
      setCards(await fetchEvidenceCards(cid, opts));
      setStep("workbench");
    });
  }

  async function onCombo(cardIds: string[], hypothesis: string): Promise<void> {
    await run(async () => {
      const combo = await createCombo(cardIds, hypothesis, opts);
      setProjectId(combo.project_id);
      const pt = await fetchProjectTopics(combo.project_id, opts);
      setTopics(pt.topics);
      setChosenTopicId(pt.chosen_topic_id);
      setStep("topics");
    });
  }

  async function onSelectTopic(topicId: string): Promise<void> {
    await run(async () => {
      setChosenTopicId(topicId);
      const res = await submitTopicAnalysis(projectId, topicId, budgetCny, opts);
      setJobId(res.job_id);
      setStep("gate");
    });
  }

  return (
    <main data-demo-flow="true" data-step={step}>
      {/* 取证属性保留（既有断言面），但**加载态现在真的画出来了**：
          原先只有一个 `hidden` 的占位符，用户什么都看不到。 */}
      <p data-demo-busy={busy ? "true" : "false"} hidden>
        {busy ? "…" : ""}
      </p>
      {busy ? <LoadingSkeleton rows={2} /> : null}
      {failure ? <ErrorState detail={failure} /> : null}
      {step === "plaza" && (
        <section>
          <button type="button" data-demo-load-plaza onClick={() => void loadPlaza()}>
            {t("demo.load_plaza")}
          </button>
          {plazaLoaded ? (
            <PlazaCards
              clusters={clusters}
              onSelectCluster={(cid) => void onSelectCluster(cid)}
            />
          ) : (
            <p data-demo-not-loaded="true">{t("demo.not_loaded")}</p>
          )}
        </section>
      )}
      {step === "workbench" && (
        <section>
          <WorkbenchView clusterId={clusterId} cards={cards} />
          <ComboEntryView cards={cards} onSubmit={(ids, h) => void onCombo(ids, h)} />
        </section>
      )}
      {step === "topics" && (
        <TopicListView
          topics={topics}
          chosenTopicId={chosenTopicId}
          onSelectTopic={(tid) => void onSelectTopic(tid)}
        />
      )}
      {step === "gate" && (
        <section data-demo-gate="true">
          <p data-demo-chosen-topic>{chosenTopicId}</p>
          <a data-demo-job-link href={`/jobs/${jobId}`}>
            {t("demo.view_progress")}
          </a>
        </section>
      )}
    </main>
  );
}
