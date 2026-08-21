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
import { Panel, Group, Separator } from "react-resizable-panels";

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

  return (
    <Group orientation="horizontal" id="asterism-workspace-layout" className="flex min-h-0 flex-1">
      <Panel defaultSize={25} minSize={18} className="min-w-0">
        {deleteError && (
          <p className="border-b border-border bg-red-50 p-2 text-xs text-destructive dark:bg-red-950/40">
            {deleteError}
          </p>
        )}
        <LibraryColumn
          sources={sources}
          selectedId={selectedId}
          onSelect={handleSelect}
          onDelete={handleDelete}
          onCreated={handleCreated}
          onAdded={handleAdded}
        />
      </Panel>

      <Separator className="workspace-resize-handle" />

      <Panel defaultSize={50} className="min-w-0">
        {selectedId ? (
          <ReaderPane sourceId={selectedId} onMarkedRead={handleMarkedRead} onHighlightSelected={setAttachedHighlight} />
        ) : (
          <div className="flex h-full items-center justify-center p-6">
            <p className="text-sm text-muted-foreground">Select an article to read</p>
          </div>
        )}
      </Panel>

      <Separator className="workspace-resize-handle" />

      <Panel defaultSize={25} minSize={20} className="min-w-0">
        {selectedId ? (
          <ChatPanel
            sourceId={selectedId}
            attachedHighlight={attachedHighlight}
            onClearAttachedHighlight={() => setAttachedHighlight(null)}
          />
        ) : (
          <div className="flex h-full items-center justify-center p-6">
            <p className="text-sm text-muted-foreground">Chat opens once you select an article</p>
          </div>
        )}
      </Panel>
    </Group>
  );
}
