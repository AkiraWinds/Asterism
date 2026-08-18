import { Critique } from "@/lib/api";
import { AnalysisSectionError } from "./AnalysisSectionError";
import { FeedbackControls } from "./FeedbackControls";
import { useFeedback } from "@/lib/useFeedback";

const SECTIONS: { key: keyof Critique; label: string }[] = [
  { key: "hidden_assumptions", label: "Hidden assumptions" },
  { key: "potential_issues", label: "Potential issues" },
  { key: "needs_verification", label: "Needs verification" },
  { key: "bias_indicators", label: "Bias indicators" },
];

export function CritiqueView({
  sourceId,
  critique,
  error,
  onRetry,
  retrying,
}: {
  sourceId: string;
  critique: Critique | null;
  error: string | null;
  onRetry: () => void;
  retrying: boolean;
}) {
  const { find, upsertLocal } = useFeedback(sourceId);

  if (!critique) {
    return <AnalysisSectionError message={error ?? "Unknown error"} onRetry={onRetry} retrying={retrying} />;
  }

  return (
    <div className="flex flex-col gap-4">
      {SECTIONS.map(({ key, label }) => {
        const items = critique[key];
        if (items.length === 0) return null;
        return (
          <div key={key}>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</h3>
            <ul className="mt-2 flex flex-col gap-2 pl-5 text-sm text-foreground">
              {items.map((item, i) => (
                <li key={i} className="list-disc">
                  {item}
                  <div className="mt-1">
                    <FeedbackControls
                      sourceId={sourceId}
                      kind="critique"
                      content={item}
                      section={key}
                      existingFeedback={find("critique", key, item)}
                      onFeedbackChange={upsertLocal}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
