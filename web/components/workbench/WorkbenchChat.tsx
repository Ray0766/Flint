import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

/**
 * `WB-03-a`：中栏的对话区（蓝本第 111~125 行）。
 *
 * 蓝本形状照做：顶上一行标题 + 提示、下面 `flex:1;overflow-y:auto` 的消息区、
 * 消息是左右分列的气泡（自己说的靠右、系统回的靠左）、生成中多一个「…」气泡。
 *
 * ## 一处形状上的差别，写明为什么
 *
 * 蓝本把标题那一行放在滚动区**外面**（`flex-shrink:0`）。本仓把它放在滚动区
 * **里面**并 `position:sticky` 钉住——效果一样（滚动时它留在原位），
 * 而这样 `WorkbenchShell` 一个字都不用改：那个骨架是 `WB-01` 验过的件，
 * 为了一行标题去动它的槽位，会让 `WB-01` 那份真浏览器取证变成一张旧照片。
 *
 * ## 屏上 NEVER 印内部 id
 *
 * 卡 id / 项目 id 这些是 A 类脚手架（`FB-10`）：对用户毫无意义，
 * 只会让人以为产品还没做完。它们留在 `data-*` 上供取证用——
 * 取证要拿「屏上显示的值 == 数据源里的值」去比，而那条比对不需要把 id 印出来。
 *
 * ## 三种态各说各的
 *
 * | 态 | 记号 | 屏上说的 |
 * |---|---|---|
 * | 在等 | `pending` | 正在做哪一步 |
 * | 成了 | `receipt` | 这一步真的产出了什么 |
 * | 失败 | `failure` | **哪一步**失败 + 服务端自己那句话 |
 *
 * 合并任意两种，用户就分不出「还要等」与「已经结束了」——
 * 而 `mark_failed` 那一族的病正是这么来的：失败不写事件，屏上一直转圈。
 */

export type ChatMessageKind = "ask" | "pending" | "receipt" | "failure" | "notice";

export type ChatMessage = {
  id: string;
  /** 谁说的。`user` 靠右，`system` 靠左（蓝本 `m.justify`）。 */
  role: "user" | "system";
  kind: ChatMessageKind;
  /** 屏上这一句。**上游给什么就显示什么**，本组件不加工。 */
  text: string;
  /** 服务端自己那句话（失败时原样带出来，NEVER 改写）。 */
  quote?: string;
  /** 这一步是哪一步（失败时点名用；也落到 `data-wb-msg-step` 上）。 */
  step?: string;
  /** 取证用的真值：卡 id / 项目 id / 主题 id。**不印在屏上**。 */
  evidence?: Record<string, string>;
};

export type WorkbenchChatProps = {
  messages: ChatMessage[];
};

export function WorkbenchChat({ messages }: WorkbenchChatProps): JSX.Element {
  const pending = messages.some((m) => m.kind === "pending");

  return (
    <div
      className="wb-chat"
      data-wb-chat="true"
      data-wb-chat-pending={pending ? "true" : "false"}
    >
      <div className="wb-chat__head">
        <span className="wb-chat__title">{t("wb.chat.head")}</span>
        <span className="wb-chat__hint">{t("wb.chat.hint")}</span>
      </div>
      {messages.length === 0 ? (
        <p className="wb-chat__empty" data-wb-chat-empty="true">
          {t("wb.chat.placeholder")}
        </p>
      ) : (
        <ol className="wb-chat__list">
          {messages.map((message) => (
            <li
              key={message.id}
              className={`wb-chat__row wb-chat__row--${message.role}`}
              data-wb-msg={message.id}
              data-wb-msg-kind={message.kind}
              data-wb-msg-role={message.role}
              data-wb-msg-step={message.step}
              {...Object.fromEntries(
                Object.entries(message.evidence ?? {}).map(
                  ([key, value]) => [`data-wb-msg-${key}`, value],
                ),
              )}
            >
              <div className={`wb-chat__bubble wb-chat__bubble--${message.kind}`}>
                <span className="wb-chat__text">{message.text}</span>
                {/* 服务端那句话**原样**放在自己的一行里：
                    揉进上面那句会让「我们说的」与「服务端说的」分不开，
                    而用户要拿去问的是后者。 */}
                {message.quote ? (
                  <span className="wb-chat__quote" data-wb-msg-quote="true">
                    {message.quote}
                  </span>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
