"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AnalysisResult } from "@/lib/api";
import { DigestView } from "./DigestView";
import { CritiqueView } from "./CritiqueView";
import { ClaimsView } from "./ClaimsView";

type Tab = "original" | "digest" | "critique" | "claims";

const TABS: { id: Tab; label: string }[] = [
  { id: "original", label: "Original" },
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
}: {
  sourceId: string;
  content: string;
  analysis: AnalysisResult;
  onRetry: () => void;
  retrying: boolean;
}) {
  const [active, setActive] = useState<Tab>("original");

  return (
    <div className="mt-6">
      <div className="flex gap-1 border-b border-neutral-200 dark:border-neutral-800">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActive(tab.id)}
            className={`px-3 py-2 text-sm font-medium ${
              active === tab.id
                ? "border-b-2 border-neutral-900 text-neutral-900 dark:border-neutral-100 dark:text-neutral-100"
                : "text-neutral-500 hover:text-neutral-800 dark:text-neutral-400 dark:hover:text-neutral-200"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="mt-4">
        {active === "original" && (
          <div className="prose prose-sm prose-neutral dark:prose-invert max-w-none rounded-lg border border-neutral-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900">
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
