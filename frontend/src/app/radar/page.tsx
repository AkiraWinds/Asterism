"use client";

// Radar page: composes the four Radar widgets. `items` and `lastAdded` are the
// only pieces of state shared across widgets (a refresh replaces the whole item
// list; adding an item surfaces a confirmation in the refresh bar), so they live
// here. Feed sources and boost topics are fully self-contained components with
// no cross-widget state, so they need no props at all.
import { useEffect, useState } from "react";
import Link from "next/link";
import { listRadarItems, RadarItem } from "@/lib/api";
import { RadarRefreshBar } from "@/components/RadarRefreshBar";
import { RadarItemFeed } from "@/components/RadarItemFeed";
import { RadarFeedSources } from "@/components/RadarFeedSources";
import { RadarBoostTopics } from "@/components/RadarBoostTopics";

export default function RadarPage() {
  const [items, setItems] = useState<RadarItem[]>([]);
  const [lastAdded, setLastAdded] = useState<{ id: string; title: string } | null>(null);
  const [itemsError, setItemsError] = useState<string | null>(null);

  useEffect(() => {
    listRadarItems()
      .then(setItems)
      .catch((err) => setItemsError(err instanceof Error ? err.message : "Failed to load radar items"));
  }, []);

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

      <RadarRefreshBar onRefreshed={setItems} lastAdded={lastAdded} />
      {itemsError && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{itemsError}</p>}
      <RadarItemFeed items={items} onItemsChange={setItems} onAdded={setLastAdded} />

      <div className="mt-10 grid grid-cols-1 gap-6 sm:grid-cols-2">
        <RadarFeedSources />
        <RadarBoostTopics />
      </div>
    </main>
  );
}
