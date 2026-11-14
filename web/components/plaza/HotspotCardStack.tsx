"use client";

// PLAZA-01：热点线索卡**堆叠**（今日精选）。几何逐条照 owner 指定的素材
// `前端设计/Flint 热点线索卡堆叠/CardStack.dc.html`：
//
//     容器 420px 高 · perspective 1100px
//     扇形 48°（每档 spreadDeg/3 = 16°）· 重叠 0.48（间距 = 520 × (1−0.48) = 270px）
//     卡 520×320 · 中心卡上浮 22px、放大 1.03 · 侧卡后退 140px/档、绕 X 轴 12°
//     底部圆点导航 + 「N / M · 点击侧卡或拖拽当前卡切换」
//
// ## 它只负责**排布**，卡面本体是 `HotspotCard`
//
// 我们刚为「两个广场各自漂移」吃过亏（那正是本批要治的病）。所以这里一个卡面槽都不画：
// 传进来什么就摆什么，判据 `test_plaza_cards.py` 盯着本文件里**零 `hotspot-card__*` 类名**。
//
// ## 三条进出路，NEVER 只留拖拽
//
// 1. **键盘**：容器可聚焦，方向键左右切换，焦点环用 `--focus-ring`；
// 2. **点侧卡**：点哪张哪张到前面；
// 3. **拖当前卡**：越过阈值就翻一张；
// 4. **点当前卡**：选中它（进工作台）——堆叠 NEVER 只是个看板，它是入口。
//
// 只留拖拽的话，用键盘的人与用读屏的人**根本到不了第二张卡**——
// 那不是「体验差一点」，是这一屏对他们只有一条热点。
// `prefers-reduced-motion` 下不接管指针（拖拽会带来大幅位移），键盘与点击照常。

import { useCallback, useEffect, useRef, useState, type JSX, type CSSProperties } from "react";

import { HotspotCard } from "../hotspot-card/HotspotCard";
import { t } from "../../lib/i18n/t";
import type { PlazaCardProps } from "./clusterToCard";

// 素材原值。改这几个数就是改视觉，所以它们在一处、有名字。
const CARD_W = 520;
const CARD_H = 320;
const SPREAD_DEG = 48;
const OVERLAP = 0.48;
const MAX_OFFSET = 2;               // 前后各露两张，再远的隐藏
const SPACING = Math.round(CARD_W * (1 - OVERLAP));
const STEP_DEG = SPREAD_DEG / 3;
const DRAG_THRESHOLD = 114;         // 素材：min(160, 520 × 0.22)

function positionOf(offset: number, dragX: number, dragging: boolean): CSSProperties {
  const abs = Math.abs(offset);
  const isActive = offset === 0;
  const hidden = abs > MAX_OFFSET;
  const x = offset * SPACING + (isActive ? dragX : 0);
  const y = abs * 10 + (isActive ? -22 : 0);
  return {
    position: "absolute",
    left: "50%",
    bottom: 0,
    width: CARD_W,
    height: CARD_H,
    marginLeft: -CARD_W / 2,
    zIndex: 100 - abs,
    transform: `translateX(${x}px) translateY(${y}px) translateZ(${-abs * 140}px) `
      + `rotateZ(${offset * STEP_DEG}deg) rotateX(${isActive ? 0 : 12}deg) `
      + `scale(${isActive ? 1.03 : 0.94})`,
    transformStyle: "preserve-3d",
    opacity: hidden ? 0 : 1,
    pointerEvents: hidden ? "none" : "auto",
    cursor: isActive ? (dragging ? "grabbing" : "grab") : "pointer",
    transition: dragging && isActive
      ? "none"
      : "transform .55s cubic-bezier(.22,.9,.3,1.08), opacity .4s ease",
  };
}

export function HotspotCardStack({
  cards,
  onSelectCluster,
}: {
  cards: PlazaCardProps[];
  /** 点**当前**那张即选中它（进工作台）。点侧卡只是把它送到前面。 */
  onSelectCluster?: (clusterId: string) => void;
}): JSX.Element {
  const [active, setActive] = useState(0);
  const [dragX, setDragX] = useState(0);
  const [dragging, setDragging] = useState(false);
  const drag = useRef({ startX: 0 });
  const len = cards.length;

  const wrap = useCallback((n: number): number => ((n % len) + len) % len, [len]);
  const go = useCallback((d: number): void => {
    setActive((a) => wrap(a + d));
    setDragX(0);
  }, [wrap]);

  useEffect(() => {
    if (!dragging) return undefined;
    const onMove = (e: PointerEvent): void => setDragX(e.clientX - drag.current.startX);
    const onUp = (): void => {
      setDragging(false);
      setDragX((dx) => {
        if (dx > DRAG_THRESHOLD) go(-1);
        else if (dx < -DRAG_THRESHOLD) go(1);
        return 0;
      });
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [dragging, go]);

  return (
    <section className="plaza-stack" data-plaza-stack="true">
      <h3 className="plaza-stack__heading">{t("plaza.stack.heading")}</h3>
      <div
        className="plaza-stack__deck"
        data-testid="plaza-stack-deck"
        // 可聚焦 + 方向键：键盘可达的那一半（`role="listbox"` 会承诺一套本组件没实现的
        // 选中语义，所以这里只做 group + 一句用法说明）。
        tabIndex={0}
        role="group"
        aria-label={t("plaza.stack.heading")}
        aria-describedby="plaza-stack-hint"
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft") go(-1);
          if (e.key === "ArrowRight") go(1);
          // NAV-02：点当前这张卡现在**真的会跳屏**了。改前方向键能翻、
          // 却没有一个键能「打开」——键盘用户走到堆叠上只能来回翻页。
          // 空格要 `preventDefault`：默认行为是滚动一屏。
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelectCluster?.(cards[active].clusterId);
          }
        }}
      >
        {cards.map((card, i) => {
          let offset = i - active;
          if (len > 1) {
            const alt = offset > 0 ? offset - len : offset + len;
            if (Math.abs(alt) < Math.abs(offset)) offset = alt;
          }
          const isActive = offset === 0;
          return (
            <div
              key={card.clusterId}
              className="plaza-stack__slot"
              data-cluster-id={card.clusterId}
              data-cluster-category={card.categoryId}
              data-stack-active={String(isActive)}
              style={positionOf(offset, dragX, dragging)}
              onClick={() => {
                // 拖动中的那一下 NEVER 算点击（手指抖一下就跳走是最恼人的一种）。
                if (Math.abs(dragX) >= 4) return;
                if (isActive) onSelectCluster?.(card.clusterId);
                else setActive(i);
              }}
              onPointerDown={(e) => {
                if (!isActive) return;
                if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
                drag.current.startX = e.clientX;
                setDragging(true);
                setDragX(0);
              }}
            >
              <HotspotCard {...card} />
            </div>
          );
        })}
      </div>
      <div className="plaza-stack__dots">
        {cards.map((card, i) => (
          <button
            key={card.clusterId}
            type="button"
            className="plaza-stack__dot"
            data-dot-active={String(i === active)}
            aria-label={t("plaza.stack.dot", { name: card.nameNative })}
            aria-current={i === active ? "true" : undefined}
            onClick={() => setActive(i)}
          />
        ))}
      </div>
      <p className="plaza-stack__counter" id="plaza-stack-hint" data-testid="plaza-stack-counter">
        {t("plaza.stack.counter", {
          current: String(active + 1).padStart(2, "0"),
          total: String(len).padStart(2, "0"),
        })}
        <span className="plaza-stack__kbd-hint">{t("plaza.stack.hint")}</span>
      </p>
    </section>
  );
}
