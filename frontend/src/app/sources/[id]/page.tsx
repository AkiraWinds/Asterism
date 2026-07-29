"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { analyzeSource, getSource, SourceDetail } from "@/lib/api";
import { TriageCard } from "@/components/TriageCard";
import { AnalysisTabs } from "@/components/AnalysisTabs";
import { ChatPanel } from "@/components/ChatPanel";

export default function SourcePage() {
  const { id } = useParams<{ id: string }>();
  const [source, setSource] = useState<SourceDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSource(id)
      .then(setSource)
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Failed to load source"));
  }, [id]);

  async function handleAnalyze() {
    setError(null);
    setAnalyzing(true);
    try {
      const analysis = await analyzeSource(id);
      setSource((prev) => (prev ? { ...prev, analysis } : prev));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to analyze source");
    } finally {
      setAnalyzing(false);
    }
  }

  const backLink = (
    <Link
      href="/"
      className="text-sm text-neutral-500 hover:text-neutral-800 hover:underline dark:text-neutral-400 dark:hover:text-neutral-100"
    >
      ← Back
    </Link>
  );

  if (loadError) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-12">
        {backLink}
        <p className="mt-4 text-sm text-red-600 dark:text-red-400">
          Couldn&apos;t load this source: {loadError}
        </p>
      </main>
    );
  }

  if (!source) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-12">
        {backLink}
        <p className="mt-4 text-sm text-neutral-500 dark:text-neutral-400">Loading…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      {backLink}

      <div className="mt-4 grid grid-cols-1 gap-8 lg:grid-cols-[1fr_360px]">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">
            {source.title}
          </h1>

          {source.analysis?.triage && <TriageCard triage={source.analysis.triage} />}

          {error && <p className="mt-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

          {source.analysis ? (
            <AnalysisTabs
              content={source.content}
              analysis={source.analysis}
              onRetry={handleAnalyze}
              retrying={analyzing}
            />
          ) : (
            <button
              type="button"
              onClick={handleAnalyze}
              disabled={analyzing}
              className="mt-6 rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900 dark:hover:bg-neutral-300"
            >
              {analyzing ? "Analyzing…" : "Analyze"}
            </button>
          )}
        </div>

        <div className="h-[70vh] lg:sticky lg:top-12">
          <ChatPanel sourceId={id} />
        </div>
      </div>
    </main>
  );
}
