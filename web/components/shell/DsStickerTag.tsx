"use client";

// DS-01：`_ds` 的贴纸标签，Flint 侧的封装。
//
// 它是 owner 指定的那份素材（`前端设计/Flint 热点线索卡堆叠/CardStack.dc.html`）
// 顶行左边那一枚，也是屏头那行 mono 副标该有的形态：纸面上贴一张微微歪的小标签。
//
// ## 四个色调**不是四种情绪**
//
// `_ds` 的色彩纪律：装饰域随便用，语义域受限。贴纸的 `tone` 属于装饰域，
// 所以这里不给它派语义——「这条是争议」该用 `DsStatusMark`，不是把贴纸涂红。
//
// 本文件里 NEVER 出现视觉常量，理由与 `DsStatusMark.tsx` 同：抄一份就有两份视觉在漂。

import type { CSSProperties, JSX, ReactNode } from "react";

import { useDsComponent } from "./dsBundle";

/** 色调。真相在 `_ds_bundle.js` 的 `tones` 表。 */
export type DsTone = "paper" | "indigo" | "sulfur" | "moss";

type DsStickerTagProps = {
  children?: ReactNode;
  /** 歪多少度。`_ds` 自己夹在 ±1.5 之间，这里不再夹一次——夹两遍等于有两份规则。 */
  rotate?: number;
  tone?: DsTone;
  /** 数值与 id 走 mono（`_ds` 的 Type 纪律），散文不走。默认 mono。 */
  mono?: boolean;
  style?: CSSProperties;
};

export function DsStickerTag({
  children,
  rotate,
  tone,
  mono,
  style,
}: DsStickerTagProps): JSX.Element {
  const Tag = useDsComponent<DsStickerTagProps>("StickerTag");

  // bundle 还没到：内容原样交出，不带任何贴纸的样子。
  if (Tag === null) {
    return <span data-ds-pending="StickerTag">{children}</span>;
  }
  return (
    <span data-ds-component="StickerTag">
      <Tag rotate={rotate} tone={tone} mono={mono} style={style}>
        {children}
      </Tag>
    </span>
  );
}
