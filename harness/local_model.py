"""免费本地档模型接入的**唯一定义处**：地址、模型名、provider 工厂。

## 为什么要有这个文件（`COMBO-WIRE-01`）

改前 `harness/demo_server.py` 与 `harness/run_worker.py` **各写一份**同样的三行：

```python
OLLAMA = os.environ.get("FLINT_LOCAL_BASE_URL", "http://localhost:11434/v1")
MODEL = os.environ.get("FLINT_FREE_TIER_MODEL", "qwen3.6:35b-a3b")
LocalProvider(base_url=OLLAMA, model=MODEL, http_client=httpx.Client(timeout=600.0),
              disable_reasoning=True, max_tokens=4096)
```

而 combo 这一族要接进 API 进程时，那就是**第三份**。三份默认值哪天分了叉，
「combo 用的是哪个模型」会有两个答案——**而两个答案在屏上、在日志里长得一模一样**
（同形先例就在 `demo_server.py` 的 `REDIS_URL` 注释里：API 推 A 队列而 worker 守 B 队列，
症状是「作业永远 queued」，与「worker 没起来」分不出来）。

## 三条边界

- **免费本地档，零 key**：`LocalProvider` 有 `api_key` 参数，这里**一个都不传**。
  付费开通是 owner 人审节点（S2-10）；
- **NEVER 在产品树里编一个默认地址**（`flint/api/app.py:469` 写死了这条理由：
  猜出来的地址要么连不上，要么连上了某个不该连的东西）。这里是 harness，
  默认值指向本机 Ollama 是 demo 面自己的事，可部署应用那一侧照
  `flint/config.py#ModelAccess` 从环境读；
- 参数（超时 600 秒 / 关推理 / 4096 上限）三处此前逐字相同，搬进来时**一个字没改**。
"""
from __future__ import annotations

import os

import httpx

from flint.llm.local import LocalProvider

#: 本机 OpenAI 兼容端点。`start-demo.ps1` 给后端与 worker 两个进程都设了它。
OLLAMA = os.environ.get("FLINT_LOCAL_BASE_URL", "http://localhost:11434/v1")
#: 免费档模型名。`start-demo.ps1` 里的 `$Model` 就是经这个变量交过来的——
#: 脚本打印的那句「combo/Gate 走免费本地 $Model」靠这条链才是真话。
MODEL = os.environ.get("FLINT_FREE_TIER_MODEL", "qwen3.6:35b-a3b")

#: 生成类调用的超时：本地 35b 出一份结构化产物是分钟级的。
TIMEOUT = 600.0


def build_local_provider(timeout: float = TIMEOUT) -> LocalProvider:
    """造一只免费本地档 provider。

    每个调用方拿到的是**自己的实例**（`httpx.Client` 不必跨进程/跨线程共用），
    但**参数只有这一处**——「同一组参数」而不是「同一个对象」是本仓要的那条口径。
    """
    return LocalProvider(
        base_url=OLLAMA, model=MODEL, http_client=httpx.Client(timeout=timeout),
        disable_reasoning=True, max_tokens=4096)
