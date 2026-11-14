// GRAPH-10：全局撤销栈（跨视图**一条**链，§6-H5）。
//
// 用户按 ⌘Z 时脑子里是**一条时间线**：他要撤的是「我刚才做的那件事」，
// 不管那件事发生在图谱上、编辑器里还是图书馆里。每个视图各留一条栈的话，
// 同一个 ⌘Z 在不同视图下撤掉的是不同时刻的操作，而用户并不知道自己此刻在哪条栈上。
//
// 所以本模块**不导出类、也不导出工厂**：没有第二条栈可造。图谱的操作
// （GRAPH-04 拖动、GRAPH-07 连线、GRAPH-09 批量角色）与其它视图共用这一条。
//
// ## 先执行后出栈
//
// 撤销动作失败时那一条**留在栈上**：出栈再执行的话，失败之后这一步就永远消失了——
// 用户既没撤成，也再也撤不了，而界面上什么都看不出来。
//
// ## 满了丢最旧的
//
// 上限 200 是一个写死的手写值（不是估计出来的「合适值」）：够覆盖一次连续编辑，
// 又不让闭包无限堆着。满了丢**最旧**的——丢最新的等于让用户刚做的那步撤不回来，
// 而那正是他最可能想撤的一步。

// ## 受保护 block 的操作 NEVER 进栈（S2-5，DEF-03 接线时补）
//
// `locked ∨ author=="user" ∨ user_modified` 的 block 前端强制只读，所以它身上
// 本来就不该有可撤销的操作。真出现了，说明**上游已经违规改过它**——
// 此时入栈会把违规变成一条正常的历史，用户按 ⌘Z 撤掉的是一次本不该发生的修改。
//
// `pushBlockUndo` 因此有返回值：挡下与入栈长得不一样，调用方 NEVER 以为一定入了栈。

import { isProtected } from "../types";
import type { Block } from "../types";

/** 栈深上限。满了丢最旧的一条。 */
export const UNDO_LIMIT = 200;

export type UndoEntry = {
  /** 哪个视图产生的（graph / editor / library …），用于提示与排查 */
  view: string;
  /** 撤什么（add-edge / move-node …） */
  label: string;
  /** 真正的撤销动作；抛错 = 撤销失败，该条留在栈上 */
  undo: () => void | Promise<void>;
};

const stack: UndoEntry[] = [];

/** 读栈（**副本**：外部改它 NEVER 影响真身）。栈顶在末尾。 */
export function getUndoStack(): UndoEntry[] {
  return [...stack];
}

export function undoDepth(): number {
  return stack.length;
}

export function clearUndo(): void {
  stack.length = 0;
}

export function pushUndo(entry: UndoEntry): void {
  if (entry.view.trim() === "" || entry.label.trim() === "") {
    throw new Error(
      "undo entry needs a view and a label: an entry that cannot say what it is " +
        "gives the user nothing to decide on",
    );
  }
  stack.push(entry);
  if (stack.length > UNDO_LIMIT) stack.splice(0, stack.length - UNDO_LIMIT);
}

/**
 * block 相关操作的入栈口。受保护 block 一律挡下（S2-5），返回值说明入没入。
 *
 * 与 `pushUndo` 分开而不是塞进它：图谱那三处（节点/边/角色）根本没有 block，
 * 硬要它们造一个假 block 才能入栈，比多一个函数糟得多。
 */
export function pushBlockUndo(block: Block, entry: UndoEntry): boolean {
  if (isProtected(block)) return false;
  pushUndo(entry);
  return true;
}

/** 撤最近一步。空栈返回 null（新开一页按 ⌘Z 不该炸）。 */
export async function undo(): Promise<UndoEntry | null> {
  const entry = stack[stack.length - 1];
  if (entry === undefined) return null;
  await entry.undo();       // 先执行：抛错就不出栈，用户还能再试一次
  stack.pop();
  return entry;
}
