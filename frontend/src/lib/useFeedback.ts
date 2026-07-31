"use client";

import { useCallback, useEffect, useState } from "react";
import { Feedback, FeedbackKind, getFeedback } from "@/lib/api";

/** Fetches feedback.json once per source and exposes a lookup by exact
 * (kind, section, content) match — mirrors the backend's find_feedback_entry.
 * Re-fetch after any local mutation via refresh(), rather than trying to
 * merge partial updates into the list client-side. */
export function useFeedback(sourceId: string) {
  const [entries, setEntries] = useState<Feedback[]>([]);

  const refresh = useCallback(() => {
    getFeedback(sourceId).then(setEntries).catch(() => setEntries([]));
  }, [sourceId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  function find(kind: FeedbackKind, section: string | undefined, content: string): Feedback | null {
    const normalized = content.trim();
    return (
      entries.find(
        (e) => e.kind === kind && e.section === (section ?? null) && e.content.trim() === normalized
      ) ?? null
    );
  }

  function upsertLocal(updated: Feedback) {
    setEntries((prev) => {
      const idx = prev.findIndex((e) => e.id === updated.id);
      if (idx === -1) return [...prev, updated];
      const next = [...prev];
      next[idx] = updated;
      return next;
    });
  }

  return { find, upsertLocal };
}
