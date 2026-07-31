import { Digest } from "@/lib/api";
import { AnalysisSectionError } from "./AnalysisSectionError";
import { FeedbackControls } from "./FeedbackControls";
import { useFeedback } from "@/lib/useFeedback";

export function DigestView({
  sourceId,
  digest,
  error,
  onRetry,
  retrying,
}: {
  sourceId: string;
  digest: Digest | null;
  error: string | null;
  onRetry: () => void;
  retrying: boolean;
}) {
  const { find, upsertLocal } = useFeedback(sourceId);

  if (!digest) {
    return <AnalysisSectionError message={error ?? "Unknown error"} onRetry={onRetry} retrying={retrying} />;
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm leading-relaxed text-neutral-800 dark:text-neutral-200">{digest.summary}</p>

      {digest.highlights.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
            Highlights
          </h3>
          <ul className="mt-2 flex flex-col gap-2">
            {digest.highlights.map((h) => (
              <li key={h.id} className="text-sm text-neutral-800 dark:text-neutral-200">
                <span className="mr-2 rounded bg-neutral-100 px-1.5 py-0.5 text-xs text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400">
                  {h.type}
                </span>
                {h.text}
              </li>
            ))}
          </ul>
        </div>
      )}

      {digest.concepts.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
            Concepts
          </h3>
          <ul className="mt-2 flex flex-col gap-2">
            {digest.concepts.map((c) => (
              <li key={c.id} className="flex flex-col gap-1 text-sm text-neutral-800 dark:text-neutral-200">
                <div>
                  <span className="font-medium">{c.term}</span> — {c.definition}
                </div>
                <FeedbackControls
                  sourceId={sourceId}
                  kind="concept"
                  content={c.definition}
                  term={c.term}
                  existingFeedback={find("concept", undefined, c.definition)}
                  onFeedbackChange={upsertLocal}
                />
              </li>
            ))}
          </ul>
        </div>
      )}

      {digest.structure.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
            Structure
          </h3>
          <ol className="mt-2 list-decimal pl-5 text-sm text-neutral-800 dark:text-neutral-200">
            {digest.structure.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
