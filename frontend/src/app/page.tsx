"use client";

// The unified workspace: Library/Radar list (column 1), reader+analysis for
// the selected source (column 2+3 combined), and chat scoped to that source
// (column 4). Replaces the old separate home list, /sources/[id], and /radar
// pages — see docs/superpowers/specs/2026-08-18-unified-reader-layout-design.md.
import { useCallback, useEffect, useState } from "react";
import { deleteSource, listSources, SourceSummary } from "@/lib/api";
import { LibraryColumn } from "@/components/LibraryColumn";
import { ReaderPane } from "@/components/ReaderPane";
import { ChatPanel } from "@/components/ChatPanel";
import { WorkspaceLayout } from "@/components/WorkspaceLayout";

export default function WorkspacePage() {
  const [sources, setSources] = useState<SourceSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [attachedHighlight, setAttachedHighlight] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    listSources().then(setSources);
  }, []);

  function handleSelect(id: string) {
    setSelectedId(id);
    // A highlight attached from a previously open article shouldn't silently
    // carry over as chat context for a different one.
    setAttachedHighlight(null);
  }

  async function handleDelete(id: string) {
    try {
      await deleteSource(id);
      setSources((prev) => prev.filter((s) => s.id !== id));
      if (selectedId === id) setSelectedId(null);
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete source");
    }
  }

  function handleCreated(source: SourceSummary) {
    setSources((prev) => [source, ...prev]);
    handleSelect(source.id);
  }

  function handleAdded(source: SourceSummary) {
    setSources((prev) => [source, ...prev]);
  }

  // Stable identity (useCallback, not a plain function) is required here:
  // this is passed to ReaderPane as `onMarkedRead`, which its dwell-timer
  // useCallback depends on, which its scroll-reset effect in turn depends
  // on. An unstable reference here made that effect re-fire — and reset
  // the reader's scroll position to the top — on every unrelated parent
  // re-render, e.g. every text selection (which updates attachedHighlight).
  const handleMarkedRead = useCallback((id: string, readAt: string) => {
    setSources((prev) => prev.map((s) => (s.id === id ? { ...s, read_at: readAt } : s)));
  }, []);

  // Same stability requirement as handleMarkedRead above: this is threaded
  // through ReaderPane to SelectionToolbar's effect deps, so an unstable
  // reference here would re-subscribe its selectionchange/mouseup/keydown
  // listeners (and, transitively, re-trigger the scroll-reset effect that
  // depends on onMarkedRead) on every unrelated parent re-render.
  const handleHighlightCleared = useCallback(() => setAttachedHighlight(null), []);

  return (
    <WorkspaceLayout
      deleteError={
        deleteError && (
          <p className="border-b border-border bg-red-50 p-2 text-xs text-destructive dark:bg-red-950/40">
            {deleteError}
          </p>
        )
      }
      libraryColumn={
        <LibraryColumn
          sources={sources}
          selectedId={selectedId}
          onSelect={handleSelect}
          onDelete={handleDelete}
          onCreated={handleCreated}
          onAdded={handleAdded}
        />
      }
      readerPane={
        selectedId ? (
          <ReaderPane
            sourceId={selectedId}
            onMarkedRead={handleMarkedRead}
            onHighlightSelected={setAttachedHighlight}
            onHighlightCleared={handleHighlightCleared}
          />
        ) : (
          <div className="flex h-full items-center justify-center p-6">
            <p className="text-sm text-muted-foreground">Select an article to read</p>
          </div>
        )
      }
      chatPanel={
        selectedId ? (
          <ChatPanel
            sourceId={selectedId}
            attachedHighlight={attachedHighlight}
            onClearAttachedHighlight={() => setAttachedHighlight(null)}
          />
        ) : (
          <div className="flex h-full items-center justify-center p-6">
            <p className="text-sm text-muted-foreground">Chat opens once you select an article</p>
          </div>
        )
      }
    />
  );
}
