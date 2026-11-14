"""PAY-03：支付四条安全边界的扫描器（DEC-024）。

用法：
  python tools/check_payment_safety.py flint tools docs [--json]

退出码 0 = 三条扫描面干净；1 = 有命中（逐条点名文件与行）；
**扫不到任何文件也返 1**——见下。

## 它守哪三条（第四条「幂等」不在这里）

| 规则 | 形态 | 为什么 |
|---|---|---|
| `payment_secret` | 赋给变量的**真密钥值** | 密钥进仓 = 任何拿到仓库的人都能收钱 |
| `card_field` | `card_number` / `cvv` / `pan` 一类字段 | 不碰卡号 = 不进 PCI 合规面（owner 裁决） |
| `unverified_callback` | 看起来是支付回调、却没有任何验签调用 | 不验签的回调 = 谁都能说这笔付过了 |

**第四条「扣费带幂等键」不是静态形态**，它要真跑一次重放才证得了——
所以那条打在 `tests/v041/test_payment_safety.py` 的真账本用例上，不在这里。
写在这里说明白，免得有人以为这把尺子管四条。

## 扫 0 个文件**报红**，NEVER 报干净

路径写错、目录空了、glob 没匹配上——三种情况都长得像「干净」。
F-08 的形态就是「过滤器谁都匹配不上却报绿」，这里正面挡掉。

## 三条不误伤的地方（一把会误伤的尺子会被立刻关掉）

1. **从环境变量读密钥是正解**，NEVER 拦：`os.environ["FLINT_PAYPAL_SECRET"]` 放行；
2. **注释与占位不算**：`# APIv3 密钥只从环境变量读` 与 `"<your-key-here>"` 都放行——
   判据只看**赋给变量的真值形态**；
3. **只有看起来是支付回调的函数**才被验签规则管：见函数就要验签的话整棵树都会红。

## 本扫描器自己零外联、零读密钥

它只读盘上的文本。NEVER 发请求（那会把一把安全尺子变成一个外联点），
也 NEVER 去读环境里的真密钥来比对（读了就等于在日志里多一份泄露面）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA = "payment-safety/1"

SCAN_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".mjs", ".md", ".json", ".yaml", ".yml")
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", ".pytest_cache", ".mypy_cache"}

# 本文件自己与它的判据里必然写着这些形态（那是规则本身与阴性对照），
# 逐个显式豁免——NEVER 用「跳过 tools/ 与 tests/」这种大刀，那会把真问题一起放掉。
SELF_EXEMPT = {
    "tools/check_payment_safety.py",
    "tests/v041/test_payment_safety.py",
    "docs/支付接入方案-v041.md",
    "docs/trace/PAY-03.md",
}

# ① 密钥：判的是**赋给变量的真值**，不是「出现了这个词」。
#    右边必须是一个够长的字面量——占位符 `<your-key-here>` 与
#    `os.environ[...]` 都不是字面量，自然放行。
_SECRET_ASSIGN = re.compile(
    r"""(?ix)
    \b(
        (?:wechat|weixin)_?apiv3_?key | mch_?key | api_?v3_?key |
        client_?secret | app_?secret | (?:alipay_?)?private_?key |
        paypal_?secret | merchant_?private_?key
    )\s*[:=]\s*["'`]([^"'`\n]{16,})["'`]
    """
)
_PLACEHOLDER = re.compile(r"^(?:<|\{|\$|x{4,}|your[-_]|placeholder|example|changeme)", re.IGNORECASE)
_PRIVATE_KEY_BLOCK = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")

# ② 卡号字段：判的是**字段/键名**，不是正文里出现这三个字母。
_CARD_FIELD = re.compile(
    r"""(?ix)
    (?:^|[\s,(\[{])
    (card_?number | cardnumber | pan | cvv | cvc | card_?cvv |
     expiry_?(?:month|year) | exp_?(?:month|year) | primary_?account_?number)
    \s*[:=]
    """
)

# ③ 回调：函数名或装饰器里带这些词的，视为支付回调。
_CALLBACK_DEF = re.compile(
    r"""(?ix)
    ^\s*(?:async\s+)?def\s+
    (\w*(?:notify|callback|webhook|ipn)\w*)
    \s*\(
    """
)
_PAYMENT_HINT = re.compile(
    r"(?i)(wechat|weixin|alipay|paypal|pay|notify|webhook|trade|charge|refund)")
_VERIFY_CALL = re.compile(
    r"(?i)\b(verify[_a-z]*sign\w*|sign\w*verify|verify_webhook\w*|check_?sign\w*|"
    r"validate_?signature|verify_signature)\b")


@dataclass
class Finding:
    file: str
    line: int
    rule: str
    detail: str


@dataclass
class Scan:
    files: int = 0
    findings: list[Finding] = field(default_factory=list)


def _iter_files(roots: list[Path]) -> list[Path]:
    out: list[Path] = []
    for root in roots:
        if root.is_file():
            out.append(root)
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
                continue
            if SKIP_DIRS & set(path.parts):
                continue
            out.append(path)
    return out


def _strip_comment(line: str) -> str:
    """去掉行注释：注释里解释规则不算犯规。

    与 FB-10 同一条口径——**判据落在代码上，不落在解释代码的话上**。
    """
    for marker in ("#", "//"):
        idx = line.find(marker)
        if idx != -1:
            line = line[:idx]
    return line


def scan_text(rel: str, text: str) -> list[Finding]:
    found: list[Finding] = []
    lines = text.splitlines()
    for number, raw in enumerate(lines, start=1):
        line = _strip_comment(raw)

        for match in _SECRET_ASSIGN.finditer(line):
            value = match.group(2)
            if _PLACEHOLDER.match(value):
                continue                      # 占位符不是密钥
            found.append(Finding(rel, number, "payment_secret",
                                 f"{match.group(1)} 被赋了一个字面量密钥"))
        if _PRIVATE_KEY_BLOCK.search(line):
            found.append(Finding(rel, number, "payment_secret", "文件里有私钥块"))
        for match in _CARD_FIELD.finditer(line):
            found.append(Finding(rel, number, "card_field",
                                 f"出现卡号类字段 {match.group(1)}"))

    found.extend(_scan_callbacks(rel, lines))
    return found


def _scan_callbacks(rel: str, lines: list[str]) -> list[Finding]:
    """看起来是支付回调、却整段没有验签调用 → 红。

    「整段」= 从 `def` 到下一个同级或更浅缩进的非空行。
    只看函数体内部，因为验签写在别的函数里救不了这一个。
    """
    found: list[Finding] = []
    for index, raw in enumerate(lines):
        match = _CALLBACK_DEF.match(raw)
        if match is None or not _PAYMENT_HINT.search(match.group(1)):
            continue
        indent = len(raw) - len(raw.lstrip())
        body: list[str] = []
        for follow in lines[index + 1:]:
            if follow.strip() and (len(follow) - len(follow.lstrip())) <= indent:
                break
            body.append(follow)
        if not any(_VERIFY_CALL.search(_strip_comment(b)) for b in body):
            found.append(Finding(
                rel, index + 1, "unverified_callback",
                f"{match.group(1)} 看起来是支付回调，但整段没有验签调用"))
    return found


def _relative(path: Path, repo: Path) -> str:
    """统一成**仓根下的 posix 路径**。

    两个坑都在这一行上，实测都踩过：
    - 传进来的目标是相对路径时（`tools`），`rglob` 给的也是相对路径，
      而 `Path("tools/x.py").is_relative_to(<绝对仓根>)` 是 False——
      于是 rel 落成原样，Windows 上带反斜杠；
    - 带反斜杠的 rel 与 `SELF_EXEMPT` 里的 posix 写法**永远对不上**，
      豁免与豁免的判据双双静默失效，而两边看起来都是绿的。
    """
    resolved = path if path.is_absolute() else (Path.cwd() / path)
    resolved = resolved.resolve()
    if resolved.is_relative_to(repo):
        return resolved.relative_to(repo).as_posix()
    return resolved.as_posix()


def scan(roots: list[Path], repo: Path) -> Scan:
    result = Scan()
    for path in _iter_files(roots):
        rel = _relative(path, repo)
        result.files += 1
        if rel in SELF_EXEMPT:
            continue
        result.findings.extend(
            scan_text(rel, path.read_text(encoding="utf-8", errors="replace")))
    return result


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="支付安全边界扫描（密钥 / 卡号 / 回调验签）")
    ap.add_argument("targets", nargs="+")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    repo = Path(__file__).resolve().parents[1]
    result = scan([Path(t) for t in args.targets], repo)
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "files_scanned": result.files,
        "findings": [f.__dict__ for f in result.findings],
    }

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for finding in result.findings:
            print(f"  ✗ {finding.file}:{finding.line} [{finding.rule}] {finding.detail}")

    # `--json` 时 stdout **只出 JSON**：人读摘要一并混进去的话，
    # 调用方 `json.loads(stdout)` 会当场炸在「Extra data」上（实测红过一次）。
    summary = sys.stderr if args.as_json else sys.stdout
    if result.files == 0:
        # 扫 0 个文件**报红**：路径写错、目录空了、后缀没匹配上，
        # 三种情况都长得像「干净」。
        print("扫到 0 个文件：这不是干净，是没扫到东西——检查路径与后缀", file=sys.stderr)
        return 1
    if result.findings:
        print(f"支付安全边界命中 {len(result.findings)} 条", file=sys.stderr)
        return 1
    print(f"支付安全边界干净（扫了 {result.files} 个文件）", file=summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
