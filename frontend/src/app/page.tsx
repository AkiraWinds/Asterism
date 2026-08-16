"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { X } from "@phosphor-icons/react";
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
        <h1 className="font-heading text-3xl font-bold tracking-tight text-foreground">Asterism</h1>
        <Link href="/graph" className="text-sm text-muted-foreground hover:text-foreground hover:underline">
          Concept Graph →
        </Link>
      </div>

      <SourceForm />

      <ul className="mt-8 flex flex-col divide-y divide-border">
        {sources.map((s) => (
          <li key={s.id} className="flex items-center justify-between gap-3 py-3">
            <Link href={`/sources/${s.id}`} className="block flex-1 text-sm text-foreground hover:underline">
              {s.title}
            </Link>
            <button
              type="button"
              onClick={() => handleDelete(s.id, s.title)}
              disabled={deletingId === s.id}
              aria-label={`Delete ${s.title}`}
              className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-red-50 hover:text-destructive disabled:opacity-50 dark:hover:bg-red-950/40"
            >
              {deletingId === s.id ? "…" : <X size={16} weight="thin" />}
            </button>
          </li>
        ))}
      </ul>
    </main>
  );
}
