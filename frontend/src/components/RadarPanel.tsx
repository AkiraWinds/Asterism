"use client";

// Radar tab content for column 1 of the unified workspace — same four-widget
// composition as the old standalone /radar page, just without its own page
// chrome. See docs/superpowers/specs/2026-08-18-unified-reader-layout-design.md.
import { useEffect, useState } from "react";
import { listRadarItems, RadarItem, SourceSummary } from "@/lib/api";
import { RadarRefreshBar } from "./RadarRefreshBar";
import { RadarItemFeed } from "./RadarItemFeed";
import { RadarFeedSources } from "./RadarFeedSources";
import { RadarBoostTopics } from "./RadarBoostTopics";

// `onAdded` reports every successful add up to the workspace page so the
// Library tab's sources list (owned by page.tsx, not this component) learns
// about the new source too — without it, a source added here is invisible in
// Library until a full page reload.
export function RadarPanel({ onAdded }: { onAdded: (source: SourceSummary) => void }) {
  const [items, setItems] = useState<RadarItem[]>([]);
  const [lastAdded, setLastAdded] = useState<{ id: string; title: string } | null>(null);
  const [itemsError, setItemsError] = useState<string | null>(null);

  useEffect(() => {
    listRadarItems()
      .then(setItems)
      .catch((err) => setItemsError(err instanceof Error ? err.message : "Failed to load radar items"));
  }, []);

  function handleAdded(result: { id: string; title: string }) {
    setLastAdded(result);
    onAdded({ id: result.id, title: result.title, created_at: new Date().toISOString(), read_at: null });
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <RadarRefreshBar onRefreshed={setItems} lastAdded={lastAdded} />
      {itemsError && <p className="text-sm text-destructive">{itemsError}</p>}
      <RadarItemFeed items={items} onItemsChange={setItems} onAdded={handleAdded} />
      <RadarFeedSources />
      <RadarBoostTopics />
    </div>
  );
}
