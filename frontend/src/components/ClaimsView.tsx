import { Claim } from "@/lib/api";
import { AnalysisSectionError } from "./AnalysisSectionError";
import { FeedbackControls } from "./FeedbackControls";
import { useFeedback } from "@/lib/useFeedback";

const TYPE_LABELS: Record<Claim["type"], string> = {
  factual: "Factual",
  opinion: "Opinion",
  prediction: "Prediction",
};

export function ClaimsView({
  sourceId,
  claims,
  error,
  onRetry,
  retrying,
}: {
  sourceId: string;
  claims: Claim[] | null;
  error: string | null;
  onRetry: () => void;
  retrying: boolean;
}) {
  const { find, upsertLocal } = useFeedback(sourceId);

  if (!claims) {
    return <AnalysisSectionError message={error ?? "Unknown error"} onRetry={onRetry} retrying={retrying} />;
  }

  if (claims.length === 0) {
    return <p className="text-sm text-muted-foreground">No claims extracted.</p>;
  }

  return (
    <ul className="flex flex-col gap-4">
      {claims.map((claim) => (
        <li key={claim.id} className="rounded-lg border border-border p-4">
          <span className="mb-2 inline-block rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
            {TYPE_LABELS[claim.type]}
          </span>
          <p className="text-sm text-foreground">{claim.text}</p>
          <blockquote className="mt-2 border-l-2 border-border pl-3 text-xs italic text-muted-foreground">
            {claim.source_quote}
          </blockquote>
          <div className="mt-2">
            <FeedbackControls
              sourceId={sourceId}
              kind="claim"
              content={claim.source_quote}
              existingFeedback={find("claim", undefined, claim.source_quote)}
              onFeedbackChange={upsertLocal}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
