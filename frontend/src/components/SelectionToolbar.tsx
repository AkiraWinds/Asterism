"use client";

// Floating toolbar that appears when the user selects text inside a given
// container (e.g. the source's "Original" tab content). It auto-attaches the
// selected text to the chat panel via `onHighlightSelected`, and offers two
// highlight-saving actions that both call POST /sources/{id}/highlights:
// "Save as note" (no note text) and "Add comment" (opens an inline field for
// the user's own note first). Both persist the same underlying record with
// note: null vs note: "<text>" — see
// docs/superpowers/specs/2026-07-30-knowledge-graph-phase6b-design.md.
//
// `onHighlightSelected` is only ever called with a genuinely new non-empty
// in-container selection — never with `null`. The attached highlight is a
// "latched" value owned by the parent; clearing it is an explicit user action
// (dismiss button / after send), not something that fires just because the
// live selection collapsed (e.g. clicking into the chat input). See
// docs/superpowers/plans/2026-07-29-chat-copilot.md final-review fix notes.
import { useEffect, useState } from "react";
import { saveHighlight } from "@/lib/api";

export function SelectionToolbar({
  sourceId,
  containerRef,
  onHighlightSelected,
}: {
  sourceId: string;
  containerRef: React.RefObject<HTMLElement | null>;
  onHighlightSelected: (text: string) => void;
}) {
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);
  const [selectedText, setSelectedText] = useState("");
  const [commentMode, setCommentMode] = useState(false);
  const [commentText, setCommentText] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    function handleSelectionChange() {
      const selection = window.getSelection();
      const container = containerRef.current;
      const text = selection?.toString().trim() ?? "";

      if (!selection || !container || text.length === 0 || selection.rangeCount === 0) {
        setPosition(null);
        setSelectedText("");
        setCommentMode(false);
        return;
      }

      const range = selection.getRangeAt(0);
      if (!container.contains(range.commonAncestorContainer)) {
        setPosition(null);
        setSelectedText("");
        setCommentMode(false);
        return;
      }

      const rect = range.getBoundingClientRect();
      setPosition({ top: Math.max(8, rect.top - 40), left: rect.left });
      setSelectedText(text);
      onHighlightSelected(text);
    }

    document.addEventListener("selectionchange", handleSelectionChange);
    return () => document.removeEventListener("selectionchange", handleSelectionChange);
  }, [containerRef, onHighlightSelected]);

  async function handleSaveAsNote() {
    setSaveError(null);
    try {
      await saveHighlight(sourceId, selectedText, null);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save highlight");
    }
  }

  async function handleSubmitComment() {
    setSaveError(null);
    try {
      await saveHighlight(sourceId, selectedText, commentText.trim() || null);
      setCommentMode(false);
      setCommentText("");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save highlight");
    }
  }

  if (!position || !selectedText) return null;

  return (
    <div
      className="fixed z-10 flex flex-col gap-1 rounded-md border border-neutral-200 bg-white px-2 py-1 shadow-md dark:border-neutral-700 dark:bg-neutral-800"
      style={{ top: position.top, left: position.left }}
    >
      {commentMode ? (
        <div className="flex gap-1">
          <input
            type="text"
            autoFocus
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSubmitComment();
            }}
            placeholder="Your note…"
            className="rounded border border-neutral-300 px-2 py-1 text-xs dark:border-neutral-600 dark:bg-neutral-900"
          />
          <button type="button" onClick={handleSubmitComment} className="rounded px-2 py-1 text-xs text-neutral-700 dark:text-neutral-200">
            Save
          </button>
        </div>
      ) : (
        <div className="flex gap-1">
          <button type="button" onClick={handleSaveAsNote} className="rounded px-2 py-1 text-xs text-neutral-700 hover:bg-neutral-100 dark:text-neutral-200 dark:hover:bg-neutral-700">
            Save as note
          </button>
          <button type="button" onClick={() => setCommentMode(true)} className="rounded px-2 py-1 text-xs text-neutral-700 hover:bg-neutral-100 dark:text-neutral-200 dark:hover:bg-neutral-700">
            Add comment
          </button>
        </div>
      )}
      {saveError && <p className="px-2 text-xs text-red-600 dark:text-red-400">{saveError}</p>}
    </div>
  );
}
