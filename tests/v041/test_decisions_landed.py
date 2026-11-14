"""裁决落地：owner 的历次裁决逐字进 `DECISIONS-v04.md`。

第 6 批 `DEC-035-038-LANDING` 落前四条，第 7 批 `DEC-039-041-LANDING` 落三条，
第 8 批 `DEC-042-LANDING` 落一条，第 9 批 `DEC-043-LANDING` 落两条。
**四批共用这一个文件**（四张卡的 `verify_cmd` 都指着它），所以判据按
「全部已落的条」写，而不是按「本批那几条」写——
按批写的话，上一批的条目会随着卡的收工失去看守。

## 为什么裁决要有判据

`DECISIONS-v04.md` 是 owner 的变更通道落点。**只记结论的一行等于没记**——
下一个人（或下一个会话的我）看到「维持 DEC-034」时，无从知道当时权衡的是什么，
于是要么盲从、要么把它重开一遍。所以每条 MUST 带**来由**与**影响面**。

## 追加式，NEVER 回改

`DECISIONS-v04.md` 与 `docs/progress-v041.jsonl` 同一条纪律：
既有行是**已经被引用过的事实**（本仓有 trace 直接写着 `DEC-030` 之类的编号）。
回改一行，那些引用会指向另一个意思，而**指错的引用与指对的长得一模一样**。

## 后三条各自最容易被写空的那一句

三条裁决里，真正在约束后续实现的**不是结论，是结论附带的那句禁令**——
而禁令恰恰是转述时最先掉的东西：

- `DEC-039` 真正的产品是**那条禁令**（全仓禁止拿 `last_active` / `first_seen`
  做算术得出「陈旧」），不是「把槽藏起来」这个动作；
- `DEC-040` 只在**呈现层**合并 `global` 与 `NULL`，库里两者 MUST 保持可分辨；
- `DEC-041` 种完主题**必须撤掉** `CONSOLE_BASELINE` 里那条 404 额度。

所以下面给这三句各挂一条独立判据——**写进正文才算落地，只写结论不算**。
"""
from __future__ import annotations

import re
from itertools import pairwise
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DECISIONS = REPO / "DECISIONS-v04.md"

# 已落的七条。每条挂一个**它必须提到的关键事实**——
# 只断言「编号出现了」的话，写一行 `- **DEC-035**：见工单` 也能过。
LANDED: dict[str, tuple[str, ...]] = {
    # 第 6 批（DEC-035-038-LANDING）
    "DEC-035": ("region", "迁移", "静静地什么都不筛"),
    "DEC-036": ("Topic", "名称三元组", "改规格"),
    "DEC-037": ("403", "取证样例", "白名单"),
    "DEC-038": ("DEC-034", "已经有主", "标签文字"),
    # 第 7 批（DEC-039-041-LANDING）
    "DEC-039": ("SLOT-02", "Revalidator", "snapshot_stale", "last_active"),
    "DEC-040": ("ghtrend", "未归区", "回填", "103"),
    "DEC-041": ("DEMO-TOPIC", "夹具", "CONSOLE_BASELINE", "404"),
    # 第 8 批（DEC-042-LANDING）
    "DEC-042": ("分析界面", "图谱工作台", "HOTSPOT-02", "入台"),
    # 第 9 批（DEC-043-LANDING）
    "DEC-043": ("组合", "POST /projects/combo", "热榜", "ENTRY-04"),
    "DEC-044": ("contracts/", "关系表", "snapshots", "最新一条"),
    # 第 9 批（DEC-045-LANDING · owner 2026-08-09 的五条）
    "DEC-045": ("下一版", "筛选器", "REGION-08", "CN-02"),
    "DEC-046": ("右上角", "PRINCIPLES#A3", "prefs", "SHELL-01"),
    "DEC-047": ("DARK-01", "跟随系统", "V0 files 前端设计", "SHELL-02"),
    "DEC-048": ("pg_tables", "持久层", "not_provided", "PERSIST-01"),
    "DEC-049": ("孤岛", "ENTRY-04", "DEC-043", "端点"),
    # owner 2026-08-09 第二轮（解阻用的两条）
    "DEC-050": ("SHELL-02", "prefs", "跟随系统", "outputs"),
    "DEC-051": ("workbenches", "workbench_graphs", "project_id", "K6"),
    # 第 10 批（DEC-052-LANDING）
    "DEC-052": ("真实源联网工作窗口", "CN-04", "fixtures/_probe/", "K2-01"),
    "DEC-053": ("访客系统", "NEVER 硬编", "对抗件", "K2-01"),
    "DEC-054": ("geo=HK", "港区", "approx_traffic", "下一版"),
    # 第 11 批（DEC-055-056-LANDING）
    "DEC-055": ("evidence_snapshot", "内嵌不引用", "取证失败", "FAV-WRITES"),
    "DEC-056": ("DEC-045", "DEC-054", "EMIT_REGION", "provenance"),
    # 第 12 批（DEC-057-058-LANDING）——**补挂**：那一批只推了水位，
    # 没把这两条挂进本表。水位判据说「最高编号是 058」，
    # 而「058 的正文里有没有东西」当时没有任何一条判据在看，
    # 于是这两条与「只写了一行结论」在判据眼里长得一模一样。
    "DEC-057": ("GATE1-REAL", "fixtures/_probe/gate1/", "DEC-052", "40"),
    "DEC-058": ("region_of_members", "源常量", "REGION-SPAN", "NULL"),
    # 第 14 批（DEC-059-LANDING）
    "DEC-059": ("WB-01", "compose", "DESIGN-01~03", "Block"),
    # 第 15 批（DEC-060-LANDING）
    "DEC-060": ("colors.css", "29 条路由", "互链带", "steward"),
}

# 逐批分开列，为的是让「哪一批落了什么」在判据里看得见——
# 合在一起的话，下一批再加时没人说得清哪几条属于哪一批。
BATCH_6 = ("DEC-035", "DEC-036", "DEC-037", "DEC-038")
BATCH_7 = ("DEC-039", "DEC-040", "DEC-041")
BATCH_8 = ("DEC-042",)
# 第 9 批分两卡落：`DEC-043-LANDING` 落 043/044，`DEC-045-LANDING` 落 045~049。
# 两张卡同属第 9 批，所以逐批相对判里它们算**一批**；
# 拆成两组的话，`pairwise` 会去判 044 与 045 的先后——那是同一批内部的顺序，
# 由 `test_new_entries_are_appended_after_the_existing_ones` 的全序判据看着。
BATCH_9 = ("DEC-043", "DEC-044", "DEC-045", "DEC-046", "DEC-047", "DEC-048",
           "DEC-049", "DEC-050", "DEC-051")
BATCH_10 = ("DEC-052", "DEC-053", "DEC-054")
BATCH_11 = ("DEC-055", "DEC-056")
BATCH_12 = ("DEC-057", "DEC-058")
# 第 13 批（视觉批）没有裁决要落——**空批不占编号**，
# 所以这里从 12 直接跳到 14，而 DEC 编号本身仍然连续。
BATCH_14 = ("DEC-059",)
BATCH_15 = ("DEC-060",)


def _text() -> str:
    return DECISIONS.read_text(encoding="utf-8")


def _entry(number: str) -> str:
    """取某一条 DEC 的正文（到下一条 DEC 行为止）。"""
    text = _text()
    start = text.index(f"**{number}**")
    rest = text[start:]
    nxt = re.search(r"\n- \*\*DEC-\d{3}\*\*", rest)
    return rest if nxt is None else rest[: nxt.start()]


# ───────────────────────── 一、七条都在，且编号接得上


def test_every_landed_decision_is_present() -> None:
    """改名自 `test_all_four_decisions_landed`：条数从四变七，名字里的「四」过期了。

    留着旧名字的话，下一个人读到「四条」会以为只落了四条——
    **而判据的名字是它被读到的第一句话**。
    """
    text = _text()

    for number in LANDED:
        assert f"**{number}**" in text, f"{number} 没落进 DECISIONS-v04.md"


def test_the_numbers_continue_the_existing_watermark() -> None:
    """编号接现有水位。跳号或重号都会让 trace 里的引用指错条目。

    改前钉的是 `numbers[-1] == 38`（第 6 批的水位）。第 7 批落了 039~041 之后
    它红了——**红的是自己描述的那个水位过去了，不是有人乱编号**。
    第 8 批 042、第 9 批 043~044 各红过一次，同一个道理。
    第 9 批的第二张落地卡再落 045~049，水位 44 → 49，它第五次红。
    owner 一次答完三件之后又落 050~051（解阻用的两条），水位 49 → 51，第六次。
    第 10 批落 052（真实源联网工作窗口），水位 51 → 52，第七次；
    CN-04 探测出实况之后 owner 又落 053/054（weibo 访客握手 · gtrends 港区代理），
    水位 52 → 54，第八次。
    第 11 批落 055/056（收藏快照后端自取 · CN/HK 两区分家），水位 54 → 56，第九次。
    owner 一次答完第 11 批三件之后落 057/058（Gate① 网络授权窗口 · 跨区簇走乙），
    水位 56 → 58，第十次。
    第 13 批是视觉批，**一条裁决都没有，水位原地不动**——空批不占编号。
    第 14 批落 059（新增计划书主工作台 · 旧屏改名退居次要），水位 58 → 59，第十一次。
    第 15 批落 060（v4 调色板并入 `_ds` · 保路由局部吸收 · 本轮出卡不直接改码），
    水位 59 → 60，第十二次。
    第 17 批 owner 2026-10-27 一次点选四条：061（成文端点收分析作业号）· 062（Gate① 第二个
    真实网络窗口）· 063（总览改查表 + 重写补事件）· 064（冻结件修订窗口），水位 60 → 64，
    第十三次。那一批当天被叫停，这条判据没跟上，`MAC-04` 在 macOS 上首跑全量时补的。
    owner 2026-11-14 落 065（UI 从 0 重新设计，`REDESIGN-01`），水位 64 → 65，第十四次。
    水位跟着事实走，而「不许跳号、不许重号」这两条意图一字未动。
    """
    numbers = sorted({int(m) for m in re.findall(r"DEC-0(\d{2})\b", _text())})

    assert numbers[-1] == 65, f"最高编号是 DEC-0{numbers[-1]}，不是 DEC-065"
    for expected in range(35, 66):
        assert expected in numbers, f"DEC-0{expected} 缺号"
    assert len(numbers) == len(set(numbers))


# ───────────────────────── 二、每条写明来由与影响面，NEVER 只记结论


def test_each_decision_gives_its_reason_not_just_the_verdict() -> None:
    """只记结论的一行等于没记：下一个人无从知道当时权衡的是什么。"""
    for number, musts in LANDED.items():
        body = _entry(number)
        assert len(body) > 200, f"{number} 太短（{len(body)} 字），像是只记了结论"
        for must in musts:
            assert must in body, f"{number} 没提到关键事实：{must}"


def test_each_decision_names_what_it_affects() -> None:
    """影响面要点到**具体的东西**（文件 / 卡号 / 端点），NEVER 只说「影响前端」。"""
    for number in LANDED:
        body = _entry(number)
        assert re.search(r"`[^`]+`", body), f"{number} 的影响面里没有一个具体的名字"


def test_the_landing_says_who_decided_and_when() -> None:
    """每条都写明**谁裁的、哪天裁的**——署名与日期是它能被复核的前提。

    改前这里硬写着 `2026-08-08`（前七条都是那天裁的）。`DEC-042` 是
    **2026-08-09** 裁的，它当场红了——**红的是那个硬编的日期，不是漏了署名**。
    改成「有一个日期」而不是「有那一个日期」：日期本来就该跟着裁决走。
    """
    for number in LANDED:
        body = _entry(number)
        assert "owner" in body, f"{number} 没写是谁裁的"
        assert re.search(r"20\d\d-\d\d-\d\d", body), f"{number} 没写裁决日期"


# ───────────────────────── 三、追加式：既有行一个字都没动


def test_the_existing_decisions_were_not_rewritten() -> None:
    """既有行是**已经被引用过的事实**（trace 里直接写着编号）。

    回改一行，那些引用会指向另一个意思——而**指错的引用与指对的长得一模一样**。
    这里钉住几条被引用最多的：它们的关键词必须还在。
    """
    text = _text()

    for number, keyword in (
        ("DEC-032", "接口未提供"),
        ("DEC-033", "skipped_by_owner"),
        ("DEC-034", "disputed"),
    ):
        body = _entry(number)
        assert keyword in body, f"{number} 被改写了：找不到 {keyword!r}"
    assert text.count("**DEC-034**") == 1, "DEC-034 出现了不止一次（重号或被复制）"


def test_new_entries_are_appended_after_the_existing_ones() -> None:
    """新条目在文件**尾部**，且编号顺序与文件顺序一致：追加式写入的可见形态。

    改名自 `test_the_four_are_appended_after_the_existing_ones`——同上，
    「四」这个数过期了。判的东西没变，而且从「钉两对」改成**逐对判全序**：
    钉死两对的话，把 DEC-040 插到 DEC-036 前面也能过。

    上界改前是 `57`（写死在第 11 批那天的水位上），于是 057~059 三条
    **不在全序范围内**——它们插到哪儿都不会红。改成跟着最高编号走：
    水位每涨一次，这条判据自己就把新条目纳进来。
    """
    text = _text()
    highest = max(int(m) for m in re.findall(r"\*\*DEC-0(\d{2})\*\*", text))
    order = [text.index(f"**DEC-0{n}**") for n in range(35, highest + 1)]

    assert order[0] > text.index("**DEC-034**"), "新条目跑到了 DEC-034 前面"
    assert order == sorted(order), (
        f"文件顺序与编号顺序不一致：{order}——有条目被插在了中间"
    )


# ───────────────────────── 四、DEC-038 是「维持」，所以要说清代价


def test_maintaining_dec_034_records_its_cost() -> None:
    """维持一条决定**也要写代价**——不写的话，下一个人会以为它是免费的。

    `DEC-034` 的代价是 owner 自己确认过的：A/B/C 三类在记号上看起来一样。
    """
    body = _entry("DEC-038")

    assert "代价" in body
    assert re.search(r"A[/、]B[/、]C|三类", body), "没写清代价落在哪三类上"


# ───────────────────────── 五、后三条各自那句禁令 MUST 进正文
#
# 这三条判据判的都是**同一种失手**：结论转述对了，而结论附带的禁令掉了。
# 掉了之后条目读起来仍然通顺——「陈旧槽不显示」「global 归入未归区」
# 「demo 库种一条主题」三句话各自都成立，**而下一个实现的人拿不到边界**。


def test_dec_039_bans_the_timestamp_shortcut_by_name() -> None:
    """`DEC-039` 的产品是**那条禁令**，不是「把槽藏起来」这个动作。

    禁令 MUST 点名两个字段（`last_active` 与 `first_seen`）并写明是**全仓**范围——
    只写「不要瞎算陈旧」的话，下一个人会以为那是句劝告。

    为什么这条禁令值得单独钉：拿时间戳做算术得出「陈旧」，**是新写一套比对**，
    而且**它说的是系统不知道的事**——Revalidator 判的是「一份分析引用过的事实变没变」，
    而热点簇不引用事实，它本身就是事实的来源之一。
    """
    body = _entry("DEC-039")

    assert "last_active" in body and "first_seen" in body, (
        "禁令没点名那两个字段——不点名的禁令拦不住任何一次具体的写法"
    )
    assert "全仓" in body, "没写清禁令的范围是全仓"
    assert re.search(r"NEVER|禁止", body), "没有一句是禁令语气"


def test_dec_040_keeps_null_and_global_distinguishable_in_the_database() -> None:
    """`DEC-040` 只在**呈现层**合并，库里 `NULL` 与 `global` MUST 保持可分辨。

    把 `NULL` 回填成 `global` 会抹掉「这条簇从来没归过区」这个事实——
    而**抹掉之后，抹掉本身也看不见了**：回填过的行与本来就是 `global` 的行长得一模一样。
    """
    body = _entry("DEC-040")

    assert "呈现层" in body, "没写清合并只发生在呈现层"
    assert "回填" in body, "没写「NEVER 把 NULL 回填成 global」这一句"
    assert re.search(r"NEVER|禁止|不.{0,4}回填", body), "回填那句不是禁令语气"


def test_dec_041_requires_the_404_allowance_to_be_withdrawn() -> None:
    """`DEC-041` 有一条硬判据：种完主题**撤掉** `CONSOLE_BASELINE` 那条 404 额度。

    不撤的话，这条裁决就只是「库里多了一行」——**额度还在，屏上再退回 404 时没人会响**。
    额度是当初为「那一屏本来就没有数据」开的，数据有了，额度就该收回去。
    """
    body = _entry("DEC-041")

    assert "CONSOLE_BASELINE" in body, "没点名那条额度挂在哪"
    assert "404" in body
    assert re.search(r"撤|收回|去掉", body), "没写明额度要被撤掉"
    assert "夹具" in body, "没写清种进去的是夹具、不是模型产出"


def test_the_three_new_ones_say_which_sheet_they_close() -> None:
    """后三条各自关掉一张 `docs/blocked/` 的单——**点名是它能被核对的前提**。

    只写「已解决」的话，那张单会在盘上继续开着，
    而下一批的人会把同一件事再做一遍。
    """
    sheets = {
        "DEC-039": "SLOT-02",
        "DEC-040": "REGION-08",
        "DEC-041": "DEMO-TOPIC",
    }
    # `DEC-042` 不关单——它是一条**新的走法**，不是对某张单的答复。
    # 硬把它塞进这张表会逼出一个不存在的单号。
    for number, sheet in sheets.items():
        body = _entry(number)
        assert sheet in body, f"{number} 没点名它关掉的那张单：{sheet}"


def test_each_batch_landed_after_the_one_before_it() -> None:
    """每一批都落在**前一批之后**——位置本身是「追加式」的证据。

    改名自 `test_the_batch_seven_entries_are_the_last_three`：
    第 8 批落了 `DEC-042`，「最后三条」这个说法过期了。
    改成逐批相对判，下一批再加时不用回来改。

    「不用回来改」当时说早了：`batches` 那一行**手写到第 9 批为止**，
    10~14 批的条目谁都没在看。逐批判的是「批与批之间的先后」，
    而漏掉的批次连这一层都没有——补齐到今天这一批。
    """
    text = _text()
    batches = (BATCH_6, BATCH_7, BATCH_8, BATCH_9, BATCH_10, BATCH_11,
               BATCH_12, BATCH_14, BATCH_15)

    for earlier, later in pairwise(batches):
        assert min(text.index(f"**{n}**") for n in later) > max(
            text.index(f"**{n}**") for n in earlier
        ), f"{later} 没有全部落在 {earlier} 之后"


# ───────────────────────── 六、DEC-042：卡片主体是导航，动作按钮是动作


def test_dec_042_separates_the_card_body_from_the_action_buttons() -> None:
    """`DEC-042` 的核心是**那条分界**，不是「点卡片有反应」。

    卡片主体是**导航**（进这个热点的分析界面），三个动作按钮是**动作**
    （收藏 / 入台 / 分享）。两者混为一谈的后果是具体的：
    用户想收藏，手指落在按钮旁边一点，屏就整个跳走了。

    `HOTSPOT-02` 的点击排除区判据**正为此而建**——这条裁决要点名它，
    否则下一个人会以为「给卡片加个 href」就完事了。
    """
    body = _entry("DEC-042")

    assert "HOTSPOT-02" in body, "没点名那条已经存在的点击排除区判据"
    assert "NEVER" in body, "两者不许混为一谈那句不是禁令语气"


def test_dec_042_says_where_each_of_the_two_goes() -> None:
    """**两个去向各自写清**：主体 → 分析界面；入台 → 图谱工作台。

    只写「点卡片进分析界面」的话，owner 那句「要使用卡片才进入图谱工作台」
    就丢了一半——而那一半正是他特意加的。
    """
    body = _entry("DEC-042")

    assert "分析界面" in body
    assert "图谱工作台" in body
    assert "入台" in body, "没写清是哪个动作把人带去图谱工作台"


def test_dec_042_forbids_running_an_analysis_on_open() -> None:
    """打开分析界面**只是查看**，NEVER 顺手跑一次分析。

    `AnalysisView` 文件头那句要照进裁决里：那会让用户每次点开都付一次钱，
    且同一个热点可能每次显示不同的判定——**判定本身就不再可被引用**。
    """
    body = _entry("DEC-042")

    assert "只是查看" in body or "只读" in body, "没写清进入不触发"
    assert "付一次钱" in body or "不再可被引用" in body, "没写清代价"


# ───────────────────────── 七、DEC-043/044：接通批的两条裁决


def test_dec_043_says_why_the_combo_route_beats_the_shorter_one() -> None:
    """`DEC-043` 真正的产品是**为什么不走那条更短的路**。

    只记「走甲」的话，下一个人看到乙案更短会以为当时没想到——
    而甲乙都摆在桌上，取甲是因为**乙绕开了「组合」这个产品概念**：
    那样建出来的项目只挂着一个热点，而证据卡、竞品强度、Coverage
    全是按「一组热点支撑一个假设」设计的。
    """
    body = _entry("DEC-043")

    assert "甲" in body and "乙" in body, "没写清当时权衡的是哪两条路"
    assert "端点早就装配好了" in body, "没说清甲案缺的只是入口，不是后端"
    assert "假设" in body, "没写清取甲的那个理由"


def test_dec_044_keeps_the_frozen_contract_out_of_it() -> None:
    """`DEC-044` 有一条**硬**的：`contracts/` 一字不动。

    `Job` 无 `cluster` 字段这件事保持原样，对应关系**落在关系表里**。
    不写这一句的话，最省事的实现就是给 `Job` 加个字段——
    而那是 `S2-1` 判死的动作（冻结件是唯一真相，不够用要停下报 owner）。
    """
    body = _entry("DEC-044")

    assert "contracts/" in body and "一字不动" in body, "没写清冻结件的边界"
    assert "关系表" in body, "没说清对应关系落在哪儿"


def test_dec_044_retires_the_guess_and_says_why_that_is_now_ok() -> None:
    """**在此之前「缺就是缺」是对的**——这条裁决要说清什么变了。

    猜 job id 那条路一直被判死（猜错时用户看到的是另一个热点的判定）。
    现在删掉它不是推翻那条纪律，是**它的前提变了**：有真相可查了。
    不写这一层的话，下一个人会以为「猜一个」曾经也行。
    """
    body = _entry("DEC-044")

    assert "猜" in body, "没提那条被删掉的路"
    assert "现在有真相可查了" in body, "没说清为什么现在可以删"
    assert "另一个热点的判定" in body, "没说清当初为什么判死它"


# ───────────────────────── 八、DEC-045~049：owner 2026-08-09 的五条
#
# 这五条是同一次对话里说的，落成五条而不是一条，为的是让**影响面各自归位**：
# 合成一条「本版收窄 + 挪下拉 + 补切换 + 建八表 + 加入口」的话，
# 下一个人改其中一件时无从知道另外四件是不是也跟着变。


def test_dec_045_defers_the_multi_source_question_by_name() -> None:
    """`DEC-045` 推迟的是**「不同地区用不同信息源」**，不是「地区」这个功能。

    owner 原话把两件事分开了：这一版做中国区的内容，**多源多区下一版**。
    只写「本版只做中国区」的话，下一个人会以为九区的列与 query 该拆掉——
    而那正是这条裁决明令保留的东西。
    """
    body = _entry("DEC-045")

    assert "下一版" in body, "没写清推迟到什么时候"
    assert re.search(r"信息源|多源", body), "没写清推迟的是「不同地区不同信息源」这一件"
    assert re.search(r"NEVER 删代码|保留不拆", body), "没写清九区既有能力保留"


def test_dec_045_keeps_the_other_regions_visible_instead_of_hiding_them() -> None:
    """其余八区**留在筛选器里并如实说明无内容**，NEVER 悄悄隐藏。

    隐藏与「说明无内容」在屏上是两回事：隐藏之后用户**不知道这个能力存在**，
    而它下一版就要用。这一句是收窄呈现与删功能之间的分界线，
    不写的话最省事的实现就是把选项从下拉里摘掉。
    """
    body = _entry("DEC-045")

    assert "筛选器" in body, "没写清其余八区留在哪儿"
    assert "隐藏" in body, "没写「NEVER 悄悄隐藏」那一句"
    assert re.search(r"不知道这个能力存在|下一版就要用", body), "没写清隐藏的代价"


def test_dec_046_names_the_two_axes_that_never_move_together() -> None:
    """`DEC-046` 真正的约束是**两条轴各自独立**，不是「下拉挪个位置」。

    切地区 NEVER 改语言、切语言 NEVER 改热点集合（`PRINCIPLES#A3`）。
    挪位置这个动作最容易顺手把两者并成一个「区域设置」控件——
    并了之后，一个说中文的人想看美国区的热点就没法表达了。
    """
    body = _entry("DEC-046")

    assert "PRINCIPLES#A3" in body, "没点名那两条轴的出处"
    assert "切地区" in body and "切语言" in body, "两条轴没有各自写清"
    assert "NEVER" in body, "两条轴那句不是禁令语气"


def test_dec_046_keeps_one_value_behind_the_two_places_that_show_it() -> None:
    """右上角与 `/settings/locale` 显示的 MUST 是**同一个值**，且存得住。

    两处各存一份的话，用户在右上角切了区、进详情屏看到的还是旧的——
    而**两个真相长得一模一样**，谁也说不出哪个是对的。
    存得住靠 `prefs` 表（`PERSIST-01`），NEVER 只存在内存里。
    """
    body = _entry("DEC-046")

    assert "/settings/locale" in body, "没写清详情屏保留"
    assert "prefs" in body, "没写清选择存在哪儿"
    assert re.search(r"同一个值|各存一份", body), "没写清两处是同一个值"


def test_dec_047_makes_follow_the_system_an_explicit_option() -> None:
    """三态里**「跟随系统」MUST 是一个显式选项**。

    两态会把「我没选过」和「我选了白天」混成一个：
    前者在系统切暗时该跟着变暗，后者 NEVER 变——
    合并之后这两种人只能有一种被满足，而**屏上看不出自己是哪一种**。
    """
    body = _entry("DEC-047")

    assert "跟随系统" in body, "没写清三态里的第一态"
    assert re.search(r"三态|三个", body), "没写清是三态"
    assert re.search(r"我没选过|混成一个", body), "没写清两态错在哪儿"


def test_dec_047_says_the_palette_exists_and_scopes_the_zero_hit_claim() -> None:
    """`DARK-01` 早就建好了板与双通道，**缺的只是控件**——这一层要写清。

    还有一件 MUST 写准：「零命中」的范围是 `web/`（唯一前端工程根）。
    `V0 files 前端设计/components/theme-toggle.tsx` 里**是有**一个 `ThemeToggle` 的，
    那是 `DEC-026` 划的**视觉蓝本**、NEVER 当工程目录。
    把范围写成「全仓」的话，下一个人 grep 一次就会以为这条裁决的前提是假的，
    进而怀疑整条裁决——**说过头的真话与假话一样会被推翻**。
    """
    body = _entry("DEC-047")

    assert "DARK-01" in body, "没写清板是谁建的"
    assert "V0 files 前端设计" in body, "没把蓝本目录排除在「零命中」之外"
    assert re.search(r"控件", body), "没写清缺的是控件不是板"


def test_dec_048_names_all_eight_tables_it_creates() -> None:
    """八张表**逐个点名**——只写「建齐缺表」的话，下一个人不知道是哪八张。

    这八个名字同时是 `PERSIST-01~04` 四张卡的分工依据，
    也是出口判据「八张表全部建成」唯一可核对的清单。
    """
    body = _entry("DEC-048")

    for table in (
        "favorites",
        "share_links",
        "prefs",
        "templates",
        "workbenches",
        "graph_nodes",
        "graph_edges",
        "cluster_verdicts",
    ):
        assert table in body, f"DEC-048 没点名 {table} 这张表"


def test_dec_048_says_the_root_cause_is_persistence_not_wiring() -> None:
    """根因是**持久层从没建**，不是接线没做——这一句决定了修在哪一层。

    写成「接口没接上」的话，下一个人会去前端找断线，
    而前端早就接完了（`POST /workbenches` 实测回框架 404）。
    出处 MUST 写明是 `pg_tables` 实查，NEVER 只写「实测发现」。
    """
    body = _entry("DEC-048")

    assert "pg_tables" in body, "没写清这八张表不存在是怎么查出来的"
    assert "不是接线没做" in body, "没写清根因不在接线那一层"
    assert "not_provided" in body, "没写清屏上那一态是这条根因的表征"


def test_dec_049_says_which_islands_it_opens_and_defers_to_dec_043() -> None:
    """`DEC-049` 是 `DEC-043` 的**落地口径**，不是一条新裁决。

    两者 MUST 互相点名：`DEC-043` 定的是走甲，`DEC-049` 定的是甲怎么落——
    不点名的话，下一个人会把它当成把同一件事记了两遍，
    然后删掉其中一条，而**两条的影响面并不相同**。
    """
    body = _entry("DEC-049")

    assert "DEC-043" in body, "没点名它落的是哪一条裁决"
    assert "孤岛" in body, "没写清这一步打开的是什么"
    assert "ENTRY-04" in body, "没写清由哪张卡实现"


def test_the_five_new_ones_each_name_a_card_that_implements_them() -> None:
    """五条各自点名**实现它的那张卡**——裁决与实现之间要有一条可走的路。

    只写裁决不写卡号的话，落地这件事就没有主：
    下一批的人读到一条裁决，无从知道它是已经做了还是还没做。
    """
    cards = {
        "DEC-045": "CN-02",
        "DEC-046": "SHELL-01",
        "DEC-047": "SHELL-02",
        "DEC-048": "PERSIST-01",
        "DEC-049": "ENTRY-04",
    }
    for number, card in cards.items():
        body = _entry(number)
        assert card in body, f"{number} 没点名实现它的卡：{card}"


def test_cn_01_is_recorded_as_needing_the_owner_in_person() -> None:
    """真实源抓取的**首次实跑**是 `worker.md` §7 事前必审四类之一。

    `DEC-022` 授权的是 B 档抓取的**纪律形态**（抓完必录 fixtures），
    授权与实跑是两件事——写成「已授权」的话，
    下一个会话会直接去跑，而那正是 owner 保留给自己的那一次点头。
    这一句落在 `DEC-045`（本版做中国区内容）里，因为它是那条裁决的执行边界。
    """
    body = _entry("DEC-045")

    assert "CN-01" in body, "没点名那张红线卡"
    assert "DEC-022" in body, "没写清已经授权的是哪一条"
    assert re.search(r"在场|点一次|首次实跑", body), "没写清欠的是什么"


# ───────────────────────── 九、DEC-050/051：owner 一次答完之后解阻的两条


def test_dec_050_says_why_theme_is_not_stored_per_device() -> None:
    """`DEC-050` 真正的产品是**那段「为什么不按设备存」**。

    只写「outputs 加两处」的话，下一个人看到「夜里用手机白天用台式机
    想要的不一样」这个真实需求，会以为当时没想到——
    而 owner 想到了并给了答案：**三态里的「跟随系统」已经覆盖它**。
    选「跟随系统」的人每台设备各跟各的系统走；显式选了亮或暗的人，
    是在说「我到哪都要这个」。
    """
    body = _entry("DEC-050")

    assert "跟随系统" in body, "没写清那个真实需求被哪一态覆盖了"
    assert "每台设备各跟各的系统走" in body
    assert "服务端为真相" in body, "没点名它与哪条既有纪律一致"


def test_dec_050_records_that_stopping_was_the_right_move() -> None:
    """owner 逐字说了「那是对的行为」——**这一句 MUST 留着**。

    不留的话，下一次撞上同样的 outputs 缺口时，
    下一个人会以为「停下开单」是一次失误，然后自己把 outputs 悄悄扩了。
    """
    body = _entry("DEC-050")

    assert "那是对的行为" in body


def test_dec_051_keeps_the_frozen_contract_out_of_it() -> None:
    """`DEC-051` 选第三条的**理由**就是冻结件一字不动。

    另外两条一条要凭空造一段项目关系（造出来的行与真的长得一模一样），
    一条要改冻结件（`S2-1` 判死的动作）。
    """
    body = _entry("DEC-051")

    assert "冻结件一字不动" in body
    assert "凭空造" in body, "没写清另一条路错在哪儿"


def test_dec_051_writes_down_the_cost_it_takes_on() -> None:
    """**分家是有代价的**，而代价 MUST 写下来。

    「我的工作台列表」将来会有两个来源，合并口径今天没有答案——
    到 `K6` 交互稿落地时必须回来定一次。
    不写的话，那天的人会以为这是一个新问题。
    """
    body = _entry("DEC-051")

    assert "两个来源" in body
    assert "K6" in body
    assert "NEVER 到那时才发现" in body


def test_dec_051_pins_the_null_project_id_semantics() -> None:
    """`project_id text NULL` 的语义 MUST 逐字写死。

    `NULL` =「这张图还没有归属任何项目」，且 **NEVER 往这一列写一个编出来的项目 id**。
    不写死的话，回填那天人手上没有真项目 id，最可能做的事就是编一个。
    """
    body = _entry("DEC-051")

    assert "project_id" in body
    assert "NEVER 往这一列写一个编出来的项目 id" in body
    assert "UPDATE" in body, "没写清将来那一步是 UPDATE 而不是带回填的迁移"


# ───────────────────────── 六、DEC-052：三个关键句 MUST 逐字在

# 这一条与上面那些「四个关键词都在」的判据**不是同一件事**。
# 关键词判的是「这条决策讲的是那件事」；这里判的是**三句划边界的话一个字都没丢**——
# 它们是 worker 被授权去联真实网络时唯一的刹车，掉一句就等于把刹车拆了一根。
DEC_052_HARD_LINES = (
    # 边界：域名族 + 额度 + 每次往返都要留证
    "域名族只许四源本家",
    "fixtures/_probe/{source}/",
    "开关一律命令行 flag，NEVER 环境变量",
    # CN-06 那一次预授权，以及它 NEVER 冒用哪个旗标
    "CN-06 那一次端到端真实录制由本裁决预授权",
    "--authorized-by=DEC-052",
    "NEVER 冒用 --owner-is-here",
    # 不在裁决内的那件事
    "每日定时的持续真实采集不在本裁决内",
    # CI 那条底线照旧
    "CI 照旧 NEVER 联网",
)


def test_dec_052_keeps_every_line_that_draws_a_boundary() -> None:
    """三处边界逐字在：**调试窗口边界 · CN-06 预授权 · 每日定时采集不在裁决内**。

    为什么判逐字而不判大意：这条决策是**一次授权**，而授权书里被改写过的句子
    与原句之间的差别，恰恰是「能做什么」与「不能做什么」的差别。
    `--owner-is-here` 那一句尤其——它的语义是「owner 此刻在场」，
    而 `CN-06` 是**预授权**、owner 并不在场；两个旗标混用一次，
    下一个人就再也分不出「谁点的头」。
    """
    entry = _entry("DEC-052")

    for line in DEC_052_HARD_LINES:
        assert line in entry, f"DEC-052 掉了这句划边界的话：{line}"


def test_dec_052_names_the_three_cards_it_authorises_and_no_more() -> None:
    """授权面**判等值**：CN-04 / CN-05 / CN-06 三张，多一张少一张都要有人回来改这里。

    只判「CN-04 在里面」的话，将来有人把第四张卡塞进这条授权，判据不会红——
    **而那正是一次没人签过字的联网授权**。
    """
    entry = _entry("DEC-052")
    cards = sorted(set(re.findall(r"CN-0\d", entry)) - {"CN-01"})

    assert cards == ["CN-04", "CN-05", "CN-06"], cards


def test_dec_052_was_appended_at_the_end_and_051_is_intact() -> None:
    """**只追加在末尾**：052 排在 051 之后，且 051 那一条没被这一步碰断。

    第一版这条判据写的是 `before.rstrip().endswith("。")`——**它自己错了**：
    切到 `**DEC-052**` 之前的那段结尾是 `…。
- `（下一条的列表符号），
    `rstrip()` 只去空白、把那个 `-` 留下了，于是它必红。
    量的东西没变，改的是量法：直接看 051 那一条**自己**的结尾。

    「既有字节逐字节未动」那一条**不在判据里**，在落地那一步现场量：
    追加前后比 `after[:len(before)] == before`（`docs/trace/DEC-052-LANDING.md` 记着
    实测 56361 → 59768、前缀相等为 True）。判据这边量不了它——
    一条判据只看得见**现在**的文件，看不见追加之前那一份。
    """
    text = _text()

    assert text.count("**DEC-052**") == 1, "052 落了不止一次"
    assert text.index("**DEC-051**") < text.index("**DEC-052**"), "052 没排在 051 后面"
    assert _entry("DEC-051").rstrip().endswith("。"), "051 那一条被截断了"
    # 末尾追加：052 之后 NEVER 再冒出别的 DEC 条目。
    assert not re.search(r"\n- \*\*DEC-\d{3}\*\*", _entry("DEC-052"))


# ───────────────────────── 七、DEC-053 / 054：授权与口径各自的边界句

#: `DEC-053` 授权的是**访客握手**，不是账号。这四句划的就是那条线。
DEC_053_HARD_LINES = (
    "cookie 值 MUST 每次动态获取，NEVER 硬编任何一枚",
    "上游对抗件，预期会碎",
    "授权上限就是访客握手",
    "NEVER 升级成账号登录或引入任何凭据",
)

#: `DEC-054` 的诚实性**由三件东西扛，缺一即 review_failed**——三件都要在条目里点名。
DEC_054_HARD_LINES = (
    "geo=HK",
    "region 落 CN",
    "provenance manifest 记真实 geo=HK 的 URL",
    "Google 趋势（港区）",
    "区间下界",
    "NEVER 编精确值",
    "下一版做多区时本代理口径撤销",
)


def test_dec_053_keeps_the_line_between_a_visitor_and_an_account() -> None:
    """访客握手 ≠ 账号登录。**这条线掉了，下一次「再多一点」就没有拦阻。**

    owner 逐字写了「授权上限就是访客握手」与「要更多回来找 owner」——
    没有这两句的话，下一个人读到的是「weibo 可以想办法进去」。
    """
    entry = _entry("DEC-053")

    for line in DEC_053_HARD_LINES:
        assert line in entry, f"DEC-053 掉了这句划边界的话：{line}"


def test_dec_054_names_all_three_things_that_carry_the_honesty() -> None:
    """`DEC-054` 的诚实性由三件东西扛：**DEC 文本 · manifest · 屏上署名**。

    这一条是本仓少有的「产品口径与数据事实不一致」的地方——采的是港区、落的是 CN 区。
    它之所以不是数据谎言，**全靠那三件同时在**；掉任何一件，
    屏上就变成「港区的榜冒充大陆热点」，而那正是 worker 上一轮拒绝的形状。
    所以三件都要在条目里点得出名字。
    """
    entry = _entry("DEC-054")

    for line in DEC_054_HARD_LINES:
        assert line in entry, f"DEC-054 掉了这句撑住诚实性的话：{line}"


def test_dec_054_says_the_proxy_is_temporary() -> None:
    """代理口径**写明它会被撤销**。

    一条没有退出条件的临时口径，下一版就是永久口径——
    而那时没有人记得它当初是个代办。
    """
    entry = _entry("DEC-054")

    assert "下一版" in entry and "撤销" in entry


# ───────────────────────── 八、DEC-055 / 056

#: `DEC-055` 划的那条线：**改的是谁来放，不是放什么**。
DEC_055_HARD_LINES = (
    "evidence_snapshot 从必填改成可选",
    "内嵌不引用",
    "NEVER 存空快照冒充成功",
    "NEVER 与「内容已被清理」共用同一句话",
)

#: `DEC-056` 的三处：撤代理 · 回填是改标签不是改事实 · 三者一致。
DEC_056_HARD_LINES = (
    "EMIT_REGION 从 CN 改为 HK",
    "NEVER 把它们合起来",
    "回填是把标签改回与出处一致，不是改写事实",
    "其余七区 NEVER 顺手打开",
)


def test_dec_055_keeps_the_line_between_who_puts_it_there_and_what_goes_in() -> None:
    """`DEC-055` 改的是**谁来放**，冻结件的「内嵌不引用」一字不动。

    最要紧的是那条边界：取不到证据卡时 **NEVER 存空快照冒充成功**，
    且**取证失败**与**内容已被清理**  NEVER 共用同一句话——
    两者该让用户做的事完全不同（一个去重试，一个去接受）。
    """
    entry = _entry("DEC-055")

    for line in DEC_055_HARD_LINES:
        assert line in entry, f"DEC-055 掉了这句：{line}"


def test_dec_056_says_out_loud_that_it_revises_dec_045() -> None:
    """**一次对既有裁决的回改 NEVER 只体现在新条目里**。

    `DECISIONS-v04.md` 是 append-only，`DEC-045` 那一行一个字都不能动。
    所以「它被改了」这件事只能由 `DEC-056` **单向声明**——
    而声明得够响，读 `DEC-045` 的人才顺着找得到。
    这条判据钉的就是那句声明在。
    """
    entry = _entry("DEC-056")

    assert "本条修订 DEC-045" in entry, "没说清它改了 DEC-045"
    assert "DEC-045 的其余部分" in entry, "没说清 DEC-045 哪些部分继续有效"


def test_dec_056_triggers_the_exit_condition_dec_054_wrote_for_itself() -> None:
    """`DEC-054` 自己写下的退出条件被**点名触发**。

    那条退出条件是「下一版做多区时本代理口径撤销、改真区」。
    一条临时口径最容易的死法不是被违反，是**没有人记得去撤销它**——
    所以撤销这件事要有一条判据看着。
    """
    entry = _entry("DEC-056")

    assert "触发 DEC-054" in entry or "DEC-054 自己写下的退出条件" in entry
    assert "代理口径就此撤销" in entry


def test_dec_056_keeps_every_line_that_draws_a_boundary() -> None:
    """两个常量 NEVER 合起来 · 回填只改标签 · 其余七区 NEVER 顺手打开。"""
    entry = _entry("DEC-056")

    for line in DEC_056_HARD_LINES:
        assert line in entry, f"DEC-056 掉了这句：{line}"


def test_the_two_revised_decisions_were_not_rewritten() -> None:
    """acceptance③：`DEC-045` 与 `DEC-054` 的行**一字不动**。

    回改一行的话，本仓所有引用过它们的 trace 会指向另一个意思——
    **而指错的引用与指对的长得一模一样**。
    """
    for number, keyword in (("DEC-045", "筛选器"), ("DEC-054", "geo=HK")):
        body = _entry(number)
        assert keyword in body, f"{number} 被改写了：找不到 {keyword!r}"
        # 它们各自**只出现一次**（没有被复制一份改着用）。
        assert _text().count(f"**{number}**") == 1, number

# ───────────────────────── 九、DEC-059：新增一屏，NEVER 替换掉已经做成的那一屏


#: `DEC-059` 的三句要害。三句各管一件**转述时最先掉的事**：
#: 第一句管「新增还是替换」，第二句管「旧屏的成果保不保得住」，
#: 第三句管「生成走哪条链」——三句里任何一句掉了，
#: 剩下的两句读起来都仍然通顺，而实现会走岔。
DEC_059_HARD_LINES = (
    "不替换现有「AI 设计工作台」",
    "一个字不改，成果一点不丢",
    "生成 MUST 走既有 compose 真链",
)


def test_dec_059_says_it_adds_a_screen_rather_than_replacing_one() -> None:
    """**新增一屏**，不是替换——这是本条与「重做设计工作台」的分界。

    替换的代价是具体的：`DESIGN-01~03` 三张卡做成的端点、作业与固化流程
    会跟着那一屏一起消失，而**消失之后，消失本身也看不见了**——
    新屏跑得好好的，没有人会去数少了什么。
    """
    body = _entry("DEC-059")

    assert "不替换现有「AI 设计工作台」" in body, "没写清是新增而不是替换"
    assert "改名" in body, "没写清旧屏的去向（改名退居次要）"


def test_dec_059_protects_what_design_01_to_03_already_built() -> None:
    """`DESIGN-01~03` 的**端点 / 作业 / 固化流程一个字不改**。

    「退居次要」是导航上的位置变化，NEVER 是功能的削减——
    这两件事在屏上长得很像（都是「那一屏不在第一位了」），
    而后者是把已经验收过的东西丢掉。
    """
    body = _entry("DEC-059")

    assert "DESIGN-01~03" in body, "没点名被保护的是哪三张卡的成果"
    assert "一个字不改，成果一点不丢" in body, "保护那一句掉了"


def test_dec_059_bans_the_blueprint_way_of_generating_by_name() -> None:
    """生成 MUST 走 **compose 真链**，NEVER 照蓝本让 LLM 直吐 HTML 再正则抠回来。

    这一条是本批最硬的一条，而它**必须点名两样东西**才拦得住：
    点名要走的那条链（`flint/jobs/compose.py`），以及点名不许出现的那个动作
    （用正则从 LLM 输出里抠 `<block` / `<part`）。
    只写「要走真链」的话，下一个人照蓝本抄一遍也自认为走了真链——
    蓝本那套绕过去的是 `Block` 判别联合的全部约束
    （`claim_ids` / `fact_ids` / 三通道 / 提升不变量 / 渲染门禁）。
    """
    body = _entry("DEC-059")

    for line in DEC_059_HARD_LINES:
        assert line in body, f"DEC-059 掉了这句：{line}"
    assert "flint/jobs/compose.py" in body, "没点名要走的那条链"
    assert "正则" in body and "<block" in body, "没点名不许出现的那个动作"


def test_dec_059_says_where_its_text_came_from() -> None:
    """**本条的原文出处与前几条不同，条目里 MUST 说出来。**

    `DEC-055`~`DEC-058` 都是 owner 贴进来的独立 DEC 块，条目里写的是
    「以下为 owner 粘贴的原文，一字未改」。本条 owner 没另贴 DEC 块——
    原文取自第 14 批工单【2】【3】两节，仍是 owner 的原话、一字未改，
    **但那句「owner 粘贴的原文」在这里会是假的**。

    一条裁决最容易的死法不是被违反，是**出处说不清**：
    下一个人看到「owner 粘贴的原文」，就不会再回去核对措辞。
    """
    body = _entry("DEC-059")

    assert "工单" in body, "没写清原文取自哪里"
    assert "未另贴" in body or "没有另贴" in body, "没说清 owner 本批没贴 DEC 块"


# ───────────────────────── 十、DEC-060：换的是值不是位置 · 路由一条不动


#: `DEC-060` 的三句要害。三句各管一件**转述时最先掉的事**：
#: 第一句管「换板换的是什么」（值，不是那一层在哪），
#: 第二句管「信息架构动不动」（29 条路由 / 7 个入口 / 5 tab 怎么吸收），
#: 第三句管「设计稿的记法进不进本仓」。
#: 三句里任何一句掉了，剩下的两句读起来都仍然通顺，而实现会走岔：
#: 掉第一句 → 有人把 v4 变量搬进 `app/globals.css` 当唯一层（那要退役 `_ds`）；
#: 掉第二句 → 有人照 v4 收成三屏（29 条路由里有 22 条从此点不到）；
#: 掉第三句 → `--bg`/`--panel`/`--accent` 混进本仓，两套命名各自漂移。
DEC_060_HARD_LINES = (
    "换的是**值**不是位置",
    "保 29 条路由与 7 个导航入口",
    "NEVER 引进本仓",
)


def test_dec_060_says_the_palette_changes_values_not_the_layer() -> None:
    """**唯一颜色来源仍是 `_ds/tokens/colors.css`**——换的是值，不是那一层在哪。

    被否决的那条路要写清代价，否则下一个人会以为它只是「另一种做法」：
    v4 变量进 `app/globals.css` 当唯一层 = 退役 `_ds` token 层、
    重映射约 80 个组件、重写 5 个判据文件。
    """
    body = _entry("DEC-060")

    assert "colors.css" in body, "没点名唯一颜色来源是哪个文件"
    assert "换的是**值**不是位置" in body, "换板那一句掉了"
    assert "globals.css" in body and "否决" in body, "没写清被否决的是哪条路"


def test_dec_060_keeps_every_route_and_every_nav_entry() -> None:
    """**29 条路由与 7 个导航入口一条不动**，v4 的 5 tab 只以屏内互链带吸收。

    这一条要点名两样东西才拦得住：不许出现的（合并屏 / 改 `NAV_ITEMS`），
    与要出现的（屏内互链带）。只写「保路由」的话，
    下一个人新建一个 `/judge` 也自认为没删路由——**加一屏同样是改架构**。
    """
    body = _entry("DEC-060")

    assert "保 29 条路由与 7 个导航入口" in body
    assert "互链带" in body, "没写清 5 tab 以什么形式吸收"
    assert "NAV_ITEMS" in body, "没点名不许动的那张表"


def test_dec_060_bans_the_design_files_variable_names() -> None:
    """v4 那 12 个变量名是**设计稿的记法**，只搬值 NEVER 搬名。

    搬了名字的代价：`--bg`/`--panel`/`--accent` 与 `--paper`/`--surface`/`--sulfur`
    两套命名并存，而组件读的是哪一套在屏上看不出来。
    """
    body = _entry("DEC-060")

    for line in DEC_060_HARD_LINES:
        assert line in body, f"DEC-060 掉了这句：{line}"
    assert "--bg" in body and "--accent" in body, "没点名那几个不许进来的名字"


def test_dec_060_says_where_its_text_came_from() -> None:
    """**本条的出处与 `DEC-059` 又不同，条目里 MUST 说出来。**

    `DEC-055`~`DEC-058` 是 owner 贴的独立 DEC 块；`DEC-059` 取自工单原话；
    本条的文字是 **steward 拟的选项文本**，owner 从三组选项里各选定一项。
    写成「owner 原文」在这里会是假的——而下一个人看到那句话，
    就不会再回去核对措辞（`DEC-059` 已经踩过一次同类）。
    """
    body = _entry("DEC-060")

    assert "steward" in body, "没写清文字是谁拟的"
    assert "选项" in body, "没写清 owner 做的是「从选项里选」"
    assert "NEVER 写成「owner 原文」" in body or "NEVER 写成「owner 粘贴的」" in body, (
        "没把那句禁令写进条目里")
