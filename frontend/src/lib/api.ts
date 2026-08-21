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
  read_at: string | null;
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

export type FeedbackKind = "concept" | "claim" | "critique";

export interface Feedback {
  id: string;
  kind: FeedbackKind;
  section: string | null;
  content: string;
  term: string | null;
  rating: "up" | "down";
  promoted: boolean;
  promoted_at: string | null;
  created_at: string;
  updated_at: string;
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

export async function deleteSource(id: string): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/sources/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to delete source"));
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

export async function markSourceRead(id: string): Promise<{ read_at: string }> {
  const res = await fetch(`${BACKEND_URL}/sources/${id}/read`, { method: "POST" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to mark source read"));
  return res.json();
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  turn_count: number;
}

export async function listConversations(sourceId: string): Promise<ConversationSummary[]> {
  const res = await fetch(`${BACKEND_URL}/sources/${sourceId}/chats`, { cache: "no-store" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to load conversations"));
  return res.json();
}

export async function createConversation(sourceId: string): Promise<ConversationSummary> {
  const res = await fetch(`${BACKEND_URL}/sources/${sourceId}/chats`, { method: "POST" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to create new chat"));
  return res.json();
}

// Returns the auto-created replacement conversation if this deleted the last
// remaining thread (a source always keeps at least one), else null.
export async function deleteConversation(
  sourceId: string,
  conversationId: string
): Promise<ConversationSummary | null> {
  const res = await fetch(`${BACKEND_URL}/sources/${sourceId}/chats/${conversationId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to delete chat"));
  const body = await res.json();
  return body.replacement;
}

export async function getChatHistory(id: string, conversationId: string): Promise<ChatTurn[]> {
  const res = await fetch(`${BACKEND_URL}/sources/${id}/chat?conversation_id=${conversationId}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to load chat history"));
  const body = await res.json();
  return body.turns;
}

// Native EventSource can't send a POST body, so the SSE stream is read manually
// via fetch()'s ReadableStream: each chunk is decoded, split into "\n\n"-delimited
// frames, and dispatched by its "event:" line (default "message").
export async function streamChatMessage(
  id: string,
  conversationId: string,
  message: string,
  attachedHighlight: string | null,
  onChunk: (text: string) => void
): Promise<{ truncated: boolean; errorMessage: string | null }> {
  const res = await fetch(`${BACKEND_URL}/sources/${id}/chat?conversation_id=${conversationId}`, {
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

export interface ReviewQueueEntry {
  id: string;
  candidate_concept_id: string;
  existing_concept_id: string;
  llm_judgment: string;
  proposed_edge_type: "related" | "contradicts" | "extends";
  created_at: string;
}

export async function getReviewQueue(): Promise<ReviewQueueEntry[]> {
  const res = await fetch(`${BACKEND_URL}/graph/review-queue`, { cache: "no-store" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to load review queue"));
  return res.json();
}

export async function resolveReviewQueueEntry(
  entryId: string,
  action: "merge" | "keep_separate"
): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/graph/review-queue/${entryId}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to resolve review queue entry"));
}

export interface WikiPageAspect {
  slug: string;
  term: string;
}

export interface WikiPage {
  slug: string;
  term: string;
  updated_at: string;
  body: string;
  aspects: WikiPageAspect[];
}

export async function getWikiPageByConceptId(conceptId: string): Promise<WikiPage | null> {
  const res = await fetch(`${BACKEND_URL}/wiki/pages/${conceptId}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to load wiki page"));
  return res.json();
}

export async function getWikiPageBySlug(slug: string): Promise<WikiPage | null> {
  const res = await fetch(`${BACKEND_URL}/wiki/pages/by-slug/${slug}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to load wiki page"));
  return res.json();
}

export async function getFeedback(sourceId: string): Promise<Feedback[]> {
  const res = await fetch(`${BACKEND_URL}/sources/${sourceId}/feedback`, { cache: "no-store" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to load feedback"));
  const body = await res.json();
  return body.entries;
}

export async function putFeedback(
  sourceId: string,
  kind: FeedbackKind,
  content: string,
  rating: "up" | "down",
  options: { section?: string; term?: string } = {}
): Promise<Feedback> {
  const res = await fetch(`${BACKEND_URL}/sources/${sourceId}/feedback`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      kind,
      content,
      rating,
      section: options.section ?? null,
      term: options.term ?? null,
    }),
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to save feedback"));
  return res.json();
}

export async function promoteFeedback(sourceId: string, feedbackId: string): Promise<HighlightProcessResult> {
  const res = await fetch(`${BACKEND_URL}/sources/${sourceId}/feedback/${feedbackId}/promote`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to promote to graph"));
  return res.json();
}

export interface FeedSource {
  id: string;
  name: string;
  url: string;
  enabled: boolean;
  last_fetched_at: string | null;
  last_fetch_status: string | null;
  last_fetch_error: string | null;
  created_at: string;
}

export interface BoostTopic {
  id: string;
  term: string;
  created_at: string;
}

export interface RadarItem {
  id: string;
  source_id: string;
  url: string;
  title: string;
  summary: string;
  published_at: string | null;
  relevance_score: number;
  quality_score: number;
  reasoning: string;
  status: string;
  added_source_id: string | null;
  created_at: string;
}

export interface RadarRefreshSummary {
  per_source: Record<string, Record<string, unknown>>;
}

export async function listRadarItems(): Promise<RadarItem[]> {
  const res = await fetch(`${BACKEND_URL}/radar`, { cache: "no-store" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to list radar items"));
  const body = await res.json();
  return body.items;
}

export async function refreshRadar(): Promise<RadarRefreshSummary> {
  const res = await fetch(`${BACKEND_URL}/radar/refresh`, { method: "POST" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to refresh radar"));
  return res.json();
}

export async function addRadarItem(id: string): Promise<{ id: string; title: string }> {
  const res = await fetch(`${BACKEND_URL}/radar/items/${id}/add`, { method: "POST" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to add item"));
  return res.json();
}

export async function dismissRadarItem(id: string): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/radar/items/${id}/dismiss`, { method: "POST" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to dismiss item"));
}

export async function listFeedSources(): Promise<FeedSource[]> {
  const res = await fetch(`${BACKEND_URL}/radar/sources`, { cache: "no-store" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to list feed sources"));
  const body = await res.json();
  return body.sources;
}

export async function addFeedSource(name: string, url: string): Promise<FeedSource> {
  const res = await fetch(`${BACKEND_URL}/radar/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, url }),
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to add feed source"));
  return res.json();
}

export async function deleteFeedSource(id: string): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/radar/sources/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to delete feed source"));
}

export async function listBoostTopics(): Promise<BoostTopic[]> {
  const res = await fetch(`${BACKEND_URL}/radar/boost-topics`, { cache: "no-store" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to list boost topics"));
  const body = await res.json();
  return body.topics;
}

export async function addBoostTopic(term: string): Promise<BoostTopic> {
  const res = await fetch(`${BACKEND_URL}/radar/boost-topics`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ term }),
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to add boost topic"));
  return res.json();
}

export async function deleteBoostTopic(id: string): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/radar/boost-topics/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to delete boost topic"));
}

export interface Preferences {
  font_scale: number;
}

export async function getPreferences(): Promise<Preferences> {
  const res = await fetch(`${BACKEND_URL}/preferences`, { cache: "no-store" });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to load preferences"));
  return res.json();
}

export async function updatePreferences(fontScale: number): Promise<Preferences> {
  const res = await fetch(`${BACKEND_URL}/preferences`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ font_scale: fontScale }),
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to save preferences"));
  return res.json();
}
