# 06 · Chrome 插件与 Tauri 桌面壳

## Chrome 插件：为什么它能抓到服务器抓不到的内容

[extension/manifest.json](../../extension/manifest.json)：MV3。`content_scripts` 把 `content.js` 注入 `<all_urls>`（[:24-36](../../extension/manifest.json)），`twitter-autocapture.js` 只注入 twitter.com/x.com（[:37-49](../../extension/manifest.json)）；`background.js` 是 service worker；`host_permissions` 只限定 `http://localhost/*`。

抓取流程：

1. [content.js:121-164](../../extension/content.js) 的 `handleCapture()`——在 `waitForContent()`（[:106-119](../../extension/content.js)，轮询等 Twitter 的 `[data-testid="tweetText"]` 最多 3 秒出现）之后，直接读**当前已渲染、已登录的 DOM**：`document.documentElement.outerHTML` + 标题 + URL。然后把这些数据**发消息给 background worker**，而不是自己直接 fetch（[background.js:1-6](../../extension/background.js) / [content.js:135](../../extension/content.js) 的注释：这是为了绕开 CORS / Private Network Access 限制）。
2. [background.js:6-35](../../extension/background.js) 的 `getApiUrl()`/`probePort()`——扫描候选端口 `[3000, 3001, 3002, 3003, 41932]`，逐个打 `/api/config`，确认 `data.app === "secondbrain"` 才信任这个端口（防止本机其他服务占用同端口被误连），把找到的端口缓存进 `chrome.storage.local`。
3. [background.js:68-86](../../extension/background.js) 的 `captureFromContent()`——把 `{html, title, url}` POST 到 `${apiUrl}/api/capture`，由 [src/app/api/capture/route.ts:19-48](../../src/app/api/capture/route.ts) 接住，走 `processSourceInBackground`/`processFileInBackground`（见 [02-capture-pipeline.md](02-capture-pipeline.md)）。
4. [twitter-autocapture.js:1-89](../../extension/twitter-autocapture.js)——在捕获阶段（capture phase，[:9, 71](../../extension/twitter-autocapture.js) 里的 `true` 参数）监听书签按钮点击，用一个上限 500 条的 `sb-captured-tweets` 列表去重（[:46](../../extension/twitter-autocapture.js)），自动触发同一条 `capture` 消息——这就是"点赞/收藏推文自动捕获"功能的实现。

**为什么这条路径不可替代**（对应 [01-big-picture.md](01-big-picture.md) 的 immutable 原则）：插件拿到的是浏览器里**已经登录、已经跑完 JS**的真实 DOM（`content.js:131` 的 `document.documentElement.outerHTML`），服务器端 `fetch()` 面对 Twitter/X 这类 SPA 时既没有登录态也不会执行 JS，永远拿不到同样的内容。这正是 `meta.json`/`original.html` 必须不可变、"重新分析"绝不能用服务器抓取结果覆盖原始数据的原因。

## Tauri 桌面壳：非常薄，几乎没做原生的事

代码层面验证（不是猜测）：

- [src-tauri/src/lib.rs:1-16](../../src-tauri/src/lib.rs)：只构建了一个 `tauri::Builder`，挂了一个仅在 debug 模式下用的日志插件（`tauri_plugin_log`，[:5-11](../../src-tauri/src/lib.rs)），然后 `.run()`——**没有注册任何自定义 Tauri command / `invoke_handler`**。
- [src-tauri/src/main.rs:1-6](../../src-tauri/src/main.rs)：标准入口，调用 `app_lib::run()`。
- `Cargo.toml` 依赖极简：`tauri`、`tauri-plugin-log`、`serde`/`serde_json`，没有文件系统/shell 等其他 Tauri 插件。全仓库搜 `@tauri-apps/api`/`invoke(` 在 `src/` 下**没有任何匹配**——前端从不调用 Rust 侧。
- [src-tauri/tauri.conf.json:6-11](../../src-tauri/tauri.conf.json)：`frontendDist`/`devUrl` 都指向 `http://localhost:41932`，`beforeDevCommand`/`beforeBuildCommand` 就是跑 `next dev -p 41932` / `next build`——也就是说 Tauri 加载的是**真实运行中的 Next.js server**（因为这个应用依赖 Next API routes 做文件系统访问，不是纯静态导出），只是套了个原生窗口（1200x800，可调整大小）。

**它存在的唯一目的**：给 Second Brain 一个原生桌面图标/窗口/Dock 存在感，除此之外没有任何原生能力——完全符合 AGENTS.md「local-first，文件系统是唯一数据源，Web UI 只是一个视图」的原则（桌面壳也只是"再套一层视图"）。

## 下一步

最后看 [07-gotchas-and-drift.md](07-gotchas-and-drift.md)，了解哪些 AGENTS.md 里写的东西其实和代码现状有出入——避免被文档误导。
