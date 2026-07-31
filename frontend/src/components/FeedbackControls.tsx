"use client";

// Per-item feedback (up/down) + promote-to-graph action, shared across
// DigestView (concepts), ClaimsView, and CritiqueView. The parent view owns
// fetching feedback.json once and matching each rendered item to its entry
// by (kind, section, content) — this component only renders state and fires
// the two mutations (PUT rating, POST promote). See
// docs/superpowers/specs/2026-08-01-analysis-feedback-promote-design.md.
import { useState } from "react";
import { Feedback, FeedbackKind, putFeedback, promoteFeedback } from "@/lib/api";

export function FeedbackControls({
  sourceId,
  kind,
  content,
  section,
  term,
  existingFeedback,
  onFeedbackChange,
}: {
  sourceId: string;
  kind: FeedbackKind;
  content: string;
  section?: string;
  term?: string;
  existingFeedback: Feedback | null;
  onFeedbackChange: (updated: Feedback) => void;
}) {
  const [isRating, setIsRating] = useState(false);
  const [isPromoting, setIsPromoting] = useState(false);
  const [promoteError, setPromoteError] = useState<string | null>(null);

  async function handleRate(rating: "up" | "down") {
    if (isRating) return;
    setIsRating(true);
    try {
      const updated = await putFeedback(sourceId, kind, content, rating, { section, term });
      onFeedbackChange(updated);
    } finally {
      setIsRating(false);
    }
  }

  async function handlePromote() {
    if (isPromoting || !existingFeedback) return;
    setIsPromoting(true);
    setPromoteError(null);
    try {
      await promoteFeedback(sourceId, existingFeedback.id);
      onFeedbackChange({ ...existingFeedback, promoted: true, promoted_at: new Date().toISOString() });
    } catch (err) {
      setPromoteError(err instanceof Error ? err.message : "Failed to promote");
    } finally {
      setIsPromoting(false);
    }
  }

  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <button
        type="button"
        aria-label="Good"
        disabled={isRating}
        onClick={() => handleRate("up")}
        className={`rounded px-1 ${
          existingFeedback?.rating === "up"
            ? "text-green-600 dark:text-green-400"
            : "text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300"
        }`}
      >
        &#128077;
      </button>
      <button
        type="button"
        aria-label="Bad"
        disabled={isRating}
        onClick={() => handleRate("down")}
        className={`rounded px-1 ${
          existingFeedback?.rating === "down"
            ? "text-red-600 dark:text-red-400"
            : "text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300"
        }`}
      >
        &#128078;
      </button>
      {existingFeedback?.rating === "up" && (
        <button
          type="button"
          disabled={isPromoting || existingFeedback.promoted}
          onClick={handlePromote}
          className="rounded border border-neutral-300 px-1.5 py-0.5 text-neutral-600 disabled:opacity-60 dark:border-neutral-700 dark:text-neutral-400"
        >
          {existingFeedback.promoted ? "Promoted" : isPromoting ? "Promoting..." : "Promote to graph"}
        </button>
      )}
      {promoteError && <span className="text-red-600 dark:text-red-400">{promoteError}</span>}
    </span>
  );
}
