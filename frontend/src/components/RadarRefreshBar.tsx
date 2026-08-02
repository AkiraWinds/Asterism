"use client";

// Refresh control for the Radar page: triggers a pipeline run across all feed
// sources, shows the per-source summary/error from that run, and surfaces the
// "added to library" confirmation for whatever item was most recently added
// (that add action itself happens in RadarItemFeed, hence `lastAdded` as a prop
// rather than local state — the parent page is the single source of truth for
// `items`, which both this bar and the item feed need to agree on after a refresh).
import { useState } from "react";
import { refreshRadar, listRadarItems, RadarItem, RadarRefreshSummary } from "@/lib/api";

interface RadarRefreshBarProps {
  onRefreshed: (items: RadarItem[]) => void;
  lastAdded: { id: string; title: string } | null;
}

export function RadarRefreshBar({ onRefreshed, lastAdded }: RadarRefreshBarProps) {
  const [refreshing, setRefreshing] = useState(false);
  const [refreshSummary, setRefreshSummary] = useState<RadarRefreshSummary | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  async function handleRefresh() {
    setRefreshing(true);
    setRefreshError(null);
    try {
      const summary = await refreshRadar();
      setRefreshSummary(summary);
      onRefreshed(await listRadarItems());
    } catch (err) {
      setRefreshError(err instanceof Error ? err.message : "Failed to refresh");
    } finally {
      setRefreshing(false);
    }
  }

  return (
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
  );
}
