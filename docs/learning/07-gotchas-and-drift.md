# 07 · 文档 vs 代码的落差（读 AGENTS.md 时留意）

[AGENTS.md](../../AGENTS.md) 是这个仓库的"канон"项目规范，写得很早、也很有前瞻性，但有几处描述的是**设计意图**而非**当前代码现状**。新人容易被这些地方带偏，列在这里方便对照：

## 1. "Claims" 功能没有实现

AGENTS.md 的「Claim-Level Granularity」一节（描述"claim"是可独立评估真假的陈述，要做跨源比对）在代码里**完全没有落地**——`grep -rn "claim" src` 零匹配。

现状：这个想法被 source 级别的 **Connections** 机制部分取代了——`analyzeConnections`/`Connection` 类型（`redundant`/`contradicts`/`related`，[src/lib/types.ts:119](../../src/lib/types.ts)）做的是"这条新捕获和哪些旧条目重复/矛盾/相关"，粒度是整篇文章，不是逐条陈述。

**如果有人让你"实现 Claims 功能"**：先确认是要做真正的逐条 claim 提取+比对（全新功能），还是其实说的是已有的 Connections 机制。

## 2. UI 上没有第三个"Claims"标签

对应上一条——[EntryView.tsx:151](../../src/components/EntryView.tsx) 的 `activeTab` 类型只有 `"digest" | "critique"` 两种，[types.ts:140-149](../../src/lib/types.ts) 的 `Analysis` 类型也没有 `claims` 字段。AGENTS.md「UI Structure → Source View」提到的 `Digestion | Critique | Claims` 三个 tab，目前实际只有前两个。

## 3. 库的"Tree view / Flat view 切换"没有实现

AGENTS.md 在「Organization Rules」和「UI Structure」两处都提到"UI 选项：树状视图 / 扁平视图切换"。但代码里 [SectionTree.tsx](../../src/components/SectionTree.tsx)/[TreeItem.tsx](../../src/components/TreeItem.tsx) **始终**渲染 `buildTree()`（[src/lib/tree.ts:14-96](../../src/lib/tree.ts)）产出的层级树，没有找到任何切换到"扁平列表"的开关或状态。

## 4. 一些容易搞混的相似命名

- `/api/history/stream`（Brain Waves 话题演变可视化的缓存端点）和 chat 的流式响应（`/api/chat`）名字都带 "stream"，但完全是两回事——前者跟 agent 对话无关。
- `src/app/dashboard/page.tsx` 看起来像一个独立页面，实际上只是重新导出 `src/app/page.tsx`——真正的 UI 逻辑全在后者。

## 为什么整理这一篇

不是说 AGENTS.md 写错了——它记录的是产品设计意图和历史决策（很多"Lessons Learned"条目非常有价值，值得精读）。但作为新人写代码时，**以 grep/读代码为准，AGENTS.md 为辅**——尤其是「MVP Scope」「UI Structure」这类描述功能范围的章节，最容易和实现进度产生落差。如果你在开发中确认了新的落差，按 AGENTS.md 自己的规则（「Continuous Learning」一节）把发现更新回 AGENTS.md，也欢迎回来更新这一篇。
