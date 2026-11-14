"""新浪访客系统匿名握手（`CN-04` / `DEC-053` 授权）。

# ⚠ 上游对抗件，预期会碎

**这个文件里的每一个常量都是对方随时可以改的东西。** 它不是一份稳定契约，
是一次对反爬机制的适配。碎的时候的正确反应是：广场**如实降级**并说明缺哪一源，
NEVER 去猜一个新参数、NEVER 因为它碎了就去找一条要凭据的路。
（`DEC-053` 逐字：碎了广场如实降级，本版没有推送告警。）

## 为什么要有这一步

`CN-04` 探测实证：五条免登录路全废——`s.weibo.com` 与 `m.weibo.cn` 全部 302 到
访客系统，`weibo.com` 两条 ajax 全 403。`DEC-053` 因此授权走访客握手。

**它不是账号登录**：全程没有用户名和密码，`fp` 是一段公开的浏览器环境描述；
任何浏览器匿名打开微博时做的都是同一件事。
**授权上限就是这个**——NEVER 升级成账号登录，NEVER 引入任何凭据。
要更多，回去找 owner（`DEC-053` 原话）。

## 三跳（实测，留痕在 `fixtures/_probe/weibo/`）

| 跳 | 端点 | 实测 |
|---|---|---|
| ① | `POST /visitor/genvisitor`（表单 `cb=gen_callback&fp={…}`） | `{"retcode":20000000,"msg":"succ","data":{"tid":"…"}}` |
| ② | `GET /visitor/visitor?a=incarnate&t={tid}&…` | `succ`，Set-Cookie `SUB` `SUBP` `SRF` `SRT` `SVB` |
| ③ | 带上一步的 cookie 取榜单 | **200 · 105724 字节 · 52 行** |

端点名不是猜的：`fpPostInterface: "visitor/genvisitor"` 逐字写在
`passport.weibo.com/js/visitor/mini_original.js` 里（那份 JS 也已探测留痕）。

## cookie **每次动态获取**，NEVER 硬编

`DEC-053` 逐字。硬编一枚的坏处不是它会过期——是**它过期之后代码看起来仍然是对的**：
请求照发、回来一份访客系统页面、解析抛 `ParseDrift`，
而排查的人会去查解析器。所以这里每次跑都重新握一次手，
且**仓库里 NEVER 出现任何一个 cookie 的值**（探测留痕也只记 cookie 的名字）。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import httpx

from flint.sources.errors import SourceFetchError

#: 握手两跳的地址。**集中在这里**，与下面的指纹一起构成「会碎的那一面」。
GENVISITOR_URL = "https://passport.weibo.com/visitor/genvisitor"
INCARNATE_URL = "https://passport.weibo.com/visitor/visitor"

#: 浏览器指纹参数。**这一块就是对抗件的核心**，对方改一次它就失效。
#: 值全部是公开的环境描述，**没有一个是凭据**。
FINGERPRINT: dict[str, str] = {
    "os": "1",
    "browser": "Chrome127,0,0,0",
    "fonts": "undefined",
    "screenInfo": "1920*1080*24",
    "plugins": "",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)

#: 上游用 JSONP 包着回，回调名由请求指定。
_GEN_CALLBACK = "gen_callback"
_INCARNATE_CALLBACK = "cross_domain"

#: 成功码。上游用它而不是 HTTP 状态码表达成败——**两跳都回 200，
#: 失败也回 200**，所以 NEVER 只看状态码。
_OK_RETCODE = "20000000"

_TID = re.compile(r'"tid"\s*:\s*"([^"]+)"')
_RETCODE = re.compile(r'"retcode"\s*:\s*"?(\d+)"?')


class VisitorHandshakeFailed(SourceFetchError):
    """握手没走通。

    继承 `SourceFetchError` 而不是新开一档：对上游而言这就是「取不到」，
    而错误分类**三类不增不减不改名**（`CN-04` acceptance）。
    握手失败与榜单 5xx 在降级显示上是同一件事——用户看到的都是「这一源今天缺席」。
    """


@dataclass
class VisitorSession:
    """一次握手的产物。**只带 cookie 名给外面看**，值留在 httpx 的 jar 里。"""

    client: httpx.Client
    tid: str
    cookie_names: tuple[str, ...] = field(default=())


def _retcode_of(body: str) -> str:
    hit = _RETCODE.search(body)
    return hit.group(1) if hit else ""


def handshake(client: httpx.Client) -> VisitorSession:
    """走完两跳，让 `client` 手上带着访客 cookie。

    **每次调用都重新握**（`DEC-053`：cookie 值 MUST 每次动态获取）。
    两跳都回 200 时才算成，且**成败看 `retcode` 不看状态码**——
    上游失败时照样回 200，只看状态码会把一次失败当成功，
    然后在解析那一层报一个说不清的 `ParseDrift`。
    """
    payload = f"cb={_GEN_CALLBACK}&fp={json.dumps(FINGERPRINT, separators=(',', ':'))}"
    first = client.post(
        GENVISITOR_URL,
        content=payload.encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": USER_AGENT},
    )
    if first.status_code != 200:
        raise VisitorHandshakeFailed("weibo", first.status_code, first.text[:200])
    if _retcode_of(first.text) != _OK_RETCODE:
        raise VisitorHandshakeFailed(
            "weibo", 200, f"genvisitor 没回成功码：{first.text[:200]}")
    found = _TID.search(first.text)
    if found is None:
        raise VisitorHandshakeFailed(
            "weibo", 200, f"genvisitor 没给 tid：{first.text[:200]}")
    tid = found.group(1)

    second = client.get(
        INCARNATE_URL,
        params={"a": "incarnate", "t": tid, "w": "2", "c": "095", "gc": "",
                "cb": _INCARNATE_CALLBACK, "from": "weibo"},
        headers={"User-Agent": USER_AGENT},
    )
    if second.status_code != 200:
        raise VisitorHandshakeFailed("weibo", second.status_code, second.text[:200])
    if _retcode_of(second.text) != _OK_RETCODE:
        raise VisitorHandshakeFailed(
            "weibo", 200, f"incarnate 没回成功码：{second.text[:200]}")

    names = tuple(sorted(dict(client.cookies)))
    if "SUB" not in names:
        # 没拿到 `SUB` 就等于没握上：后面那一发会被 302 弹回访客系统，
        # 而那时报的错离真正的原因隔了一层。
        raise VisitorHandshakeFailed(
            "weibo", 200, f"incarnate 之后没有 SUB cookie：{names}")
    return VisitorSession(client=client, tid=tid, cookie_names=names)
