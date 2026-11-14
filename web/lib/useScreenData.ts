"use client";

// WIRE-03：客户端组件取一条只读端点用的钩子。
//
// 只做一件事：把 `fetchScreen` 的五态搬进 React 状态，**不做任何转换**。
// 转换（比如把 `not_configured` 折成 `not_provided`）要发生在屏里，
// 且要看得见——折在这里就没人知道两者被合并过了。
//
// ## `UIX-05`：出了一个 `refetch()`
//
// 改前签名是 `useScreenData<T>(path): Fetched<T>`——它只在 `path` 变化时重取，
// **没有别的重取入口**。第 6 批起出现「写完要重读」的屏
// （`ENTRY-02` 的选主题第一个），那时只有三条路：
//
// | 做法 | 代价 |
// |---|---|
// | 前端记一份（乐观更新） | **刷新一次就没了，而用户以为自己已经选过** |
// | 拿一个变化的假 query 骗它重取 | `DEC-035` 判死的形状：靠 FastAPI 静默忽略未声明 query 去实现副作用 |
// | `window.location.reload()` | 能用、诚实，但整屏重来（滚动位置与屏内状态全丢） |
//
// `ENTRY-02` 当时走的是第三条——**那是当时唯一诚实的选择**。本卡给出第四条。
//
// ## `refetch` 恒是同一个函数
//
// 走 `useCallback`。每渲染新造一个的话，把它放进任何 `useEffect` 的依赖里
// 都会造成**无限重取**——而那个症状是「屏在疯狂打后端」，看起来像后端被攻击。
//
// ## 重取时**先回到 loading**
//
// 不回的话，旧数据会在新请求飞行期间留在屏上，而屏上没有任何东西说明它是旧的——
// 用户按下「选这条」，屏上一秒钟内显示的还是没选之前的样子，
// 他会以为自己没点上，于是再点一次。
//
// **NEVER 在这里做乐观更新**：那就是「前端记一份」，只是换了个地方记。

import { useCallback, useEffect, useState } from "react";

import { API_BASE } from "./apiBase";
import { fetchScreen, type Fetched } from "./screenClient";

export interface ScreenData<T> {
  state: Fetched<T>;
  /**
   * 重取一次。**写完之后调它**，而不是整屏 `reload()`。
   *
   * 它只做「再问一次后端」这一件事——NEVER 接受一个「新值」参数：
   * 那会让调用方把自己算出来的东西塞进屏上，而屏上显示的恒该是**库里那个值**。
   */
  refetch: () => void;
}

export function useScreenData<T>(path: string | null): ScreenData<T> {
  const [state, setState] = useState<Fetched<T>>({ kind: "loading" });
  // 重取靠**递增一个计数**触发下面那个 effect。它不是「假 query」——
  // 这个数**从不进 URL**，只是 effect 的依赖项。
  // （假 query 那种做法把状态塞进请求，后端哪天不再忽略它就当场坏掉。）
  const [attempt, setAttempt] = useState(0);

  const refetch = useCallback(() => {
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    if (path === null) return;
    let alive = true;
    // 重取时先回到 loading：不回的话，旧数据会在新请求飞行期间留在屏上，
    // 而屏上没有任何东西说明它是旧的。
    setState({ kind: "loading" });
    void fetchScreen<T>(path, { baseUrl: API_BASE }).then((next) => {
      // 组件已卸载还去 setState，React 会告警，且那次结果本来也没人看。
      if (alive) setState(next);
    });
    return () => {
      alive = false;
    };
  }, [path, attempt]);

  return { state, refetch };
}
