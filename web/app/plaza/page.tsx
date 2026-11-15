"use client";

import { useEffect, useState, type JSX } from "react";

import { API_BASE } from "../../lib/apiBase";
import { useScreenData } from "../../lib/useScreenData";
import { PlazaCards } from "../../components/plaza/PlazaCards";
import { RegionSwitch } from "../../components/region-switch/RegionSwitch";
import { Screen } from "../../components/shell/Screen";
import { fetchPlazaHot, fetchPlazaHotScoped, type PlazaCluster } from "../../lib/viewsClient";
import { DEFAULT_REGION } from "../../lib/regions";
import { FROZEN } from "../../lib/frozen";

/** CN-03：往回找多少天。34 天是 `fixtures/` 现有回放窗口的长度，
 *  再多给一周的余量——**NEVER 无上限地往回走**：库真的空着时，
 *  那会变成一个看不见尽头的请求串，而屏上什么都不说。 */
const DAY_LOOKBACK = 41;

/** 一天都问不到时的兜底。**它出现在屏上时 MUST 带着说明**（见解析 effect）。 */
const DAY_FALLBACK = "2026-07-04";
import { withUnassigned } from "../../lib/regions";
import { t } from "../../lib/i18n/t";

// UI-02 主链路第一屏：广场看热点。
//
// 风格来源：`前端设计/Flint 热点线索卡堆叠/CardStack.dc.html`（owner 2026-08-07 指定）。
// 呈现层是 `PlazaCards`（堆叠精选 + 网格全量，两处都渲染同一个 `HotspotCard`），
// 本屏只做取数与接线——**NEVER 为了视觉再写一个广场组件**：
// 两个广场会各自漂移，而它们渲染的是同一份数据。
//
// PLAZA-01 之前这里接的是 `PlazaView`：一个 `<ul><li>`，**全文件 0 个 className**，
// 于是拿不到设计系统任何样式——那就是 owner 看到的 4077px 项目符号列表的机械根因。
// 那个组件本卡**退役并删除**（全仓零引用后删），NEVER 留着两个广场。
//
// ## 「查看判定」入口为什么可能不可点（DEC-012）
//
// **这段话在 `DEC-044` 之后过期了，`WIRE-VERDICT` 改成实况。**
//
// 改前这里断言那条按热点取判定的端点**不存在**，并据此说对应关系只能由调用方持有。
// （那句话不在这里复述——一句变假的断言被原样引一遍，
//   下一个人扫过去读到的仍是那句假话。）
// `PERSIST-04` 按 `DEC-044` 建了那条端点、`cluster_verdicts` 就是那份真相——
// **那句话今天是假的**，留着它会让下一个人以为这条路还不能走
// （而读注释的判据在本批已经踩过六次，一句变假的注释比没有注释更贵）。
//
// 今天的实况：本屏的入口仍**只在 URL 带 `?verdictJob=` 时才带着它跳**——
// 广场这一层不去问判定（零计算，见下），
// 而分析屏没拿到那个参数时会自己去问 `/clusters/{id}/verdict`。
// 猜一个 job 去问那条禁令**一字未改**：分析屏是去问真相，不是去猜。
//
// 零计算：后端已按 total_heat 排好，本屏不排序、不筛选、不合成任何数值。
// 只声明本屏用得到的两个字段。取不到就是 `null`——
// **NEVER 编一份地区清单顶上**（LOC-01：清单只有一处真相）。
type LocaleForPlaza = {
  region?: string;
  lang?: string;
  options?: { region?: string[] };
};

export default function PlazaPage(): JSX.Element {
  const [clusters, setClusters] = useState<PlazaCluster[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [day, setDay] = useState("");
  // CN-03：这一天是**怎么定下来的**——屏上要说得出口。
  //   url      = 用户自己指定的
  //   resolved = 库里最新有数据的那一天
  //   fallback = 一天都没问到，落到兜底（**MUST 在屏上明说**）
  const [dayOrigin, setDayOrigin] =
    useState<"pending" | "url" | "resolved" | "fallback">("pending");
  const [verdictJob, setVerdictJob] = useState<string | null>(null);
  // REGION-10：当前区。**URL 是它的真相**——写进 query 之后，刷新停在同一个区，
  // 分享出去的链接也指向同一屏。只放在内存里的话，同事点开你的链接会看到另一个区
  // 的热点，而两人都以为在看同一屏。
  const [region, setRegion] = useState<string>(DEFAULT_REGION);
  // 版本范围由**服务端**给（`CURRENT_SCOPE` 一处真相），前端只搬运。
  const [scope, setScope] = useState<{ inScope?: boolean; liftsWhen?: string }>({});
  // ENTRY-04 / `DEC-049`：多选态。**切区 / 切日 NEVER 清空它**——
  // 用户跨区挑热点凑一个假设是正常用法（组合本来就允许跨簇），
  // 一换区就清空的话，他每次回来都要重挑一遍，而屏上不会有任何解释。
  // 计数条恒显示已选张数，所以「选了的还在」这件事屏上看得见。
  const [picked, setPicked] = useState<string[]>([]);
  // 地区清单与当前区**从 `GET /settings/locale` 取**（LOC-01 已把副本退役）——
  // NEVER 在广场再抄一份：两份清单会各自漂移，而它们说的是同一件事。
  const { state: locale } = useScreenData<LocaleForPlaza>("/settings/locale");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    // CN-03：**URL 带了就以 URL 为准**（`REGION-10` 同一条纪律：URL 是当前视图的真相）。
    // 没带时不再写死一个日期，去问库里最新有数据的那一天（见下面那个 effect）。
    const fromUrl = params.get("day");
    if (fromUrl) {
      setDay(fromUrl);
      setDayOrigin("url");
    }
    setVerdictJob(params.get("verdictJob"));
    // CN-02 / `DEC-045`：**默认区为 CN**。改前默认是空串（= 全部区），
    // 于是首屏混着 global 那 103 条一起显示，而本版做的是中国区。
    // URL 上带了 `region=` 时以它为准（`REGION-10`：URL 是当前区的真相），
    // **包括显式的空值**——那是用户明确要看全部，与「没带这个参数」是两件事，
    // NEVER 把他打回 CN。
    setRegion(params.has("region") ? (params.get("region") ?? "") : DEFAULT_REGION);
  }, []);

  // CN-03：**落在库里有数据的最新那一天**，不再写死 `2026-07-04`。
  //
  // ## 为什么是「往回走」而不是问一条端点
  //
  // 今天没有任何端点回「最新有数据的那一天」——`GET /plaza/hot` 必须带 `day`。
  // 加一条那样的端点要动 `flint/api/`，而那不在本卡 outputs 里。
  // 所以从今天往回一天一天问，**第一天问到东西就停**。
  //
  // 代价说清楚：库里最新数据离今天越远，首屏多发的请求就越多。
  // `CN-01` 得到 owner 点头、真实抓取跑起来之后，**今天就有数据**，这里恒是 1 次。
  // 想把它变成 1 次常量，就给 `/plaza/hot` 的响应加一格「最新有数据的那一天」——
  // 留给某张 outputs 含 `flint/api/` 的卡。
  //
  // ## 一天都问不到时**明说**
  //
  // 兜底那一天照旧渲染，但屏上带 `data-day-origin="fallback"` 与一句话——
  // **NEVER 让屏上安静地显示另一天的数据**：用户会把兜底那天的热点
  // 当成今天的热点去做判断。
  useEffect(() => {
    if (dayOrigin !== "pending") return;
    let live = true;
    void (async () => {
      const start = new Date();
      for (let back = 0; back <= DAY_LOOKBACK; back += 1) {
        if (!live) return;
        const probe = new Date(start);
        probe.setUTCDate(probe.getUTCDate() - back);
        const iso = probe.toISOString().slice(0, 10);
        try {
          const rows = await fetchPlazaHot(iso, { baseUrl: API_BASE });
          if (rows.length > 0) {
            if (!live) return;
            setDay(iso);
            setDayOrigin("resolved");
            return;
          }
        } catch {
          // 单独一天问不到就往前再问一天：一次网络抖动 NEVER 变成「库里没有数据」。
        }
      }
      if (!live) return;
      setDay(DAY_FALLBACK);
      setDayOrigin("fallback");
    })();
    return () => {
      live = false;
    };
  }, [dayOrigin]);

  // 取数只依赖 **day 与 region 两条**。把 `locale` 整个放进来的话，
  // 切语言会顺手把热点集合换一批——那正是 `PRINCIPLES#A3` 禁止的耦合
  // （语言与地区是两条正交的轴）。
  useEffect(() => {
    if (!day) return;
    let live = true;
    setClusters(null);          // 重新取数 → 回到骨架卡，NEVER 让旧集合停在屏上
    setFailed(false);
    fetchPlazaHotScoped(day, { baseUrl: API_BASE, region: region || undefined })
      .then((got) => {
        if (!live) return;
        setClusters(got.clusters);
        setScope({ inScope: got.regionInScope, liftsWhen: got.scopeLiftsWhen });
      })
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [day, region]);

  // 筛选面的完整选项 = 地区清单（唯一真相在 `/settings/locale`）+ 未归区。
  // 清单拿不到时 `withUnassigned` 回 `null` 原样传下去——**NEVER 只剩未归区一项**：
  // 那读起来像「只有这一个区可选」，是一句结论；真相是「这份清单没查到」。
  const filterRegions = withUnassigned(
    locale.kind === "ready" ? locale.data.options?.region : null,
  );

  const chooseRegion = (next: { region: string; lang: string }): void => {
    // `lang` 由组件原样带回，这里**不读它**：切区 NEVER 改语言（A3）。
    const params = new URLSearchParams(window.location.search);
    if (next.region) params.set("region", next.region);
    else params.delete("region");
    window.history.replaceState(null, "", `?${params.toString()}`);
    setRegion(next.region);
  };

  return (
    <Screen
      title={t("plaza.screen.title")}
      meta={day ? t("plaza.screen.meta", { day }) : ""}
    >
      {/* CN-03：这一天是怎么定下来的，屏上说得出口。 */}
      <p data-day-origin={dayOrigin} data-testid="plaza-day-origin">
        {dayOrigin === "fallback"
          ? t("plaza.day.fallback", { day })
          : dayOrigin === "pending"
            ? t("plaza.day.resolving")
            : t("plaza.day.showing", { day })}
      </p>
      {failed ? (
        <p className="job-failed" data-plaza-error>
          {t("plaza.screen.error")}
        </p>
      ) : (
        <>
          {/* REGION-10：地区筛选器。清单恒来自 `GET /settings/locale` 的
              `options.region`（LOC-01：一处真相）；拿不到时组件自己标未提供态，
              NEVER 渲染一个空下拉。
              **区名原样显示**：`global` 今天不是一个区，是 `ghtrend` 写死的常量
              （单据 REGION-08-GLOBAL-IS-A-SOURCE-CONSTANT-NOT-A-REGION）。
              映射成「全球」会让用户选完拿到只来自 GitHub Trending 的那一批。

              REGION-11 / DEC-040：**未归区是筛选面上的第十个选项**，由本屏追加
              （`withUnassigned`），NEVER 塞进 `options.region`——那是 locale 的
              地理词表，`PUT /settings/locale` 拿它校验用户偏好，
              塞进去等于允许把「未归区」存成一个人的常住地。 */}
          {/* NARROW-05: the nine regions are a `DEC-066` frozen item. The switch
              closes; a `region=` already in the URL still works (REGION-10). */}
          {FROZEN.regionsAndLanguages ? null : (
            <RegionSwitch
              region={region}
              regions={filterRegions}
              lang={locale.kind === "ready" ? (locale.data.lang ?? "") : ""}
              onChange={chooseRegion}
            />
          )}
          {/* PLAZA-03：四态由 PlazaCards 自己分。
              `clusters === null` 是**还在取**，它在那里变成骨架卡——
              改前这里是一行「正在读取当日热点」的文字，占不住卡片的位，
              数据落地那一刻整屏跳一次。 */}
          <PlazaCards
            clusters={clusters}
            region={region || (locale.kind === "ready" ? (locale.data.region ?? null) : null)}
            // 空结果时那句「换个区试试」列的是**筛选面**的其它选项，
            // 所以这里也带上未归区：它今天是库里最大的一批（104 条），
            // 从「其它去处」里漏掉它，等于把最可能有结果的那一项藏起来。
            // NARROW-05: with the switch closed, naming other regions would point at
            // a control that is not there, so the empty state lists none.
            regions={FROZEN.regionsAndLanguages ? [] : filterRegions}
            // CN-02：三态里的第一态由它决定
            //（本版暂无该区内容 / 该区当日无数据 / 读失败）。
            regionInScope={scope.inScope}
            scopeLiftsWhen={scope.liftsWhen ?? null}
            // ENTRY-04：多选 + 建组合入口。
            selectedClusterIds={picked}
            onToggleSelect={(clusterId) =>
              setPicked((prev) =>
                prev.includes(clusterId)
                  ? prev.filter((id) => id !== clusterId)
                  : [...prev, clusterId])
            }
            onBuildCombo={() =>
              // 路由写成字面量而不是走帮手：帮手会让可达性尺子（`NAV-01`）
              // 看不见这条边——它读的是源码里的字面路径。
              window.location.assign(
                `/combo?clusters=${picked.map(encodeURIComponent).join(",")}`)
            }
            // NAV-02：点卡片主体 → 这个热点的分析界面（DEC-042 ①）。
            // 改前这个入参一直空着——`PlazaCards` 早就有它，广场屏没往里传，
            // 于是点卡片什么都不会发生。**卡片主体是导航，三个按钮是动作**，
            // 而按钮的点击排除区在 `HotspotCardActions` 的容器上（HOTSPOT-02）。
            //
            // **NEVER 往这条 URL 上带 verdictJob**：本屏 URL 上那个 job 是
            // 调用方手上的一条判定（DEC-012），它不属于任何一张具体的卡——
            // 广场今天 154 张，它顶多是其中一张的。带过去等于替系统宣布
            // 「这个 job 就是这张卡的判定」，而这条对应关系没有持久化真相
            // （docs/blocked/HOTSPOT-03.md）。猜错时用户看到的是**另一个热点的判定**。
            //
            // 路由写成字面量而不是走一个 `route()` 帮手：帮手会让可达性尺子
            // （NAV-01）看不见这条边——它读的是源码里的字面路径。
            onSelectCluster={(clusterId) =>
              window.location.assign(`/clusters/${encodeURIComponent(clusterId)}`)
            }
          />
          <p className="data-row" data-gate-entry>
            <span className="data-row__label">{t("plaza.gate_entry.label")}</span>
            {verdictJob ? (
              <a className="data-row__value" data-gate-link href={`/gate/${verdictJob}`}>
                {t("plaza.gate_entry.open")}
              </a>
            ) : (
              <span className="data-row__value" data-gate-unjudged>
                {t("plaza.gate_entry.unjudged")}
              </span>
            )}
          </p>
        </>
      )}
    </Screen>
  );
}
