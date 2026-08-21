"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AnalysisResult } from "@/lib/api";
import { DigestView } from "./DigestView";
import { CritiqueView } from "./CritiqueView";
import { ClaimsView } from "./ClaimsView";

export type AnalysisTab = "reader" | "digest" | "critique" | "claims";

const TABS: { id: AnalysisTab; label: string }[] = [
  { id: "reader", label: "Reader" },
  { id: "digest", label: "Digest" },
  { id: "critique", label: "Critique" },
  { id: "claims", label: "Claims" },
];

export function AnalysisTabs({
  sourceId,
  content,
  analysis,
  onRetry,
  retrying,
  active,
  onTabChange,
}: {
  sourceId: string;
  content: string;
  analysis: AnalysisResult;
  onRetry: () => void;
  retrying: boolean;
  active: AnalysisTab;
  onTabChange: (tab: AnalysisTab) => void;
}) {
  return (
    <div className="mt-6">
      <div className="flex gap-1 border-b border-border">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => onTabChange(tab.id)}
            className={`px-3 py-2 text-sm font-medium ${
              active === tab.id ? "border-b-2 border-accent text-accent" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="mt-4">
        {active === "reader" && (
          <div className="prose prose-sm prose-neutral dark:prose-invert max-w-none rounded-lg border border-border bg-card p-3 @min-[560px]:p-5 @min-[720px]:prose-base">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
        )}
        {active === "digest" && (
          <DigestView
            sourceId={sourceId}
            digest={analysis.digest}
            error={analysis.digest_error}
            onRetry={onRetry}
            retrying={retrying}
          />
        )}
        {active === "critique" && (
          <CritiqueView
            sourceId={sourceId}
            critique={analysis.critique}
            error={analysis.critique_error}
            onRetry={onRetry}
            retrying={retrying}
          />
        )}
        {active === "claims" && (
          <ClaimsView
            sourceId={sourceId}
            claims={analysis.claims}
            error={analysis.claims_error}
            onRetry={onRetry}
            retrying={retrying}
          />
        )}
      </div>
    </div>
  );
}
