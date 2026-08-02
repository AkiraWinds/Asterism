"use client";

// Renders the shortlisted radar items with Add/Dismiss actions. `items` and the
// setter live in the parent page (RadarRefreshBar also needs to overwrite `items`
// wholesale after a refresh run), so this component takes items down and reports
// mutations back up via callbacks rather than owning the list itself. Per-item
// pending/error UI state is local since nothing outside this component needs it.
import { Dispatch, SetStateAction, useState } from "react";
import { addRadarItem, dismissRadarItem, RadarItem } from "@/lib/api";

interface RadarItemFeedProps {
  items: RadarItem[];
  onItemsChange: Dispatch<SetStateAction<RadarItem[]>>;
  onAdded: (result: { id: string; title: string }) => void;
}

export function RadarItemFeed({ items, onItemsChange, onAdded }: RadarItemFeedProps) {
  const [pendingAction, setPendingAction] = useState<{ id: string; action: "add" | "dismiss" } | null>(null);
  const [itemError, setItemError] = useState<{ id: string; message: string } | null>(null);

  async function handleAdd(item: RadarItem) {
    setPendingAction({ id: item.id, action: "add" });
    setItemError(null);
    try {
      const result = await addRadarItem(item.id);
      onAdded(result);
      onItemsChange((prev) => prev.filter((i) => i.id !== item.id));
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
      onItemsChange((prev) => prev.filter((i) => i.id !== item.id));
    } catch (err) {
      setItemError({ id: item.id, message: err instanceof Error ? err.message : "Failed to dismiss item" });
    } finally {
      setPendingAction(null);
    }
  }

  return (
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
  );
}
