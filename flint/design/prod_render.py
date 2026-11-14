"""DESIGN-31（隔离带·G6）：生产渲染门——只认已注册模板。

## 这道门是两阶段模型的承重墙

G0 给了探索期几乎无约束的自由，而那份自由的安全性**完全押在这道门上**：
没有它，探索期随手生成的任意 HTML（带示例数字、带外部引用、水印没人检查）
会直接漏进生产渲染，两阶段退化成一阶段——工单 §11-③：
「G0 的『几乎无约束』就从特性变成事故通道」。

## 白名单而不是黑名单

判据只有一条：生产渲染的输入必须是**注册表里的一条记录**，而不是
「一段看起来合规的 HTML」。任何「检查一下就放行」的实现都是黑名单，而黑名单永远漏。

落到接口上：`ProductionRenderer.render` **根本没有接受 html 的参数**——
不是「检查了一下 html」，而是那个口子不存在。

## 四种「已注册」的反例

- **别人的模板**：注册表按 owner 分（D7）；
- **停用的模板**：停用就是为了让它别再被用；
- **被改过的模板**：内容与 checksum 对不上 = 有人绕过注册流程改了它，
  而下游拿到的会是「版本号没变、内容已变」（S2-2 第三条铁律：产物可复现）；
- **不存在的 id**。

## 插槽两侧都要对齐

少给值 → 拒绝（NEVER 把 `{{block:b-1}}` 原样渲染给客户看）；
多给值 → 也拒绝（那说明调用方以为自己在填另一个模板）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

SLOT_PATTERN = re.compile(r"\{\{([a-z]+:[a-z0-9_-]+)\}\}", re.IGNORECASE)


class UnregisteredTemplate(Exception):
    """生产渲染只认注册表里的模板。"""


def default_checksum(html: str) -> str:
    """校验和口径来自契约（`contracts_v04.models_v04.template_checksum`）。

    本模块另写一份就有了两种指纹：注册表构造期用契约那份、这里用自己那份，
    对不上时模板会被当成「被改过」而永远渲染不出来。
    """
    from contracts_v04.models_v04 import template_checksum

    return template_checksum(html)


@dataclass
class ExploreRenderer:
    """探索期渲染：几乎无约束（G0/G10），拿到什么画什么。"""

    def render(self, html: str) -> str:
        return html


@dataclass
class ProductionRenderer:
    """生产渲染：只接受 `template_id` + 插槽值。**没有接受 html 的口子**。"""

    registry: Any
    owner: Any
    checksum_of: Any = default_checksum

    def _lookup(self, template_id: str) -> Any:
        for record in self.registry.all():
            if record.template_id != template_id:
                continue
            if record.owner.kind != self.owner.kind or record.owner.id != self.owner.id:
                continue                      # 别人的模板不算「已注册」
            if not record.enabled:
                raise UnregisteredTemplate(
                    f"template {template_id} 已停用：停用就是为了让它别再被用"
                )
            if self.checksum_of(record.html) != record.checksum:
                raise UnregisteredTemplate(
                    f"template {template_id} 内容与 checksum 对不上："
                    "有人绕过注册流程改了它，下游会拿到「版本号没变、内容已变」的产物"
                )
            return record
        raise UnregisteredTemplate(
            f"template {template_id} 不在注册表里：生产渲染只认已固化模板（G6）"
        )

    def render(self, template_id: str, slot_values: dict[str, str]) -> str:
        record = self._lookup(template_id)
        declared = set(SLOT_PATTERN.findall(record.html))
        given = set(slot_values)

        missing = declared - given
        if missing:
            raise ValueError(
                f"插槽缺值：{sorted(missing)}——"
                "NEVER 把 {{slot}} 原样渲染给客户看"
            )
        extra = given - declared
        if extra:
            raise ValueError(
                f"插槽多给了：{sorted(extra)}——"
                "那说明调用方以为自己在填另一个模板"
            )

        return SLOT_PATTERN.sub(lambda m: slot_values[m.group(1)], record.html)
