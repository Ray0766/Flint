# Flint 设计交接包

放入仓库 design/ 目录。用浏览器直接打开 .dc.html 即可预览（需同目录 support.js）。

## 文件
- Flint v4.dc.html — 主壳：热点广场（含 Combo 组合栏）/ 判定台（主题 / Gate① / 作业 SSE / 受众选择 / vibe_pack 查看器）/ 设计台入口；CSS 变量主题（浅 / 深）定义在 body 上
- studio.dc.html — 计划书工作台（素材 / 模板 / 检查点 + 对话 + 块级画布），即「设计台」
- support.js — 预览运行时，仅供本地打开设计稿，不进生产代码

注意：Flint v4.dc.html 内 `<dc-import name="设计台">` 指向的文件本包内更名为 studio.dc.html；如需在包内联动预览，把 studio.dc.html 复制一份命名为 设计台.dc.html 即可。

## 给执行 agent 的规则摘要
- 主题令牌是唯一颜色来源：--bg / --panel / --panel2 / --ink / --sub / --line / --accent(+soft) / --ok / --bad / --warn / --unk / --shadow + body[data-theme="dark"]
- 交互语义不可变更：组合 = 2~5 张证据卡 + 关联假设必填；audience 强制单选、无默认、不选不能提交；vibe_pack 只读、不进 tiptap 编辑器
- 字段名以 contracts/models.py 为准，设计稿仅视图层
