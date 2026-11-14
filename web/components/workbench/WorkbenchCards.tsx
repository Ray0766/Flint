import type { JSX } from "react";

import { HotspotCard } from "../hotspot-card/HotspotCard";
import { clusterToCard } from "../plaza/clusterToCard";
import type { EvidenceCard, PlazaCluster } from "../../lib/viewsClient";
import { t } from "../../lib/i18n/t";

/**
 * `WB-02`：计划书工作台左栏——热点卡与证据卡的选取。
 *
 * 风格来源：`前端设计/ai工作台/Flint 设计台 v3.dc.html` 第 55~82 行。
 *
 * ## 复用，NEVER 另写
 *
 * 热点卡就是广场那个 `HotspotCard`，搬运也走广场那个 `clusterToCard`。
 * `FAV-CARD-01` 已经走过这条路，理由一字不变：**两个卡片会各自漂移，
 * 而它们呈现的是同一种东西**。
 *
 * 连搬运层一起复用是有意的：`clusterToCard` 里写着「主行恒 `name_native`」
 * 「首见日原样搬运、NEVER 算几天前」这些当初定过的决定——
 * 只复用组件的话，这些会在这里被重做一遍，而重做的人看不到那些理由。
 *
 * ## 证据卡跟着已选热点走（一处刻意没照蓝本）
 *
 * 蓝本把证据卡列成一份**与热点无关的清单**——它是个 demo，数据写死在 `state` 里。
 * 本仓照不了：证据卡按簇取（端点签名就是 `/clusters/{id}/evidence-cards`），
 * 凭空列一份「所有证据」要么多打 N 次请求，要么编一份出来。
 *
 * 所以改成「选了哪几条热点，就列那几条的证据」。一条都没选时**如实说**——
 * 空清单与「你还没选」在屏上长得一样，而后者是用户该做点什么的信号。
 *
 * ## 三种空态 NEVER 合并（`CN-02` 的既有纪律）
 *
 * | 态 | 屏上说的 | 用户该做的 |
 * |---|---|---|
 * | `empty` | 该区当日无数据 | 换一天 / 换一个区 |
 * | `out_of_scope` | 本版暂无该区内容 | 等下一版 |
 * | `failed` | 读失败 | 去查后端 |
 *
 * 判断顺序照广场：**先判 `out_of_scope`**。不在范围内时结果必然是空的，
 * 先判空的话那一态永远走不到，而屏上会说「该区当日无数据」——
 * 一句在这一版里永远为真、因而什么都没告诉用户的话。
 *
 * 两句文案**照搬广场既有的**（`plaza.empty.no_data_today` /
 * `plaza.out_of_scope.line`）：同一件事 NEVER 在两屏上说得不一样。
 */

export type WorkbenchCardsProps = {
  /** 热点。`null` = 还在取。 */
  clusters: PlazaCluster[] | null;
  /** 取热点失败（与「取回来是空的」是两件事）。 */
  failed: boolean;
  /** 服务端说的版本范围。`false` = 本版不做这个区。`undefined` = 老夹具没这一格。 */
  regionInScope?: boolean;
  /** 已选热点 id。 */
  picked: string[];
  onToggle: (clusterId: string) => void;
  /** 已选热点的证据卡。`null` = 还在取。 */
  evidence: EvidenceCard[] | null;
  /** 取证据失败。 */
  evidenceFailed: boolean;
  /** 簇 id → 簇名。只用来把出处写成人话；**id 本身取自证据卡自己**。 */
  evidenceOwner: Record<string, { name: string }>;
};

function cardsState(
  clusters: PlazaCluster[] | null, failed: boolean, regionInScope?: boolean,
): "loading" | "failed" | "out_of_scope" | "empty" | "ready" {
  if (failed) return "failed";
  if (clusters === null) return "loading";
  // 先判范围（见文件头）。
  if (regionInScope === false) return "out_of_scope";
  return clusters.length === 0 ? "empty" : "ready";
}

export function WorkbenchCards({
  clusters,
  failed,
  regionInScope,
  picked,
  onToggle,
  evidence,
  evidenceFailed,
  evidenceOwner,
}: WorkbenchCardsProps): JSX.Element {
  const state = cardsState(clusters, failed, regionInScope);
  const rows = clusters ?? [];

  return (
    <div className="wb-cards" data-wb-cards-state={state}>
      <h2 className="wb-cards__group">{t("wb.cards.tab.hotspots")}</h2>
      {state === "loading" ? (
        <p className="wb-cards__note">{t("wb.cards.loading")}</p>
      ) : null}
      {state === "failed" ? (
        <p className="wb-cards__note" data-wb-cards-note="failed">
          {t("wb.cards.failed")}
        </p>
      ) : null}
      {state === "out_of_scope" ? (
        <p className="wb-cards__note" data-wb-cards-note="out_of_scope">
          {t("wb.cards.out_of_scope")}
        </p>
      ) : null}
      {state === "empty" ? (
        <p className="wb-cards__note" data-wb-cards-note="empty">
          {t("wb.cards.empty")}
        </p>
      ) : null}
      {state === "ready" ? (
        <ul className="wb-cards__list">
          {rows.map((cluster) => {
            const card = clusterToCard(cluster);
            const isPicked = picked.includes(cluster.cluster_id);
            return (
              <li
                key={cluster.cluster_id}
                className="wb-cards__item"
                data-wb-card={cluster.cluster_id}
                data-wb-picked={isPicked ? "true" : "false"}
              >
                {/* 整张卡就是那个开关。
                    **按钮包着卡**而不是在卡旁边挂一个小方块：
                    左栏只有 250px 宽，一个 16px 的复选框在那儿是个难点中的目标，
                    而这一屏的动作只有「选/不选」一件事——整张卡可点最省事。

                    `HotspotCard.tsx` 一个字没改：它渲染的还是那七个槽。 */}
                <button
                  type="button"
                  className="wb-cards__pick"
                  data-wb-pick={cluster.cluster_id}
                  aria-pressed={isPicked}
                  aria-label={isPicked ? t("wb.cards.unpick") : t("wb.cards.pick")}
                  onClick={() => onToggle(cluster.cluster_id)}
                >
                  {/* 槽**照搬运层给的那几个**，NEVER 在这里挑挑拣拣：
                      `clusterToCard` 已经决定过「哪个字段进主行」「首见日原样搬」，
                      在这里再挑一遍等于把那些决定重做，而重做的人看不到理由。 */}
                  <HotspotCard {...card} />
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}

      <h2 className="wb-cards__group">{t("wb.evidence.title")}</h2>
      <WorkbenchEvidence
        picked={picked}
        evidence={evidence}
        failed={evidenceFailed}
        owner={evidenceOwner}
      />
    </div>
  );
}

function WorkbenchEvidence({
  picked,
  evidence,
  failed,
  owner,
}: {
  picked: string[];
  evidence: EvidenceCard[] | null;
  failed: boolean;
  owner: Record<string, { name: string }>;
}): JSX.Element {
  // 四态各自成一态，**NEVER 把「你还没选」折进「没有证据」**。
  const state = picked.length === 0
    ? "nothing_picked"
    : failed
      ? "failed"
      : evidence === null
        ? "loading"
        : evidence.length === 0
          ? "empty"
          : "ready";

  if (state !== "ready") {
    const line = {
      nothing_picked: t("wb.evidence.nothing_picked"),
      failed: t("wb.evidence.failed"),
      loading: t("wb.cards.loading"),
      empty: t("wb.evidence.empty"),
    }[state];
    return (
      <p className="wb-cards__note" data-wb-evidence-state={state}>{line}</p>
    );
  }

  return (
    <ul className="wb-cards__evidence" data-wb-evidence-state="ready">
      {(evidence ?? []).map((card) => {
        const from = owner[card.cluster_id];
        return (
          <li
            key={card.card_id}
            className="wb-cards__evidence-item"
            data-wb-evidence={card.card_id}
            /* 出处取**证据卡自己带的那一格**（`EvidenceCard.cluster_id`），
               NEVER 从别处的映射里查——查表会在表缺一条时悄悄给出空串，
               而卡上本来就写着它属于谁。 */
            data-wb-evidence-cluster={card.cluster_id}
          >
            {/* 面上给人看的是**关键词**，与既有的 `WorkbenchView` 同一种呈现。
                NEVER 把 `card_id` 印出来：那是内部 id（`FB-10` 的 A 类脚手架），
                它留在 `data-wb-evidence` 上供取证用。 */}
            <span className="wb-cards__evidence-title">
              {card.keyword_ids.join("、")}
            </span>
            {/* **每一条都说得出自己属于哪个热点**：混着列而不说出处的话，
                用户没法判断一条证据支持的是哪个热点。
                名字查不到时退回簇 id——**说一个准确的 id 好过不说**。 */}
            <span className="wb-cards__evidence-from">
              {t("wb.evidence.of_cluster", { name: from?.name ?? card.cluster_id })}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
