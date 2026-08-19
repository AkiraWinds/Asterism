"use client";

// Shows the already-compiled wiki page for whichever concept is selected in
// the graph panel (ConceptGraphView). Purely a reader — no compile-trigger
// UI here; wiki freshness is a backend/scheduling concern handled
// elsewhere (see docs/superpowers/specs/2026-08-19-graph-wiki-panel-design.md
// for why this is a deliberate scope boundary, not an oversight).

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { GraphConceptNode, WikiPage, WikiPageAspect, getWikiPageByConceptId, getWikiPageBySlug } from "@/lib/api";

const MIN_PROVENANCE_COUNT = 3; // mirrors backend/app/wiki/selection.py's threshold, for the explanatory copy below

export function WikiPagePanel({ node }: { node: GraphConceptNode | null }) {
  const [page, setPage] = useState<WikiPage | null>(null);
  const [pageLoading, setPageLoading] = useState(false);
  // Error from the initial per-node fetch — replaces the whole panel, since
  // there's nothing else loaded yet to fall back to.
  const [pageError, setPageError] = useState<string | null>(null);
  // When set, the panel is showing this aspect's body instead of the
  // overview's — cleared whenever the selected graph node changes.
  const [activeAspect, setActiveAspect] = useState<WikiPage | null>(null);
  const [aspectLoading, setAspectLoading] = useState(false);
  // Error from an *aspect* fetch. Kept separate from pageError so a failed
  // aspect click never takes down the overview the user already has loaded
  // — it's rendered as a dismissible banner alongside the back button
  // instead of replacing the panel (see openAspect below).
  const [aspectError, setAspectError] = useState<string | null>(null);
  // Tracks the slug of the most recently clicked aspect so a late-resolving
  // fetch for an aspect the user has already moved on from can be dropped
  // instead of clobbering state (see openAspect below).
  const latestAspectSlug = useRef<string | null>(null);

  useEffect(() => {
    let stale = false;
    setActiveAspect(null);
    setAspectError(null);
    latestAspectSlug.current = null;
    setPageError(null);
    if (node === null) {
      setPage(null);
      return;
    }
    setPageLoading(true);
    getWikiPageByConceptId(node.id)
      .then((result) => {
        if (!stale) setPage(result);
      })
      .catch((err) => {
        if (!stale) setPageError(err instanceof Error ? err.message : "Failed to load wiki page");
      })
      .finally(() => {
        if (!stale) setPageLoading(false);
      });
    // Cleanup runs when `node` changes again (or the component unmounts)
    // before this fetch resolves — mark it stale so its callbacks no-op.
    return () => {
      stale = true;
    };
  }, [node]);

  function openAspect(aspect: WikiPageAspect) {
    latestAspectSlug.current = aspect.slug;
    setAspectLoading(true);
    setAspectError(null);
    getWikiPageBySlug(aspect.slug)
      .then((result) => {
        // Drop this response if the user has since clicked a different
        // aspect (or the node/effect above reset the tracked slug).
        if (latestAspectSlug.current !== aspect.slug) return;
        if (result === null) {
          // 404 means "this aspect page doesn't exist (any more)" — distinct
          // from "no aspect clicked yet", which also reads as `null`. Surface
          // that explicitly instead of silently reverting to the overview.
          setAspectError("That aspect page is no longer available.");
          setActiveAspect(null);
          return;
        }
        setActiveAspect(result);
      })
      .catch((err) => {
        if (latestAspectSlug.current !== aspect.slug) return;
        setAspectError(err instanceof Error ? err.message : "Failed to load aspect page");
        setActiveAspect(null);
      })
      .finally(() => {
        if (latestAspectSlug.current !== aspect.slug) return;
        setAspectLoading(false);
      });
  }

  if (node === null) {
    return <p className="text-sm text-muted-foreground">Select a concept to read its page.</p>;
  }

  if (pageLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  if (pageError) {
    return <p className="text-sm text-destructive">Couldn&apos;t load the wiki page: {pageError}</p>;
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
          onClick={() => {
            setActiveAspect(null);
            setAspectError(null);
          }}
          className="mb-3 text-sm text-muted-foreground hover:text-foreground hover:underline"
        >
          ← Back to {page?.term}
        </button>
      )}
      {aspectError && <p className="mb-3 text-sm text-destructive">{aspectError}</p>}
      {aspectLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <>
          <h2 className="font-heading text-xl font-bold text-foreground">{shown.term}</h2>
          {shown.updated_at && (
            <p className="mt-1 text-xs text-muted-foreground">Updated {shown.updated_at.slice(0, 10)}</p>
          )}
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
        </>
      )}
    </div>
  );
}
