"""ENTRY-04 / `DEC-049`：广场多选卡片建组合——**项目族的活入口**。

`DEC-043` 定的是**走甲**（广场多选建组合，而不是分析界面直接建项目），
`DEC-049` 定的是**甲怎么落**。项目族六屏在第 8 批 `NAV-05` 之后内部已经连通，
缺的只是走进这一族的第一步（`docs/blocked/MAIN-CHAIN-HAS-NO-LIVE-ENTRANCE.md`）。

## 一句要先说清的话：**广场选的是热点卡，组合要的是证据卡**

`POST /projects/combo` 的 `card_ids` 是 **`evidence_cards`** 里的 id，
而广场上一张卡是一个**热点簇**——一个热点底下可能有好几张证据卡。

所以从广场带过去的参数叫 **`?clusters=`**，不叫 `card_ids`：
叫成 `card_ids` 的话，下一个人会直接把它转发给端点，
而那些 id 在 `evidence_cards` 里**一条都查不到**——
请求会失败，而失败信息说的是「这些卡不存在」，
读的人无从知道真正的原因是「这里传的根本不是那种 id」。

`2~5` 这个数也因此**不在广场判**：它说的是证据卡张数，
真正判它的是 `/combo` 那一屏（`comboCountValid`）与服务端。

## 多选 NEVER 干扰既有单击

`DEC-042` 把卡片分成三层，本卡加的是第三层：

| 层 | 是什么 | 点它会怎样 |
|---|---|---|
| 卡片主体 | **导航** | 进这个热点的分析界面 |
| 三个动作按钮 | **动作** | 收藏 / 入台 / 分享 |
| **选择控件**（本卡加的） | **选中态** | 只把这张卡放进组合，**屏不跳走** |

混起来的后果 `HOTSPOT-02` 已经写过：用户想勾选、手指落在旁边一点，
屏就整个跳走了，而他并不知道自己刚才导航去了哪。
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLAZA_CARDS = REPO / "web" / "components" / "plaza" / "PlazaCards.tsx"
PLAZA_PAGE = REPO / "web" / "app" / "plaza" / "page.tsx"
COMBO_PAGE = REPO / "web" / "app" / "combo" / "page.tsx"
COMBO_VIEW = REPO / "web" / "components" / "views" / "ComboEntryView.tsx"
MESSAGES = REPO / "web" / "messages"
#: 换行符写成 `chr(10)`：这份判据里有几处要把源码按行拼回去，
#: 而反斜杠 n 那个字面量在被改写脚本经手时会被当成真的换行插进来
#: （本卡为此连着炸了三次，红的每次都是判据文件自己的语法）。
NEWLINE = chr(10)


# ───────────────────────── 一、多选态真的加上了


def test_the_plaza_has_a_selection_control_on_each_card() -> None:
    """每张卡有一个**独立的**选择控件。"""
    code = PLAZA_CARDS.read_text(encoding="utf-8")

    assert 'data-testid="plaza-card-checkbox"' in code
    assert 'data-testid="plaza-card-select"' in code
    assert "onToggleSelect" in code


def test_the_selection_layer_is_optional_so_existing_callers_are_untouched() -> None:
    """`onToggleSelect` 没给 = 这一屏没有多选态。

    做成必填的话，`DemoFlow` 那个既有调用点会当场坏掉——
    而它与广场是两件事。
    """
    code = PLAZA_CARDS.read_text(encoding="utf-8")

    assert "onToggleSelect?:" in code, "多选层不是可选的"
    assert "const selectable = onToggleSelect !== undefined;" in code


def test_the_build_entrance_appears_only_with_two_or_more() -> None:
    """acceptance①：**选中两张或更多** → 建组合入口可用。"""
    code = PLAZA_CARDS.read_text(encoding="utf-8")

    assert "selected.length >= 2" in code
    assert 'data-testid="plaza-combo-build"' in code
    assert "disabled={!canBuild}" in code


def test_the_counter_is_always_visible_not_only_when_ready() -> None:
    """计数条**恒在**，哪怕一张都没选。

    只在选够时才出现的话，用户不知道「要选几张才能建」——
    而那正是他要问的第一个问题。
    """
    code = PLAZA_CARDS.read_text(encoding="utf-8")
    bar = code.split('data-testid="plaza-combo-bar"')[1].split("</section>")[0]

    assert "plaza-combo-count" in bar, "计数条里没有计数"
    assert 'data-testid="plaza-combo-hint"' in code, "没有「选两张才能建」那句提示"
    # 计数条**在三态分支之上**：放在「有卡」那一支里的话，
    # 切到没有卡的区时整条计数条消失，而用户的选中态还在——
    # 屏上说「没有」，手里其实握着两张（第一版就是这样，真浏览器抓出来的）。
    assert code.index('data-testid="plaza-combo-bar"') < code.index("{outOfScope ? ("), (
        "计数条被放进了某一态的分支里——换个区它就不见了")


# ───────────────────────── 二、多选 NEVER 干扰既有单击（两者各有判据）


def test_clicking_the_card_body_still_navigates_to_the_analysis_screen() -> None:
    """`DEC-042` ①：卡片主体仍是**导航**。本卡一个字都没动它。"""
    code = PLAZA_CARDS.read_text(encoding="utf-8")

    assert "onClick={() => onSelectCluster?.(card.clusterId)}" in code
    assert 'role={onSelectCluster ? "link" : undefined}' in code


def test_the_selection_control_stops_the_click_from_bubbling() -> None:
    """勾选**不跳屏**：`stopPropagation` 拦住冒泡。

    少了它，勾一下会既选中又跳去分析界面——
    而用户并不知道自己刚才导航去了哪（`HOTSPOT-02` 的原话）。
    """
    code = PLAZA_CARDS.read_text(encoding="utf-8")
    block = code.split('data-testid="plaza-card-select"')[1].split("</label>")[0]

    assert "e.stopPropagation()" in block, "勾选框没有拦住冒泡"


def test_the_keyboard_path_is_still_guarded_by_the_target_check() -> None:
    """键盘那一半：`<li>` 上的 `e.target !== e.currentTarget` 还在。

    `stopPropagation` 拦的是 click，**keydown 照样冒上来**——
    这是点击排除区的键盘形态（第 8 批 `NAV-02` 栽过一次）。
    """
    code = PLAZA_CARDS.read_text(encoding="utf-8")

    assert "if (e.target !== e.currentTarget) return;" in code


def test_the_three_action_buttons_are_untouched() -> None:
    """三个动作按钮**一个字没动**：收藏 / 入台 / 分享还是动作，不是选中。"""
    code = PLAZA_CARDS.read_text(encoding="utf-8")

    for name in ("onFavorite", "onAddToWorkbench", "onShare"):
        assert f"{name}={{" in code, f"{name} 不见了"


# ───────────────────────── 三、进 /combo，且参数名说的是实话


def test_the_entrance_goes_to_combo_with_the_selected_clusters() -> None:
    """acceptance①：进 `/combo` 并带上所选的卡。

    路由写成**字面量**而不是走帮手：帮手会让可达性尺子（`NAV-01`）
    看不见这条边——它读的是源码里的字面路径。
    """
    page = PLAZA_PAGE.read_text(encoding="utf-8")

    assert "/combo?clusters=" in page
    assert "window.location.assign(" in page


def test_the_parameter_is_named_clusters_because_that_is_what_it_is() -> None:
    """**参数名说实话**：广场选的是热点卡，`card_ids` 是证据卡（见模块 docstring）。

    叫成 `card_ids` 的话，下一个人会直接把它转发给端点，
    而那些 id 在 `evidence_cards` 里一条都查不到。
    """
    page = PLAZA_PAGE.read_text(encoding="utf-8")

    assert "card_ids=" not in page, "广场把热点 id 当成证据卡 id 传出去了"


def test_the_combo_screen_reads_many_clusters_and_keeps_the_single_path() -> None:
    """`/combo` 认 `?clusters=a,b,c`，**同时留着** `?cluster=` 那条老路。

    老路是 `NAV-05` 接的九条边之一，换掉它会把那条边弄断。
    """
    code = COMBO_PAGE.read_text(encoding="utf-8")

    assert 'params.get("clusters")' in code
    assert 'params.get("cluster")' in code
    assert "Promise.all(" in code, "没有逐簇取卡——跨簇选卡仍然做不到"


def test_the_combo_screen_still_never_invents_cards() -> None:
    """取不到的簇就是没有卡，**NEVER 编几张出来**（既有口径）。"""
    code = COMBO_PAGE.read_text(encoding="utf-8")

    assert ".catch(() => [])" in code, "某一簇取失败时没有如实退成空"
    assert "groups.flat()" in code


def test_cross_cluster_selection_is_now_actually_possible() -> None:
    """`ComboEntryView` 文件头写着「允许跨簇」——**在这之前那句话做不到**。

    那一屏一次只拿得到一个簇的卡（`?cluster=` 单值），
    所以「跨簇」是一句没有落点的话。本卡让它成立。
    """
    view = COMBO_VIEW.read_text(encoding="utf-8")
    page = COMBO_PAGE.read_text(encoding="utf-8")

    assert "允许跨簇" in view
    assert "wanted.map(" in page, "没有按多个簇分别取卡"


# ───────────────────────── 四、2~5 与空假设都归服务端


def test_the_plaza_does_not_re_judge_the_two_to_five_rule() -> None:
    """`2~5` 说的是**证据卡**张数，广场选的是热点——**两者不是同一个计数**。

    在广场判一次的话，用户选了 6 个热点会被拦下，
    而那 6 个热点底下可能一共只有 3 张证据卡。
    """
    # **先剥注释再扫**：上面那段解释「为什么不在广场判」的注释里
    # 正好点名了 `comboCountValid`，而一把读注释的尺子会把那句解释当成违规——
    # 红的是尺子自己。本轮第二次撞上这个形状（`SHELL-01` 是第一次）。
    code = _code_only(PLAZA_CARDS)

    assert "COMBO_MAX" not in code and "comboCountValid" not in code, (
        "广场重判了一次 2~5")


def _code_only(path: Path) -> str:
    """剥掉三种注释（`//` 行、块注释行、JSX 的 `{/* … */}`）之后的源码。"""
    import re

    text = re.sub(r"\{/\*.*?\*/\}", "", path.read_text(encoding="utf-8"),
                  flags=re.DOTALL)
    return NEWLINE.join(
        line for line in text.splitlines()
        if not line.lstrip().startswith(("//", "*", "/*"))
    )


def test_the_empty_hypothesis_copy_is_still_the_server_word() -> None:
    """acceptance③：空假设由服务端判（`EMPTY_HYPOTHESIS`），
    **前端一句拒绝话都不写**。

    写了就要挑一句，而两条端点对空假设的答复并不是同一句
    （`docs/blocked/EMPTY-HYPOTHESIS-TWO-CODES.md`）。
    """
    code = COMBO_PAGE.read_text(encoding="utf-8")

    assert "outcome.message" in code, "服务端的话没有原样带出来"
    assert "EMPTY_HYPOTHESIS" not in code, "前端自己写了一句空假设的拒绝话"


# ───────────────────────── 五、选中态在切区/切页时 NEVER 悄悄清空


def test_the_selection_survives_a_region_or_day_change() -> None:
    """acceptance⑤：**NEVER 悄悄清空用户已选的卡**。

    跨区挑热点凑一个假设是正常用法（组合本来就允许跨簇）。
    一换区就清空的话，用户每次回来都要重挑一遍，而屏上不会有任何解释。
    """
    page = PLAZA_PAGE.read_text(encoding="utf-8")

    # 取数那个 effect 里 NEVER 出现清空动作。
    effect = page.split("fetchPlazaHotScoped(")[0].split("useEffect(() => {")[-1]
    assert "setPicked([])" not in effect, "切区/切日时把已选的卡清空了"
    assert "setPicked([])" not in page, "有一处把选中态清空了——那一处要写明理由"


def test_the_selection_state_is_declared_where_it_survives_refetch() -> None:
    """选中态住在**屏**上，不在取数结果里——所以重新取数不会带走它。"""
    page = PLAZA_PAGE.read_text(encoding="utf-8")

    assert "const [picked, setPicked] = useState<string[]>([]);" in page
    assert "selectedClusterIds={picked}" in page


def test_the_counter_makes_the_surviving_selection_visible() -> None:
    """「选了的还在」这件事**屏上看得见**——计数条恒显示已选张数。

    存着而不显示的话，用户切回来看到一屏没勾的卡，
    会以为选中态没了，然后重挑一遍。
    """
    cards = PLAZA_CARDS.read_text(encoding="utf-8")

    assert 'data-selected-count={selected.length}' in cards


# ───────────────────────── 六、文案两种语言都有


def test_the_new_copy_is_keyed_in_both_languages() -> None:
    zh = json.loads((MESSAGES / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((MESSAGES / "en.json").read_text(encoding="utf-8"))

    for key in ("plaza.combo.selected", "plaza.combo.build",
                "plaza.combo.need_two", "plaza.combo.pick"):
        assert key in zh, f"zh 缺 {key}"
        assert key in en, f"en 缺 {key}"


def test_no_hardcoded_chinese_in_the_new_plaza_pieces() -> None:
    """顶栏与广场是每天都看得到的地方，硬编一句中文等于让英文用户永远看见它。"""
    import re

    jsx_comment = re.compile(r"\{/\*.*?\*/\}", re.DOTALL)
    literal = re.compile(r'"[^"\n]*[一-鿿][^"\n]*"')
    text = jsx_comment.sub("", PLAZA_CARDS.read_text(encoding="utf-8"))
    body = "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith(("//", "*", "/*"))
    )

    assert literal.findall(body) == []
