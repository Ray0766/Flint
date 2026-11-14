# MAC-07 · 落盘生成物的换行（@2026-11-14）

出处：`docs/trace/MAC-01.md` §7.5 第 1 条、`docs/trace/MAC-02.md` §三丙类末行。

## 一、装载清单

`harness/replay30.py:110-120` · `harness/gate1_regress.py:65-75` · `harness/m3_regress.py:228-236` ·
`harness/m4_regress.py:168-177` · `harness/drill7.py:150-154` ·
`fixtures/_generate_trial_specs.py:230-248` · `flint/spec/pack_zip.py:40-56` · `.gitattributes`。

## 二、根因

五个写入点用 `Path.write_text(text, encoding="utf-8")`，没指定换行。Python 文本模式在 Windows 上
把 `\n` 写成 `\r\n`。入库那份是 Windows 上生成的；`.gitattributes` 是 `* -text`，git 不做转换。
于是在 macOS 上每跑一遍，同样的内容被重写成 LF，66 个文件显示为已修改。

`harness/m4_regress.py:173` 早就带着 `newline="\n"`——这个坑有人踩过，只修了一处。

## 三、改动

| 位置 | 改了什么 |
|---|---|
| `harness/replay30.py`、`harness/gate1_regress.py`、`harness/m3_regress.py`、`harness/drill7.py`、`fixtures/_generate_trial_specs.py`（两处） | `write_text` 加 `newline="\n"` |
| `docs/trace/replay30/` 30 个、`docs/trace/goldcases/` 20 个、`docs/trace/golddocs-doc/` 12 个、`assets/trial_specs/` 4 个 json、`docs/trace/drill7.md` | CRLF → LF，共 67 个文件。`git diff --ignore-cr-at-eol` 对这批路径无输出：内容一个字没变 |

这个提交的 diff 行数很大（每个文件整篇），看它要带 `--ignore-cr-at-eol`。

## 四、判据先行

`tests/v041/test_generated_artifacts_lf.py`（8 条）先写，改前 `6 failed, 2 passed`：
五个写入点各红一条（`m4_regress` 那条本来就绿）+ 入库文件带 CRLF 一条。改后 8 passed。

写入点那一条用 AST 判，不靠跑出来的产物：在 POSIX 上不写 `newline` 产物也是 LF，
跑一遍分不出写没写。

## 五、验证

重新生成一遍（`tests/m1/test_m1_037` 至 `041`、`tests/m2`、`tests/m3/test_m3_025.py`、`tests/m4`，
605 passed）之后，这批路径里还会变的只剩 4 个文件，其余 66 个不动。

## 六、还剩 4 个每跑必变的，没有动

| 文件 | 为什么每次都变 |
|---|---|
| `assets/trial_specs/{one,two,three}/pack.zip` | `flint/spec/pack_zip.py:48-54` 用 `archive.writestr(名字, 文本)`，zip 条目的时间戳取当前时刻 |
| `docs/trace/drill7.md` | 第 27 行 `job_duration_seconds_sum` 是墙钟耗时 |

这两样在 Windows 上也是每跑必变，不是迁机器带来的。zip 那个要改的是产物代码（给条目一个固定时间戳），
会改变交给用户的导出包的字节；墙钟那一行要改的是演练报告写什么。都不是换行问题，本卡没有碰。
在它们修掉之前，跑完全量 pytest 要 `git restore` 这 4 个文件。
