"use client";

import { useState } from "react";
import { SourceSummary } from "@/lib/api";
import { AddSourceBar } from "./AddSourceBar";
import { SourceListSection } from "./SourceListSection";
import { RadarPanel } from "./RadarPanel";

type Tab = "library" | "radar";

// Column 1 of the unified workspace: Library (add-source control + To
// Read/Read list) and Radar (discovered feed items) as tabs, kept separate
// rather than merged into one scroll — see the "Column 1" rationale in
// docs/superpowers/specs/2026-08-18-unified-reader-layout-design.md.
export function LibraryColumn({
  sources,
  selectedId,
  onSelect,
  onDelete,
  onCreated,
}: {
  sources: SourceSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onCreated: (source: SourceSummary) => void;
}) {
  const [tab, setTab] = useState<Tab>("library");

  return (
    <div className="flex h-full flex-col">
      <div className="flex border-b border-border">
        <button
          type="button"
          onClick={() => setTab("library")}
          className={`flex-1 border-b-2 px-3 py-2 text-sm font-medium ${
            tab === "library"
              ? "border-accent text-accent"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Library
        </button>
        <button
          type="button"
          onClick={() => setTab("radar")}
          className={`flex-1 border-b-2 px-3 py-2 text-sm font-medium ${
            tab === "radar"
              ? "border-accent text-accent"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Radar
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {tab === "library" ? (
          <div className="flex flex-col gap-4 p-4">
            <AddSourceBar onCreated={onCreated} />
            <SourceListSection sources={sources} selectedId={selectedId} onSelect={onSelect} onDelete={onDelete} />
          </div>
        ) : (
          <RadarPanel />
        )}
      </div>
    </div>
  );
}
