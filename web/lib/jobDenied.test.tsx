// UIX-04：403 之后屏上说「无权查看」，而不是一张永远转下去的骨架。
//
// 这份判据分两层：
//   ① `probeJobAccess` 把状态码映射成态（401/403/其它 三条各一例）；
//   ② `JobDeniedNotice` 真的把那句话渲染出来，且**不劝人重试**。
//
// 源码里有 `data-job-denied` 与「渲染出来了」是两件事——
// 分支写错条件时源码判据照样绿，所以这一份必须跑起来看渲染树。

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { JobDeniedNotice } from "../components/shell/JobDeniedNotice";
import {
  initialJobStreamState,
  openJobStream,
  probeJobAccess,
  type JobStreamState,
} from "./jobClient";

function fetchReturning(status: number): typeof fetch {
  return vi.fn(async () => new Response(null, { status })) as unknown as typeof fetch;
}

describe("probeJobAccess", () => {
  it("403 → denied（「你能干什么」的问题：去要权限）", async () => {
    expect(await probeJobAccess("j-1", { fetchImpl: fetchReturning(403) }))
      .toBe("denied");
  });

  it("401 → unauthenticated（「你是谁」的问题：去登录）——两者 NEVER 并成一句", async () => {
    expect(await probeJobAccess("j-1", { fetchImpl: fetchReturning(401) }))
      .toBe("unauthenticated");
  });

  it("500 → unknown：**别的失败 NEVER 被说成无权**", async () => {
    // 说成无权的话，用户会去要一个他本来就有的权限，而真正的问题在后端。
    expect(await probeJobAccess("j-1", { fetchImpl: fetchReturning(500) }))
      .toBe("unknown");
  });

  it("fetch 发不出去（真断网）→ unknown，NEVER 猜成 denied", async () => {
    const boom = vi.fn(async () => {
      throw new Error("network down");
    }) as unknown as typeof fetch;
    expect(await probeJobAccess("j-1", { fetchImpl: boom })).toBe("unknown");
  });
});

describe("openJobStream 在流出错后探一次", () => {
  class FakeES {
    onmessage: ((e: { data: string; lastEventId: string }) => void) | null = null;
    onerror: ((e: unknown) => void) | null = null;
    closed = false;
    close(): void {
      this.closed = true;
    }
  }

  it("403 时把 access 标成 denied，且 connection 仍然如实是 disconnected", async () => {
    const sources: FakeES[] = [];
    const states: JobStreamState[] = [];
    const fake = class {
      constructor() {
        const es = new FakeES();
        sources.push(es);
        return es as unknown as FakeES;
      }
    } as unknown as typeof EventSource;

    openJobStream("j-1", (s) => states.push(s), {
      EventSourceImpl: fake,
      fetchImpl: fetchReturning(403),
    });
    sources[0].onerror?.(null);
    // 探针是异步的：让微任务跑完。
    await new Promise((r) => setTimeout(r, 0));

    const last = states[states.length - 1];
    expect(last.access).toBe("denied");
    // **断线仍然是真的**：我们确实收不到消息了。屏上由谁盖住谁是呈现层的事，
    // 客户端 NEVER 为了让屏好看而改写事实。
    expect(last.connection).toBe("disconnected");
  });

  it("探不出来时一个字都不改（access 留在 unknown）", async () => {
    const sources: FakeES[] = [];
    const states: JobStreamState[] = [];
    const fake = class {
      constructor() {
        const es = new FakeES();
        sources.push(es);
        return es as unknown as FakeES;
      }
    } as unknown as typeof EventSource;

    openJobStream("j-1", (s) => states.push(s), {
      EventSourceImpl: fake,
      fetchImpl: fetchReturning(500),
    });
    sources[0].onerror?.(null);
    await new Promise((r) => setTimeout(r, 0));

    expect(states[states.length - 1].access).toBe("unknown");
  });

  it("初始态里 access 是 unknown（**NEVER 默认成 denied**）", () => {
    expect(initialJobStreamState.access).toBe("unknown");
  });
});

describe("屏上那条分支的条件", () => {
  it("**正向枚举那两个态**，NEVER 写成 `!== \"unknown\"`", async () => {
    // `!== "unknown"` 会把「这个字段不存在」（旧调用方、桩、老录制）也当成拒绝——
    // 而那正是 `probeJobAccess` 自己拒绝去做的事。
    // 第一版就是这么写的，当场把两条既有判据打红：桩里没有 `access`，
    // 于是那一屏的五个取证属性整片消失。
    const { readFileSync } = await import("node:fs");
    const { join } = await import("node:path");
    const page = readFileSync(
      join(__dirname, "..", "app", "jobs", "[id]", "page.tsx"), "utf8");
    const code = page
      .split("\n")
      .filter((l) => !l.trim().startsWith("//") && !l.trim().startsWith("*"))
      .join("\n");

    expect(code).toContain('s.access === "denied"');
    expect(code).not.toContain('s.access !== "unknown"');
  });
});

describe("JobDeniedNotice", () => {
  it("403：屏上说无权，并说清下一步是要权限", () => {
    render(<JobDeniedNotice reason="denied" />);
    expect(screen.getByRole("alert")).toBeTruthy();
    const box = screen.getByRole("alert");
    expect(box.getAttribute("data-job-denied")).toBe("denied");
    expect(box.textContent).toContain("无权查看");
    expect(box.textContent).toContain("权限");
  });

  it("401：换一句话——去登录，而不是去要权限", () => {
    render(<JobDeniedNotice reason="unauthenticated" />);
    const box = screen.getByRole("alert");
    expect(box.getAttribute("data-job-denied")).toBe("unauthenticated");
    expect(box.textContent).toContain("登录");
    expect(box.textContent).not.toContain("无权查看");
  });

  it("**NEVER 劝人重试**：403 重试一万次也还是 403", () => {
    // 断线件说的是「正在重连」（可恢复）；这一件是终局的。
    // 劝重试是一句假话，比不说更坏。
    //
    // **禁的是「劝」，不是「提到」**：本件的文案逐字写着「重试不会有用」——
    // 那是在否掉重试这条路，与劝人重试正好相反。
    // 第一版判据禁了「重试」二字，当场把这句实话判成违规
    // （本仓第十一次撞见「把说明问题的那句话当成问题本身」）。
    const advice = [/稍后重试/, /请重试/, /再试一次/, /retry later/i, /try again/i];
    for (const reason of ["denied", "unauthenticated"] as const) {
      const { unmount } = render(<JobDeniedNotice reason={reason} />);
      const text = screen.getByRole("alert").textContent ?? "";
      for (const pattern of advice) {
        expect(text).not.toMatch(pattern);
      }
      unmount();
    }
  });

  it("403 那一句**明说重试没用**——只是不劝，还不够", () => {
    // 什么都不说的话，用户自己会去刷新，而刷新永远不会成功。
    // 把「这条路走不通」讲出来，才省下他那一次徒劳。
    render(<JobDeniedNotice reason="denied" />);
    expect(screen.getByRole("alert").textContent).toContain("重试不会有用");
  });

  it("它是 alert 而不是 status：看不到任何东西是需要立刻知道的事", () => {
    render(<JobDeniedNotice reason="denied" />);
    expect(screen.getByRole("alert").getAttribute("aria-live")).toBeNull();
  });
});
