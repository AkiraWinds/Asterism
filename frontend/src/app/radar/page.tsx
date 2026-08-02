"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  addRadarItem,
  dismissRadarItem,
  listRadarItems,
  refreshRadar,
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

  useEffect(() => {
    listRadarItems().then(setItems);
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
    </main>
  );
}
