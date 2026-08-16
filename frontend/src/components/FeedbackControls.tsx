"use client";

// Per-item feedback (up/down) + promote-to-graph action, shared across
// DigestView (concepts), ClaimsView, and CritiqueView. The parent view owns
// fetching feedback.json once and matching each rendered item to its entry
// by (kind, section, content) — this component only renders state and fires
// the two mutations (PUT rating, POST promote). See
// docs/superpowers/specs/2026-08-01-analysis-feedback-promote-design.md.
import { useState } from "react";
import { ThumbsDown, ThumbsUp } from "@phosphor-icons/react";
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
  // Shared between rating and promoting: both mutations can fail (network,
  // validation, or — for promote — a graph pipeline error reported via HTTP
  // 200 + extraction_error), and both should surface visibly rather than
  // failing silently.
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

  async function handleRate(rating: "up" | "down") {
    if (isRating) return;
    setIsRating(true);
    setFeedbackError(null);
    try {
      const updated = await putFeedback(sourceId, kind, content, rating, { section, term });
      onFeedbackChange(updated);
    } catch (err) {
      setFeedbackError(err instanceof Error ? err.message : "Failed to rate");
    } finally {
      setIsRating(false);
    }
  }

  async function handlePromote() {
    if (isPromoting || !existingFeedback) return;
    setIsPromoting(true);
    setFeedbackError(null);
    try {
      const result = await promoteFeedback(sourceId, existingFeedback.id);
      // The backend returns HTTP 200 with extraction_error set (not a 4xx/5xx)
      // when the highlight was saved and feedback marked promoted, but the
      // graph pipeline itself failed (ConfigError/ProviderError) — so nothing
      // was actually added to the graph. promoted: true still correctly
      // reflects the backend's persisted state; the error just needs to be
      // surfaced alongside it rather than silently dropped.
      onFeedbackChange({ ...existingFeedback, promoted: true, promoted_at: new Date().toISOString() });
      if (result.extraction_error) {
        setFeedbackError(result.extraction_error);
      }
    } catch (err) {
      setFeedbackError(err instanceof Error ? err.message : "Failed to promote");
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
          existingFeedback?.rating === "up" ? "text-green-600 dark:text-green-400" : "text-muted-foreground hover:text-foreground"
        }`}
      >
        <ThumbsUp size={14} weight="thin" />
      </button>
      <button
        type="button"
        aria-label="Bad"
        disabled={isRating}
        onClick={() => handleRate("down")}
        className={`rounded px-1 ${existingFeedback?.rating === "down" ? "text-destructive" : "text-muted-foreground hover:text-foreground"}`}
      >
        <ThumbsDown size={14} weight="thin" />
      </button>
      {existingFeedback?.rating === "up" && (
        <button
          type="button"
          disabled={isPromoting || existingFeedback.promoted}
          onClick={handlePromote}
          className="rounded border border-border px-1.5 py-0.5 text-muted-foreground disabled:opacity-60"
        >
          {existingFeedback.promoted ? "Promoted" : isPromoting ? "Promoting..." : "Promote to graph"}
        </button>
      )}
      {feedbackError && <span className="text-destructive">{feedbackError}</span>}
    </span>
  );
}
