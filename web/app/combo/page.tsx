"use client";

import { useEffect, useState, type JSX } from "react";

import { API_BASE } from "../../lib/apiBase";
import { ComboEntryView } from "../../components/views/ComboEntryView";
import { Screen } from "../../components/shell/Screen";
import { fetchEvidenceCards, type EvidenceCard } from "../../lib/viewsClient";
import { submitCombo } from "../../components/chain/chainClient";
import { t } from "../../lib/i18n/t";
import type { ActionOutcome } from "../../components/plaza/cardActions";

// CHAIN-04 / 蓝本 P3：combo 入口（关联假设建项）。**改前这一屏不存在**——
// `ComboEntryView` 组件建好了，但全仓只有 `DemoFlow` 那个演示串屏在用。
//
// ## 卡从哪来
//
// 证据卡按簇取（`GET /clusters/{id}/evidence-cards`）。簇 id 由 URL 带进来：
// 用户是从广场点一张热点卡走过来的，那张卡的 `cluster_id` 就是这里的入口参数。
// **没带簇 id 时不发请求**——猜一个簇去问，取回来的是**另一个热点的证据卡**，
// 而用户会拿它们去建项（这与广场屏 `DEC-012` 拒绝猜 verdictJob 是同一条）。
//
// ## 成功之后去哪
//
// 端点回 `{project_id, topic_ids, degraded}`。跳到那个项目的主题列表
// （`CHAIN-03` 刚建的那一屏）——combo 的产物就是主题，让用户直接看见它们。
export default function ComboEntryPage(): JSX.Element {
  const [clusterId, setClusterId] = useState<string | null>(null);
  const [cards, setCards] = useState<EvidenceCard[] | null>(null);
  const [outcome, setOutcome] = useState<ActionOutcome | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    // ENTRY-04 / `DEC-049`：广场多选过来时带的是 **`?clusters=a,b,c`**。
    //
    // **参数名叫 `clusters` 而不是 `card_ids`**：广场上选的是**热点卡**，
    // 而 `POST /projects/combo` 要的 `card_ids` 是**证据卡**——
    // 一个热点底下可能有好几张证据卡。叫成 `card_ids` 会让下一个人
    // 直接把它转发给端点，而那些 id 在 `evidence_cards` 里一条都查不到。
    //
    // 单簇那条老路（`?cluster=`）原样留着：`NAV-05` 接的九条边里有它。
    const many = (params.get("clusters") ?? "")
      .split(",").map((s) => s.trim()).filter(Boolean);
    const one = params.get("cluster");
    const wanted = many.length > 0 ? many : one ? [one] : [];
    if (wanted.length === 0) return;           // 没带簇 id：一个请求都不发
    setClusterId(wanted.join(","));
    let live = true;
    // 逐簇取，**按选中顺序拼起来**——`ComboEntryView` 支持跨簇选卡
    // （它文件头写着「允许跨簇」），而在这之前那一屏一次只拿得到一个簇的卡，
    // 所以那句话一直是做不到的。
    Promise.all(
      wanted.map((id) =>
        fetchEvidenceCards(id, { baseUrl: API_BASE }).catch(() => [])),
    )
      // 取不到的簇就是没有卡，NEVER 编几张出来；
      // 一簇都取不到时是空表，那一屏自己会如实说。
      .then((groups) => live && setCards(groups.flat()))
      .catch(() => live && setCards([]));
    return () => {
      live = false;
    };
  }, []);

  const submit = (cardIds: string[], hypothesis: string): void => {
    void submitCombo(cardIds, hypothesis, { baseUrl: API_BASE }).then((result) => {
      setOutcome(result);
      const projectId = result.kind === "ok" ? result.detail["project_id"] : null;
      if (typeof projectId === "string" && projectId !== "") {
        window.location.assign(
          `/projects/${encodeURIComponent(projectId)}/topics`);
      }
    });
  };

  return (
    <Screen title={t("combo.screen.title")} meta={t("combo.screen.meta")}>
      {clusterId === null ? (
        // 「没带簇 id」是**用法**问题，不是故障：说清该怎么进来。
        <p className="chain-form__outcome" data-combo-no-cluster="true">
          {t("combo.need_cluster")}
        </p>
      ) : cards === null ? (
        <p data-combo-loading="true">{t("screen.loading")}</p>
      ) : (
        <ComboEntryView cards={cards} onSubmit={submit} />
      )}
      {outcome && outcome.kind !== "ok" ? (
        <p
          className="chain-form__outcome"
          data-testid="combo-outcome"
          data-outcome-kind={outcome.kind}
          role="status"
        >
          {outcome.kind === "not_provided"
            ? t("chain.not_provided")
            : outcome.kind === "unsupported"
              ? t("card.action.unsupported", { allowed: outcome.allowed.join(" / ") })
              // 后端自己的说明原样带出来。**前端一句拒绝话都不写**——
              // 写了就要挑一句，而两条端点对空假设的答复并不是同一句
              // （docs/blocked/EMPTY-HYPOTHESIS-TWO-CODES.md）。
              : outcome.message || t("chain.failed", { status: String(outcome.status) })}
        </p>
      ) : null}
    </Screen>
  );
}
