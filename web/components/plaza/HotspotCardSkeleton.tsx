// PLAZA-03：加载中的**骨架卡**（规格 #2.14 第一条状态规则）。
//
// ## 为什么不是一行「加载中」文字
//
// 卡片布局要占位。一行文字占不住位，于是数据回来的那一刻整屏跳一次——
// 用户正在读的那句话会被顶走，正要点的那个东西会移到别处。
// 骨架卡占的是**将来那张卡的位置与大小**，所以数据落地时屏幅不动。
//
// ## 为什么不用 `shell/LoadingSkeleton`
//
// 那个画的是**横条**（`state__skeleton-row`），给行式内容用的。
// 广场是卡片网格与扇形堆叠，横条既占不对位置、也不告诉人「这里将出现一张卡」。
// 两者不是同一件东西，NEVER 为了「复用」把不合的形状套上去。
//
// ## 它借的是同一个卡壳
//
// 外层照旧是 `.hotspot-card`——纸纹、边框、圆角、投影、内边距全部继承 `DS-02` 那一份，
// 所以骨架与真卡**尺寸逐像素相同**。这里只多加一个 `--skeleton` 修饰类来画那几道灰条，
// NEVER 另写一个「长得像卡片」的盒子（那就有两份卡面在漂了）。

import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

export function HotspotCardSkeleton({ count = 6 }: { count?: number }): JSX.Element {
  return (
    <div
      className="plaza-skeleton"
      data-plaza-state="loading"
      data-testid="plaza-skeleton"
      // 读屏软件要知道这里在等东西；那几道灰条本身对它没有意义，故 aria-hidden。
      aria-busy="true"
      aria-live="polite"
    >
      <span className="plaza-skeleton__label">{t("plaza.screen.loading")}</span>
      {/* 堆叠那一段也要占位：只占网格的话，数据落地时上面凭空多出 420px 的台面，
          整屏照样跳一次——那正是「用骨架而不是一行文字」要避免的事。 */}
      <div className="plaza-skeleton__deck" data-testid="plaza-skeleton-deck">
        <article
          className="hotspot-card hotspot-card--skeleton hotspot-card--skeleton-front"
          aria-hidden="true"
        >
          <div className="hotspot-card__top">
            <span className="plaza-skeleton__bar plaza-skeleton__bar--tag" />
          </div>
          <span className="plaza-skeleton__bar plaza-skeleton__bar--title" />
          <div className="hotspot-card__foot">
            <span className="plaza-skeleton__bar plaza-skeleton__bar--meta" />
          </div>
        </article>
      </div>
      <div className="plaza-skeleton__grid">
        {Array.from({ length: count }, (_, i) => (
          <article
            key={i}
            className="hotspot-card hotspot-card--skeleton"
            data-testid="hotspot-card-skeleton"
            aria-hidden="true"
          >
            <div className="hotspot-card__top">
              <span className="plaza-skeleton__bar plaza-skeleton__bar--tag" />
            </div>
            <span className="plaza-skeleton__bar plaza-skeleton__bar--title" />
            <div className="hotspot-card__foot">
              <span className="plaza-skeleton__bar plaza-skeleton__bar--meta" />
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
