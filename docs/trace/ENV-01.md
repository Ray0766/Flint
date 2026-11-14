# ENV-01 · 不带 `PYTHONIOENCODING=utf-8` 会有 27 条判据假红

**结论**：闸接在开跑之前。不带那个变量时，**一条判据都不会跑**，
屏上只有一句 ASCII 的「怎么办」。

装载：卡 `ENV-01` · `docs/V041-BATCH7-COMPLETION.md` · `tests/conftest.py`
· `worker.md` · `Makefile`

---

## 1 那条链子

```
子进程（尺子脚本）按 GBK 往 stdout 写中文
  → 父进程按 UTF-8 解
  → 读取线程抛 UnicodeDecodeError
  → subprocess.run 回来的 stdout 是 None
  → 判据里 "xxx" in done.stdout 炸
  → TypeError: argument of type 'NoneType' is not iterable
```

**那句 `TypeError` 与代码坏了长得一模一样。** 第 7 批实测：
不带 **35 红** / 带上 **8 红**——那 8 条才是真的。
差的 27 条足以让下一个会话相信自己撞上一片回归，然后去修没坏的东西。

## 2 判的是实况，不是「那个变量在不在」

真正咬人的是**父进程用什么编码解子进程的字节**。变量只是设定它的一种办法：

- Linux/CI 上默认就是 UTF-8，没有那个变量也安全——判变量会**误报**；
- 变量设成 `gbk` 也算「在」，而那照样炸——判变量会**漏报**。

所以量 `sys.stdout.encoding`。两个方向的错都堵掉了，且这条尺子在 CI 上是空操作。

## 3 消息的第一行是 ASCII，而且是那句「怎么办」

这条消息**要从一个非 UTF-8 的 stdout 走出去**——中文那几段在读者屏上多半是乱码。
实测长这样：

```
[flint] stdout encoding is gbk, not UTF-8.
[flint] Run:  PYTHONIOENCODING=utf-8 pytest -q

�����ı�׼������� gbk������ UTF-8��
```

**乱码里唯一还读得出来的就是那两行。** 把结论放在中文段落末尾的话，
真正需要它的那一次，它恰好看不见。

消息里另外点名了那句假红长什么样（`NoneType`）与实测的三个数（27 / 35 / 8）。
只说「请设置环境变量」的话，下一个人设完、红消失了，
他仍然不知道刚才那 27 条是假的——下一次不带变量时他会重新怀疑代码。

## 4 闸放在 `pytest_configure`

不是某一条用例里：**那 27 条一旦开跑，满屏 `TypeError` 就已经把这句说明淹没了**
——而它正是用来防止那种误读的。

出口留了一个明写的（`FLINT_ALLOW_NON_UTF8_STDOUT=1`），并在消息里说清
「那时红的那几十条要自己分辨」。留明写的出口比让人去注释掉一道闸好：
**注释掉的那道闸不会有人再打开。**

## 5 一处定义，他处引用

| 处 | 写了什么 |
|---|---|
| `tools/check_encoding_env.py` | 那句人话与判定逻辑（唯一真相） |
| `tests/conftest.py` | `pytest_configure` 调它 |
| `worker.md §4.3b` | 固定纪律段，并指向上面那个文件 |
| `Makefile#gate` | 全局门那条命令带上变量 |

判据 `test_the_discipline_is_written_once_and_referenced` 要求后两处**指向**它，
而不是重抄一遍措辞——抄两份会各自漂移。

## 6 断点：判据自己第三次踩同一个坑

阴性对照原本写的是 `assert "TypeError" not in said`。

**而那句人话自己就点名了 `TypeError`**（那正是它的作用）。
拿禁词去查，把说明问题的那句话当成了问题本身——本批第十七次同一形状。

改后判的是它真正要证明的那件事：**一条判据都没跑起来**——
没有 traceback、没有 `passed`、没有 `failed`。

另外两处小的：`MESSAGE` 是模板（`{bypass}` 还没填），判据要判**读者真会看到的那一段**，
所以抽了 `hazard_text()`；`pytest.exit` 把消息写到 **stderr**，
判据收两股流而不是挂在那个实现细节上。

## 7 门

```
pytest tests/v041/test_encoding_guard.py -q     8 passed
  含阴性对照：清掉变量真跑一次 → rc=1，只有那句说明，零判据执行
  含正向对照：带上变量 → rc=0，那句说明一个字都不出现
ruff check .                                     All checks passed
```
