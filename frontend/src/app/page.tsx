"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listSources, SourceSummary } from "@/lib/api";
import { SourceForm } from "@/components/SourceForm";

export default function HomePage() {
  const [sources, setSources] = useState<SourceSummary[]>([]);

  useEffect(() => {
    listSources().then(setSources);
  }, []);

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
          <li key={s.id}>
            <Link
              href={`/sources/${s.id}`}
              className="block py-3 text-sm text-neutral-800 hover:text-neutral-950 hover:underline dark:text-neutral-200 dark:hover:text-white"
            >
              {s.title}
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
