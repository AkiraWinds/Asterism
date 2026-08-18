"use client";

// The middle-pane reader/analysis view for one selected source. Extracted
// from the old /sources/[id] page as part of the unified-workspace redesign
// — same fetch/auto-analyze/tabs/selection-toolbar logic, now parameterized
// by `sourceId` instead of owning its own route, plus a scroll-progress bar
// and auto-read mechanic that didn't exist before. See
// docs/superpowers/specs/2026-08-18-unified-reader-layout-design.md.
import { useEffect, useRef, useState } from "react";
import { analyzeSource, getSource, markSourceRead, SourceDetail } from "@/lib/api";
import { TriageCard } from "./TriageCard";
import { AnalysisTabs, AnalysisTab } from "./AnalysisTabs";
import { SelectionToolbar } from "./SelectionToolbar";

// Scrolling the Reader tab to (at least) this fraction of its scrollable
// height, and staying there this long, auto-marks the source read. Viewing
// only the AI-summary tabs never counts — see the "Read/Unread Tracking"
// section of the design spec linked above.
const READ_SCROLL_THRESHOLD = 0.98;
const READ_DWELL_MS = 3000;

export function ReaderPane({
  sourceId,
  onMarkedRead,
  onHighlightSelected,
}: {
  sourceId: string;
  onMarkedRead: (sourceId: string) => void;
  onHighlightSelected: (text: string) => void;
}) {
  const [source, setSource] = useState<SourceDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<AnalysisTab>("reader");
  const [scrollPct, setScrollPct] = useState(0);
  const contentRef = useRef<HTMLDivElement>(null);
  const paneRef = useRef<HTMLDivElement>(null);
  const autoAnalyzeStarted = useRef(false);
  const alreadyMarkedRead = useRef(false);
  const dwellTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Always holds the *current* sourceId prop. getSource/analyzeSource are
  // async and can resolve after the user has already switched to a different
  // source — every .then/.catch below compares against this ref (not just
  // the sourceId it closed over) before touching state, so a stale response
  // for a source we've navigated away from can never bleed into what's
  // currently rendered.
  const currentSourceIdRef = useRef(sourceId);

  // Switching sources resets everything — this component is reused across
  // selections rather than remounted (sourceId is state, not a route param).
  useEffect(() => {
    currentSourceIdRef.current = sourceId;
    const requestedSourceId = sourceId;
    setSource(null);
    setLoadError(null);
    setActiveTab("reader");
    setScrollPct(0);
    autoAnalyzeStarted.current = false;
    alreadyMarkedRead.current = false;
    if (dwellTimeoutRef.current) {
      clearTimeout(dwellTimeoutRef.current);
      dwellTimeoutRef.current = null;
    }
    getSource(sourceId)
      .then((s) => {
        if (currentSourceIdRef.current !== requestedSourceId) return;
        setSource(s);
        alreadyMarkedRead.current = s.read_at !== null;
      })
      .catch((err) => {
        if (currentSourceIdRef.current !== requestedSourceId) return;
        setLoadError(err instanceof Error ? err.message : "Failed to load source");
      });
  }, [sourceId]);

  const handleAnalyzeRef = useRef<() => void>(() => {});

  async function handleAnalyze() {
    const requestedSourceId = sourceId;
    setError(null);
    setAnalyzing(true);
    try {
      const analysis = await analyzeSource(sourceId);
      if (currentSourceIdRef.current !== requestedSourceId) return;
      setSource((prev) => (prev ? { ...prev, analysis } : prev));
    } catch (err) {
      if (currentSourceIdRef.current !== requestedSourceId) return;
      setError(err instanceof Error ? err.message : "Failed to analyze source");
    } finally {
      if (currentSourceIdRef.current === requestedSourceId) setAnalyzing(false);
    }
  }
  handleAnalyzeRef.current = handleAnalyze;

  // A freshly created source has no analysis.json yet — start it automatically
  // instead of leaving it behind a manual "Analyze" click.
  useEffect(() => {
    if (source && !source.analysis && !autoAnalyzeStarted.current) {
      autoAnalyzeStarted.current = true;
      handleAnalyzeRef.current();
    }
  }, [source]);

  // Shared by handlePaneScroll and the tab-switch effect below: both need to
  // start/stop the same "sat at (effectively) 100% for READ_DWELL_MS"
  // countdown that ends in marking the source read.
  function clearDwellTimer() {
    if (dwellTimeoutRef.current) {
      clearTimeout(dwellTimeoutRef.current);
      dwellTimeoutRef.current = null;
    }
  }

  function startDwellTimer() {
    if (dwellTimeoutRef.current) return;
    dwellTimeoutRef.current = setTimeout(() => {
      dwellTimeoutRef.current = null;
      alreadyMarkedRead.current = true;
      markSourceRead(sourceId).then(() => onMarkedRead(sourceId));
    }, READ_DWELL_MS);
  }

  // Each tab is a fresh reading position — reset scroll and any pending
  // dwell timer from a previous tab when switching. Also re-runs whenever
  // the Reader tab's underlying content string changes (i.e. right after it
  // first renders for this source), so short content that already fits
  // entirely within the pane gets checked below without waiting on a resize.
  useEffect(() => {
    const el = paneRef.current;
    el?.scrollTo({ top: 0 });
    clearDwellTimer();
    if (activeTab === "reader" && el && el.scrollHeight <= el.clientHeight) {
      // Content fits on screen without scrolling — no "scroll" DOM event will
      // ever fire, so a scroll-driven check alone would never see this
      // reach 100%. Treat "nothing left to scroll" the same as "scrolled all
      // the way down" and let the same dwell timer decide whether it counts
      // as read.
      setScrollPct(1);
      if (!alreadyMarkedRead.current) startDwellTimer();
    } else {
      setScrollPct(0);
    }
  }, [activeTab, source?.content]);

  useEffect(() => {
    return () => {
      if (dwellTimeoutRef.current) clearTimeout(dwellTimeoutRef.current);
    };
  }, []);

  function handlePaneScroll() {
    if (activeTab !== "reader") return;
    const el = paneRef.current;
    if (!el) return;
    const scrollable = el.scrollHeight - el.clientHeight;
    const pct = scrollable <= 0 ? 1 : el.scrollTop / scrollable;
    setScrollPct(pct);

    if (alreadyMarkedRead.current) return;
    if (pct >= READ_SCROLL_THRESHOLD) {
      startDwellTimer();
    } else {
      clearDwellTimer();
    }
  }

  if (loadError) {
    return <p className="p-6 text-sm text-destructive">Couldn&apos;t load this source: {loadError}</p>;
  }

  if (!source) {
    return <p className="p-6 text-sm text-muted-foreground">Loading…</p>;
  }

  return (
    <div className="flex h-full flex-col">
      {activeTab === "reader" && (
        <div className="h-1 shrink-0 bg-muted">
          <div
            className="h-1 bg-accent transition-[width]"
            style={{ width: `${Math.round(scrollPct * 100)}%` }}
          />
        </div>
      )}
      <div ref={paneRef} onScroll={handlePaneScroll} className="flex-1 overflow-y-auto px-6 py-6">
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
              active={activeTab}
              onTabChange={setActiveTab}
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

      <SelectionToolbar sourceId={sourceId} containerRef={contentRef} onHighlightSelected={onHighlightSelected} />
    </div>
  );
}
