# SHIP-11 · trace

**卡**：本批收尾——完成态报告 + 五条门 + 七项功能可测状态表。

## 顺序（卡面写死，逐条照做）

1. 先写各卡 trace 与台账（本批七张卡的 trace 都已落盘）；
2. 再跑五条门；
3. **最后只改完成态报告的数字**——门跑完之后 NEVER 再动被判据读的文件
   （第 9 批那次「5013 passed」是假数字，就是因为门跑完 88 秒后又关了三张单）。

## 五条门第一轮：3 failed

三条红**全是本批推翻了它们前提的尺子**，逐条点名：

| 红的 | 谁推翻了它 | 处置 |
|---|---|---|
| `test_cn06_e2e_real::test_the_screen_name_says_hong_kong` | `DEC-056` 撤销代理口径 | 翻成「署名必须**不带**地区缀」——同一件事的两面 |
| `test_design_submit::test_the_payload_carries_what_the_consumer_reads` | `SMOKE-01` 实跑 | 见下，这一条最值得记 |
| `test_fav_writes::test_the_frontend_never_invents_snapshot_content` | `DEC-055` | 从「里面 NEVER 出现编的字段」翻成「**整格都不由前端说**」 |

三条**全部翻面，一条都没删**。

### 那条判据自己就是缺陷

`test_the_payload_carries_what_the_consumer_reads` 的名字写着
「payload 带的是**消费方读的那个**」，而它断言的是 `payload["brief"]`——
**消费方读的是 `payload["prompt"]`**（`design_generate.py:118`）。

> 一条名叫「两边对得上」的判据，钉住的正是那个对不上的键，**而它一直是绿的**。

翻面时不只改了字面，还把**消费方那一侧一起读进来**：
两边从此对着同一个名字，谁先动都会红。

## ruff 第一轮：5 errors

全是本轮新写的三个判据文件（一个用不上的 `noqa`、一处 import 未排序、
一个没用到的 `Any`、两处 `import x as x` 别名）。**逐条改，没有用 `--fix` 盲改**。

## 「吸收批那 9 条」本批不做（卡面 acceptance⑤）

`docs/research/对标审阅-2026-08.md` §2 那 9 条要严格化的对象是**判定与引用**。

**推迟理由**：本批之前 `cluster_verdicts` 全库 0 行、compose 提交回 503、
设计生成从来没跑通过——**要严格化的东西基本是空的**。
对着空表做严格化，做出来的判据只会证明「空表符合规范」。

**重启条件**：⑥热点分析在真网络上跑通一次（需要 owner 开授权窗口）之后，
库里第一次有真判定与真引用，那 9 条才有检得到的东西。
