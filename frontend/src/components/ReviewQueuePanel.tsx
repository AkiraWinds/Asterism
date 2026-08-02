"use client";

// Surfaces the medium-confidence dedup queue from the backend (GET
// /graph/review-queue): concept-merge candidates the LLM judge wasn't
// confident enough to auto-apply, plus anything classified `contradicts`.
// Each entry names two concept IDs, not terms, so this fetches the graph
// alongside the queue to resolve human-readable labels for both sides.
import { useEffect, useState } from "react";
import {
  GraphConceptNode,
  ReviewQueueEntry,
  getGraph,
  getReviewQueue,
  resolveReviewQueueEntry,
} from "@/lib/api";

export function ReviewQueuePanel({ onResolved }: { onResolved?: () => void }) {
  const [entries, setEntries] = useState<ReviewQueueEntry[] | null>(null);
  const [nodesById, setNodesById] = useState<Map<string, GraphConceptNode>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const [resolvingId, setResolvingId] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getReviewQueue(), getGraph()])
      .then(([queue, graph]) => {
        setEntries(queue);
        setNodesById(new Map(graph.nodes.map((n) => [n.id, n])));
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load review queue"));
  }, []);

  async function handleResolve(entryId: string, action: "merge" | "keep_separate") {
    if (resolvingId) return;
    setResolvingId(entryId);
    setError(null);
    try {
      await resolveReviewQueueEntry(entryId, action);
      setEntries((prev) => (prev ?? []).filter((e) => e.id !== entryId));
      onResolved?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to resolve entry");
    } finally {
      setResolvingId(null);
    }
  }

  if (error) {
    return <p className="text-sm text-red-600 dark:text-red-400">Couldn&apos;t load the review queue: {error}</p>;
  }

  if (!entries) {
    return <p className="text-sm text-neutral-500 dark:text-neutral-400">Loading review queue…</p>;
  }

  if (entries.length === 0) {
    return null;
  }

  return (
    <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950/30">
      <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
        Needs review ({entries.length})
      </h2>
      <p className="mt-1 text-xs text-neutral-600 dark:text-neutral-400">
        These concept pairs were too ambiguous to merge automatically — decide whether they&apos;re the same idea.
      </p>
      <ul className="mt-3 space-y-3">
        {entries.map((entry) => {
          const candidate = nodesById.get(entry.candidate_concept_id);
          const existing = nodesById.get(entry.existing_concept_id);
          const isResolving = resolvingId === entry.id;
          return (
            <li
              key={entry.id}
              className="rounded-md border border-neutral-200 bg-white p-3 text-sm dark:border-neutral-700 dark:bg-neutral-900"
            >
              <div className="grid gap-2 sm:grid-cols-2">
                <div>
                  <p className="font-medium text-neutral-900 dark:text-neutral-100">
                    {candidate?.term ?? entry.candidate_concept_id}
                  </p>
                  {candidate && (
                    <p className="mt-0.5 text-xs text-neutral-600 dark:text-neutral-300">{candidate.definition}</p>
                  )}
                </div>
                <div>
                  <p className="font-medium text-neutral-900 dark:text-neutral-100">
                    {existing?.term ?? entry.existing_concept_id}
                  </p>
                  {existing && (
                    <p className="mt-0.5 text-xs text-neutral-600 dark:text-neutral-300">{existing.definition}</p>
                  )}
                </div>
              </div>
              <p className="mt-2 text-xs italic text-neutral-500 dark:text-neutral-400">{entry.llm_judgment}</p>
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  disabled={isResolving}
                  onClick={() => handleResolve(entry.id, "merge")}
                  className="rounded border border-neutral-300 px-2 py-1 text-xs text-neutral-700 hover:bg-neutral-100 disabled:opacity-60 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
                >
                  {isResolving ? "Working…" : "Merge"}
                </button>
                <button
                  type="button"
                  disabled={isResolving}
                  onClick={() => handleResolve(entry.id, "keep_separate")}
                  className="rounded border border-neutral-300 px-2 py-1 text-xs text-neutral-700 hover:bg-neutral-100 disabled:opacity-60 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
                >
                  {isResolving ? "Working…" : "Keep separate"}
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
