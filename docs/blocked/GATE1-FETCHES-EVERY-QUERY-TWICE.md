# Gate① 每条 query 都去取两遍

**状态** open · 2026-08-11 · `GATE1-REAL`

## 实测（`DEC-057` 那一跑的留痕）

28 发真实请求，**只有 13 个不同的 URL**——每个 URL 打了 2 遍（有一个 4 遍）。

```
×4  export.arxiv.org/api/query?search_query=all:brain-computer+interface&max_results=3
×2  export.arxiv.org/api/query?search_query=all:BCI&max_results=3
×2  api.github.com/search/repositories?q=brain-computer+interface&per_page=3
…
```

## 为什么

`flint/jobs/gate1.py` 在**两处**各调一次 searcher：

- `:429` `for doc in deps.searcher(query)`
- `:441` `docs_by_query[query_id_for(query)] = deps.searcher(query)`

两处要的是同一批文档，而 searcher **每次都真的去打网络**（它自己不缓存）。

## 代价

**一次分析的网络开销是它需要的两倍。** 今天看不出来是因为额度够；
而 GitHub 免登录搜索每分钟只有 10 发（见
`docs/blocked/GITHUB-UNAUTH-SEARCH-IS-10-PER-MINUTE.md`），
一次稍大的分析会因为这一倍白白撞上限。

## 没在本卡改

`GATE1-REAL` 的卡面是「跑通一次并证明出口」，不含 gate1 的取数结构。
改它要决定「谁持有那批 docs」——那是 `retrieve` 那一步的形状问题。

**NEVER 顺手加一层缓存了事**：缓存会把「取了两次」变成「看起来取了一次」，
而两处各自要什么这件事仍然没人说得清。
