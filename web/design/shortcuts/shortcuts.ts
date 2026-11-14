// DESIGN-22：快捷键与 ⌘K 命令面板（G28）。
//
// **绑定表是唯一真相**：六条绑定写在一张表里，注册与「设置里查看」读的是同一份。
// 分两处写的话，用户在设置里看到的和实际按下去发生的会不一样——
// 而他会照着设置里那份去按，然后以为键盘坏了。
//
// **⌘Z 不在这里实现撤销**：它派发到 GRAPH-10 的全局撤销栈。快捷键层自己维护
// 一条撤销链，就会出现「按钮撤的和快捷键撤的不是同一件事」。
//
// **平台修饰键**：mac 用 ⌘（metaKey），其它平台用 Ctrl。判定由调用方传入——
// 组件自己嗅探 UA 会在触屏笔记本/远程桌面这类场合判错（与 GRAPH-13 同一条纪律）。
//
// **输入框里不抢键**：用户在文本框里按 ⌘Z 想撤的是刚才那几个字，不是画布上的操作。
// 只有 ⌘⏎（发送）与 ⌘K（命令面板）在输入态下仍生效——那两条本来就是给输入用的。

export type ShortcutId =
  | "send"
  | "undo"
  | "toggleAiPanel"
  | "tabGraph"
  | "tabTree"
  | "commandPalette";

export type ShortcutBinding = {
  id: ShortcutId;
  /** 主键（小写；Enter 用 "enter"） */
  key: string;
  /** 是否需要平台修饰键（⌘ / Ctrl） */
  mod: boolean;
  /** 在输入框里是否仍然生效 */
  worksInInput: boolean;
  /** 设置页展示用的文案 key */
  labelKey: string;
};

/** 六条绑定：注册与「设置里查看」共用这一份。 */
export const SHORTCUTS: readonly ShortcutBinding[] = [
  { id: "send", key: "enter", mod: true, worksInInput: true, labelKey: "design.shortcut.send" },
  { id: "undo", key: "z", mod: true, worksInInput: false, labelKey: "design.shortcut.undo" },
  {
    id: "toggleAiPanel", key: "\\", mod: true, worksInInput: false,
    labelKey: "design.shortcut.toggle_ai",
  },
  { id: "tabGraph", key: "1", mod: true, worksInInput: false, labelKey: "design.shortcut.tab_graph" },
  { id: "tabTree", key: "2", mod: true, worksInInput: false, labelKey: "design.shortcut.tab_tree" },
  {
    id: "commandPalette", key: "k", mod: true, worksInInput: true,
    labelKey: "design.shortcut.palette",
  },
];

export type KeyEventLike = {
  key: string;
  metaKey: boolean;
  ctrlKey: boolean;
  /** 事件源是否为输入控件 */
  inInput: boolean;
};

export type Platform = "mac" | "other";

/** 事件 → 绑定 id；没有匹配就是 null（NEVER 猜一个最近的）。 */
export function matchShortcut(
  event: KeyEventLike,
  platform: Platform,
): ShortcutId | null {
  const mod = platform === "mac" ? event.metaKey : event.ctrlKey;
  const key = event.key.toLowerCase();
  for (const binding of SHORTCUTS) {
    if (binding.key !== key) continue;
    if (binding.mod !== mod) continue;
    if (event.inInput && !binding.worksInInput) return null;
    return binding.id;
  }
  return null;
}

/** 设置页要展示的清单：与注册用的是同一份表。 */
export function listShortcuts(): readonly ShortcutBinding[] {
  return SHORTCUTS;
}
