"""`OriginValidationError` → HTTP 答复的**唯一**一处映射。

> 本模块由 v0.4.1 第 6 批的 `FIX-10` 建（`docs/steward/tasks-v041-b6.json`）。

## 改前：同一件事，两条端点两个答复

两条端点走的是**同一个校验器**（`flint/topic/create.py#_require_str`，
`flint/graph/store.py` 逐字写着「H8: 复用 combo 的 hypothesis 校验语义」），
抛的也是同一个异常、同一句话。**分叉只在 HTTP 映射那一层**：

```
POST /projects/combo          → 400 VALIDATION_FAILED
POST /workbenches/{id}/edges  → 422 EMPTY_HYPOTHESIS
```

规格 `#2.3` 写的是同一判据。前端于是要为同一件事写两套分支——
而写着写着必然漏掉一条，那时用户拿到的是一句通用报错，
光标不会回到假设输入框。

## 统一到 `EMPTY_HYPOTHESIS` / 422

`ErrorCode` 的注释逐字说明了它为什么单列：

> 「边上没写假设」与「请求体格式不对」的修法完全不同，
> 前端要据此把光标送回假设输入框而不是弹一句通用报错。

把它并回 `VALIDATION_FAILED` 就是把那句注释作废。
反过来，combo 的**其余**校验失败（卡数不对、卡不存在）**仍然是**
`VALIDATION_FAILED`——它们确实是「请求体不对」。

## 那句话从校验器身上取，NEVER 手抄

本模块在导入期真调一次 `_require_str({}, "hypothesis")`，把它抛出来的消息
捕获下来当唯一真相。校验器哪天改了措辞，映射与判据自动跟着走——
手抄一份的话，改了一处而另一处没改时，**判据仍然是绿的**，
而两条端点会开始说两句话。

**为什么用私名 `_require_str`**：它是这条消息的**产生者**，
而本模块要的正是「与产生者逐字一致」。绕开它去 import 一个公开常量，
就等于又建了一份可以分叉的副本。
"""
from __future__ import annotations

from typing import Final

from fastapi.responses import JSONResponse

from flint.api.schemas import ErrorBody, ErrorCode
from flint.topic.create import OriginValidationError, _require_str


def _derive_empty_hypothesis_message() -> str:
    try:
        _require_str({}, "hypothesis")
    except OriginValidationError as raised:
        return str(raised)
    raise AssertionError(
        "`_require_str({}, 'hypothesis')` 竟然没抛——空假设的校验没了，"
        "本模块的整个前提不成立"
    )


#: 「假设是空的」那一句，**由校验器产生**。前端预检逐字用它（`web/lib/topicClient.ts`）。
EMPTY_HYPOTHESIS_MESSAGE: Final[str] = _derive_empty_hypothesis_message()


def _body(code: ErrorCode, message: str) -> dict[str, object]:
    return ErrorBody(code=code, message=message).model_dump(exclude_none=True)


def origin_validation_error(err: OriginValidationError) -> JSONResponse:
    """把 `OriginValidationError` 翻成答复。**两条端点共用这一处。**

    - 假设是空的 → **422 `EMPTY_HYPOTHESIS`**（前端据此把光标送回假设输入框）；
    - 其余（卡数不对、卡不存在、缺 catalog…）→ **400 `VALIDATION_FAILED`**。

    分辨靠的是**与校验器逐字相同的那句话**，不是子串猜测：
    猜的话，一条「hypothesis 里有非法字符」之类的新错误也会被当成「空假设」，
    而它们的修法不同。
    """
    if str(err) == EMPTY_HYPOTHESIS_MESSAGE:
        return JSONResponse(
            status_code=422, content=_body("EMPTY_HYPOTHESIS", str(err)))
    return JSONResponse(
        status_code=400, content=_body("VALIDATION_FAILED", str(err)))
