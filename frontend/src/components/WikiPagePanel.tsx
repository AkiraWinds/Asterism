"use client";

// Shows the already-compiled wiki page for whichever concept is selected in
// the graph panel (ConceptGraphView). Purely a reader — no compile-trigger
// UI here; wiki freshness is a backend/scheduling concern handled
// elsewhere (see docs/superpowers/specs/2026-08-19-graph-wiki-panel-design.md
// for why this is a deliberate scope boundary, not an oversight).

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { GraphConceptNode, WikiPage, getWikiPageByConceptId, getWikiPageBySlug } from "@/lib/api";

const MIN_PROVENANCE_COUNT = 3; // mirrors backend/app/wiki/selection.py's threshold, for the explanatory copy below

export function WikiPagePanel({ node }: { node: GraphConceptNode | null }) {
  const [page, setPage] = useState<WikiPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // When set, the panel is showing this aspect's body instead of the
  // overview's — cleared whenever the selected graph node changes.
  const [activeAspect, setActiveAspect] = useState<WikiPage | null>(null);

  useEffect(() => {
    setActiveAspect(null);
    setError(null);
    if (node === null) {
      setPage(null);
      return;
    }
    setLoading(true);
    getWikiPageByConceptId(node.id)
      .then(setPage)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load wiki page"))
      .finally(() => setLoading(false));
  }, [node]);

  function openAspect(aspect: { slug: string }) {
    setLoading(true);
    setError(null);
    getWikiPageBySlug(aspect.slug)
      .then(setActiveAspect)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load aspect page"))
      .finally(() => setLoading(false));
  }

  if (node === null) {
    return <p className="text-sm text-muted-foreground">Select a concept to read its page.</p>;
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  if (error) {
    return <p className="text-sm text-destructive">Couldn&apos;t load the wiki page: {error}</p>;
  }

  const shown = activeAspect ?? page;

  // No wiki page yet for this concept — show what's already known locally
  // (term/definition came with the graph data, no extra request needed)
  // plus why there's nothing more to read.
  if (shown === null) {
    return (
      <div>
        <h2 className="font-heading text-xl font-bold text-foreground">{node.term}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{node.definition}</p>
        <p className="mt-4 text-sm text-muted-foreground">
          This concept doesn&apos;t have a wiki page yet — it needs at least {MIN_PROVENANCE_COUNT} linked sources
          (or to be marked golden) before one is generated.
        </p>
      </div>
    );
  }

  return (
    <div>
      {activeAspect && (
        <button
          type="button"
          onClick={() => setActiveAspect(null)}
          className="mb-3 text-sm text-muted-foreground hover:text-foreground hover:underline"
        >
          ← Back to {page?.term}
        </button>
      )}
      <h2 className="font-heading text-xl font-bold text-foreground">{shown.term}</h2>
      <p className="mt-1 text-xs text-muted-foreground">Updated {shown.updated_at.slice(0, 10)}</p>
      <div className="prose prose-sm prose-neutral dark:prose-invert max-w-none mt-4 rounded-lg border border-border bg-card p-5">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{shown.body}</ReactMarkdown>
      </div>
      {!activeAspect && page && page.aspects.length > 0 && (
        <div className="mt-4">
          <p className="text-sm font-medium text-foreground">Aspects</p>
          <ul className="mt-1 flex flex-col gap-1">
            {page.aspects.map((aspect) => (
              <li key={aspect.slug}>
                <button
                  type="button"
                  onClick={() => openAspect(aspect)}
                  className="text-sm text-accent hover:underline"
                >
                  {aspect.term}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
