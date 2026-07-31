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

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
  attached_highlight: string | null;
  truncated: boolean;
  created_at: string;
}

export interface UserHighlight {
  id: string;
  source_quote: string;
  note: string | null;
  created_at: string;
}

export interface GraphConceptNode {
  id: string;
  term: string;
  definition: string;
  self_relevant: boolean;
}

export interface GraphEdge {
  id: string;
  from_id: string;
  to_id: string;
  type: "related" | "contradicts" | "extends";
  summary: string;
}

export interface GraphData {
  nodes: GraphConceptNode[];
  edges: GraphEdge[];
}

export interface HighlightProcessResult {
  highlight: UserHighlight;
  concepts: GraphConceptNode[];
  edges: GraphEdge[];
  queued: unknown[];
  extraction_error: string | null;
  duplicate: boolean;
}

// Backend failures return a structured body — either an AgentErrorResponse
// ({ message }) from the agent-integration paths, or a plain FastAPI
// HTTPException ({ detail }) from everything else. Prefer whichever is
// present and fall back to a hardcoded default if the body isn't JSON or
// has neither field.
async function extractErrorMessage(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    return body?.message ?? body?.detail ?? fallback;
  } catch {
    return fallback;
  }
}

export async function listSources(): Promise<SourceSummary[]> {
  const res = await fetch(`${BACKEND_URL}/sources`, { cache: "no-store" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to list sources"));
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
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to create source"));
  return res.json();
}

export async function getSource(id: string): Promise<SourceDetail> {
  const res = await fetch(`${BACKEND_URL}/sources/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to get source"));
  return res.json();
}

export async function analyzeSource(id: string): Promise<AnalysisResult> {
  const res = await fetch(`${BACKEND_URL}/sources/${id}/analyze`, { method: "POST" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to analyze source"));
  return res.json();
}

export async function getChatHistory(id: string): Promise<ChatTurn[]> {
  const res = await fetch(`${BACKEND_URL}/sources/${id}/chat`, { cache: "no-store" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to load chat history"));
  const body = await res.json();
  return body.turns;
}

// Native EventSource can't send a POST body, so the SSE stream is read manually
// via fetch()'s ReadableStream: each chunk is decoded, split into "\n\n"-delimited
// frames, and dispatched by its "event:" line (default "message").
export async function streamChatMessage(
  id: string,
  message: string,
  attachedHighlight: string | null,
  onChunk: (text: string) => void
): Promise<{ truncated: boolean; errorMessage: string | null }> {
  const res = await fetch(`${BACKEND_URL}/sources/${id}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, attached_highlight: attachedHighlight }),
  });
  if (!res.ok || !res.body) {
    throw new Error(await extractErrorMessage(res, "Failed to send chat message"));
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let errorMessage: string | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      let event = "message";
      let data: { text?: string; message?: string } = {};
      for (const line of frame.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice("event: ".length);
        else if (line.startsWith("data: ")) data = JSON.parse(line.slice("data: ".length));
      }

      if (event === "message" && data.text) onChunk(data.text);
      if (event === "error") errorMessage = data.message ?? "Response interrupted";

      boundary = buffer.indexOf("\n\n");
    }
  }

  return { truncated: errorMessage !== null, errorMessage };
}

export async function saveHighlight(
  sourceId: string,
  sourceQuote: string,
  note: string | null
): Promise<HighlightProcessResult> {
  const res = await fetch(`${BACKEND_URL}/sources/${sourceId}/highlights`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_quote: sourceQuote, note }),
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to save highlight"));
  return res.json();
}

export async function getHighlights(sourceId: string): Promise<UserHighlight[]> {
  const res = await fetch(`${BACKEND_URL}/sources/${sourceId}/highlights`, { cache: "no-store" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to load highlights"));
  const body = await res.json();
  return body.highlights;
}

export async function getGraph(): Promise<GraphData> {
  const res = await fetch(`${BACKEND_URL}/graph`, { cache: "no-store" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to load graph"));
  return res.json();
}
