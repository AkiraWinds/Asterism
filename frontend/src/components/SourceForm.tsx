"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createSource } from "@/lib/api";

type Mode = "link" | "text";

export function SourceForm() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("link");
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const source = mode === "link" ? await createSource({ url }) : await createSource({ title, content });
      router.push(`/sources/${source.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save source");
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mt-8 flex flex-col gap-3 rounded-lg border border-border bg-card p-5 shadow-sm"
    >
      <div className="flex gap-1">
        <button
          type="button"
          onClick={() => setMode("link")}
          className={`rounded-md px-3 py-1 text-xs font-medium ${
            mode === "link" ? "bg-accent text-accent-on" : "bg-muted text-muted-foreground"
          }`}
        >
          Paste link
        </button>
        <button
          type="button"
          onClick={() => setMode("text")}
          className={`rounded-md px-3 py-1 text-xs font-medium ${
            mode === "text" ? "bg-accent text-accent-on" : "bg-muted text-muted-foreground"
          }`}
        >
          Write text
        </button>
      </div>

      {mode === "link" ? (
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com/article"
          required
          type="url"
          className="rounded-md border border-border bg-transparent px-3 py-2 text-sm outline-none focus:border-accent"
        />
      ) : (
        <>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Title"
            required
            className="rounded-md border border-border bg-transparent px-3 py-2 text-sm outline-none focus:border-accent"
          />
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Content"
            required
            rows={4}
            className="rounded-md border border-border bg-transparent px-3 py-2 text-sm outline-none focus:border-accent"
          />
        </>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}

      <button
        type="submit"
        disabled={submitting}
        className="self-end rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-on hover:bg-accent-secondary disabled:opacity-50"
      >
        {submitting ? "Saving…" : "Save"}
      </button>
    </form>
  );
}
