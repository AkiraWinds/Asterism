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
    <main style={{ padding: 24 }}>
      <h1>Asterism</h1>

      <form onSubmit={handleSubmit}>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Title"
          required
        />
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Content"
          required
        />
        <button type="submit">Save</button>
      </form>

      <ul>
        {sources.map((s) => (
          <li key={s.id}>
            <Link href={`/sources/${s.id}`}>{s.title}</Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
