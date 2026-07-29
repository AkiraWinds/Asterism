"use client";

// Floating toolbar that appears when the user selects text inside a given
// container (e.g. the source's "Original" tab content). It auto-attaches the
// selected text to the chat panel via `onHighlightSelected`, and renders two
// currently-disabled action buttons ("Save as note" / "Add comment") that are
// wired up in a later phase.
import { useEffect, useState } from "react";

export function SelectionToolbar({
  containerRef,
  onHighlightSelected,
}: {
  containerRef: React.RefObject<HTMLElement | null>;
  onHighlightSelected: (text: string | null) => void;
}) {
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);
  const [selectedText, setSelectedText] = useState("");

  useEffect(() => {
    function handleSelectionChange() {
      const selection = window.getSelection();
      const container = containerRef.current;
      const text = selection?.toString().trim() ?? "";

      if (!selection || !container || text.length === 0 || selection.rangeCount === 0) {
        setPosition(null);
        setSelectedText("");
        onHighlightSelected(null);
        return;
      }

      const range = selection.getRangeAt(0);
      if (!container.contains(range.commonAncestorContainer)) {
        setPosition(null);
        setSelectedText("");
        onHighlightSelected(null);
        return;
      }

      const rect = range.getBoundingClientRect();
      setPosition({ top: rect.top + window.scrollY - 40, left: rect.left + window.scrollX });
      setSelectedText(text);
      onHighlightSelected(text);
    }

    document.addEventListener("selectionchange", handleSelectionChange);
    return () => document.removeEventListener("selectionchange", handleSelectionChange);
  }, [containerRef, onHighlightSelected]);

  if (!position || !selectedText) return null;

  return (
    <div
      className="fixed z-10 flex gap-1 rounded-md border border-neutral-200 bg-white px-2 py-1 shadow-md dark:border-neutral-700 dark:bg-neutral-800"
      style={{ top: position.top, left: position.left }}
    >
      <button
        type="button"
        disabled
        title="Coming in Phase 6"
        className="cursor-not-allowed rounded px-2 py-1 text-xs text-neutral-400 dark:text-neutral-500"
      >
        Save as note
      </button>
      <button
        type="button"
        disabled
        title="Coming in Phase 6"
        className="cursor-not-allowed rounded px-2 py-1 text-xs text-neutral-400 dark:text-neutral-500"
      >
        Add comment
      </button>
    </div>
  );
}
