# 03 · Agent 层：如何"零 API Key"调用 Claude Code / Codex

Asterism 不直接调用任何模型 API，而是把用户本机**已登录**的 `claude`（Claude Code CLI）或 `codex`（OpenAI Codex CLI）当作子进程调用——这是它"不需要单独付费 API Key"的原因。这一层是全仓库分层最清晰的一块，也是新增 provider（比如未来接 ACP）时该改的地方。

## 分层（从下往上）

| 文件                                                                         | 职责                                                                                                                                                                                               |
| ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [src/lib/agentTypes.ts](../../src/lib/agentTypes.ts)                         | 定义 `AgentProvider = "claude" \| "codex"` 联合类型和静态元数据                                                                                                                                    |
| [src/lib/agentProviders.ts](../../src/lib/agentProviders.ts)                 | `AGENT_CLI_PROVIDERS`——每个 provider 一份 `AgentCliProviderDefinition`：`buildTextArgs`/`buildFileArgs`/`buildChatArgs`、命令路径解析、环境变量清理（[:155-233](../../src/lib/agentProviders.ts)） |
| [src/lib/agent.ts](../../src/lib/agent.ts)                                   | 面向业务代码的统一接口：`callAgent`、`callAgentWithFileAccess`、`getAgentChatCommand`、`getAgentStatus(es)`（[:148-225, 231-271](../../src/lib/agent.ts)）                                         |
| [src/lib/claude.ts](../../src/lib/claude.ts)                                 | 业务侧唯一调用 `callAgent`/`callAgentWithFileAccess` 的地方——所有"分析内容"的逻辑都经过这里，不直接碰 agent.ts                                                                                     |
| [src/lib/codexAppServerProtocol.ts](../../src/lib/codexAppServerProtocol.ts) | Codex `app-server --stdio` 的协议状态机（仅用于交互式 chat）                                                                                                                                       |
| [src/lib/agentChatEvents.ts](../../src/lib/agentChatEvents.ts)               | 把 Claude / Codex 两种不同格式的流式事件，归一成一个统一的 `AgentStreamEvent` 类型给 UI 用                                                                                                         |

**规则**（也是 AGENTS.md 明确写的）：业务代码永远调用 `agent.ts` 提供的抽象接口，不直接 `spawn("claude", ...)` 或 `spawn("codex", ...)`。provider 专属的拼参数逻辑全部封在 `agentProviders.ts` 里。

## Provider 是怎么选出来的

`getConfiguredAgentProvider()`（[agent.ts:34-41](../../src/lib/agent.ts)）：优先读环境变量 `SECONDBRAIN_AGENT_PROVIDER`，否则读 `config.json` 里的 `agentProvider` 字段（`loadUserConfig()`），默认 `"claude"`。用户在 `AgentModeGate`/`SettingsModal` 里切换 provider，最终就是改这个配置项。

## 两种 CLI 具体怎么被"拼命令行"调用

- **Claude Code**：`claude --print --output-format text|stream-json ...`，prompt 通过 stdin 传入（[agentProviders.ts:161-181](../../src/lib/agentProviders.ts)）。
- **Codex 一次性分析**（文本/文件分析场景，比如 capture pipeline 里的 digest/critique）：`codex exec --sandbox read-only --ephemeral ... -`（[agentProviders.ts:192-224](../../src/lib/agentProviders.ts)）。
- **Codex 交互式 chat**：**不是** `codex exec`，而是 `codex app-server --stdio`（`chatTransport: "codex-app-server"`，[agentProviders.ts:225-228](../../src/lib/agentProviders.ts)）——这是 AGENTS.md 里特别强调的一点，因为 `codex exec --json` 只在最后吐出一条 assistant 答案，不适合做流式 UI chat。

## 流式聊天怎么传回前端

`/api/chat/route.ts` spawn 出 chat 命令，逐行读 stdout 的 NDJSON：

- **Claude**：直接解析 `stream-json` 格式的 `content_block_delta` / `assistant` / `user` 工具调用事件（[chat/route.ts:248-300](../../src/app/api/chat/route.ts)）。
- **Codex**：委托给 `createCodexAppServerProtocol()`（[codexAppServerProtocol.ts](../../src/lib/codexAppServerProtocol.ts)），完整实现了 AGENTS.md 提到的生命周期：
  1. 发 `initialize` → 收到 `initialized`
  2. 发 `thread/start`（[:65-92](../../src/lib/codexAppServerProtocol.ts)），从响应里取出 `result.thread.id`
  3. 发 `turn/start`（[:23-27, 40-61, 102-108](../../src/lib/codexAppServerProtocol.ts)）
  4. 收到 `turn/completed` / `turn/failed` 结束（[:111-114](../../src/lib/codexAppServerProtocol.ts)）

两种 provider 各自的原始事件，最终都被 `parseCodexEvent`（[agentChatEvents.ts:1-7, 94-99](../../src/lib/agentChatEvents.ts)）归一处理，特别处理了 `item/agentMessage/delta` 增量消息，以及工具调用（`exec_command` begin/end）事件——这样上层 UI 组件（`CoLearningPanel.tsx`）不需要关心底层用的是哪个 provider。

> 注意：`/api/history/stream` 名字容易和 chat streaming 搞混，但它其实是一个不相关的功能——"Brain Waves" 话题演变可视化的缓存端点，背后是 `extractTopicStream()`。

## 下一步

看 [04-frontend-structure.md](04-frontend-structure.md)，了解 `CoLearningPanel` 等 UI 组件怎么消费这些流式事件、以及整个三栏式界面是怎么拼起来的。
