"use client";

import { X } from "@phosphor-icons/react";
import { SourceSummary } from "@/lib/api";

function SourceRow({
  source,
  selected,
  onSelect,
  onDelete,
}: {
  source: SourceSummary;
  selected: boolean;
  onSelect: () => void;
  onDelete: () => void;
}) {
  return (
    <li
      className={`flex items-center justify-between gap-2 rounded-md px-2 py-2 text-sm ${
        selected ? "bg-accent-secondary/30 text-foreground" : "text-foreground hover:bg-muted"
      }`}
    >
      <button type="button" onClick={onSelect} className="flex-1 truncate text-left">
        {source.title}
      </button>
      <button
        type="button"
        onClick={onDelete}
        aria-label={`Delete ${source.title}`}
        className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-red-50 hover:text-destructive dark:hover:bg-red-950/40"
      >
        <X size={16} weight="thin" />
      </button>
    </li>
  );
}

// Column 1's Library-tab list, split into To Read / Read by whether
// read_at is set — see the read/unread design in
// docs/superpowers/specs/2026-08-18-unified-reader-layout-design.md.
export function SourceListSection({
  sources,
  selectedId,
  onSelect,
  onDelete,
}: {
  sources: SourceSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const toRead = sources.filter((s) => !s.read_at);
  const read = sources.filter((s) => s.read_at);

  function handleDelete(id: string, title: string) {
    if (!window.confirm(`Delete "${title}"? This can't be undone.`)) return;
    onDelete(id);
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="px-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">To Read</h2>
        <ul className="mt-1 flex flex-col gap-0.5">
          {toRead.map((s) => (
            <SourceRow
              key={s.id}
              source={s}
              selected={s.id === selectedId}
              onSelect={() => onSelect(s.id)}
              onDelete={() => handleDelete(s.id, s.title)}
            />
          ))}
        </ul>
      </div>
      <div>
        <h2 className="px-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Read</h2>
        <ul className="mt-1 flex flex-col gap-0.5">
          {read.map((s) => (
            <SourceRow
              key={s.id}
              source={s}
              selected={s.id === selectedId}
              onSelect={() => onSelect(s.id)}
              onDelete={() => handleDelete(s.id, s.title)}
            />
          ))}
        </ul>
      </div>
    </div>
  );
}
