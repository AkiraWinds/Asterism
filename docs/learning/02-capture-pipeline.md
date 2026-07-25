# 02 · 捕获 → 分析 全流程（最核心的一条主线）

这一篇追踪：用户粘贴一个链接（或 Chrome 插件一键抓取）之后，代码里到底发生了什么，直到这条内容变成一张可读的 Triage Card。

## 入口：`POST /api/capture`

[src/app/api/capture/route.ts:19-109](../../src/app/api/capture/route.ts)

这是一个**两阶段**设计：

1. 校验输入（url / text / html / file），调用 `createPendingSource()`（[src/lib/storage.ts:485](../../src/lib/storage.ts)）——**立即**写入不可变的 `meta.json`，拿到一个 `id`。
2. **不等待**分析完成，直接把 pending 状态的 source 返回给前端（用户马上能在 UI 里看到"处理中"的卡片），然后在后台触发 `processSourceInBackground()`（文件/PDF 走 `processFileInBackground()` / `handlePdfUrl`，同一文件里的另外几个分支，[route.ts:94, 162, 264](../../src/app/api/capture/route.ts)）。

这解释了为什么 UI 上新捕获的条目会先显示"处理中"再变成"就绪"——**没有 loading spinner 阻塞请求**，而是轮询文件是否出现（前端轮询逻辑在 `useSourceActions.ts`，见 [04 篇](04-frontend-structure.md)）。

## 三步流水线：`src/lib/capturePipeline.ts`

真正的处理逻辑在这里，分三步、层层降级（后面的步骤失败不影响前面已经落地的结果）：

### 第一步：Extract（提取正文）

[capturePipeline.ts:29-50](../../src/lib/capturePipeline.ts)

- HTML 输入 → `extractFromHtml`
- URL 输入 → `extractFromUrl`（服务器端 fetch，用 `@mozilla/readability` 抽正文）
- 纯文本输入 → `formatTextContent`（用 AI 把粗文本格式化成 Markdown，[claude.ts:98](../../src/lib/claude.ts)）

三种情况都在 [src/lib/content.ts](../../src/lib/content.ts) 里实现。结果通过 `saveSourceContent()` 写入 `content.md`（[storage.ts:632-648](../../src/lib/storage.ts)）。

### 第二步：Analyze（AI 分析）

[capturePipeline.ts:56-62](../../src/lib/capturePipeline.ts)

`analyzeContent()`（[claude.ts:134-183](../../src/lib/claude.ts)）：

1. 用 `promptAnalyzeContent`（[src/lib/prompts.ts:69](../../src/lib/prompts.ts)）拼出 prompt——**所有 prompt 字符串都集中在 `prompts.ts`，不会散落在业务代码里**。
2. 通过 `callAgent()`（见 [03-agent-layer.md](03-agent-layer.md)）把 prompt 丢给本地 Claude Code / Codex CLI。
3. 把返回的 JSON 解析成 `Analysis` 类型（triage 打分 + digest + critique）。

结果通过 `saveSourceAnalysis()` 写入 `analysis.json`，**同时重新生成 `README.md`（Triage Card）**（[storage.ts:655-693](../../src/lib/storage.ts)）。

### 第三步：Connections（跨源关联，独立、可失败）

[capturePipeline.ts:64, 127-292](../../src/lib/capturePipeline.ts)

1. `listSourcesForConnections` 拉最近的库条目。
2. `findRelatedSources`（[claude.ts:208](../../src/lib/claude.ts)）粗筛。
3. `analyzeConnections`（[claude.ts:242](../../src/lib/claude.ts)）细判——判断新条目和旧条目是 `redundant` / `contradicts` / `related`（类型定义见 [types.ts:119](../../src/lib/types.ts)）。
4. `smartMergeIntoRelatedSources` → `mergeSourceIntoConnections`（[claude.ts:307](../../src/lib/claude.ts)）——**反向改写**被关联到的*其他*旧条目的 `analysis.json`，把这条新连接也补记进去。

这一步失败**绝不会**让整条捕获流程标记为失败（[capturePipeline.ts:143-150](../../src/lib/capturePipeline.ts)）——Triage Card 该显示还是显示，只是暂时没有"关联"信息。

## 用一张图串起来

```
用户粘贴链接 / 插件抓取
        │
        ▼
POST /api/capture ──(立即)──► createPendingSource() ──► meta.json 落地，返回 pending source
        │
        ▼ (后台，不阻塞响应)
capturePipeline.ts
  ① Extract  → content.ts        → saveSourceContent()  → content.md
  ② Analyze  → claude.ts + prompts.ts → saveSourceAnalysis() → analysis.json + README.md(Triage Card)
  ③ Connections → claude.ts        → 更新本条目 + 反向更新旧条目的 analysis.json（失败不影响①②）
```

## 相关测试

[tests/content.test.ts](../../tests/content.test.ts) 覆盖第一步的提取逻辑；[tests/storage-summaries.test.ts](../../tests/storage-summaries.test.ts) 覆盖 storage 层的读写。

## 下一步

想知道 `callAgent()` 到底是怎么把 prompt 变成一次真实的 `claude` / `codex` 子进程调用的，看 [03-agent-layer.md](03-agent-layer.md)。
