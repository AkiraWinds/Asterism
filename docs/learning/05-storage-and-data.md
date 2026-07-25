# 05 · Storage 层与数据结构

## `src/lib/storage.ts`（2613 行）——全仓库最大的文件，但结构很规整

它就是这个应用的"数据库驱动"，所有文件系统读写都封装在这里，其他代码不直接碰 `fs`。按 `^export (async )?function` 分组，大致是这些板块：

| 板块            | 代表函数                                                                                                                                                                             |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 配置/根目录     | `getRootPathSource`、`loadUserConfig`/`saveUserConfig`、`ensureUserDataInitialized`                                                                                                  |
| **Source CRUD** | `createPendingSource:485`、`saveSourceContent:632`、`saveSourceAnalysis:655`、`setSourceConnections:700`、`completeSource:760`、`failSource:839`、`saveSource:858`、`loadSource:975` |
| 列表/检索       | `listSources:1136`、`listSourceSummaries:1157`、`listSourcesForConnections:1310`                                                                                                     |
| 文件夹树        | `listFolders`、`createFolder:1803`、`deleteFolder:1828`、`renameFolder:1865`、`moveEntry:1681`、`deleteEntry:1716`、`findEntryPath:1612`                                             |
| Profile 文档    | `loadProfileDoc`/`saveProfileDoc:1932-1954`（对应 `USER.md`/`MEMORY.md`）                                                                                                            |
| Feed 缓存/历史  | `loadFeedCache`、`saveFeedCache`、`listFeedSnapshots`、`markFeedItemsSeen`、`starBriefingItem`（约 [:1958-2222](../../src/lib/storage.ts)）                                          |
| 对话记录        | `listConversations`/`loadConversation`/`saveConversation:2236-2306`                                                                                                                  |
| Notebook        | 2306 行之后                                                                                                                                                                          |

（行号均见 [src/lib/storage.ts](../../src/lib/storage.ts)，具体函数可以直接搜函数名定位。）

## Immutable vs Derived 边界在代码里怎么体现

这是 [01-big-picture.md](01-big-picture.md) 提到的核心原则，落地位置：

- `meta.json`/`original.*` 只在创建时写一次（`createPendingSource:485-511`），之后只有 schema 版本迁移时会用 `rewriteJson`（[storage.ts:155-199](../../src/lib/storage.ts)）原地改写——代码里明确写了注释说明"meta.json immutability is preserved"。
- `content.md`/`analysis.json`/`README.md` 是可重新生成的——每一条保存路径（`saveSourceContent:645`、`saveSourceAnalysis:675-693`、`saveSource:898-923`）都只覆盖这三个文件，从不碰 `meta.json`/`original.*`。

**如果你要加一个"重新分析"或"批量迁移"相关的功能，先确认你的写入路径只碰这三个 derived 文件。**

## Schema 与类型：`schemas.ts` vs `types.ts`

- [src/lib/schemas.ts](../../src/lib/schemas.ts)：Zod **运行时**校验器。`AnalysisSchema` 定义 `analysis.json` 的结构（triage/digest/critique/connections），用 `.prefault({})`/`.catch()` 对 AI 输出的畸形 JSON 做兜底容错；`OriginalDataSchema` 用 passthrough 保证向前兼容。
- [src/lib/types.ts](../../src/lib/types.ts)（316 行）：对应的 **TypeScript 类型**，加上其余所有跨 API/UI 层用到的类型——`SourceMeta`、`FeedItem`、`AgentConversation`、`NotebookDocument`、`HistoryEvent` 等。

一般规则：改 `analysis.json` 之类持久化数据的结构，两个文件都要同步改（schema 负责运行时校验/容错，types 负责编译期类型）。

## Feed / "For You"：数据从哪来

`generateFeed()`（[src/app/api/feed/route.ts:136-296](../../src/app/api/feed/route.ts)）：

1. Radar 话题来自 `config.feedInterests`（用户在 `SettingsModal.tsx` 手动设置，或者 `POST /api/feed/interests` → `extractUserInterests()`，[claude.ts:387](../../src/lib/claude.ts)，从库里自动提取）。
2. 拉 RSS（始终启用）+ 可选 Brave Search（仅当设了 `BRAVE_SEARCH_API_KEY`），走 `searchNews()`（[src/lib/search.ts:165-230](../../src/lib/search.ts)，并发抓取 RSS + 按 query/source 调用 Brave）。
3. 用 `loadFeedHistory` 去重已读过的 URL。
4. 用 starred/dismissed highlights 和「已学到/已了解」的概念，在配置的时间窗口内构建 `interactionContext`（[route.ts:190-234](../../src/app/api/feed/route.ts)）。
5. `filterFeedItems()` + `generateBriefing()`（[claude.ts:501, 596](../../src/lib/claude.ts)）用库里已有内容摘要 + 兴趣 + 交互信号做排序/筛选。
6. 结果缓存进 `saveFeedCache`，前端由 [useFeed.ts](../../src/hooks/useFeed.ts) 消费（本地存储管理 dismiss 状态，`/api/feed/star`/`/api/feed/seen` 管理已读/星标）。

## Claims 功能的现状（重要，避免踩坑）

`grep -rn "claim" src` **没有任何匹配**——AGENTS.md「Claim-Level Granularity」那一节描述的逐条 claim 提取/比对功能**目前代码里并未实现**。现有最接近的东西是：

- `critique.potentialIssues`/`needsVerification` 字段（[schemas.ts:55-60](../../src/lib/schemas.ts)，[claude.ts:175-180](../../src/lib/claude.ts)）
- Source 级别的 `Connection`/`analyzeConnections` 机制（`redundant`/`contradicts`/`related`，[types.ts:119](../../src/lib/types.ts)）——做的是**源与源**之间的粗粒度比对，不是逐条 claim。

详见 [07-gotchas-and-drift.md](07-gotchas-and-drift.md)。

## 下一步

看 [06-extension-and-desktop.md](06-extension-and-desktop.md)，了解 Chrome 插件怎么把内容送到 `/api/capture`、以及 Tauri 桌面壳到底做了多少事。
