"use client";

// DS-01：`_ds` 的八态状态标记，Flint 侧的封装。
//
// ## 它**不是**另一个 StatusMark
//
// 本仓已有 `web/components/shell/StatusMark.tsx`（`UIX-03` 建的），那一个说的是
// **作业状态**（queued / running / done / failed），来自后端的 `data-row-state` 一族。
// 这一个说的是 `_ds` 的**内容状态**八态（已证 / 待复核 / 待处理 / 争议 / 推测 /
// 空缺 / 只读 / 降级生成）——正好是 Flint 三条铁律在屏上的形状：
// 结论有没有引用、数字是不是三通道、这一块是不是被锁。
//
// 两者 NEVER 合并：合并之后「作业跑挂了」与「这条结论有争议」会共用一个记号。
// 名字带 `Ds` 前缀就是为了让这件事在 import 那一行就看得出来。
//
// ## 本文件里 NEVER 出现视觉常量
//
// 边框、底纹、记号形状全在 `_ds` 那边。抄一份过来的话，两份视觉从此各自漂移，
// 而屏上看不出哪一份才是设计系统。判据逐条盯着这件事
// （`test_the_wrapper_is_a_delegate_not_a_visual_replica`）。

import type { CSSProperties, JSX } from "react";

import { useDsComponent } from "./dsBundle";

/**
 * 八态。**真相在 `_ds_bundle.js` 的 `DEFS` 表**，这里只是把它写成类型好让 tsc 挡住错值；
 * 判据从 bundle 源码解析属性名逐字比对，改了那边这里就会红。
 */
export type DsStatus =
  | "verified"
  | "review"
  | "blocking"
  | "disputed"
  | "speculative"
  | "void"
  | "sealed"
  | "degraded";

type DsStatusMarkProps = {
  status: DsStatus;
  label?: string;
  style?: CSSProperties;
};

export function DsStatusMark({
  status,
  label,
  style,
}: DsStatusMarkProps): JSX.Element {
  const Mark = useDsComponent<DsStatusMarkProps>("StatusMark");

  // bundle 还没到：**只把文字交出来**，NEVER 画一个像 _ds 的东西顶上。
  // 顶上去的那一版会在慢网下被截图、被当成设计系统的样子——而它谁也不是。
  if (Mark === null) {
    return (
      <span data-ds-pending="StatusMark" data-ds-status={status}>
        {label ?? ""}
      </span>
    );
  }
  return (
    <span data-ds-component="StatusMark" data-ds-status={status}>
      <Mark status={status} label={label} style={style} />
    </span>
  );
}
