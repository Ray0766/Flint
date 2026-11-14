"use client";

// PLAZA-01：广场的呈现层。**堆叠（今日精选）在上，网格（全量）在下。**
// PLAZA-03：加上规格 #2.14 的四条状态规则。
//
// ## 为什么是两段，而不是全部堆叠
//
// 素材的堆叠一次聚焦一张（它的副标题写着「5 条线索待浏览」），
// 而广场当日有 154 条。堆叠适合精选，不适合浏览全量——
// 让人按 154 次方向键才看完一天的热点，那不叫界面。
// 这是 steward 的假设（工单 §9 ①），owner 可当场划掉；划掉时改的是本文件的组合，
// 卡面与堆叠本身一行都不用动。
//
// ## 零计算（acceptance④）
//
// 后端已按 `total_heat` 排好。本屏**不排序、不筛选、不合成任何数值**：
// 精选就是取前 `FEATURED` 条（`slice`，不是「挑出最热的几条」——那是排序），
// 网格就是全量按原序铺开。
// 判据 `test_plaza_cards.py` 盯着本目录零 `sort` / 零 `filter` / 零算术。
//
// ## 卡面只有一份
//
// 堆叠与网格都渲染 `HotspotCard`，两处都不画卡面内部的任何一槽。
// 我们刚为「两个广场各自漂移」吃过亏，判据盯着这一条。
//
// ## 四态互不串台（PLAZA-03）
//
// 每一态**各有各的 `data-plaza-state`**，且逐条对应规格 #2.14：
//
// | 态 | `data-plaza-state` | 规格原话 |
// |---|---|---|
// | 还在取 | `loading` | 加载中 → 骨架卡 |
// | 查过了、这一区当日没有 | `empty` | 「该区当日无数据」并给出可切换的区 |
// | 这一区的源全灭 | `source_outage` | 该区卡片区显示缺数据角标（E6 降级行），其余照常 |
// | 有数据 | `ready` | — |
//
// **`loading` 与 `empty` NEVER 共用一个表示**：前者是「还没查」，后者是「查过了没有」。
// 混成一句，用户会把还在转的圈读成「今天没有热点」——本仓一路在守的同一条纪律。
//
// **源全灭那一态不吞掉已有的卡**：角标挂在卡片区上方，下面该渲染的照常渲染
// （规格原话「其余区照常」）。把内容藏起来等于用一次降级抹掉所有还好的部分。

import { useState, type JSX } from "react";

import { API_BASE } from "../../lib/apiBase";
import { HotspotCard } from "../hotspot-card/HotspotCard";
import { HotspotCardActions } from "../hotspot-card-actions/HotspotCardActions";
import { HotspotCardSkeleton } from "./HotspotCardSkeleton";
import { HotspotCardStack } from "./HotspotCardStack";
import {
  addToWorkbench, favoriteCluster, shareCluster, workbenchTarget,
  type ActionOutcome,
} from "./cardActions";
import { ClusterSourceLines } from "./ClusterSourceLines";
import { clusterToCard } from "./clusterToCard";
import { t } from "../../lib/i18n/t";
import type { PlazaCluster } from "../../lib/viewsClient";

/** 精选取前几条。**取前 N 不是排序**——顺序是后端给的，这里只截一段。 */
const FEATURED = 5;

export type PlazaCardsProps = {
  /** `null` = **还在取**（不是「没有」）。两者 NEVER 共用一个表示。 */
  clusters: PlazaCluster[] | null;
  /** 当前地区，来自 `GET /settings/locale`。`null` = 没查到，那时空态不说「该区」。 */
  region?: string | null;
  /** 可切换的区，同样来自 `GET /settings/locale`。**NEVER 在广场自带一份清单**（LOC-01）。 */
  regions?: readonly string[] | null;
  /**
   * 该区的源是否全灭（E6 降级行）。
   *
   * **后端今天还没有这个信号**：`GET /plaza/hot` 回的是 `{day, clusters, weak_signals}`，
   * 没有任何一处说「这一区的源挂了」。所以这里**参数化留位**——
   * 缺省 `false`，行为与今天逐字相同；信号建成后把它接上即可，屏与判据都不用改。
   * NEVER 由前端去猜：「一条都没有」既可能是源挂了，也可能是这一区当日真的没有热点，
   * 而这两件事该说的话完全相反。
   */
  sourceOutage?: boolean;
  /** CN-02 / `DEC-045`：这一区在本版有没有内容。
   *  `false` → 屏上说「本版暂无该区内容」，**与「该区当日无数据」分开成两态**。
   *  省略 = 没有这个信息（老回放夹具），按「在范围内」处理——
   *  **NEVER 默认成「不在范围」**：那会让一个正常的空结果被说成「本版不做」。 */
  regionInScope?: boolean;
  /** 收窄何时解除（服务端给的人话）。 */
  scopeLiftsWhen?: string | null;
  onSelectCluster?: (clusterId: string) => void;
  /** ENTRY-04 / `DEC-049`：已选中的热点卡。
   *  **省略 = 这一屏没有多选态**（`DemoFlow` 等既有调用点原样不变）。 */
  selectedClusterIds?: readonly string[];
  /** 勾选/取消一张卡。给了它才渲染选择控件。 */
  onToggleSelect?: (clusterId: string) => void;
  /** 「用选中的卡建组合」——`≥2` 张时才给。
   *
   *  `PLZ-COMBO-01` 起带上**这一屏输入的关联假设**：既有调用点写的是
   *  `() => …`，多一个入参对它们没有影响（TS 允许少收），
   *  所以这条缝加上去**一个既有调用点都不用改**。
   *  今天广场那一屏还没把它带进 `/combo` 的地址（那一步在别的卡的 outputs 里），
   *  用户到那一屏仍要再打一遍——**这件事写进 trace，NEVER 假装它已经接上了**。 */
  onBuildCombo?: (hypothesis: string) => void;
};

export function PlazaCards({
  clusters,
  region,
  regions,
  sourceOutage = false,
  regionInScope,
  scopeLiftsWhen,
  onSelectCluster,
  selectedClusterIds,
  onToggleSelect,
  onBuildCombo,
}: PlazaCardsProps): JSX.Element {
  // 三动作的结果**按卡片各记各的**：一张卡的答复 NEVER 显示到另一张上。
  // 记的是 `{哪张卡, 哪个动作, 什么结果}`——三个动作各自独立（HOTSPOT-02 的原话）。
  const [acted, setActed] = useState<{
    clusterId: string;
    of: "favorite" | "workbench" | "share";
    outcome: ActionOutcome;
  } | null>(null);

  // NAV-03：**「入台」才是进图谱工作台的那条路**（DEC-042 ②）。
  // 改前三个按钮都真的在调后端，而**按完停在原地**——用户不知道有没有成事。
  //
  // 只有入台导航：收藏与分享是**动作**，不是去处。把人带走的话，
  // 他刚点的那张卡就没了，而他多半还想接着看别的。
  //
  // 去哪一个工作台由服务端说（`workbenchTarget` 读 `graph_id`）。
  // 服务端没给就**留在原地**：拿 cluster_id 拼一个跳过去，
  // 用户会落进一个不存在的图谱，并以为是自己的数据丢了。
  const [navMissing, setNavMissing] = useState<string | null>(null);
  /* `PLZ-COMBO-01`：Combo 栏里那句关联假设。
     **这个 hook 必须在早退之前**（`clusters === null` 那一支下面就有一个 `return`）——
     第一版把它写在早退**之后**，React 当场报
     「Rendered more hooks than during the previous render」，
     `nav02` 与 `mainchain` 两个测试文件 9 条一起红。
     **红的是我引入的真缺陷，不是判据**：加载态那一帧的 hook 数少一个，
     数据回来之后多一个，React 对不上号。 */
  const [hypothesis, setHypothesis] = useState("");

  const run = (
    clusterId: string,
    of: "favorite" | "workbench" | "share",
    call: (base: string, id: string) => Promise<ActionOutcome>,
  ): void => {
    void call(API_BASE, clusterId).then((outcome) => {
      setActed({ clusterId, of, outcome });
      setNavMissing(null);
      // 收藏 / 分享 NEVER 导航；失败 NEVER 导航（阴性对照盯着这两条）。
      // 说明写成整行注释而不是行尾注释：`test_plaza_states` 的中文判据只剥整行，
      // 行尾的那半句会被它当成屏上的文案——**判据没错，是这句话站错了地方**。
      if (of !== "workbench") return;
      if (outcome.kind !== "ok") return;
      const target = workbenchTarget(outcome);
      if (target === null) {
        // 成了、却不知道去哪一个——这与「失败」是两件事，NEVER 合并：
        // 前者用户的东西已经存下了，后者没有。
        setNavMissing(clusterId);
        return;
      }
      window.location.assign(`/workbenches/${encodeURIComponent(target)}`);
    });
  };
  if (clusters === null) {
    return (
      <section className="plaza" data-plaza="true">
        <HotspotCardSkeleton />
      </section>
    );
  }

  const cards = clusters.map(clusterToCard);
  const others = (regions ?? []).filter((r) => r !== region);
  // **三态在这里分开**（`DEC-045`）：
  //   out_of_scope 这一版不做这个区   → 等下一版
  //   empty        做了、查过了、没有   → 换一天 / 换一个区
  //   （读失败由 `PlazaPage` 的 `data-plaza-error` 表示，那是第三处）
  // 判断顺序是刻意的：不在范围内时结果**必然**是空的，
  // 先判空的话这一态永远走不到，而屏上会说「该区当日无数据」——
  // 一句在这一版里永远为真、因而什么都没告诉用户的话。
  const outOfScope = regionInScope === false;
  // ENTRY-04：多选是**独立的一层**。`onToggleSelect` 没给 = 这一屏没有多选态，
  // 于是既有调用点（`DemoFlow` 那个演示串屏）一个字都不用改。
  const selectable = onToggleSelect !== undefined;
  const selected = selectedClusterIds ?? [];
  // 「两张或更多」（`DEC-049`）。**上限不在这里判**：
  // 组合的 2~5 说的是**证据卡**，而这里选的是**热点**——
  // 一个热点底下可能有好几张证据卡，两者不是同一个计数。
  // 真正的 2~5 由 `/combo` 那一屏与服务端判（`comboCountValid` / `EMPTY_HYPOTHESIS`）。
  // `PLZ-COMBO-01`（v4 那条 Combo 栏比现网多的两样之一）：假设进同一条栏。
  //
  // **上限在这里 NEVER 判**（`ENTRY-04` 的既有纪律，判据
  // `test_plaza_multiselect_combo.py::test_the_plaza_does_not_re_judge_the_two_to_five_rule`）：
  // `2~5` 说的是**证据卡**张数，而这一屏选的是**热点**——两者不是同一个计数。
  // 在这里判一次的话，用户选了 6 个热点会被拦下，
  // 而那 6 个热点底下可能一共只有 3 张证据卡。
  // 卡面 acceptance⑤ 要「上限 5 在屏上说得出」，与这条既有纪律**互相矛盾**——
  // 按既有纪律执行并开单：`docs/blocked/PLAZA-UPPER-BOUND-CONTRADICTS-ENTRY-04.md`。
  // 与后端同口径：空白（含全空格）不算填了。后端 `EMPTY_HYPOTHESIS` 走的是
  // `strip()`，前端各判各的话，屏上说「就绪」而服务端当场拒。
  const hypothesisFilled = hypothesis.trim() !== "";
  // 「两张或更多」是**广场自己那条**（`DEC-049`），与证据卡的 2~5 不是同一件事。
  const canBuild = selected.length >= 2 && hypothesisFilled;
  // v4 第 524 行那条三态提示（`comboMsg`）。**四态各说各的**：
  //   一张没选 → 说怎么开始；不够 → 说还差几张；够了没写假设 → 说假设必填；
  //   都齐了 → 说下一步会产出什么。
  // 合并任意两态，用户就不知道自己卡在哪一步。
  const comboHint = selected.length === 0
    ? t("plaza.combo.empty_hint")
    : selected.length < 2
      ? t("plaza.combo.need_n", { n: String(2 - selected.length) })
      : !hypothesisFilled
        ? t("plaza.combo.need_hypothesis")
        : t("plaza.combo.ready");

  return (
    <section
      className="plaza"
      data-plaza="true"
      data-plaza-state={
        outOfScope
          ? "out_of_scope"
          : cards.length === 0
            ? "empty"
            : sourceOutage
              ? "source_outage"
              : "ready"
      }
    >
      <p data-topic-deferred="true">{t("plaza.topic_deferred")}</p>
      {selectable ? (
        /* ENTRY-04 / `DEC-049`：**6 座孤岛的入口**。
           计数条恒在（哪怕一张没选）——只在选够时才出现的话，
           用户不知道「选几张才能建」，而那正是他要问的第一个问题。

           **位置在三态分支之上**：第一版把它放在「有卡」那一支里，
           于是切到一个没有卡的区（`empty` / `out_of_scope`）时整条计数条消失，
           而用户的选中态**还在**——屏上说「没有」，手里其实握着两张。
           那正是 acceptance⑤ 要防的「悄悄」：不是清空了，是**看不见了**，
           而看不见与清空了在用户那里是同一件事。 */
        <section
          className="plaza-combo-bar"
          data-testid="plaza-combo-bar"
          data-selected-count={selected.length}
        >
          <span data-testid="plaza-combo-count">
            {t("plaza.combo.selected", { n: String(selected.length) })}
          </span>
          {/* v4 把假设输入框放进**同一条栏**：选卡与写假设是同一件事的两半，
              分在两屏的话，用户在广场选完卡、到下一屏才发现还要写一句。 */}
          <label className="plaza-combo-bar__hyp">
            <span className="plaza-combo-bar__hyp-label">
              {t("plaza.combo.hypothesis_label")}
            </span>
            <input
              type="text"
              data-testid="plaza-combo-hypothesis"
              value={hypothesis}
              placeholder={t("plaza.combo.hypothesis_placeholder")}
              onChange={(event) => setHypothesis(event.target.value)}
            />
          </label>
          <button
            type="button"
            data-testid="plaza-combo-build"
            disabled={!canBuild}
            onClick={() => onBuildCombo?.(hypothesis.trim())}
          >
            {t("plaza.combo.build")}
          </button>
          {/* 提示恒在，且四态各说各的（v4 第 524 行那条）。
              只在不可点时才显示的话，「就绪」这一态就没人说出来——
              而那正是用户最需要确认的一态。 */}
          <span
            data-testid="plaza-combo-hint"
            data-combo-state={
              selected.length === 0
                ? "empty"
                : selected.length < 2
                  ? "need_more"
                  : !hypothesisFilled
                    ? "need_hypothesis"
                    : "ready"
            }
          >
            {comboHint}
          </span>
        </section>
      ) : null}
      {sourceOutage ? (
        <p
          className="plaza-badge plaza-badge--outage"
          data-testid="plaza-outage-badge"
          role="status"
        >
          {t("plaza.badge.source_outage")}
        </p>
      ) : null}
      {outOfScope ? (
        <div
          className="plaza-empty"
          data-plaza-out-of-scope="true"
          data-testid="plaza-out-of-scope"
        >
          <p className="plaza-empty__line">{t("plaza.out_of_scope.line")}</p>
          {/* 说清什么时候解除——只说「暂无」的话，用户不知道该等还是该放弃。 */}
          <p className="plaza-empty__line" data-testid="plaza-out-of-scope-lifts">
            {t("plaza.out_of_scope.lifts_when", {
              when: scopeLiftsWhen ?? t("plaza.out_of_scope.next_version"),
            })}
          </p>
          {others.length > 0 ? (
            <p className="plaza-empty__regions" data-testid="plaza-out-of-scope-regions">
              <span className="plaza-empty__regions-label">
                {t("plaza.empty.other_regions")}
              </span>
              {others.map((r) => (
                <span key={r} className="plaza-empty__region" data-region={r}>
                  {r}
                </span>
              ))}
            </p>
          ) : null}
        </div>
      ) : cards.length === 0 ? (
        <div className="plaza-empty" data-plaza-empty="true" data-testid="plaza-empty">
          <p className="plaza-empty__line">{t("plaza.empty.no_data_today")}</p>
          {/* 「给出可切换的区」：清单是真的（来自 /settings/locale）。
              **REGION-09/10 之后切换也是真的**——所以那句「切换还没接上」被删了：
              它现在是假话，而留着假话比没有提示更坏（用户会因此不去用一个能用的东西）。
              仍然 NEVER 回落到别的区假装有数据（规格 #2.14 的原话）：
              这里只列出别的区，切不切由用户在顶部的筛选器决定。 */}
          {others.length > 0 ? (
            <p className="plaza-empty__regions" data-testid="plaza-empty-regions">
              <span className="plaza-empty__regions-label">
                {t("plaza.empty.other_regions")}
              </span>
              {others.map((r) => (
                <span key={r} className="plaza-empty__region" data-region={r}>
                  {r}
                </span>
              ))}
            </p>
          ) : null}
        </div>
      ) : (
        <>
          <HotspotCardStack
            cards={cards.slice(0, FEATURED)}
            onSelectCluster={onSelectCluster}
          />
          <section className="plaza-grid" data-plaza-grid="true">
            <h3 className="plaza-grid__heading">{t("plaza.grid.heading")}</h3>
            <ul className="plaza-grid__list" data-plaza-list="true">
              {clusters.map((cluster, index) => {
                const card = cards[index];
                return (
                <li
                  key={card.clusterId}
                  className="plaza-grid__item"
                  data-cluster-id={card.clusterId}
                  data-cluster-category={card.categoryId}
                  // NAV-02：这一下点击**现在真的会跳屏**了（改前调用方一直没传
                  // `onSelectCluster`，点下去什么都不发生）。既然它成了导航，
                  // 就不能只有鼠标能用——键盘用户走到这张卡上会**过不去**。
                  // 所以补上 `role="link"` + 可聚焦 + 回车/空格触发。
                  // 空格要 `preventDefault`：默认行为是滚动一屏，
                  // 用户会看到页面跳走一段而卡没打开。
                  role={onSelectCluster ? "link" : undefined}
                  tabIndex={onSelectCluster ? 0 : undefined}
                  onClick={() => onSelectCluster?.(card.clusterId)}
                  onKeyDown={(e) => {
                    if (!onSelectCluster) return;
                    // **只有这张卡本身被聚焦时才算**。少了这一句，
                    // 在「收藏」上按回车会既收藏又跳走——`stopPropagation`
                    // 拦的是 click，keydown 照样冒上来。这是点击排除区的键盘形态。
                    if (e.target !== e.currentTarget) return;
                    if (e.key !== "Enter" && e.key !== " ") return;
                    e.preventDefault();
                    onSelectCluster(card.clusterId);
                  }}
                >
                  {selectable ? (
                    /* **多选走独立的选择控件**（`DEC-042` / `HOTSPOT-02` 的点击排除区）：
                       卡片主体是导航、三个按钮是动作、这个勾选框是第三样东西。
                       `stopPropagation` 拦 click；`onKeyDown` 那一层由 `<li>` 自己
                       用 `e.target !== e.currentTarget` 拦着（键盘形态）——
                       少了任何一半，勾一下就会连带跳去分析界面。 */
                    <label
                      className="plaza-grid__select"
                      data-testid="plaza-card-select"
                      data-cluster-id={card.clusterId}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <input
                        type="checkbox"
                        data-testid="plaza-card-checkbox"
                        checked={selected.includes(card.clusterId)}
                        onChange={() => onToggleSelect?.(card.clusterId)}
                      />
                      <span>{t("plaza.combo.pick")}</span>
                    </label>
                  ) : null}
                  <HotspotCard {...card} />
                  {/* REGION-12：各源的**原话**（`PLAZA-02` 缺口二）。
                      卡面主行是 `canonical_name`——那是**我们**给这个热点起的名字；
                      这里是**每个源自己**说的那句话。两者不同才是常态
                      （微博说「脑机接口」、GitHub 说 `bci`），
                      而 `PRINCIPLES#B4` 要的正是「把话还给说话的人」。 */}
                  <ClusterSourceLines
                    bySource={cluster.by_source}
                    bySourceRegion={cluster.by_source_region}
                    bySourceText={cluster.by_source_text}
                  />
                  <HotspotCardActions
                    onFavorite={() => run(card.clusterId, "favorite", favoriteCluster)}
                    onAddToWorkbench={() =>
                      run(card.clusterId, "workbench", addToWorkbench)
                    }
                    onShare={() => run(card.clusterId, "share", shareCluster)}
                    outcome={acted?.clusterId === card.clusterId ? acted.outcome : null}
                    outcomeOf={acted?.clusterId === card.clusterId ? acted.of : null}
                    note={
                      navMissing === card.clusterId
                        ? t("card.action.workbench_no_target")
                        : null
                    }
                  />
                </li>
                );
              })}
            </ul>
          </section>
        </>
      )}
    </section>
  );
}
