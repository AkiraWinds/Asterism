"use client";

import { useState } from "react";
import { createSource, SourceSummary } from "@/lib/api";

type Mode = "link" | "text";

// Pinned, always-visible add-source control for column 1 of the unified
// workspace — condensed from the old SourceForm (which navigated to the new
// source's own page on success; that page no longer exists, so this calls
// onCreated instead and lets the parent select it in place). See
// docs/superpowers/specs/2026-08-18-unified-reader-layout-design.md.
export function AddSourceBar({ onCreated }: { onCreated: (source: SourceSummary) => void }) {
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
      setUrl("");
      setTitle("");
      setContent("");
      onCreated(source);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save source");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2 rounded-lg border border-border bg-card p-3">
      <div className="flex gap-1">
        <button
          type="button"
          onClick={() => setMode("link")}
          className={`rounded-md px-2 py-1 text-xs font-medium ${
            mode === "link" ? "bg-accent text-accent-on" : "bg-muted text-muted-foreground"
          }`}
        >
          Link
        </button>
        <button
          type="button"
          onClick={() => setMode("text")}
          className={`rounded-md px-2 py-1 text-xs font-medium ${
            mode === "text" ? "bg-accent text-accent-on" : "bg-muted text-muted-foreground"
          }`}
        >
          Text
        </button>
      </div>

      {mode === "link" ? (
        <div className="flex gap-2">
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/article"
            required
            type="url"
            className="flex-1 rounded-md border border-border bg-transparent px-2 py-1.5 text-sm outline-none focus:border-accent"
          />
          <button
            type="submit"
            disabled={submitting}
            className="shrink-0 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-accent-on hover:bg-accent-hover disabled:opacity-50"
          >
            {submitting ? "…" : "Add"}
          </button>
        </div>
      ) : (
        <>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Title"
            required
            className="rounded-md border border-border bg-transparent px-2 py-1.5 text-sm outline-none focus:border-accent"
          />
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Content"
            required
            rows={3}
            className="rounded-md border border-border bg-transparent px-2 py-1.5 text-sm outline-none focus:border-accent"
          />
          <button
            type="submit"
            disabled={submitting}
            className="self-end rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-accent-on hover:bg-accent-hover disabled:opacity-50"
          >
            {submitting ? "Saving…" : "Save"}
          </button>
        </>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}
    </form>
  );
}
