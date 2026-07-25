# 新手学习指南（Learning Docs）

> 面向「第一次打开这个仓库」的读者。目标不是重复 [README.md](../../README.md)（卖点/使用说明）或 [AGENTS.md](../../AGENTS.md)（给 AI agent 看的项目规范），
> 而是把**功能 → 代码位置**这条线画清楚，让你能在半小时内建立起「这个仓库长什么样、改一个功能该去哪找代码」的心智模型。

## 怎么用这份指南

按顺序读，每一篇都会指向具体的 `file:line`，建议边读边打开对应文件：

1. **[01-big-picture.md](01-big-picture.md)** — 这是什么项目、整体技术栈、目录树速览、最重要的一条设计原则（immutable vs derived 文件）。
2. **[02-capture-pipeline.md](02-capture-pipeline.md)** — 核心主线：一个链接是怎么变成一条「已分析」的库条目的。全仓库最值得先搞懂的一条流程。
3. **[03-agent-layer.md](03-agent-layer.md)** — Claude Code / Codex CLI 是怎么被当作"没有 API Key 的模型后端"调用的。
4. **[04-frontend-structure.md](04-frontend-structure.md)** — 三栏式 UI 是怎么拼出来的，state 怎么流动。
5. **[05-storage-and-data.md](05-storage-and-data.md)** — 文件系统即数据库：`storage.ts` 和数据结构（schemas/types）。
6. **[06-extension-and-desktop.md](06-extension-and-desktop.md)** — Chrome 插件抓取、Tauri 桌面壳。
7. **[07-gotchas-and-drift.md](07-gotchas-and-drift.md)** — AGENTS.md 里写了但代码里没实现（或已被替代）的地方，避免被文档带偏。

## 30 秒总览

Asterism（原 fork 自 SecondBrain）是一个 **local-first 的个人知识库**：

- 你粘贴一个链接/文本/PDF，或者用 Chrome 插件一键抓取 → 系统把内容存成本地文件 → 调用你本地已登录的 **Claude Code 或 Codex CLI**（不是调用付费 API）做 Digestion / Critique 分析、打分 → 你在三栏式界面里读、和 agent 对话、把内容组织进 Notebook。
- **没有后端数据库**，`user_data/` 目录下的文件本身就是唯一数据源（single source of truth）；Web UI 只是这些文件的一个视图。
- 技术栈：Next.js (App Router) + TypeScript + Tailwind，Node 侧做文件 I/O 和 agent 子进程调用，外加一个 Chrome MV3 插件和一个薄的 Tauri 桌面壳。

带着这张图去读后面几篇，会容易得多。
