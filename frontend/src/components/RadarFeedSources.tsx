"use client";

// Feed source management widget for the Radar page. Fully self-contained — its
// own list, its own add/delete handlers — since nothing outside this widget
// needs to read or react to feed-source state, unlike the refresh bar/item feed
// pair which share `items`.
import { useEffect, useState } from "react";
import { addFeedSource, deleteFeedSource, listFeedSources, FeedSource } from "@/lib/api";

export function RadarFeedSources() {
  const [sources, setSources] = useState<FeedSource[]>([]);
  const [sourceName, setSourceName] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceError, setSourceError] = useState<string | null>(null);

  useEffect(() => {
    listFeedSources()
      .then(setSources)
      .catch((err) => setSourceError(err instanceof Error ? err.message : "Failed to load feed sources"));
  }, []);

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

  return (
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
  );
}
