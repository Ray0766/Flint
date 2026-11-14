"use client";

import { useCallback, useEffect, useRef, useState, type JSX } from "react";

import { API_BASE } from "../../lib/apiBase";
import { WorkbenchCards } from "../../components/workbench/WorkbenchCards";
import { WorkbenchChat, type ChatMessage } from "../../components/workbench/WorkbenchChat";
import { WorkbenchComposer } from "../../components/workbench/WorkbenchComposer";
import { WorkbenchPreview } from "../../components/workbench/WorkbenchPreview";
import { WorkbenchSections } from "../../components/workbench/WorkbenchSections";
import { WorkbenchAnnotate } from "../../components/workbench/WorkbenchAnnotate";
import { WorkbenchTemplatePicker } from "../../components/workbench/WorkbenchTemplatePicker";
import { WorkbenchShell } from "../../components/workbench/WorkbenchShell";
import { WorkbenchTray } from "../../components/workbench/WorkbenchTray";
import { DEFAULT_REGION } from "../../lib/regions";
import { comboCountValid } from "../../lib/topicClient";
import { TEMPLATE_IDS } from "../../lib/sectionTables.generated";
import { submitCombo } from "../../components/chain/chainClient";
import type { ActionOutcome } from "../../components/plaza/cardActions";
import type { Block } from "../../lib/types";
import {
  fetchEvidenceCards,
  fetchPlazaHotScoped,
  type EvidenceCard,
  type PlazaCluster,
} from "../../lib/viewsClient";
import { t } from "../../lib/i18n/t";

/**
 * `WB-01` / `WB-02` / `DEC-059`：计划书主工作台。
 *
 * 风格来源：`前端设计/ai工作台/Flint 设计台 v3.dc.html`（owner 2026-08-12 指定）。
 *
 * ## 这是**新增的一屏**，不是替换
 *
 * `DEC-059` 第一句：「新增主工作台，不替换现有『AI 设计工作台』——
 * 后者改名退居次要，DESIGN-01~03 的端点/作业/固化流程一个字不改，成果一点不丢」。
 * 所以 `/design` 那一屏与它那一族路由在本批里**一个字没动**。
 *
 * ## 取数走既有端点，NEVER 新建一份平行取数
 *
 * 热点 `fetchPlazaHotScoped`（`GET /plaza/hot`，连版本范围一起取回）、
 * 证据 `fetchEvidenceCards`（`GET /clusters/{id}/evidence-cards`）。
 * 自己拼一份 URL 的代价不是重复代码：`fetchPlazaHot` 里写着
 * 「不传 region 时一个字都不加」这种与后端对齐过的细节，
 * 另写一份会在某个参数上悄悄偏一点，而两处返回的东西看起来一样。
 *
 * ## 往回找哪一天：与广场同一条路，**上限也同一个**
 *
 * `GET /plaza/hot` 必须带 `day`，而今天没有端点回「最新有数据的那一天」
 * （广场那一屏的注释里记着这件事与它的解法）。所以从今天往回一天一天问，
 * 第一天问到东西就停，**上限 `DAY_LOOKBACK`**——
 * NEVER 无上限地往回走：库真的空着时那是一个看不见尽头的请求串。
 */

/**
 * 一次提交的**终态消息**：成了说产出了什么，失败说**哪一步**失败 + 服务端原话。
 *
 * 服务端那句话原样带出来（`chainClient` 的既有口径：前端一句拒绝话都不写）。
 * 改写成一句通用的「生成失败」的代价是唯一有用的线索没了——
 * 用户拿着那句话才问得出问题。
 */
function _terminal(
  outcome: ActionOutcome, n: number, step: string,
): ChatMessage[] {
  if (outcome.kind === "ok") {
    const projectId = outcome.detail["project_id"];
    const topicIds = outcome.detail["topic_ids"];
    const topics = Array.isArray(topicIds) ? topicIds : [];
    return [
      {
        id: `done-${n}`, role: "system", kind: "receipt", step,
        text: t("wb.chat.receipt.project", { n: topics.length }),
        // 真 id 落在 `data-*` 上：屏上印它没有意义（`FB-10` A 类脚手架），
        // 而取证要拿它与服务端答复逐字比对。
        evidence: {
          project: typeof projectId === "string" ? projectId : "",
          topics: topics.map(String).join(" "),
        },
      },
      // 后两步今天走不了，两条各有单（见本文件头 `STEP_COMBO_KEY` 那一段）。
      // **如实说到哪一步为止**，NEVER 让屏上继续转圈假装还在跑。
      {
        id: `next-${n}`, role: "system", kind: "notice",
        text: t("wb.chat.next_not_wired"),
      },
    ];
  }
  const quote = outcome.kind === "not_provided"
    ? outcome.reason
    : outcome.kind === "unsupported"
      ? t("card.action.unsupported", { allowed: outcome.allowed.join(" / ") })
      : outcome.message || t("chain.failed", { status: String(outcome.status) });
  return [{
    id: `fail-${n}`, role: "system", kind: "failure", step,
    text: t("wb.chat.failed", { step }),
    quote,
  }];
}

/** 与广场同一个上限（`CN-03`：34 天回放窗口 + 一周余量）。 */
const DAY_LOOKBACK = 41;

/** 默认模板 = 后端组稿的默认（`ReportSubmit.template_id = "generic"`）。 */
const DEFAULT_TEMPLATE = "generic";

/**
 * `WB-03-a`：中栏提交的是这条链的**头**——`POST /projects/combo`。
 *
 * ## 为什么不是 `POST /projects/{id}/report`
 *
 * 那条端点要 `analysis_id`（一份已有分析的产物 id），而这一屏手上没有分析：
 * 它手上有的是**用户挑的卡**与**一句话**。链的全貌是
 * `combo → 项目与主题 → 分析 → report/proposal`，中栏提交的是第一段。
 * 跳过中间直接去 `report` 的话，`analysis_id` 只能填一个夹具 id——
 * 于是屏上写着「用你选的卡生成」，实际生成的是夹具那一份。
 *
 * ## 后两段今天走不了，两条各有单，屏上如实说
 *
 * - 发起分析：作业一被消费就打**真实** github / arxiv，
 *   而真实网络是事前必审（`DEC-057` 那个窗口逐字写着「只授权这一次跑通」）；
 * - 成文：`analysis_id` 今天**没有一条从分析拿回它的路**
 *   （`docs/blocked/ANALYSIS-ID-HAS-NO-PATH-FROM-AN-ANALYSIS.md`，owner 四选一待答）。
 *
 * 两条解开之后，接的地方就是 `_terminal()` 里 `ok` 那一支：
 * 把 `notice` 换成第二步、第三步的真回执。**NEVER 在解开之前先让屏上转圈**
 * ——那是 `mark_failed` 那一族的病（失败不写事件、屏上一直转）。
 */
const STEP_COMBO_KEY = "wb.chat.step.combo";

export default function WorkbenchPage(): JSX.Element {
  const [clusters, setClusters] = useState<PlazaCluster[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [regionInScope, setRegionInScope] = useState<boolean | undefined>(undefined);
  const [picked, setPicked] = useState<string[]>([]);
  const [evidence, setEvidence] = useState<EvidenceCard[] | null>(null);
  const [evidenceFailed, setEvidenceFailed] = useState(false);
  /* 右栏正在看的那一份：交付物 id + 它正文里真有的章。
     **由预览那一侧回上来**（它才是去取数的那个），NEVER 在这里再取一次——
     取两次的话，两处会在某一帧显示不同的东西。 */
  const [doc, setDoc] = useState<{ deliverableId: string | null; sectionIds: string[] }>(
    { deliverableId: null, sectionIds: [] },
  );
  const [templateId, setTemplateId] = useState(DEFAULT_TEMPLATE);
  /* `WB-06`：点选的那一块 + 这份文档属于哪个项目。
     项目 id 从地址栏 `?project=` 认（链接通之后由 `_terminal()` 的 `ok` 那一支给）——
     **NEVER 猜一个**：`GET /deliverables/{id}` 今天不回 `project_id`，
     而重写端点要它。猜错了就是把别人的项目改了。 */
  const [pickedBlock, setPickedBlock] = useState<Block | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  /** 重写产出的新版本：预览换过去（`WorkbenchPreview` 优先看这个）。 */
  const [override, setOverride] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [hypothesis, setHypothesis] = useState("");
  const [busy, setBusy] = useState(false);
  /* 消息 id 走一个自增序号，**NEVER 用时间戳或随机数**：
     两条消息在同一毫秒里生成时 key 会撞，React 会把它们当成同一条。 */
  const seq = useRef(0);

  // 模板：地址栏 `?template=` 认一次（`WB-06` 的切换控件写的是同一处状态）。
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const wanted = params.get("template");
    if (wanted && TEMPLATE_IDS.includes(wanted)) setTemplateId(wanted);
    setProjectId(params.get("project"));
  }, []);

  // 热点：往回找到有数据的那一天为止。
  useEffect(() => {
    let live = true;
    void (async () => {
      const start = new Date();
      // 走完整个窗口之后要分得清两件事：
      //   **一天都没问到而每次都在抛** = 后端不通 → `failed`；
      //   **问到了、答的是空**         = 查过了确实没有 → `empty`。
      // 不分的话，后端挂掉时屏上会说「该区当日无数据」——
      // 那是一句实话之外的话：我们根本没查成。
      let answered = false;
      for (let back = 0; back <= DAY_LOOKBACK; back += 1) {
        if (!live) return;
        const probe = new Date(start);
        probe.setUTCDate(probe.getUTCDate() - back);
        const iso = probe.toISOString().slice(0, 10);
        try {
          const got = await fetchPlazaHotScoped(iso, {
            baseUrl: API_BASE, region: DEFAULT_REGION,
          });
          if (!live) return;
          answered = true;
          // 不在版本范围内时**立刻停**：再往回问也还是不在范围内，
          // 而那一态屏上要说的是「本版暂无该区内容」，不是「当日无数据」。
          if (got.regionInScope === false) {
            setRegionInScope(false);
            setClusters([]);
            return;
          }
          if (got.clusters.length > 0) {
            setClusters(got.clusters);
            setRegionInScope(got.regionInScope);
            return;
          }
        } catch {
          // 单独一天问不到就往前再问一天：**一次网络抖动 NEVER 变成「库里没有数据」**
          // （广场那一屏同一条口径）。
        }
      }
      if (!live) return;
      // 一次都没答上来 = 后端不通，**NEVER 说成「确实没有」**。
      setFailed(!answered);
      setClusters([]);
    })();
    return () => { live = false; };
  }, []);

  // 证据：跟着已选热点走。选了几条就问几条，**没选就不问**。
  useEffect(() => {
    if (picked.length === 0) {
      setEvidence(null);
      setEvidenceFailed(false);
      return;
    }
    let live = true;
    setEvidence(null);
    setEvidenceFailed(false);
    void (async () => {
      try {
        const perCluster = await Promise.all(
          picked.map((id) => fetchEvidenceCards(id, { baseUrl: API_BASE })),
        );
        if (!live) return;
        setEvidence(perCluster.flat());
      } catch {
        if (!live) return;
        // **失败与空分开**：前者该去查后端，后者该换一条热点。
        setEvidenceFailed(true);
        setEvidence([]);
      }
    })();
    return () => { live = false; };
  }, [picked]);

  const toggle = useCallback((clusterId: string) => {
    setPicked((prev) => (
      prev.includes(clusterId)
        ? prev.filter((id) => id !== clusterId)
        : [...prev, clusterId]
    ));
  }, []);

  /* 要送出去的是**证据卡 id**，取自已经取回来的那份证据卡自己。
     NEVER 由簇 id 拼一个出来：`card-20260810-c-20260810-000` 这个形状
     看着就是「日期 + 簇 id」，拼出来在今天的数据上大概率能对上——
     而对上的那次不会有人发现它是拼的，直到某个簇底下有第二张证据卡
     （`web/app/combo/page.tsx:34-41` 的注释逐字写着这条分界）。 */
  const cardIds = (evidence ?? []).map((card) => card.card_id);

  const send = useCallback((): void => {
    const text = hypothesis.trim();
    if (busy || text === "" || !comboCountValid(cardIds.length)) return;
    const n = (seq.current += 1);
    const step = t(STEP_COMBO_KEY);
    setBusy(true);
    setMessages((prev) => [
      ...prev,
      // 自己说的那一条：屏上只印那句话，卡 id 落在 `data-*` 上（`FB-10` A 类）。
      {
        id: `ask-${n}`, role: "user", kind: "ask", text,
        evidence: { cards: cardIds.join(" ") },
      },
      { id: `pending-${n}`, role: "system", kind: "pending", step,
        text: t("wb.chat.pending", { step }) },
    ]);
    void submitCombo(cardIds, text, { baseUrl: API_BASE }).then((outcome) => {
      setBusy(false);
      setMessages((prev) => [
        // 等待那一条**换掉**而不是留着：留着的话屏上同时有「正在…」与结果，
        // 而用户读到的第一眼是「还在跑」。
        ...prev.filter((message) => message.id !== `pending-${n}`),
        ..._terminal(outcome, n, step),
      ]);
    });
  }, [busy, cardIds, hypothesis]);

  // 名字**从取回来的那份数据里查**，NEVER 另存一份：
  // 存一份的话，两处会在某次刷新之后说不同的话。
  const nameOf = (clusterId: string): string =>
    (clusters ?? []).find((c) => c.cluster_id === clusterId)?.canonical_name
      ?? clusterId;
  const owner = Object.fromEntries(
    (clusters ?? []).map((c) => [c.cluster_id, { name: c.canonical_name }]),
  );

  return (
    <div className="screen screen--workbench">
      <h1 className="screen__title">{t("wb.title")}</h1>
      <WorkbenchShell
        cards={
          <WorkbenchCards
            clusters={clusters}
            failed={failed}
            regionInScope={regionInScope}
            picked={picked}
            onToggle={toggle}
            evidence={evidence}
            evidenceFailed={evidenceFailed}
            evidenceOwner={owner}
          />
        }
        chat={<WorkbenchChat messages={messages} />}
        chatFooter={
          <>
            {/* 蓝本第 126 行：「本次组合」在消息区与输入框**之间**。 */}
            <WorkbenchTray
              items={picked.map((id) => ({ clusterId: id, name: nameOf(id) }))}
              onRemove={toggle}
            />
            <WorkbenchComposer
              value={hypothesis}
              onChange={setHypothesis}
              onSubmit={send}
              cardCount={cardIds.length}
              busy={busy}
            />
          </>
        }
        /* `WB-04`：右栏渲染**真 Block**。今天这一份从哪来：
           链刚产出的（`WB-03-b` 解阻后由 `_terminal()` 传下来）→
           地址栏 `?deliverable=` → 都没有就是空态。
           **NEVER 在这里填一个夹具 id 冒充**（`DEC-012` 判死过同形的手）。 */
        doc={
          <WorkbenchPreview
            deliverableId={override}
            onDoc={setDoc}
            onPick={setPickedBlock}
            pickedBlockId={pickedBlock?.block_id ?? null}
          />
        }
        /* `WB-06`：右栏顶上的模板切换 + 批注面板。切模板 = 换章节导航与预览的表
           （`WB-05` 那张生成表驱动），**NEVER 另建一份清单**。 */
        previewToolbar={
          <>
            <WorkbenchTemplatePicker value={templateId} onChange={setTemplateId} />
            <WorkbenchAnnotate
              block={pickedBlock}
              projectId={projectId}
              onNewVersion={setOverride}
            />
          </>
        }
        /* `WB-05`：文档左侧那条 sticky 章节导航（蓝本 138px）。
           章节表由 `assets/templates/*.yaml` 生成，**NEVER 在前端另建一份**。
           模板从地址栏 `?template=` 认（`WB-06` 的切换控件写同一处状态）。 */
        sectionNav={
          <WorkbenchSections
            templateId={templateId}
            presentSectionIds={doc.sectionIds}
            deliverableId={doc.deliverableId}
          />
        }
      />
    </div>
  );
}
