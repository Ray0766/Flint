# FAV-05 trace — 批量入台单事务 + 批量取消 @2026-08-03

## 1 verify（卡上 verify_cmd 是**合取**，两段都跑）
`cd web && npm test -- --run views/library-batch` → **6 passed**；
`pytest tests/v04/fav/test_batch_ops.py -q` → **8 passed**；
ruff 净、mypy 250 文件净、typecheck 干净。

## 2 「全成或全不成」的理由（acceptance）
批量入台 20 条、第 13 条失败——若前 12 条已落台，用户看到的是
「一半进去了、一半没有」，而他**并不知道是哪一半**。再点一次：
前 12 条要么重复、要么因幂等静默跳过，**两种都让人无法确认最终状态**。

## 3 实现选择：先全验、后全写
两阶段——先把每一条都验一遍（**收集所有失败，不是遇到第一条就停**），全过之后才写。
于是「回滚」不需要真去撤销已写入的东西：**根本没写**。
内存实现如此，SQL 实现同理（校验在事务内、失败即 ROLLBACK）。

## 4 三条容易被做成「差不多」的地方
- **清单不是可选项**：只回滚不报错，用户会以为是自己没点到。
  `失败清单指名道姓` 断言 `favorite_id` + `reason` 都在；
- **一次说清所有问题**：`test_all_failures_are_collected_not_just_the_first` —— 
  只报第一条会逼用户改一条试一次；
- **越权项报错而不是静默跳过**：静默跳过等于**悄悄少做了事**，而用户以为全做了。

## 5 前端：NEVER 乐观更新
后端是单事务，界面若在请求返回前就标「已入台」，整体回滚时会留下**一屏假的成功态**。
`NEVER 乐观更新：请求返回前不显示成功态` 用一个手动 resolve 的 Promise 卡住返回来断言；
`整体回滚时不留任何成功态` 再验一次失败路径。
报错清单在前端**逐条摊开**（哪条 + 为什么），只说「操作失败」等于让用户重试到猜出来为止。

## 6 self_review（self_review=true）
① 见 §2~§5，acceptance「部分失败整体回滚 + 报错清单」由后端 4 条 + 前端 2 条共同覆盖；
② 冻结件未动；③ 无禁用词；④ 复用 `flint/fav/store.py` 与 `flint/graph/store.py`，
批量层 NEVER 自己写入库逻辑；⑤ 装载 ~2k tokens（5%）。

## 7 产出
`flint/fav/batch.py`、`tests/v04/fav/test_batch_ops.py`（8 条）、
`web/views/library-batch/LibraryBatch.tsx`、`LibraryBatch.test.tsx`（6 条）。
