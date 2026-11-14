"use client";

import { useCallback, useState, type JSX, type ReactNode } from "react";

import { t } from "../../lib/i18n/t";

/**
 * `WB-01`：计划书主工作台的三栏骨架。
 *
 * 风格来源：`前端设计/ai工作台/Flint 设计台 v3.dc.html`（owner 2026-08-12 指定）。
 * **照它做**，NEVER 自创一版。
 *
 * ## 蓝本的形状（第 46~170 行）与本文件的对应
 *
 * ```
 * <div flex:1 min-height:0 display:flex>            .workbench__row
 *   <div width:{sideW}px flex-shrink:0 display:flex>  .workbench__side   sideW = 600
 *     <div width:{cardsW}px flex-shrink:0>            .workbench__cards  cardsW = 250
 *     <div width:7px cursor:col-resize>               .workbench__grip--cards
 *     <div flex:1 min-width:0 min-height:0>           .workbench__chat
 *   <div width:7px cursor:col-resize>                 .workbench__grip--side
 *   <div flex:1 min-width:0>                          .workbench__preview
 *     <div flex:1 overflow-y:auto padding:24px>        .workbench__canvas
 *       <div flex:0 1 860px min-width:0>                .workbench__doc
 * ```
 *
 * 三个初始值**照蓝本第 305~306 行**：`sideW: 600` · `cardsW: 250` ·
 * `previewWidth: '860px'`。这三个数 NEVER 自己拍——owner 的原话是「别自己拍」。
 *
 * ## 两处刻意没照蓝本做（都写进 `WB-01` 的 trace 与完成态报告）
 *
 * **一 · 外链字体**：蓝本 `<head>` 里引了 Google Fonts 的 IBM Plex Sans。
 * NEVER 引——CI 恒不联网（`S2-7`），而且那是一次第三方请求。
 * 字体走本仓 `_ds` 已有的 `--font-*`。
 *
 * **二 · 窄屏**：蓝本是个桌面 demo，**没有任何响应式**（三栏永远横排）。
 * 390 上照抄的话，250 + 240 + 文档挤在 390 里，每一栏都窄到读不了，
 * 而**屏上不会报错**。所以窄屏改成纵向排开、整页正常滚动
 * （`height:100vh + overflow:hidden` 那一套只在宽屏成立）。
 *
 * ## 拖宽的下限来自蓝本，不是我定的
 *
 * 蓝本 `startDrag`：`cardsW` 夹在 `[140, sideW - 240]`，`sideW` 夹在
 * `[380, innerWidth * 0.55]`。上限那一侧 `sideW - 240` 的意思是
 * **中栏永远至少留 240px**——没有它，一次拖到底会把对话栏压成 0，
 * 而压成 0 之后屏上看起来像那一栏不见了，用户不会想到往回拖。
 */

/** 蓝本第 306 行 `sideW: 600`。 */
const SIDE_INITIAL = 600;
/** 蓝本第 306 行 `cardsW: 250`。 */
const CARDS_INITIAL = 250;
/** 蓝本 `startDrag` 的两个下限：卡片栏 140，中栏 240。 */
const CARDS_MIN = 140;
const CHAT_MIN = 240;
/** 蓝本 `startDrag`：`Math.max(380, …)` 与 `Math.min(innerWidth * 0.55, …)`。 */
const SIDE_MIN = 380;
const SIDE_MAX_RATIO = 0.55;

type Axis = "side" | "cards";

/**
 * ## 滚动放在**栏内那一层**，不是放在栏上
 *
 * 蓝本三栏没有一栏自己 `overflow-y:auto`：卡片栏滚的是它里面那个
 * `flex:1;min-height:0;overflow-y:auto`（第 54 行），对话栏滚的是消息区
 * （第 116 行），预览栏滚的是画布（第 170 行）。栏本身是 flex 列，
 * 顶上的页签、底下的输入框**要钉住不跟着滚**。
 *
 * 让栏内滚得起来的那一行是 `min-height: 0`：flex 子项默认 `min-height:auto`，
 * 内容多了会把栏**撑高**而不是在栏里滚——撑高之后整页跟着滚，
 * 而屏上看起来只是「页面变长了」，没有人会想到是这一行。
 */
export type WorkbenchShellProps = {
  /** 左栏滚动区：热点/证据卡片选取（`WB-02` 填）。 */
  cards: ReactNode;
  /** 左栏钉在顶上的页签行（`WB-02` 填）。不传就不渲染。 */
  cardsHeader?: ReactNode;
  /** 中栏滚动区：对话消息（`WB-03` 填）。 */
  chat: ReactNode;
  /** 中栏钉在底下的输入区（`WB-03` 填）。不传就不渲染。 */
  chatFooter?: ReactNode;
  /** 右栏画布里那一列文档（`WB-04` 填）。 */
  doc: ReactNode;
  /** 右栏顶部工具条（`WB-04`/`WB-06` 填）。不传就不渲染那一条。 */
  previewToolbar?: ReactNode;
  /** 文档左侧的章节导航（`WB-05` 填）。不传就不渲染。 */
  sectionNav?: ReactNode;
};

export function WorkbenchShell({
  cards,
  cardsHeader,
  chat,
  chatFooter,
  doc,
  previewToolbar,
  sectionNav,
}: WorkbenchShellProps): JSX.Element {
  const [sideW, setSideW] = useState(SIDE_INITIAL);
  const [cardsW, setCardsW] = useState(CARDS_INITIAL);
  const [dragging, setDragging] = useState<Axis | null>(null);

  /* 侧栏被拖窄时，卡片栏跟着收——不收的话中栏会被挤到 240 以下。
     判据 `test_the_chat_column_survives_being_dragged_to_the_limit` 钉着这一条。

     **算出来的，不是靠一个副作用钩子同步出来的。** 第一版写的是
     「`sideW` 变了就 `setCardsW` 收一下」，两处代价：
     ① 多一次渲染，收窄那一帧屏上会闪；
     ② 「进屏副作用」是 `A6` 三态规则认取数屏的信号之一，
        而这一屏此刻一个请求都不发——于是它会被要求写一个
        「永远进不去的死分支」加载态，那正是 `A6` 自己的注释在警告的事。
        （那条规则拿**原文**判、连注释一起扫，所以这一段也不能把
         那个钩子的名字写出来。单据 `docs/blocked/A6-READS-COMMENTS.md`。）
     宽度是从 `sideW` **算得出来**的，算得出来的东西 NEVER 存成第二份状态。 */
  const cardsEffective = Math.min(cardsW, Math.max(CARDS_MIN, sideW - CHAT_MIN));

  /* 拖动照蓝本 `startDrag`：按下时记起点与基准值，`mousemove` 里算增量，
     `mouseup` 撤监听。**监听挂在 window 上而不是拖条上**——鼠标跑出那 7px
     宽的条之后事件就不再落在它身上了，而人拖得快时一定会跑出去。 */
  const startDrag = useCallback(
    (axis: Axis) => (event: React.PointerEvent<HTMLDivElement>) => {
      event.preventDefault();
      const startX = event.clientX;
      const base = axis === "side" ? sideW : cardsEffective;
      setDragging(axis);
      // 拖动时禁掉选区：不禁的话整屏文字会被刷成蓝的（蓝本同款）。
      document.body.style.userSelect = "none";

      const move = (ev: PointerEvent): void => {
        const d = ev.clientX - startX;
        if (axis === "side") {
          const max = Math.round(window.innerWidth * SIDE_MAX_RATIO);
          setSideW(Math.min(max, Math.max(SIDE_MIN, base + d)));
        } else {
          // 上限 = 当前 sideW - 中栏下限：**中栏永远留得住**。
          const limit = Math.max(CARDS_MIN, sideW - CHAT_MIN);
          setCardsW(Math.min(limit, Math.max(CARDS_MIN, base + d)));
        }
      };
      const up = (): void => {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
        document.body.style.userSelect = "";
        setDragging(null);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
    },
    [sideW, cardsEffective],
  );

  /** 键盘也拖得动：拖条是 `separator` 角色，左右键各挪 16px。
   *  只给鼠标的话，这条能力对键盘用户等于不存在。 */
  const nudge = (axis: Axis) => (event: React.KeyboardEvent<HTMLDivElement>) => {
    const step = event.key === "ArrowLeft" ? -16 : event.key === "ArrowRight" ? 16 : 0;
    if (step === 0) return;
    event.preventDefault();
    if (axis === "side") {
      const max = Math.round(window.innerWidth * SIDE_MAX_RATIO);
      setSideW((prev) => Math.min(max, Math.max(SIDE_MIN, prev + step)));
    } else {
      setCardsW((prev) =>
        Math.min(Math.max(CARDS_MIN, sideW - CHAT_MIN), Math.max(CARDS_MIN, prev + step)),
      );
    }
  };

  return (
    <div
      className="workbench"
      data-wb-dragging={dragging ?? "no"}
      /* 两个宽度走 CSS 变量而不是内联 `width`：窄屏那一档要把它们整个作废
         （纵向排开），而内联样式压得过媒体查询——那正是「响应式失效」
         最常见的一种写法。 */
      style={{ ["--wb-side" as string]: `${sideW}px`, ["--wb-cards" as string]: `${cardsEffective}px` }}
    >
      <div className="workbench__row">
        <div className="workbench__side" data-wb-side="true">
          <section
            className="workbench__col workbench__cards"
            data-wb-col="cards"
            aria-label={t("wb.col.cards")}
          >
            {cardsHeader ? (
              <div className="workbench__col-head" data-wb-head="cards">
                {cardsHeader}
              </div>
            ) : null}
            <div className="workbench__scroll" data-wb-scroll="cards">
              {cards}
            </div>
          </section>
          <div
            className="workbench__grip workbench__grip--cards"
            data-wb-grip="cards"
            role="separator"
            aria-orientation="vertical"
            aria-label={t("wb.grip.cards")}
            tabIndex={0}
            onPointerDown={startDrag("cards")}
            onKeyDown={nudge("cards")}
          />
          <section
            className="workbench__col workbench__chat"
            data-wb-col="chat"
            aria-label={t("wb.col.chat")}
          >
            <div className="workbench__scroll" data-wb-scroll="chat">
              {chat}
            </div>
            {chatFooter ? (
              <div className="workbench__col-foot" data-wb-foot="chat">
                {chatFooter}
              </div>
            ) : null}
          </section>
        </div>
        <div
          className="workbench__grip workbench__grip--side"
          data-wb-grip="side"
          role="separator"
          aria-orientation="vertical"
          aria-label={t("wb.grip.side")}
          tabIndex={0}
          onPointerDown={startDrag("side")}
          onKeyDown={nudge("side")}
        />
        <section
          className="workbench__col workbench__preview"
          data-wb-col="preview"
          aria-label={t("wb.col.preview")}
        >
          {previewToolbar ? (
            <div className="workbench__toolbar" data-wb-toolbar="true">
              {previewToolbar}
            </div>
          ) : null}
          {/* 画布是**预览栏里滚动的那一层**（蓝本第 170 行：
              `flex:1;overflow-y:auto;padding:24px` + 18px 的点阵底）。
              滚动放在画布而不是放在预览栏本身：工具条要钉在顶上不跟着滚。 */}
          <div className="workbench__canvas" data-wb-scroll="preview" data-wb-canvas="true">
            {sectionNav ? (
              <div className="workbench__nav" data-wb-nav="true">
                {sectionNav}
              </div>
            ) : null}
            <div className="workbench__doc" data-wb-doc="true">
              {doc}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
