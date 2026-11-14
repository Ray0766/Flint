"use client";

// HOTSPOT-01：热点卡片（六信息槽）。**DS-02 把它做成了素材那张卡。**
//
// 主行**恒** name_native（PRINCIPLES#B7）——复用 I18N-04-b 的 NativeName，
// NEVER 在这里另写一份名称呈现：两份实现就是两种主次规则。
//
// 字段缺失时**逐槽隐藏**，NEVER 用「—」「暂无」「N/A」占位：
// 占位符会让「这个热点没有判定」和「判定还没跑」看起来一模一样，
// 而用户据此做的决定完全不同。
//
// ## DS-02 改了什么，为什么
//
// 改前：`article.hotspot-card` 里五个平铺的 span/time，**`.hotspot-card` 在 `_ds` 与
// `globals.css` 里零样式**——组件建好了，屏上是一串裸文字。
// 「只建组件不写样式等于没做」是本批的原话，所以结构与样式**成对**交付：
// 这里出结构与类名，`web/app/globals.css` 出样式，判据取**运行时计算值**。
//
// 版式逐槽照 owner 指定的素材 `前端设计/Flint 热点线索卡堆叠/CardStack.dc.html`：
//
//     纸纹底 --surface + --tex-paper · 1px --rule 边框 · --r-card 圆角 · --shadow-sticker · 24px 内边距
//     顶行：StickerTag（左）        StatusMark（右）
//     标题：--fs-20 / 600 / --ink
//     次要行：--fs-14 / 两行截断 / --ink-2
//     ──── 1px --rule ────
//     脚注：--font-mono · tabular-nums · --ink-3
//
// 素材那份是 `.dc.html`（**已 Flint 化：零 framer-motion / 零 lucide / 零 Tailwind，
// 全用 `_ds` token**）。`uploads/CardStack.txt` 是第三方原始版，NEVER 照那份做。
//
// ## 六槽落在哪
//
// | 槽 | 位置 | 缺失时 |
// |---|---|---|
// | 原生名 | 标题 | 恒在（卡片的最小可用态） |
// | 机翻译名 | 次要行（两行截断） | 只显主行（A7 降级） |
// | 地区 | 顶行左：贴纸标签 | 隐藏该槽，NEVER 猜一个区 |
// | Gate 判定 | 顶行右：状态记号 | 隐藏该槽 |
// | 首见日期 | 脚注左 | 隐藏该槽 |
// | 热度（PLAZA-01 加） | 脚注中 | 隐藏该槽；**后端给的数原样显示，本屏零计算** |
// | 陈旧 | 脚注右：状态记号 | `false` 与「没判过」都不显示——两者都不是「陈旧」 |

import type { JSX } from "react";

import { DsStatusMark } from "../shell/DsStatusMark";
import { DsStickerTag } from "../shell/DsStickerTag";
import { NativeName, type TranslatedText } from "../native-name/NativeName";
import { enumLabel } from "../../lib/i18n/enumLabel";
import { t } from "../../lib/i18n/t";
import { verdictStatus } from "./verdictStatus";

export type HotspotCardProps = {
  nameNative: string;
  nameLang?: string;
  /** 机翻次要行；无译文时不渲染该槽（A7 降级） */
  nameDisplay?: TranslatedText | null;
  /** 首次出现日期；缺失则隐藏该槽 */
  firstSeen?: string | null;
  /** 地区；缺失（未归区）则隐藏该槽 —— NEVER 猜一个区 */
  region?: string | null;
  /**
   * 陈旧标记，来自后端 `Revalidator` 统一口径（§6-H1）；`undefined` = 未判定过。
   *
   * ## `DEC-039`：热点簇这一槽**恒不显示**，而且今天没有任何产出方会填它
   *
   * 热点簇不是一份分析：它不引用事实，**它是事实的来源之一**。`Revalidator` 判的是
   * 「一份分析引用过的事实变没变」，要 `project_id`、账本版本、被引用的那些事实三样，
   * 而 `clusters` 表一样都没有（`SLOT-02` 单实查过全部十列）。所以广场的搬运层
   * `clusterToCard` **不传** `stale`，这一槽在广场上落不到 `true`。
   *
   * **槽保留、不删**：删掉的话，恢复它的人要重新决定挂在哪一格、用什么记号、什么文案，
   * 而那些当初都是照素材 `CardStack.dc.html` 定过的。
   *
   * **恢复条件**：哪天簇身上真有可判新旧的东西——账本侧给出了「这个簇引用的事实变了」，
   * 或 `favorites` 落库后在**收藏屏**上说「你收藏的那份快照旧了」——
   * 让那一处的产出方开始传 `stale`，这一槽自己就会亮；**改那一处即可，本文件不用动**。
   *
   * **NEVER 拿 `last_active` / `first_seen` 跟今天一比来填它**：那是新写一套比对，
   * 而且它说的是系统不知道的事。`tools/check_no_timestamp_staleness.py` 全仓守着这一条。
   */
  stale?: boolean | null;
  /** Gate 四分类判定；缺失则隐藏该槽 */
  verdict?: string | null;
  /**
   * 热度。**后端给的数原样显示**——本组件不排序、不换算、不合成（PLAZA-01 加的第七槽，
   * 位置照素材脚注第三格「事实 N 条」那一格）。缺失则隐藏该槽。
   */
  heat?: number | null;
};

export function HotspotCard({
  nameNative,
  nameLang,
  nameDisplay,
  firstSeen,
  region,
  stale,
  verdict,
  heat,
}: HotspotCardProps): JSX.Element {
  return (
    <article className="hotspot-card" data-testid="hotspot-card">
      <div className="hotspot-card__top">
        {region ? (
          <span className="hotspot-card__region" data-testid="hotspot-region">
            <DsStickerTag tone="paper">{region}</DsStickerTag>
          </span>
        ) : null}
        {verdict ? (
          <span className="hotspot-card__verdict" data-testid="hotspot-verdict">
            {/* DS-03：标签走 `enumLabel`——`D_insufficient` 是数据库的值，不是给人看的话。
                映射表在 `web/lib/i18n/enumLabel.ts` 一处，NEVER 在这里编一句：
                同一个值在判定屏与卡面各编一句，两处话术就会各自漂移。
                表里没登记的值原样返回并告警，于是判据当场抓得住。 */}
            <DsStatusMark
              status={verdictStatus(verdict)}
              label={enumLabel("verdict", verdict)}
            />
          </span>
        ) : null}
      </div>
      <NativeName nameNative={nameNative} nameLang={nameLang} display={nameDisplay} />
      <div className="hotspot-card__foot">
        {firstSeen ? (
          <time
            className="hotspot-card__first-seen"
            data-testid="hotspot-first-seen"
            dateTime={firstSeen}
          >
            {firstSeen}
          </time>
        ) : null}
        {heat === null || heat === undefined ? null : (
          <span className="hotspot-card__heat" data-testid="hotspot-heat" data-heat={heat}>
            {t("card.heat.label")} {heat}
          </span>
        )}
        {stale === true ? (
          <span className="hotspot-card__stale" data-testid="hotspot-stale" data-stale="true">
            {/* 复用收藏屏那条既有文案（`favorites.stale.yes`），NEVER 为同一件事再起一个 key。
                改前这里是个**空 span**：读屏软件念不出来，屏上也只有 0 像素。 */}
            <DsStatusMark status="review" label={t("favorites.stale.yes")} />
          </span>
        ) : null}
      </div>
    </article>
  );
}
