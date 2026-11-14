// HOTSPOT-07：信息源分列渲染（PRINCIPLES#B4）。
//
// 两国对同一件事说法不一致时，把它们揉成一句「综合各国观点，总体而言……」读起来最顺，
// 也最有害：读者失去了「谁说的」这个唯一能判断可信度的东西，而那句话
// **没有任何一个来源支持它**。所以本组件只做一件事——**把话还给说话的人**：
// 一列一个地区，每条陈述带着自己的来源 id，原文逐字呈现。
//
// 本组件因此**没有**任何汇总槽位。这不是遗漏：渲染层是最容易把那句话加回来的地方。
//
// 三条纪律：
// 1. 原文逐字（B9）：NEVER 翻译、NEVER 归一化空白或全半角；
// 2. 少数派不合并：只有一条陈述的地区照样单独成列——并进多数派那列等于用列数
//    暗示可信度，而那是读者该自己判断的事；
// 3. 未归区单独成列且排最后：NEVER 塞进某个地区（那是编造来源地），也 NEVER 丢掉
//    （丢掉等于悄悄少给了一份材料）。
//
// ## FIX-17：把「谁说的」写到屏上（owner 选甲）
//
// 改前来源只进 `data-source-id`，**屏上一个字都没有**——上面那句
// 「读者失去了『谁说的』这个唯一能判断可信度的东西」，说的正是改前的这个组件自己。
//
// 「在 DOM 里」与「在屏上」是两件事。`data-*` 是给取证用的，产品语言是给人看的：
// 读屏软件念不出一个属性，肉眼也看不见它。
//
// 地区那一列不够顶：列标题是地区，只在两个源恰好分属两个区时才顺带区分了它们。
// 库里绝大多数簇的源同区或无区——**同一列里两条陈述，谁说的完全看不出来**。
//
// 判 `data-source-id` 的既有判据**原样留着**（它防的是混列，那是另一件事）；
// 新判据取**渲染后的可见文本**。

import type { JSX } from "react";

import { t } from "../../lib/i18n/t";
import { sourceName } from "./sourceName";

/** 未归区列的哨兵键；排序上恒在最后。 */
export const UNKNOWN_REGION_KEY = "__unknown__";

export type SourceStatement = {
  sourceId: string;
  /** 空串 = 未归区（REGION-02 的 UnknownSourceRegion 同一口径） */
  region: string;
  /** 原文；NEVER 是译文 */
  text: string;
};

export type SourceColumnsProps = {
  statements: SourceStatement[];
};

function groupByRegion(statements: SourceStatement[]): [string, SourceStatement[]][] {
  const grouped = new Map<string, SourceStatement[]>();
  for (const s of statements) {
    const key = s.region === "" ? UNKNOWN_REGION_KEY : s.region;
    grouped.set(key, [...(grouped.get(key) ?? []), s]);
  }
  return [...grouped.entries()].sort(([a], [b]) => {
    if (a === UNKNOWN_REGION_KEY) return 1;
    if (b === UNKNOWN_REGION_KEY) return -1;
    return a.localeCompare(b);
  });
}

export function SourceColumns({ statements }: SourceColumnsProps): JSX.Element {
  const columns = groupByRegion(statements);
  if (columns.length === 0) {
    return <p data-testid="source-columns-empty">{t("source.columns.empty")}</p>;
  }
  return (
    // `REDESIGN-02`：这几层原先一个类名都没有，样式只能挂在 `data-testid` 上。
    // 补上类名；`data-testid` 一个没动。
    <div className="source-columns" data-testid="source-columns">
      {columns.map(([region, rows]) => (
        <section key={region} className="source-column" data-testid="source-column"
          data-region={region}>
          <h3 className="source-column__label" data-testid="source-column-label">
            {region === UNKNOWN_REGION_KEY ? t("source.columns.unknown_region") : region}
          </h3>
          <ul className="source-column__list">
            {rows.map((s) => (
              <li
                key={s.sourceId}
                className="source-statement"
                data-testid="source-statement"
                data-source-id={s.sourceId}
              >
                {/* 来源名在**陈述之前**：读到那句话之前先知道是谁说的。
                    放在后面的话，读者会先形成判断再看署名——而署名正是
                    用来形成那个判断的。

                    中间那个冒号是**独立的一格**，不进任何一边的文本：
                    首版两个 span 直接相邻，屏上出来的是「Google 趋势脑机接口」
                    ——**读者分不出名字在哪儿断开**，而这个组件存在的理由
                    正是让人分得出谁说的（改完看了一眼屏才发现的）。
                    它 NEVER 混进原文那一格：原文要逐字（B9）。 */}
                <span className="source-statement__who" data-testid="source-statement-who">
                  {sourceName(s.sourceId)}
                </span>
                <span className="source-statement__sep" aria-hidden="true">：</span>
                <span data-testid="source-statement-text">{s.text}</span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
