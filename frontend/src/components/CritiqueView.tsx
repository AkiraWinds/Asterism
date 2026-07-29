import { Critique } from "@/lib/api";
import { AnalysisSectionError } from "./AnalysisSectionError";

const SECTIONS: { key: keyof Critique; label: string }[] = [
  { key: "hidden_assumptions", label: "Hidden assumptions" },
  { key: "potential_issues", label: "Potential issues" },
  { key: "needs_verification", label: "Needs verification" },
  { key: "bias_indicators", label: "Bias indicators" },
];

export function CritiqueView({
  critique,
  error,
  onRetry,
  retrying,
}: {
  critique: Critique | null;
  error: string | null;
  onRetry: () => void;
  retrying: boolean;
}) {
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
            <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
              {label}
            </h3>
            <ul className="mt-2 list-disc pl-5 text-sm text-neutral-800 dark:text-neutral-200">
              {items.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
