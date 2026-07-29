const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export interface Highlight {
  id: string;
  text: string;
  type: "insight" | "fact" | "actionable";
  source_quote: string;
}

export interface Concept {
  id: string;
  term: string;
  definition: string;
}

export interface Triage {
  score: number;
  action: "must_read" | "worth_reading" | "skim" | "summary_only" | "skip";
  reason: string;
  read_time_minutes: number;
  density: number;
  originality: number;
}

export interface Digest {
  summary: string;
  highlights: Highlight[];
  concepts: Concept[];
  structure: string[];
}

export interface Critique {
  hidden_assumptions: string[];
  potential_issues: string[];
  needs_verification: string[];
  bias_indicators: string[];
}

export interface Claim {
  id: string;
  text: string;
  type: "factual" | "opinion" | "prediction";
  source_quote: string;
}

export interface Connection {
  id: string;
  type: "redundant" | "contradicts" | "related";
  summary: string;
  details: string;
  related_source_ids: string[];
  claim_refs: string[];
}

export interface AnalysisResult {
  triage: Triage | null;
  triage_error: string | null;
  digest: Digest | null;
  digest_error: string | null;
  critique: Critique | null;
  critique_error: string | null;
  claims: Claim[] | null;
  claims_error: string | null;
  connections: Connection[];
  analyzed_at: string;
}

export interface SourceSummary {
  id: string;
  title: string;
  created_at: string;
}

export interface SourceDetail extends SourceSummary {
  content: string;
  analysis: AnalysisResult | null;
}

export async function listSources(): Promise<SourceSummary[]> {
  const res = await fetch(`${BACKEND_URL}/sources`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to list sources");
  return res.json();
}

export async function createSource(args: {
  title?: string;
  content?: string;
  url?: string;
}): Promise<SourceDetail> {
  const res = await fetch(`${BACKEND_URL}/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(args),
  });
  if (!res.ok) throw new Error("Failed to create source");
  return res.json();
}

export async function getSource(id: string): Promise<SourceDetail> {
  const res = await fetch(`${BACKEND_URL}/sources/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to get source");
  return res.json();
}

export async function analyzeSource(id: string): Promise<AnalysisResult> {
  const res = await fetch(`${BACKEND_URL}/sources/${id}/analyze`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to analyze source");
  return res.json();
}
