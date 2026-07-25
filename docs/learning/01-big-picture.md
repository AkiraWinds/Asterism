# 01 · 整体架构与设计原则

## 这是什么

Asterism（代码里包名仍叫 `secondbrain`）是一个 **local-first 的个人知识管理应用**：捕获文章/链接/文本/PDF → AI 做 Digestion（帮你理解）+ Critique（帮你批判性评估）→ 存成本地文件 → 在三栏式 UI 里阅读、和 agent 对话、整理进 Notebook。

核心理念（详见 [AGENTS.md](../../AGENTS.md) 开头）：AI 内容爆炸式增长，但人的注意力是线性的——所以让 AI 做信息分诊和组织，人只负责判断和决策。

## 技术栈一览

| 层       | 技术                                                                                                       |
| -------- | ---------------------------------------------------------------------------------------------------------- |
| Web 框架 | Next.js 16（App Router）+ React 19 + TypeScript                                                            |
| 样式     | Tailwind CSS 4                                                                                             |
| 数据校验 | Zod（[src/lib/schemas.ts](../../src/lib/schemas.ts)）                                                      |
| 可视化   | d3-force（Knowledge Galaxy）、d3-cloud（Concept Constellation）、mermaid                                   |
| AI 后端  | **没有独立模型 API**——通过子进程调用本地已登录的 `claude`（Claude Code CLI）或 `codex`（OpenAI Codex CLI） |
| 抓取     | Chrome MV3 插件（`extension/`），负责拿到"已渲染、已登录"的 DOM                                            |
| 桌面壳   | Tauri 2（`src-tauri/`），本质是给 Next.js dev server 套一个原生窗口                                        |
| 测试     | Vitest（`tests/`）                                                                                         |

一句话记住调用关系：**浏览器/插件 → Next.js API routes → `src/lib/*` 业务逻辑 → 本地文件系统 + agent CLI 子进程**。没有 Postgres、没有 Redis、没有远程后端。

## 目录树速览

```
src/
  app/            Next.js App Router：page.tsx 是唯一真正的页面，api/ 下是所有后端路由
  components/     React 组件（三栏式 UI 的各个模块）
  hooks/          业务状态封装（选中条目、库集合、拖拽、feed 等）
  lib/            核心业务逻辑：agent 调用、storage、capture pipeline、prompts、schemas
src-tauri/        Tauri 桌面壳（Rust，很薄，见 06 篇）
extension/        Chrome MV3 插件（一键抓取）
sample_data/      首次运行自动种入 user_data/ 的示例库（不会覆盖已有用户数据）
tests/            Vitest 单测，文件名基本对应 src/lib/ 里的模块
scripts/          一次性迁移脚本（meta.json 格式升级等）
docs/             文档：ONBOARDING.md（跑起来的10分钟指南）、learning/（本目录）、updates/（变更记录）
```

`user_data/`（运行时生成，默认 `./user_data`，git-ignored）才是真正的数据——这是全仓库最重要的一条设计原则，展开如下。

## 最重要的原则：文件系统即数据库，Original vs Derived

每一条"库条目"是一个目录，里面固定几个文件：

```
library/{id}/
  meta.json        [ORIGINAL·不可变] 抓取时刻的元数据，写一次，永不修改
  original.html    [ORIGINAL·不可变] 抓取时的原始 HTML/文本，永不覆盖
  content.md       [DERIVED·可重新生成] 处理后的正文（可编辑）
  analysis.json    [DERIVED·可重新生成] AI 分析结果（可编辑）
  README.md        [DERIVED·可重新生成] 人类可读的 Triage Card
  error.txt        仅在处理失败时存在
```

**处理状态由文件是否存在推断，不单独存储状态字段**：只有 `meta.json` = 处理中；三个 derived 文件都有 = Ready；有 `error.txt` = 失败。

为什么这条原则重要（见 [AGENTS.md:130](../../AGENTS.md)）：Chrome 插件抓到的是**浏览器里已登录、已跑完 JS 的真实 DOM**（比如 Twitter/X 的推文），服务器端的 `fetch()` 根本拿不到这份内容（没有登录态、不会执行 JS）。如果"重新分析"时不小心用服务器抓取的结果覆盖了 `original.html`，这份数据就永久丢失了、无法复现。所以：

- **Reanalyze 操作**只能读 `meta.json` + `original.*` → 重新生成 `content.md`/`analysis.json` → **绝不**碰 `meta.json`/`original.*`。
- 这条约束在代码里的落地位置见 [05-storage-and-data.md](05-storage-and-data.md)。

## 下一步

先看 [02-capture-pipeline.md](02-capture-pipeline.md)——从"粘贴一个链接"到"变成一条分析完的库条目"，这是最值得先吃透的一条主线，后面几篇（agent 层、storage 层）都是在给这条主线的各个环节做展开。
