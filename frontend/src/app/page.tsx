"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createSource, listSources, SourceSummary } from "@/lib/api";

export default function HomePage() {
  const [sources, setSources] = useState<SourceSummary[]>([]);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");

  async function refresh() {
    setSources(await listSources());
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await createSource(title, content);
    setTitle("");
    setContent("");
    await refresh();
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="text-3xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">
        Asterism
      </h1>

      <form
        onSubmit={handleSubmit}
        className="mt-8 flex flex-col gap-3 rounded-lg border border-neutral-200 bg-white p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900"
      >
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Title"
          required
          className="rounded-md border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-neutral-500 dark:border-neutral-700"
        />
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Content"
          required
          rows={4}
          className="rounded-md border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-neutral-500 dark:border-neutral-700"
        />
        <button
          type="submit"
          className="self-end rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 dark:bg-neutral-100 dark:text-neutral-900 dark:hover:bg-neutral-300"
        >
          Save
        </button>
      </form>

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
