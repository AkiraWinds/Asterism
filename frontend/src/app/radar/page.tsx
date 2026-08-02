"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  addBoostTopic,
  addFeedSource,
  addRadarItem,
  deleteBoostTopic,
  deleteFeedSource,
  dismissRadarItem,
  listBoostTopics,
  listFeedSources,
  listRadarItems,
  refreshRadar,
  BoostTopic,
  FeedSource,
  RadarItem,
  RadarRefreshSummary,
} from "@/lib/api";

export default function RadarPage() {
  const [items, setItems] = useState<RadarItem[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshSummary, setRefreshSummary] = useState<RadarRefreshSummary | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<{ id: string; action: "add" | "dismiss" } | null>(null);
  const [itemError, setItemError] = useState<{ id: string; message: string } | null>(null);
  const [lastAdded, setLastAdded] = useState<{ id: string; title: string } | null>(null);
  const [sources, setSources] = useState<FeedSource[]>([]);
  const [sourceName, setSourceName] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceError, setSourceError] = useState<string | null>(null);
  const [topics, setTopics] = useState<BoostTopic[]>([]);
  const [topicTerm, setTopicTerm] = useState("");
  const [topicError, setTopicError] = useState<string | null>(null);

  useEffect(() => {
    listRadarItems().then(setItems);
    listFeedSources().then(setSources);
    listBoostTopics().then(setTopics);
  }, []);

  async function handleRefresh() {
    setRefreshing(true);
    setRefreshError(null);
    try {
      const summary = await refreshRadar();
      setRefreshSummary(summary);
      setItems(await listRadarItems());
    } catch (err) {
      setRefreshError(err instanceof Error ? err.message : "Failed to refresh");
    } finally {
      setRefreshing(false);
    }
  }

  async function handleAdd(item: RadarItem) {
    setPendingAction({ id: item.id, action: "add" });
    setItemError(null);
    try {
      const result = await addRadarItem(item.id);
      setLastAdded(result);
      setItems((prev) => prev.filter((i) => i.id !== item.id));
    } catch (err) {
      setItemError({ id: item.id, message: err instanceof Error ? err.message : "Failed to add item" });
    } finally {
      setPendingAction(null);
    }
  }

  async function handleDismiss(item: RadarItem) {
    setPendingAction({ id: item.id, action: "dismiss" });
    setItemError(null);
    try {
      await dismissRadarItem(item.id);
      setItems((prev) => prev.filter((i) => i.id !== item.id));
    } catch (err) {
      setItemError({ id: item.id, message: err instanceof Error ? err.message : "Failed to dismiss item" });
    } finally {
      setPendingAction(null);
    }
  }

  async function handleAddSource(e: React.FormEvent) {
    e.preventDefault();
    setSourceError(null);
    try {
      await addFeedSource(sourceName, sourceUrl);
      setSourceName("");
      setSourceUrl("");
      setSources(await listFeedSources());
    } catch (err) {
      setSourceError(err instanceof Error ? err.message : "Failed to add source");
    }
  }

  async function handleDeleteSource(id: string) {
    setSourceError(null);
    try {
      await deleteFeedSource(id);
      setSources(await listFeedSources());
    } catch (err) {
      setSourceError(err instanceof Error ? err.message : "Failed to delete source");
    }
  }

  async function handleAddTopic(e: React.FormEvent) {
    e.preventDefault();
    setTopicError(null);
    try {
      await addBoostTopic(topicTerm);
      setTopicTerm("");
      setTopics(await listBoostTopics());
    } catch (err) {
      setTopicError(err instanceof Error ? err.message : "Failed to add topic");
    }
  }

  async function handleDeleteTopic(id: string) {
    setTopicError(null);
    try {
      await deleteBoostTopic(id);
      setTopics(await listBoostTopics());
    } catch (err) {
      setTopicError(err instanceof Error ? err.message : "Failed to delete topic");
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <div className="flex items-baseline justify-between">
        <h1 className="text-3xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">Radar</h1>
        <Link
          href="/"
          className="text-sm text-neutral-500 hover:text-neutral-800 hover:underline dark:text-neutral-400 dark:hover:text-neutral-100"
        >
          ← Sources
        </Link>
      </div>

      <div className="mt-8 rounded-lg border border-neutral-200 bg-white p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <button
          type="button"
          onClick={handleRefresh}
          disabled={refreshing}
          className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900 dark:hover:bg-neutral-300"
        >
          {refreshing ? "Refreshing…" : "Refresh"}
        </button>

        {refreshError && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{refreshError}</p>}

        {refreshSummary && !refreshError && (
          <p className="mt-3 text-sm text-neutral-600 dark:text-neutral-400">
            {Object.entries(refreshSummary.per_source)
              .map(([name, summary]) => `${name}: ${JSON.stringify(summary)}`)
              .join(" · ")}
          </p>
        )}

        {lastAdded && (
          <p className="mt-3 text-sm text-green-600 dark:text-green-400">
            Added &quot;{lastAdded.title}&quot; to library.
          </p>
        )}
      </div>

      <ul className="mt-8 flex flex-col gap-4">
        {items.map((item) => (
          <li
            key={item.id}
            className="rounded-lg border border-neutral-200 bg-white p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900"
          >
            <a
              href={item.url}
              target="_blank"
              rel="noreferrer"
              className="text-sm font-medium text-neutral-900 hover:underline dark:text-neutral-100"
            >
              {item.title}
            </a>
            <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
              Relevance: {item.relevance_score.toFixed(2)} · Quality: {item.quality_score.toFixed(2)}
            </p>
            <p className="mt-2 text-sm text-neutral-700 dark:text-neutral-300">{item.reasoning}</p>

            {itemError?.id === item.id && (
              <p className="mt-2 text-sm text-red-600 dark:text-red-400">{itemError.message}</p>
            )}

            <div className="mt-3 flex gap-2">
              <button
                type="button"
                onClick={() => handleAdd(item)}
                disabled={pendingAction?.id === item.id}
                className="rounded-md bg-neutral-900 px-3 py-1 text-xs font-medium text-white hover:bg-neutral-700 disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900 dark:hover:bg-neutral-300"
              >
                {pendingAction?.id === item.id && pendingAction.action === "add" ? "Adding…" : "Add"}
              </button>
              <button
                type="button"
                onClick={() => handleDismiss(item)}
                disabled={pendingAction?.id === item.id}
                className="rounded-md bg-neutral-100 px-3 py-1 text-xs font-medium text-neutral-600 hover:bg-red-50 hover:text-red-600 disabled:opacity-50 dark:bg-neutral-800 dark:text-neutral-400 dark:hover:bg-red-950/40 dark:hover:text-red-400"
              >
                {pendingAction?.id === item.id && pendingAction.action === "dismiss" ? "Dismissing…" : "Dismiss"}
              </button>
            </div>
          </li>
        ))}
      </ul>

      <div className="mt-10 grid grid-cols-1 gap-6 sm:grid-cols-2">
        <div className="rounded-lg border border-neutral-200 bg-white p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
          <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">Feed sources</h2>
          <ul className="mt-3 flex flex-col gap-2">
            {sources.map((s) => (
              <li key={s.id} className="flex items-start justify-between gap-2 text-sm">
                <div>
                  <span className="text-neutral-800 dark:text-neutral-200">{s.name}</span>{" "}
                  <span
                    className={`rounded px-1.5 py-0.5 text-xs ${
                      s.enabled
                        ? "bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-400"
                        : "bg-neutral-100 text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400"
                    }`}
                  >
                    {s.enabled ? "enabled" : "disabled"}
                  </span>
                  <p className="text-xs text-neutral-500 dark:text-neutral-400">{s.url}</p>
                  {s.last_fetch_status === "error" && s.last_fetch_error && (
                    <p className="text-xs text-red-600 dark:text-red-400">{s.last_fetch_error}</p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => handleDeleteSource(s.id)}
                  aria-label={`Delete ${s.name}`}
                  className="shrink-0 rounded-md p-1 text-neutral-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40 dark:hover:text-red-400"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>

          <form onSubmit={handleAddSource} className="mt-4 flex flex-col gap-2">
            <input
              value={sourceName}
              onChange={(e) => setSourceName(e.target.value)}
              placeholder="Name"
              required
              className="rounded-md border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-neutral-500 dark:border-neutral-700"
            />
            <input
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              placeholder="https://example.com/rss.xml"
              required
              type="url"
              className="rounded-md border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-neutral-500 dark:border-neutral-700"
            />
            {sourceError && <p className="text-sm text-red-600 dark:text-red-400">{sourceError}</p>}
            <button
              type="submit"
              className="self-end rounded-md bg-neutral-900 px-3 py-1 text-xs font-medium text-white hover:bg-neutral-700 dark:bg-neutral-100 dark:text-neutral-900 dark:hover:bg-neutral-300"
            >
              Add source
            </button>
          </form>
        </div>

        <div className="rounded-lg border border-neutral-200 bg-white p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
          <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">Boost topics</h2>
          <ul className="mt-3 flex flex-col gap-2">
            {topics.map((t) => (
              <li key={t.id} className="flex items-center justify-between gap-2 text-sm">
                <span className="text-neutral-800 dark:text-neutral-200">{t.term}</span>
                <button
                  type="button"
                  onClick={() => handleDeleteTopic(t.id)}
                  aria-label={`Delete ${t.term}`}
                  className="shrink-0 rounded-md p-1 text-neutral-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40 dark:hover:text-red-400"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>

          <form onSubmit={handleAddTopic} className="mt-4 flex flex-col gap-2">
            <input
              value={topicTerm}
              onChange={(e) => setTopicTerm(e.target.value)}
              placeholder="Topic term"
              required
              className="rounded-md border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-neutral-500 dark:border-neutral-700"
            />
            {topicError && <p className="text-sm text-red-600 dark:text-red-400">{topicError}</p>}
            <button
              type="submit"
              className="self-end rounded-md bg-neutral-900 px-3 py-1 text-xs font-medium text-white hover:bg-neutral-700 dark:bg-neutral-100 dark:text-neutral-900 dark:hover:bg-neutral-300"
            >
              Add topic
            </button>
          </form>
        </div>
      </div>
    </main>
  );
}
