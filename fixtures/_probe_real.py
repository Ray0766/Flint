"""CN-04/05：真实站点探测器（`DEC-052` 调试窗口专用）。

## 这个脚本是干什么的

四个适配器全部按合成夹具建（`_generate_4src.py` 自述「本环境无法对四个真实站点
做在线录制」），`CN-01` 首次实跑时它们**第一次接触真实站点**，两源当场全败。
要修它们，先得知道真实站点今天到底回什么——**这个脚本就是去问那一句**。

它**不是录制器**。录制器（`_record_cn_real.py`）产出的是判据要回放的夹具；
这个脚本产出的是**一次往返的原样留痕**，供人读、供下一步决定打哪条端点。
两者 NEVER 混用：探测留痕进不了 `fixtures/{source}/`。

## 三道闸，缺一不可（`DEC-052` 逐字）

1. **授权闸**：没有 `--authorized-by=DEC-052` 直接退 2，一个包都不发。
   **NEVER 读环境变量**——环境变量会被上一次 shell 留着，而这道闸要的是
   「这一次命令行上写明了依据」。也 NEVER 冒用 `--owner-is-here`：
   那个旗标的语义是「owner 此刻在场」，而本窗口是**预授权**，owner 并不在场。
2. **域名闸**：只许四源本家。跳转目标也要过闸——`weibo` 那条 302 正是要跟着走的，
   而跟到哪里去 MUST 仍在名单内。
3. **额度闸**：每源每日上限，按 `fixtures/_probe/{source}/` 里**当天 UTC 的留痕条数**
   现算。上限写在命令行上（`--budget`），因为 `CN-04` 是 20、`CN-05` 是 10。
   **数盘上的文件而不是记一个内存计数**：脚本跑几次都算同一天的额度。

## 留痕五样（`DEC-052` 点名）

`url` / `status` / 关键响应头 / `body` 前 2048 字节 / UTC 时间戳。
外加一个 `redirects`：302 是本卡要治的病，**跟到哪儿去了必须留下**。

body 只留前 2048 字节：这是一份**给人读的证据**，不是夹具。
留全文的话，下一个人会拿它当夹具用，而它没有 provenance manifest。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

PROBE_ROOT = Path(__file__).resolve().parent / "_probe"

#: 四源本家。`DEC-052` 逐字：weibo 族 / trends.google.com / github.com /
#: arxiv.org 与 export.arxiv.org。**子域按后缀匹配**，别的域一律拒。
ALLOWED_SUFFIXES: tuple[str, ...] = (
    "s.weibo.com", "weibo.com", "m.weibo.cn",
    "trends.google.com",
    "github.com",
    "arxiv.org", "export.arxiv.org",
)

#: 留痕里保留的响应头。全留的话会把 set-cookie 里的会话值写进仓库。
KEEP_HEADERS = ("content-type", "location", "server", "content-length",
                "x-ratelimit-remaining", "retry-after")

BODY_KEEP = 2048


class NotAuthorised(SystemExit):
    """没写依据就想发包。"""


def host_allowed(url: str) -> bool:
    """域名闸。**按后缀比**，`evil-weibo.com` 这种拼出来的不算。"""
    host = httpx.URL(url).host
    return any(host == suffix or host.endswith("." + suffix)
               for suffix in ALLOWED_SUFFIXES)


def spent_today(source: str) -> int:
    """今天（UTC）这一源已经花掉几个请求——**数盘上的留痕**，不是内存计数。"""
    day = datetime.now(UTC).date().isoformat()
    folder = PROBE_ROOT / source
    if not folder.exists():
        return 0
    return sum(1 for p in folder.glob(f"{day}T*.json"))


def probe(source: str, url: str, *, budget: int, timeout: float = 20.0,
          user_agent: str | None = None,
          full_body: bool = False,
          method: str = "GET", data: str = "",
          cookies: dict[str, str] | None = None) -> dict[str, object]:
    """打一发，留一份痕。**闸不过就抛，NEVER 先发再检查**。"""
    if not host_allowed(url):
        raise NotAuthorised(
            f"域名不在 DEC-052 的四源本家名单里：{httpx.URL(url).host}")
    used = spent_today(source)
    if used >= budget:
        raise NotAuthorised(
            f"{source} 今天已用 {used}/{budget} 个请求——DEC-052 的额度闸")

    headers = {"User-Agent": user_agent} if user_agent else {}
    started = datetime.now(UTC)
    # POST 与 cookie 是 DEC-053 的访客握手需要的（genvisitor 收表单、
    # incarnate 那一跳靠 Set-Cookie 交货）。**三道闸对它们一视同仁**。
    with httpx.Client(follow_redirects=True, timeout=timeout,
                      cookies=cookies or {}) as client:
        if method.upper() == "POST":
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            response = client.post(url, headers=headers, content=data.encode())
        else:
            response = client.get(url, headers=headers)
        got_cookies = dict(client.cookies)

    # 跳转目标也要过闸：跟着 302 走到了名单外，是一次名单外的请求。
    hops = [str(r.url) for r in response.history] + [str(response.url)]
    outside = [h for h in hops if not host_allowed(h)]

    record: dict[str, object] = {
        "schema": "probe/1",
        "authorized_by": "DEC-052",
        "source": source,
        "url": url,
        "requested_at_utc": started.isoformat(),
        "status": response.status_code,
        "final_url": str(response.url),
        "redirects": [
            {"status": r.status_code, "location": str(r.headers.get("location", ""))}
            for r in response.history
        ],
        "headers": {k: v for k, v in response.headers.items()
                    if k.lower() in KEEP_HEADERS},
        "body_head": response.text[:BODY_KEEP],
        "body_bytes": len(response.content),
        "sent_user_agent": user_agent or "",
        "left_allowed_hosts": outside,
        "method": method.upper(),
        # **只记 cookie 的名字，NEVER 记它的值**——值是凭据，进不了仓库。
        "cookie_names": sorted(got_cookies),
    }

    folder = PROBE_ROOT / source
    folder.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y-%m-%dT%H-%M-%S")
    (folder / f"{stamp}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")

    if full_body:
        # 留痕本身照旧只留 2048 字节（它是**给人读的证据**）。
        # 这一份是**另一件东西**：要转成回放夹具喂给解析判据的原样响应，
        # 所以单独一个文件、单独一个旗标——**NEVER 让留痕悄悄变成夹具**，
        # 那样下一个人会拿一份没有 provenance 的东西当夹具用。
        body_path = folder / f"{stamp}.body"
        body_path.write_bytes(response.content)
        record["full_body_saved_to"] = str(body_path.relative_to(PROBE_ROOT.parent))
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DEC-052 真实站点探测器")
    parser.add_argument("--authorized-by", default="",
                        help="MUST 是 DEC-052。NEVER 读环境变量。")
    parser.add_argument("--source", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--budget", type=int, required=True,
                        help="每源每日上限：CN-04 = 20，CN-05 = 10")
    parser.add_argument("--user-agent", default="")
    parser.add_argument("--method", default="GET")
    parser.add_argument("--data", default="")
    parser.add_argument("--full-body", action="store_true",
                        help="另存整份响应体，供转成回放夹具（留痕本身仍只留 2048 字节）")
    args = parser.parse_args(argv)

    if args.authorized_by != "DEC-052":
        print("拒绝：没有 --authorized-by=DEC-052。", file=sys.stderr)
        print("这一条是 DEC-052 的授权闸——真实网络是 worker.md §7 事前必审类，",
              file=sys.stderr)
        print("而本窗口的依据必须写在这一次的命令行上。", file=sys.stderr)
        print("NEVER 用 --owner-is-here 顶替：那个旗标的语义是「owner 此刻在场」。",
              file=sys.stderr)
        return 2

    try:
        record = probe(args.source, args.url, budget=args.budget,
                       user_agent=args.user_agent or None,
                       full_body=args.full_body,
                       method=args.method, data=args.data)
    except NotAuthorised as exc:
        print(f"拒绝：{exc}", file=sys.stderr)
        return 2

    print(json.dumps({k: v for k, v in record.items() if k != "body_head"},
                     ensure_ascii=False, indent=1))
    print("--- body 前 400 字 ---")
    print(str(record["body_head"])[:400])
    print(f"--- 今日已用 {spent_today(args.source)}/{args.budget} ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
