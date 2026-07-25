const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export interface SourceSummary {
  id: string;
  title: string;
  created_at: string;
}

export interface SourceDetail extends SourceSummary {
  content: string;
}

export async function listSources(): Promise<SourceSummary[]> {
  const res = await fetch(`${BACKEND_URL}/sources`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to list sources");
  return res.json();
}

export async function createSource(title: string, content: string): Promise<SourceDetail> {
  const res = await fetch(`${BACKEND_URL}/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, content }),
  });
  if (!res.ok) throw new Error("Failed to create source");
  return res.json();
}

export async function getSource(id: string): Promise<SourceDetail> {
  const res = await fetch(`${BACKEND_URL}/sources/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to get source");
  return res.json();
}
