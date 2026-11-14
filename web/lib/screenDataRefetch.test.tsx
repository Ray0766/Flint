// UIX-05 运行时判据：`refetch()` **真的重发请求**。
//
// 只判「函数存在」不够（单据原话）——一个空函数体照样让源码判据绿。
// 本文件里还有这张卡的**阴性对照**：不调 `refetch` 时屏上仍是旧值。
// 没有那一条，一个「碰巧因为别的原因也重取了」的实现会让正向判据绿，
// 而那时 `refetch` 有没有起作用，谁也说不出来。

import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useScreenData } from "./useScreenData";

// 后端每次被问都回一个新值——**这就是「重取真的发生了」的可观测形态**。
let answered = 0;
const calls: string[] = [];

function Probe({ path }: { path: string }): React.JSX.Element {
  const { state, refetch } = useScreenData<{ value: number }>(path);
  return (
    <div>
      <span data-testid="value">
        {state.kind === "ready" ? String(state.data.value) : state.kind}
      </span>
      <button data-testid="again" onClick={refetch}>
        again
      </button>
    </div>
  );
}

beforeEach(() => {
  answered = 0;
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    calls.push(String(url));
    answered += 1;
    return new Response(JSON.stringify({ value: answered }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useScreenData 的 refetch", () => {
  it("进屏取一次", async () => {
    render(<Probe path="/thing" />);
    await waitFor(() => expect(screen.getByTestId("value").textContent).toBe("1"));
    expect(calls.length).toBe(1);
  });

  it("调 refetch **真的再问一次**，且屏上换成新值", async () => {
    render(<Probe path="/thing" />);
    await waitFor(() => expect(screen.getByTestId("value").textContent).toBe("1"));

    await act(async () => {
      screen.getByTestId("again").click();
    });

    await waitFor(() => expect(screen.getByTestId("value").textContent).toBe("2"));
    expect(calls.length).toBe(2);
  });

  it("**阴性对照**：不调 refetch 时屏上仍是旧值", async () => {
    // 这一条是本卡的核心。没有它，一个「碰巧也重取了」的实现会让上面那条绿——
    // 而那时 refetch 有没有起作用，谁也说不出来。
    render(<Probe path="/thing" />);
    await waitFor(() => expect(screen.getByTestId("value").textContent).toBe("1"));

    // 等足够长时间，让任何「顺手重取」都有机会发生。
    await act(async () => {
      await new Promise((r) => setTimeout(r, 60));
    });

    expect(screen.getByTestId("value").textContent).toBe("1");
    expect(calls.length).toBe(1);
  });

  it("重取的 URL 与第一次**逐字相同**——NEVER 带一个变化的假 query", () => {
    // `DEC-035` 判死的形状：靠 FastAPI 静默忽略未声明 query 去实现副作用。
    // 那种机制在参数**不再被忽略**的那天当场坏掉。
    return (async () => {
      render(<Probe path="/thing" />);
      await waitFor(() => expect(calls.length).toBe(1));
      await act(async () => {
        screen.getByTestId("again").click();
      });
      await waitFor(() => expect(calls.length).toBe(2));

      expect(calls[1]).toBe(calls[0]);
      for (const fake of ["_t=", "cacheBust", "nonce", "Math.random"]) {
        expect(calls[1]).not.toContain(fake);
      }
    })();
  });

  it("重取期间**先回到 loading**，NEVER 让旧值静静留在屏上", async () => {
    // 不回的话，用户按下「选这条」，屏上一秒内显示的还是没选之前的样子——
    // 他会以为自己没点上，于是再点一次。
    let release: (() => void) | null = null;
    vi.stubGlobal("fetch", vi.fn(async () => {
      answered += 1;
      if (answered > 1) {
        await new Promise<void>((r) => {
          release = r;
        });
      }
      return new Response(JSON.stringify({ value: answered }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }));

    render(<Probe path="/thing" />);
    await waitFor(() => expect(screen.getByTestId("value").textContent).toBe("1"));

    await act(async () => {
      screen.getByTestId("again").click();
    });

    expect(screen.getByTestId("value").textContent).toBe("loading");
    await act(async () => {
      release?.();
    });
  });

  it("path 变了照旧重取（既有行为一字未改）", async () => {
    const { rerender } = render(<Probe path="/thing" />);
    await waitFor(() => expect(calls.length).toBe(1));

    rerender(<Probe path="/other" />);
    await waitFor(() => expect(calls.length).toBe(2));

    expect(calls[1]).toContain("/other");
  });
});
