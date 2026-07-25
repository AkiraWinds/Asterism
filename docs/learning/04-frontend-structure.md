# 04 · 前端结构：三栏式 UI 是怎么拼出来的

## 路由：其实只有一个页面

- [src/app/dashboard/page.tsx:1-5](../../src/app/dashboard/page.tsx) 只有一行：`export { default } from "../page"`——`/dashboard` 和 `/` 渲染的是**同一个组件**，并没有独立实现。
- [src/app/page.tsx](../../src/app/page.tsx)（862 行）才是整个应用的真身：一个巨大的 client component，持有几乎所有顶层状态，根据条件渲染 `AgentModeGate` / `OpeningWorkspace` / 三栏工作区三者之一。到底显示 `Dashboard` 还是某个 `EntryView`（文章/文档），是由 URL query 参数（`navigateToSource`/`navigateToDashboard`，[page.tsx:295-301](../../src/app/page.tsx)）和 `entry.source`/`entry.document`/`profileDoc` 这几个 state 决定的——**不是**通过额外的路由。
- [src/app/layout.tsx:54-74](../../src/app/layout.tsx)：根布局。有个值得注意的细节——预水合的 `themeScript`（[:42-52](../../src/app/layout.tsx)）被故意插到 `<body>` 而不是 `<head>`（注释在 [:61-64](../../src/app/layout.tsx) 解释：浏览器扩展往 `<head>` 里注入内容会打乱 React 的 hydration 对比，之前踩过坑——即 AGENTS.md「Lessons Learned」提到的 extension-injection hydration 问题）。

## Agent Mode Gate：进入工作区前的强制关卡

`canEnterWorkspace = agentModeEnabled && selectedAgentStatus?.state === "ready"`（[page.tsx:150-151](../../src/app/page.tsx)）。没通过就渲染 [AgentModeGate.tsx:21-193](../../src/components/AgentModeGate.tsx)（[page.tsx:462-474](../../src/app/page.tsx)）——用户在这里选 Claude Code 还是 Codex CLI，看实时连接状态，只有 `state === "ready"` 时"Enable Agent Mode"按钮才会亮起（[:173](../../src/components/AgentModeGate.tsx)）。这就是 README 里说的"Agent Mode 是强制的，没有降级的、无 agent 的工作区"。

## 三栏布局怎么拼

三栏是在 `page.tsx` 里**内联组合**的（[page.tsx:527-800](../../src/app/page.tsx)），不是通过嵌套路由或专门的 Layout 组件：

```
Sidebar (左)  ── ResizeHandle ──  <main>EntryView / Dashboard</main>（中）  ── ResizeHandle ──  CoLearningPanel (右, page.tsx:795)
```

驱动这三栏的核心 hooks：

| Hook                                                                  | 职责                                                                                                                                                                                                                         |
| --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [useSelectedEntry.ts:13-77](../../src/hooks/useSelectedEntry.ts)      | 管理 `source`/`document` 互斥状态（选一个会清掉另一个，[:24-33](../../src/hooks/useSelectedEntry.ts)），`refresh()` 重新拉取当前选中项                                                                                       |
| [useEntryCollection.ts:38-382](../../src/hooks/useEntryCollection.ts) | 在 `page.tsx` 里**实例化两次**——一次给 `library`，一次给 `notebook`，各自驱动一份 `SectionConfig` 传给 `Sidebar`；管理 entries/folders/tree 节点/拖拽/文件夹增删（配置表见 [:23-36](../../src/hooks/useEntryCollection.ts)） |
| [useSourceActions.ts:15-320](../../src/hooks/useSourceActions.ts)     | 捕获输入框、轮询"处理中"的 source、reanalyze/reaction/rating 处理函数、导航辅助（`navigateToSource`/`navigateToDashboard`，[:295-301](../../src/hooks/useSourceActions.ts)），被 `Dashboard` 和 `EntryView` 共用             |

[EntryView.tsx](../../src/components/EntryView.tsx) 接收一个完全拍平（denormalized）的 `entry` 对象加一堆回调（`onSave`/`onToggleSaved`/`onReanalyze`/`onReaction`/`onRating`/`onRemoveHighlight` 等），这些回调在 `page.tsx:594-719` 针对三种情况（profile doc / notebook document / library source）内联构建。

[CoLearningPanel.tsx:276-304](../../src/components/CoLearningPanel.tsx) 接收 `sourcePath`/`sourceId`/`documentPath`/`documentId` 这些上下文 props，再加自己的对话/流式状态。「选中文本 → 变成 co-learning 上下文」这个交互（AGENTS.md 里提到的功能）靠一个自定义的 `colearning:addContext` window 事件 + `useCoLearning()` hook（[:1078-1094](../../src/app/page.tsx)）实现——避免了跨组件 prop drilling。

## 分析 Tab：Digestion / Critique

`activeTab` 状态类型是 `"digest" | "critique"`（[EntryView.tsx:151](../../src/components/EntryView.tsx)），渲染逻辑在 [:486-540](../../src/components/EntryView.tsx) 附近，分别展示 `analysis.digest.*`（summary/highlights/concepts）和 `analysis.critique.*`（hiddenAssumptions/potentialIssues/needsVerification）。

> **注意**：这里**没有**第三个"Claims"标签，`Analysis` 类型（[types.ts:140-149](../../src/lib/types.ts)）里也没有 `claims` 字段——AGENTS.md 里描述的"Claim-Level Granularity"功能目前是用 source 级别的 `connections` 机制（[types.ts:121-132](../../src/lib/types.ts)，在 `EntryView.tsx:456-475` 渲染）替代实现的，并不是逐条 claim 级别。详见 [07-gotchas-and-drift.md](07-gotchas-and-drift.md)。

## 库树（folder tree）与拖拽

- [src/lib/tree.ts:14-96](../../src/lib/tree.ts) 的 `buildTree()`：把扁平的 `items[]` + `folders: string[]` 转成嵌套 `TreeNode[]`——给每一段路径生成文件夹节点（[:24-50](../../src/lib/tree.ts)），把条目挂到对应文件夹（[:52-71](../../src/lib/tree.ts)），排序规则是"文件夹优先、然后按最新排序"（[:74-93](../../src/lib/tree.ts)）。
- 拖拽：[TreeItem.tsx:251-257](../../src/components/TreeItem.tsx) 让叶子条目 `draggable`，文件夹节点接收 `onDragOver`/`onDrop`（[:93-97](../../src/components/TreeItem.tsx)）；真正的移动逻辑在 [useEntryCollection.ts:280-303](../../src/hooks/useEntryCollection.ts) 的 `handleDrop()`，调用 `PATCH /api/entries/{id}/move`。

## 可视化组件

- **Knowledge Galaxy**（[KnowledgeGalaxy.tsx](../../src/components/KnowledgeGalaxy.tsx)）：拉 `/api/history/galaxy`（[:57](../../src/components/KnowledgeGalaxy.tsx)），用 `d3-force`（forceSimulation/forceLink/forceManyBody/forceCollide，[:106-113](../../src/components/KnowledgeGalaxy.tsx)）做物理布局，节点是 source，被拉向各自话题簇的中心。数据来自 [src/app/api/history/galaxy/route.ts:26-145](../../src/app/api/history/galaxy/route.ts)——读 `.cache/interest-stream.json` 里的话题分配（不存在且库里 ≥3 条时会现算，调用 `extractTopicStream()`），再读每条 source 的 `analysis.json` 里的 `triage.score` 和 `connections[]` 拼边。
- **Concept Constellation**（[ConceptConstellation.tsx](../../src/components/ConceptConstellation.tsx)）：拉 `/api/history/concepts`，用 `d3-cloud` 做词云布局。数据来自 [src/app/api/history/concepts/route.ts:37-78](../../src/app/api/history/concepts/route.ts)，按 `conceptCount` 缓存在 `.cache/concept-constellation.json`，缓存失效才调用 `analyzeConceptNetwork()` 重新聚类。

## 下一步

想知道这些页面读写的数据到底怎么落到文件系统上，看 [05-storage-and-data.md](05-storage-and-data.md)。
