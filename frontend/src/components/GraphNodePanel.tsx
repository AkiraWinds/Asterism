"use client";

// Detail panel for whichever node is selected in the graph panel
// (ConceptGraphView) — a concept, a source, or a wiki/aspect page, each with
// its own render branch below. For concept nodes it shows the already-
// compiled wiki page; purely a reader — no compile-trigger UI here, wiki
// freshness is a backend/scheduling concern handled elsewhere (see
// docs/superpowers/specs/2026-08-19-graph-wiki-panel-design.md for why
// this is a deliberate scope boundary, not an oversight).

import { ReactNode, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  GraphViewNode,
  SourcePreview,
  WikiPage,
  WikiPageAspect,
  getSourcePreview,
  getWikiPageByConceptId,
  getWikiPageBySlug,
} from "@/lib/api";

// Wiki body markdown (render_related_section / render_index in
// backend/app/wiki/render.py) links to other wiki pages with a relative
// "./{slug}.md"-style href — meaningful when browsing the raw files on
// disk, but this app renders that same markdown inside a Next.js page, so
// a plain <a> would try to navigate to a route that doesn't exist (404).
// Extracts the slug so callers can intercept the click instead of letting
// the browser navigate — returns null for any other href (e.g. the
// "## Sources" section's /?source={id} deep links, which ARE a real,
// working target and should navigate normally).
function extractRelativeWikiSlug(href?: string): string | null {
  if (!href) return null;
  const match = href.match(/^\.?\/?([\w-]+)\.md$/);
  return match ? match[1] : null;
}

// Shared `a` renderer for ReactMarkdown: relative wiki-page links call
// `onWikiLinkClick` instead of navigating; everything else (the /?source=
// deep links, or any external link) renders as a normal anchor.
function makeWikiLinkComponents(onWikiLinkClick: (slug: string, term: string) => void) {
  return {
    a: ({ href, children }: { href?: string; children?: ReactNode }) => {
      const slug = extractRelativeWikiSlug(href);
      if (slug) {
        return (
          <a
            href={href}
            onClick={(e) => {
              e.preventDefault();
              onWikiLinkClick(slug, typeof children === "string" ? children : slug);
            }}
            className="cursor-pointer text-accent hover:underline"
          >
            {children}
          </a>
        );
      }
      return (
        <a href={href} className="text-accent hover:underline">
          {children}
        </a>
      );
    },
  };
}

const MIN_PROVENANCE_COUNT = 3; // mirrors backend/app/wiki/selection.py's threshold, for the explanatory copy below
// Client-side truncation threshold for the source-preview body (spec:
// "truncated with a 'show more' toggle if long"). The backend never
// truncates (see get_source_preview_endpoint) since truncating server-side
// would lose the text the toggle needs to expand into — this is purely a
// display concern, applied to both source types (html digests can be long too).
const PREVIEW_TRUNCATE_LENGTH = 500;

export function GraphNodePanel({ node }: { node: GraphViewNode | null }) {
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
  // Preview state for source nodes — populated by the effect below,
  // rendered by the kind === "source" branch further down.
  const [sourcePreview, setSourcePreview] = useState<SourcePreview | null>(null);
  const [sourcePreviewLoading, setSourcePreviewLoading] = useState(false);
  const [sourcePreviewError, setSourcePreviewError] = useState<string | null>(null);
  // Whether the truncated preview body is expanded to its full text — reset
  // to collapsed whenever the selected node changes (see the fetch effect
  // below, same convention as activeAspect/aspectError's reset).
  const [sourcePreviewExpanded, setSourcePreviewExpanded] = useState(false);

  useEffect(() => {
    let stale = false;
    setActiveAspect(null);
    setAspectError(null);
    setPageError(null);
    // Only concept nodes resolve to a wiki page via concept id — source and
    // wiki nodes are handled by their own effect/branch below.
    if (node === null || node.kind !== "concept") {
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

  useEffect(() => {
    let stale = false;
    setSourcePreview(null);
    setSourcePreviewError(null);
    setSourcePreviewExpanded(false);
    if (node === null || node.kind !== "source") return;
    // node.id is "src_<source_id>" (see backend/app/graph_store/view.py) — strip the prefix.
    const sourceId = node.id.replace(/^src_/, "");
    setSourcePreviewLoading(true);
    getSourcePreview(sourceId)
      .then((result) => {
        if (!stale) setSourcePreview(result);
      })
      .catch((err) => {
        if (!stale) setSourcePreviewError(err instanceof Error ? err.message : "Failed to load source preview");
      })
      .finally(() => {
        if (!stale) setSourcePreviewLoading(false);
      });
    return () => {
      stale = true;
    };
  }, [node]);

  // Deliberately ref-free (a prior version tracked the most-recently-
  // clicked slug in a ref to drop a stale response — dropped because
  // passing a ref-closing function into ReactMarkdown's `components` prop,
  // needed below to intercept in-body wiki links, trips the
  // react-hooks/refs rule: it can't prove the ref is read only from an
  // event handler and not during render). Two aspect/related-link clicks
  // racing — click one, then another before the first resolves — could
  // show the first one's content last if it resolves second; an acceptable
  // rare edge case here, same tradeoff DirectWikiNodeView's openLinkedPage
  // below makes.
  function openAspect(aspect: WikiPageAspect) {
    setAspectLoading(true);
    setAspectError(null);
    getWikiPageBySlug(aspect.slug)
      .then((result) => {
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
        setAspectError(err instanceof Error ? err.message : "Failed to load aspect page");
        setActiveAspect(null);
      })
      .finally(() => setAspectLoading(false));
  }

  if (node === null) {
    return <p className="text-sm text-muted-foreground">Select a concept to read its page.</p>;
  }

  // A wiki/aspect node clicked directly (not reached via a concept's aspect
  // list) carries a slug, not a concept id — fetch it by slug instead.
  if (node.kind === "wiki") {
    return <DirectWikiNodeView slug={node.id.replace(/^wiki:/, "")} term={node.term} />;
  }

  if (node.kind === "source") {
    const sourceId = node.id.replace(/^src_/, "");
    if (sourcePreviewLoading) {
      return <p className="text-sm text-muted-foreground">Loading…</p>;
    }
    if (sourcePreviewError) {
      return <p className="text-sm text-destructive">Couldn&apos;t load this source: {sourcePreviewError}</p>;
    }
    return (
      <div>
        <h2 className="font-heading text-xl font-bold text-foreground">{node.term}</h2>
        {/* NOT /sources/{id} — that route doesn't exist; source selection is
            client-side state on the unified workspace page (frontend/src/app/page.tsx),
            which reads this query param once on mount to deep-link into it. */}
        <a
          href={`/?source=${sourceId}`}
          className="mt-1 inline-block text-sm text-accent hover:underline"
        >
          Open source →
        </a>
        {sourcePreview && sourcePreview.id === sourceId && (
          <>
            <div className="prose prose-sm prose-neutral dark:prose-invert max-w-none mt-4 rounded-lg border border-border bg-card p-5">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {sourcePreview.preview_text.length > PREVIEW_TRUNCATE_LENGTH && !sourcePreviewExpanded
                  ? `${sourcePreview.preview_text.slice(0, PREVIEW_TRUNCATE_LENGTH)}…`
                  : sourcePreview.preview_text}
              </ReactMarkdown>
            </div>
            {sourcePreview.preview_text.length > PREVIEW_TRUNCATE_LENGTH && (
              <button
                type="button"
                onClick={() => setSourcePreviewExpanded((expanded) => !expanded)}
                className="mt-2 text-sm text-accent hover:underline"
              >
                {sourcePreviewExpanded ? "Show less" : "Show more"}
              </button>
            )}
          </>
        )}
      </div>
    );
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
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              // "Related concepts" links (render_related_section) point at
              // another concept's own wiki page by slug — reuse the exact
              // same fetch-and-show-inline flow the Aspects list already
              // uses below, rather than letting the browser try to
              // navigate a relative ./slug.md href that has no route.
              components={makeWikiLinkComponents((slug, term) => openAspect({ slug, term }))}
            >
              {shown.body}
            </ReactMarkdown>
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

// Renders a wiki/aspect node that was clicked directly in the graph (rather
// than reached via a concept's aspect list) — fetched by slug since a
// directly-clicked node's id carries the slug, not a concept id. Mirrors the
// fetch-by-slug pattern in openAspect above.
function DirectWikiNodeView({ slug, term }: { slug: string; term: string }) {
  const [page, setPage] = useState<WikiPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // A "Related concepts" link inside this page's own body can point at yet
  // another wiki page — swap it in here rather than trying to navigate, the
  // same idea as GraphNodePanel's activeAspect above, just scoped locally
  // since a directly-clicked wiki node has no separate "overview" to return
  // to other than the page it originally loaded.
  const [linkedPage, setLinkedPage] = useState<WikiPage | null>(null);
  const [linkedLoading, setLinkedLoading] = useState(false);
  const [linkedError, setLinkedError] = useState<string | null>(null);

  useEffect(() => {
    let stale = false;
    setLinkedPage(null);
    setLinkedError(null);
    getWikiPageBySlug(slug)
      .then((result) => {
        if (!stale) setPage(result);
      })
      .catch((err) => {
        if (!stale) setError(err instanceof Error ? err.message : "Failed to load wiki page");
      })
      .finally(() => {
        if (!stale) setLoading(false);
      });
    return () => {
      stale = true;
    };
  }, [slug]);

  // Deliberately ref-free (unlike openAspect above, which guards against a
  // stale response with a ref): two related-link clicks racing here — click
  // link A, then link B before A resolves — could show A's content last if
  // it resolves after B. An acceptable rare edge case for this secondary,
  // already-nested navigation path; not worth the extra state for.
  function openLinkedPage(linkedSlug: string) {
    setLinkedLoading(true);
    setLinkedError(null);
    getWikiPageBySlug(linkedSlug)
      .then((result) => {
        if (result === null) {
          setLinkedError("That page is no longer available.");
          setLinkedPage(null);
          return;
        }
        setLinkedPage(result);
      })
      .catch((err) => {
        setLinkedError(err instanceof Error ? err.message : "Failed to load page");
        setLinkedPage(null);
      })
      .finally(() => setLinkedLoading(false));
  }

  if (loading) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (error) return <p className="text-sm text-destructive">Couldn&apos;t load the wiki page: {error}</p>;
  if (page === null) return <p className="text-sm text-muted-foreground">This wiki page is no longer available.</p>;

  const shown = linkedPage ?? page;

  return (
    <div>
      {linkedPage && (
        <button
          type="button"
          onClick={() => {
            setLinkedPage(null);
            setLinkedError(null);
          }}
          className="mb-3 text-sm text-muted-foreground hover:text-foreground hover:underline"
        >
          ← Back to {term}
        </button>
      )}
      {linkedError && <p className="mb-3 text-sm text-destructive">{linkedError}</p>}
      {linkedLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <>
          <h2 className="font-heading text-xl font-bold text-foreground">{shown.term}</h2>
          {shown.updated_at && (
            <p className="mt-1 text-xs text-muted-foreground">Updated {shown.updated_at.slice(0, 10)}</p>
          )}
          <div className="prose prose-sm prose-neutral dark:prose-invert max-w-none mt-4 rounded-lg border border-border bg-card p-5">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={makeWikiLinkComponents(openLinkedPage)}>
              {shown.body}
            </ReactMarkdown>
          </div>
        </>
      )}
    </div>
  );
}
