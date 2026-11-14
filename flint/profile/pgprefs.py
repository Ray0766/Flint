"""PERSIST-01：语言/地区偏好的 SQL 实现（`prefs` 表，迁移 0023）。

`flint/profile/prefs.py:39` 自述「内存实现（= 本测试里的「服务端」）；
SQL 实现随 profiles 表接入」——**这就是那个接入**，只是表名是 `prefs` 不是
`profiles`（理由写在迁移 0023 的模块 docstring：语言与地区是每个用户都有的两轴，
与「有没有填过创业档案」无关）。

## 「服务端为真相」在这里才第一次成立

内存件是**进程内**的字典：换台设备就变了，进程一重启就没了。
`flint/profile/prefs.py` 文件头那句「跨设备一致不是附加功能，
它就是『服务端为真相』的可观测形式」，在换成本模块之前一直是**一句话**。

## 未设置 → 声明过的默认值，NEVER 返回 None

`get_prefs` 的既有口径是「未设置 → 声明过的默认值（zh/CN），
而不是『空』或『猜』」。SQL 实现在这里最容易失手：`fetchrow` 回 `None`
就把 `None` 传上去，于是上层拿到一个没有 `lang` 的对象。
所以这里查不到时返回 `Prefs()`——**默认值这件事在内存件里是什么样，
在这里就是什么样**。

## 两轴各占一列，NEVER 合成 `zh-CN`

`PRINCIPLES#A3`：语言只统治 UI 文案与生成内容语言，地区只决定数据源选集与
热点集合。合成串把两轴绑死，切地区必然连语言一起切。

`set_prefs` 的「只改传进来的那一项」是**它自己**做的（先读、`replace`、再写），
所以本模块的 `put` 写的是整行——**NEVER 在 SQL 里再做一次部分更新**：
两处都做合并的话，哪一处的口径说了算就说不清了。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import asyncpg

from flint.db.sync_bridge import run_sync
from flint.profile.prefs import Prefs


@dataclass
class PgPrefsStore:
    """`PrefsStore` 的 SQL 实现。两个方法（`get` / `put`）逐字对齐内存件。"""

    dsn: str

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(self.dsn)

    def get(self, user_id: str) -> Prefs:
        """一个用户的两轴。**没设过 → 声明过的默认值**，NEVER 返回 None。"""
        async def _go() -> Prefs:
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "SELECT lang, region, theme FROM prefs WHERE user_id = $1",
                    user_id)
            finally:
                await conn.close()
            if row is None:
                return Prefs()
            return Prefs(
                lang=row["lang"], region=row["region"], theme=row["theme"])

        return run_sync(_go())

    def put(self, user_id: str, prefs: Prefs) -> None:
        """整行写入。合并那一步归 `set_prefs`（见模块 docstring）。"""
        async def _go() -> None:
            conn = await self._connect()
            try:
                await conn.execute(
                    "INSERT INTO prefs (user_id, lang, region, theme, updated_at) "
                    "VALUES ($1, $2, $3, $4, $5) "
                    "ON CONFLICT (user_id) DO UPDATE SET "
                    "lang = EXCLUDED.lang, region = EXCLUDED.region, "
                    "theme = EXCLUDED.theme, updated_at = EXCLUDED.updated_at",
                    user_id, prefs.lang, prefs.region, prefs.theme,
                    datetime.now(UTC))
            finally:
                await conn.close()

        run_sync(_go())
