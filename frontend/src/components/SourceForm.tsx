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
    } catch {
      setError("Failed to save source");
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mt-8 flex flex-col gap-3 rounded-lg border border-neutral-200 bg-white p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900"
    >
      <div className="flex gap-1">
        <button
          type="button"
          onClick={() => setMode("link")}
          className={`rounded-md px-3 py-1 text-xs font-medium ${
            mode === "link"
              ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
              : "bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400"
          }`}
        >
          Paste link
        </button>
        <button
          type="button"
          onClick={() => setMode("text")}
          className={`rounded-md px-3 py-1 text-xs font-medium ${
            mode === "text"
              ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
              : "bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400"
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
          className="rounded-md border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-neutral-500 dark:border-neutral-700"
        />
      ) : (
        <>
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
        </>
      )}

      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      <button
        type="submit"
        disabled={submitting}
        className="self-end rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900 dark:hover:bg-neutral-300"
      >
        {submitting ? "Saving…" : "Save"}
      </button>
    </form>
  );
}
