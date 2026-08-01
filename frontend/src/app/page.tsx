"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { deleteSource, listSources, SourceSummary } from "@/lib/api";
import { SourceForm } from "@/components/SourceForm";

export default function HomePage() {
  const [sources, setSources] = useState<SourceSummary[]>([]);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    listSources().then(setSources);
  }, []);

  async function handleDelete(id: string, title: string) {
    if (!window.confirm(`Delete "${title}"? This can't be undone.`)) return;
    setDeletingId(id);
    try {
      await deleteSource(id);
      setSources((prev) => prev.filter((s) => s.id !== id));
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <div className="flex items-baseline justify-between">
        <h1 className="text-3xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">Asterism</h1>
        <Link
          href="/graph"
          className="text-sm text-neutral-500 hover:text-neutral-800 hover:underline dark:text-neutral-400 dark:hover:text-neutral-100"
        >
          Concept Graph →
        </Link>
      </div>

      <SourceForm />

      <ul className="mt-8 flex flex-col divide-y divide-neutral-200 dark:divide-neutral-800">
        {sources.map((s) => (
          <li key={s.id} className="flex items-center justify-between gap-3 py-3">
            <Link
              href={`/sources/${s.id}`}
              className="block flex-1 text-sm text-neutral-800 hover:text-neutral-950 hover:underline dark:text-neutral-200 dark:hover:text-white"
            >
              {s.title}
            </Link>
            <button
              type="button"
              onClick={() => handleDelete(s.id, s.title)}
              disabled={deletingId === s.id}
              aria-label={`Delete ${s.title}`}
              className="shrink-0 rounded-md p-1 text-neutral-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-50 dark:hover:bg-red-950/40 dark:hover:text-red-400"
            >
              {deletingId === s.id ? "…" : "✕"}
            </button>
          </li>
        ))}
      </ul>
    </main>
  );
}
