// DESIGN-01：设计台对话面板（G7 流式渲染，前端半）。
//
// **边到边渲染**：每收到一段就画一段。等整回合再显示的话，用户面对的是一个
// 几十秒不动的界面——他不知道是在想、还是卡住了、还是自己没点上。
// 流式的价值不在快，在**可见**。
//
// **流由调用方注入**：本面板不 new EventSource、不自己 fetch。自己开一条流
// 等于绕开既有 JobEventStream 另开第二条通道（§6-H4 禁止），
// 那之后两条流的 seq 各排各的，断线重连时先后无从判断。
//
// **零段结束不显示空回合**：那是「没有回答」，不是「回答是空字符串」——
// 画一个空气泡出来，用户会以为模型答了什么但没显示出来。

import type { JSX } from "react";
import { useEffect, useRef, useState } from "react";

import { t } from "../../lib/i18n/t";

export type DeltaHandlers = {
  onDelta: (fragment: string) => void;
  onDone: () => void;
};

export type DeltaSource = {
  /** 订阅一次，返回退订函数 */
  subscribe: (handlers: DeltaHandlers) => () => void;
};

export function ChatPanel({ source }: { source: DeltaSource }): JSX.Element {
  const [fragments, setFragments] = useState<string[]>([]);
  const [streaming, setStreaming] = useState(true);
  const handlers = useRef<DeltaHandlers | null>(null);

  handlers.current = {
    onDelta: (fragment: string) => setFragments((prev) => [...prev, fragment]),
    onDone: () => setStreaming(false),
  };

  useEffect(() => {
    // 订阅只建一次：每次渲染都重订会让同一段 delta 被收多份，文字于是重复
    const unsubscribe = source.subscribe({
      onDelta: (fragment) => handlers.current?.onDelta(fragment),
      onDone: () => handlers.current?.onDone(),
    });
    return unsubscribe;
  }, [source]);

  const text = fragments.join("");

  return (
    <div data-testid="chat-panel">
      {text === "" && !streaming ? (
        <p data-testid="chat-empty">{t("design.chat.empty")}</p>
      ) : null}
      {text === "" ? null : <p data-testid="chat-answer">{text}</p>}
      {streaming ? (
        <span data-testid="chat-streaming" role="status">
          {t("design.chat.streaming")}
        </span>
      ) : null}
    </div>
  );
}
