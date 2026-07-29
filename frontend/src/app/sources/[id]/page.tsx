"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { analyzeSource, getSource, SourceDetail } from "@/lib/api";
import { TriageCard } from "@/components/TriageCard";
import { AnalysisTabs } from "@/components/AnalysisTabs";

export default function SourcePage() {
  const { id } = useParams<{ id: string }>();
  const [source, setSource] = useState<SourceDetail | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSource(id).then(setSource);
  }, [id]);

  async function handleAnalyze() {
    setError(null);
    setAnalyzing(true);
    try {
      const analysis = await analyzeSource(id);
      setSource((prev) => (prev ? { ...prev, analysis } : prev));
    } catch {
      setError("Failed to analyze source");
    } finally {
      setAnalyzing(false);
    }
  }

  if (!source) return null;

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <Link
        href="/"
        className="text-sm text-neutral-500 hover:text-neutral-800 hover:underline dark:text-neutral-400 dark:hover:text-neutral-100"
      >
        ← Back
      </Link>

      <h1 className="mt-4 text-3xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">
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
    </main>
  );
}
