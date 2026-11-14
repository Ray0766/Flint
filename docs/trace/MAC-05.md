# MAC-05 · 环境两件：取证作业与 PDF 镜像（@2026-11-14）

出处：`docs/trace/MAC-02.md` §三甲类。起点：3 条 failed + 3 条 setup error。

## 一、装载清单

`harness/demo_seed_probe_job.py`（全文）· `tests/v041/test_probe_job_owned.py`（全文）·
`tests/m1/test_m1_004.py:104-124` · `tests/v041/test_job_denied_state.py:50-100` ·
`docs/blocked/DEMO-JOB-NOT-OWNED-BY-THE-PROBE-USER.md:1-40` · `docker/pdf/Dockerfile` ·
`tests/m3/test_m3_035.py:20-52`。

## 二、取证作业

**两条作业各自的来历不一样**：

- `probe-owned-ingest`：`FIX-09` 起就有种子脚本，新库里没有只是因为没跑过它；
- `m1004-j`：**从来没有脚本造它**。它是 `tests/m1/test_m1_004.py:113-116` 早年直接打 demo 库
  时留下的一行，后来被 `test_job_denied_state` 当成「不属于探针的作业」的活样本。
  Windows 机上它一直在，是因为那个库从没重建过。

所以第二条不只是「新机器没跑种子」，是「这个样本没有出处」。改法：让
`harness/demo_seed_probe_job.py` 连它一起种，形状逐字照 `test_m1_004` 留下的那一行
（`daily_ingest` / `queued` / 发起人 `u-sys` / org 域 `sys`），`ON CONFLICT DO NOTHING`。

判据先行：`test_probe_job_owned::test_the_seed_also_plants_the_job_the_probe_must_not_see`
先写，实现前红（`ImportError: cannot import name 'NOT_MINE_JOB_ID'`）；实现后 15 passed。
另注入一次行为层的 bug——把反向样本的发起人改成探针自己——这条红，还原后绿。

往演示库种的那一下是运维动作（判据只连测试库，`tests/v041/test_probe_job_owned.py` 开头那段纪律）：

```
$ .venv/bin/python -m harness.demo_seed_probe_job
probe-owned job ready: probe-owned-ingest (initiated_by=demo-user)
not-mine job ready: m1004-j (initiated_by=u-sys)
```

种子脚本文档串里「只写 `jobs` 一行」改成了两行；跑法补了 POSIX 的写法。
**没有把它接进 `start-demo.sh`**：脚本头写着 opt-in、NEVER 自动跑，那是 `FIX-09` 的决定，本卡不翻。
改成写进 `docs/macOS-安装.md` 第六节。

## 三、PDF 镜像

`docker build -t flint-pdf:69 docker/pdf` → exit 0，镜像 548MB。
这一步联了网（拉基础镜像、apt、pip）；它是环境预备，不在 CI 里（`docker/pdf/Dockerfile` 头注释原话）。
写进 `docs/macOS-安装.md` 第六节。

## 四、验证

`pytest tests/v041/test_job_denied_state.py tests/v041/test_sse_live.py tests/m3/test_m3_035.py tests/v041/test_probe_job_owned.py -q`
→ `40 passed`。ruff 零条；`mypy --strict harness` 28 文件零条。

## 五、顺带看到、没有动的

`test_probe_job_owned::test_the_seed_refuses_when_the_identity_does_not_exist` 在本卡第一次跑时红过一次，
紧接着重跑就绿了，之后没再出现。它判的是「测试库里没有 `demo-user` 时种子拒绝」，
红的那一次测试库的 `users` 里多半留着别的判据放进去的 `demo-user`。没有复现出来，原因是推的，不是量的。
