import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// L0/L1 前端测试：jsdom + testing-library，全程离线（fetch/EventSource 均 mock，
// NEVER 联网——CI 铁律 S2-7）。
export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    css: false,
    // FIX-04：**每条用例跑完还原被 stub 的全局**。
    //
    // 十个测试文件都 `vi.stubGlobal("fetch", …)`，而 vitest 默认不还原，
    // 也**没有任何一个文件自己还原**（实测 `unstubAllGlobals` 用量 = 0）。
    // 于是一条用例设的 stub 会活到同文件后面的用例里——
    // 后者没设 stub 时拿到的是前者的答复，而它自己以为在用真的 fetch。
    //
    // 这**不是** `UI07-LOCALE-TEST-IS-FLAKY` 那次红的原因（那次的因见
    // `__tests__/app/ui07.test.tsx#renderLoadedPage`），但它是同一类隐患，
    // 且单子点名要清点。留着它，下一次「重跑一遍就好」就有了土壤。
    unstubGlobals: true,
  },
});
