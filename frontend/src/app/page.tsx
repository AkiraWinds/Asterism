"use client";

// The unified workspace: Library/Radar list (column 1), reader+analysis for
// the selected source (column 2+3 combined), and chat scoped to that source
// (column 4). Replaces the old separate home list, /sources/[id], and /radar
// pages — see docs/superpowers/specs/2026-08-18-unified-reader-layout-design.md.
import { useEffect, useState } from "react";
import { deleteSource, listSources, SourceSummary } from "@/lib/api";
import { LibraryColumn } from "@/components/LibraryColumn";
import { ReaderPane } from "@/components/ReaderPane";
import { ChatPanel } from "@/components/ChatPanel";

export default function WorkspacePage() {
  const [sources, setSources] = useState<SourceSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [attachedHighlight, setAttachedHighlight] = useState<string | null>(null);

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
    await deleteSource(id);
    setSources((prev) => prev.filter((s) => s.id !== id));
    if (selectedId === id) setSelectedId(null);
  }

  function handleCreated(source: SourceSummary) {
    setSources((prev) => [source, ...prev]);
    handleSelect(source.id);
  }

  function handleMarkedRead(id: string) {
    setSources((prev) => prev.map((s) => (s.id === id ? { ...s, read_at: new Date().toISOString() } : s)));
  }

  return (
    <div className="flex min-h-0 flex-1">
      <div className="w-1/4 min-w-[240px] border-r border-border">
        <LibraryColumn
          sources={sources}
          selectedId={selectedId}
          onSelect={handleSelect}
          onDelete={handleDelete}
          onCreated={handleCreated}
        />
      </div>

      <div className="w-1/2 border-r border-border">
        {selectedId ? (
          <ReaderPane sourceId={selectedId} onMarkedRead={handleMarkedRead} onHighlightSelected={setAttachedHighlight} />
        ) : (
          <div className="flex h-full items-center justify-center p-6">
            <p className="text-sm text-muted-foreground">Select an article to read</p>
          </div>
        )}
      </div>

      <div className="w-1/4 min-w-[280px]">
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
      </div>
    </div>
  );
}
