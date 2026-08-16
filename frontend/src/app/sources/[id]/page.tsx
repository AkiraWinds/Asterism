"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { analyzeSource, getSource, SourceDetail } from "@/lib/api";
import { TriageCard } from "@/components/TriageCard";
import { AnalysisTabs } from "@/components/AnalysisTabs";
import { ChatPanel } from "@/components/ChatPanel";
import { SelectionToolbar } from "@/components/SelectionToolbar";

export default function SourcePage() {
  const { id } = useParams<{ id: string }>();
  const [source, setSource] = useState<SourceDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attachedHighlight, setAttachedHighlight] = useState<string | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const autoAnalyzeStarted = useRef(false);

  useEffect(() => {
    getSource(id)
      .then(setSource)
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Failed to load source"));
  }, [id]);

  const handleAnalyzeRef = useRef<() => void>(() => {});

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
  handleAnalyzeRef.current = handleAnalyze;

  // A freshly created source has no analysis.json yet — start it automatically
  // instead of leaving it behind a manual "Analyze" click. Retries via the
  // same button still use handleAnalyze directly, so this only fires once.
  useEffect(() => {
    if (source && !source.analysis && !autoAnalyzeStarted.current) {
      autoAnalyzeStarted.current = true;
      handleAnalyzeRef.current();
    }
  }, [source]);

  const backLink = (
    <Link href="/" className="text-sm text-muted-foreground hover:text-foreground hover:underline">
      ← Back
    </Link>
  );

  if (loadError) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-12">
        {backLink}
        <p className="mt-4 text-sm text-destructive">Couldn&apos;t load this source: {loadError}</p>
      </main>
    );
  }

  if (!source) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-12">
        {backLink}
        <p className="mt-4 text-sm text-muted-foreground">Loading…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      {backLink}

      <div className="mt-4 grid grid-cols-1 gap-8 lg:grid-cols-[1fr_360px]">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight text-foreground">{source.title}</h1>

          {source.analysis?.triage && <TriageCard triage={source.analysis.triage} />}

          {error && <p className="mt-4 text-sm text-destructive">{error}</p>}

          <div ref={contentRef}>
            {source.analysis ? (
              <AnalysisTabs
                sourceId={source.id}
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
                className="mt-6 rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-on hover:bg-accent-hover disabled:opacity-50"
              >
                {analyzing ? "Analyzing…" : "Analyze"}
              </button>
            )}
          </div>
        </div>

        <div className="h-[70vh] lg:sticky lg:top-12">
          <ChatPanel
            sourceId={id}
            attachedHighlight={attachedHighlight}
            onClearAttachedHighlight={() => setAttachedHighlight(null)}
          />
        </div>
      </div>

      <SelectionToolbar sourceId={id} containerRef={contentRef} onHighlightSelected={setAttachedHighlight} />
    </main>
  );
}
