// DESIGN-14：演示模式（G18，全屏 / 隐 chrome / 方向键翻页）。
//
// 演示模式是**一次借用**：借完要原样还回去。退出时不退全屏、不通知调用方恢复，
// 用户演示完回到编辑器就得自己把工作台重新拼一遍——而他刚才只是想给人看一眼。
// 所以退出有两条路都要通：Esc 与卸载，两者都退全屏。
//
// **到头不循环**：第一页再往左、最后一页再往右都停住。循环回第一页会让演示者
// 以为自己按多了一次，接着讲错顺序——而台下正看着。
//
// **空页集不进演示**：没有内容可讲时黑一屏，比什么都不做糟。
//
// **本层不改内容**：它只是换一种方式显示同一份产物（与 DESIGN-02 的零构建、
// DESIGN-12 的评论层同一条边界）。

import type { JSX } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { t } from "../../lib/i18n/t";

export type FullscreenApi = {
  enter: () => void;
  exit: () => void;
};

export type PresentModeProps = {
  pages: string[];
  fullscreen: FullscreenApi;
  onExit: () => void;
};

export function PresentMode({
  pages,
  fullscreen,
  onExit,
}: PresentModeProps): JSX.Element | null {
  const [index, setIndex] = useState(0);
  const empty = pages.length === 0;
  // 退全屏恰一次：Esc 与卸载是两条路，都要通，但不能各退一次。
  const exited = useRef(false);
  const leaveFullscreen = useCallback(() => {
    if (exited.current) return;
    exited.current = true;
    fullscreen.exit();
  }, [fullscreen]);

  useEffect(() => {
    if (empty) return;
    exited.current = false;
    fullscreen.enter();
    return leaveFullscreen;        // 卸载也退：NEVER 把浏览器留在全屏里
  }, [empty, fullscreen, leaveFullscreen]);

  useEffect(() => {
    if (empty) return;
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === "ArrowRight") {
        setIndex((prev) => Math.min(prev + 1, pages.length - 1));  // 到头停住
        return;
      }
      if (event.key === "ArrowLeft") {
        setIndex((prev) => Math.max(prev - 1, 0));
        return;
      }
      if (event.key === "Escape") {
        // 先自己退全屏再通知：用户按了 Esc，画面该立刻回来，
        // 而不是取决于调用方有没有把这个组件卸载掉。
        leaveFullscreen();
        onExit();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);   // 退出后把键还给编辑器
  }, [empty, pages.length, onExit, leaveFullscreen]);

  if (empty) return null;

  return (
    <div data-testid="present-mode" data-chrome="hidden">
      <iframe
        data-testid="present-page"
        data-index={index}
        title={t("design.present.page_title", { index: index + 1, total: pages.length })}
        sandbox="allow-scripts allow-forms"
        srcDoc={pages[index]}
      />
    </div>
  );
}
