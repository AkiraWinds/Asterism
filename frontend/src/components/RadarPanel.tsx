"use client";

// Radar tab content for column 1 of the unified workspace — same four-widget
// composition as the old standalone /radar page, just without its own page
// chrome. See docs/superpowers/specs/2026-08-18-unified-reader-layout-design.md.
import { useEffect, useState } from "react";
import { listRadarItems, RadarItem } from "@/lib/api";
import { RadarRefreshBar } from "./RadarRefreshBar";
import { RadarItemFeed } from "./RadarItemFeed";
import { RadarFeedSources } from "./RadarFeedSources";
import { RadarBoostTopics } from "./RadarBoostTopics";

export function RadarPanel() {
  const [items, setItems] = useState<RadarItem[]>([]);
  const [lastAdded, setLastAdded] = useState<{ id: string; title: string } | null>(null);
  const [itemsError, setItemsError] = useState<string | null>(null);

  useEffect(() => {
    listRadarItems()
      .then(setItems)
      .catch((err) => setItemsError(err instanceof Error ? err.message : "Failed to load radar items"));
  }, []);

  return (
    <div className="flex flex-col gap-4 p-4">
      <RadarRefreshBar onRefreshed={setItems} lastAdded={lastAdded} />
      {itemsError && <p className="text-sm text-destructive">{itemsError}</p>}
      <RadarItemFeed items={items} onItemsChange={setItems} onAdded={setLastAdded} />
      <RadarFeedSources />
      <RadarBoostTopics />
    </div>
  );
}
