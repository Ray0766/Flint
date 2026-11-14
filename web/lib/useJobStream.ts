import { useEffect, useState } from "react";
import {
  openJobStream,
  initialJobStreamState,
  type JobStreamState,
} from "./jobClient";

// L1 React 绑定：订阅 Job SSE，实时暴露归约后的 JobStreamState（状态/步骤/
// 已到达 block_id/失败/终态）。终态或卸载时自动 close（openJobStream 内建）。
export function useJobStream(
  jobId: string | null,
  opts: { EventSourceImpl?: typeof EventSource; baseUrl?: string } = {},
): JobStreamState {
  const [state, setState] = useState<JobStreamState>(initialJobStreamState);
  useEffect(() => {
    if (!jobId) return;
    setState(initialJobStreamState);
    const close = openJobStream(jobId, setState, opts);
    return close;
    // opts 为每渲染新对象——仅以 jobId 为依赖，避免重复订阅。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);
  return state;
}
