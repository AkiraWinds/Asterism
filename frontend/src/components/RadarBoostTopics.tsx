"use client";

// Boost topic management widget for the Radar page. Fully self-contained, same
// rationale as RadarFeedSources — no other part of the page needs boost-topic
// state.
import { useEffect, useState } from "react";
import { addBoostTopic, deleteBoostTopic, listBoostTopics, BoostTopic } from "@/lib/api";

export function RadarBoostTopics() {
  const [topics, setTopics] = useState<BoostTopic[]>([]);
  const [topicTerm, setTopicTerm] = useState("");
  const [topicError, setTopicError] = useState<string | null>(null);

  useEffect(() => {
    listBoostTopics().then(setTopics);
  }, []);

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
  );
}
