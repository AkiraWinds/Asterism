"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { getGraph, GraphData } from "@/lib/api";

// react-force-graph-2d touches `window` at module load time, so it must be
// loaded client-side only (Next.js SSR would otherwise crash on import).
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

// First-pass palette for the 4 node kinds and 4 edge kinds — extends the
// app's existing "Soft Lavender" tokens (frontend/src/app/globals.css) with
// new hues for source/wiki, since the canvas can't consume CSS variables
// (see the existing isDark-driven linkColor below for why this is
// hardcoded rather than a CSS class). Module-scope (not component-local) so
// these aren't re-created on every render; isDark is passed in explicitly
// at each call site since they can no longer close over component state.
const NODE_COLORS: Record<string, { light: string; dark: string }> = {
  concept: { light: "#8B5CF6", dark: "#A78BFA" }, // app-accent
  source: { light: "#0D9488", dark: "#2DD4BF" }, // teal
  wiki: { light: "#DB2777", dark: "#F472B6" }, // rose (overview)
  wikiAspect: { light: "#F0ABFC", dark: "#F5D0FE" }, // lighter rose (aspect — dimmer variant)
};

const EDGE_COLORS: Record<string, { light: string; dark: string }> = {
  concept_relation: { light: "#71717A", dark: "#A8A2B8" }, // unchanged from today's single edge color
  source_link: { light: "#0D9488", dark: "#2DD4BF" },
  wiki_link: { light: "#DB2777", dark: "#F472B6" },
  aspect_link: { light: "#F0ABFC", dark: "#F5D0FE" },
};

function nodeColorFor(node: { kind: string; is_aspect: boolean }, dark: boolean): string {
  const key = node.kind === "wiki" && node.is_aspect ? "wikiAspect" : node.kind;
  const entry = NODE_COLORS[key] ?? NODE_COLORS.concept;
  return dark ? entry.dark : entry.light;
}

function edgeColorFor(kind: string, dark: boolean): string {
  const entry = EDGE_COLORS[kind] ?? EDGE_COLORS.concept_relation;
  return dark ? entry.dark : entry.light;
}

export function ConceptGraphView({
  onSelectNode,
}: {
  onSelectNode: (node: GraphData["nodes"][number] | null) => void;
}) {
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [error, setError] = useState<string | null>(null);
  // ForceGraph2D defaults to window.innerWidth/innerHeight with no
  // auto-resize, which overflows this component's grid column and — since
  // the wrapper is `position: relative` — steals pointer events from the
  // sibling GraphNodePanel. Measure the wrapper ourselves and pass explicit
  // dimensions instead.
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  // The canvas is painted, not styled via CSS, so it can't inherit this
  // app's theme tokens (globals.css's --app-* variables) the way the rest
  // of the UI does. This app has no manual light/dark toggle — theme is
  // purely OS-driven via `prefers-color-scheme` — so mirroring that same
  // media query here, and hardcoding the two token values it switches
  // between, is the canvas-side equivalent of what every other component
  // gets for free through CSS variables.
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    setIsDark(mql.matches);
    const onChange = (e: MediaQueryListEvent) => setIsDark(e.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    getGraph()
      .then(setGraph)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load graph"));
  }, []);

  // The ref callback fires as soon as the wrapper div mounts (which happens
  // on the very first render, since the wrapper below is rendered
  // unconditionally regardless of loading/error/empty state) — so the
  // observer always has a real element to attach to, and `measure()` runs
  // immediately on mount in addition to on every subsequent resize.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const measure = () => setDimensions({ width: el.clientWidth, height: el.clientHeight });
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Memoized on `graph` specifically (not recomputed on every render): this
  // component re-renders on every click (selection state lives one level up
  // in GraphPage, and clicking triggers that parent to re-render) and on
  // every ResizeObserver callback. Without memoizing, ForceGraph2D would see
  // a brand-new graphData object reference on each of those — even though
  // the underlying nodes/edges haven't changed — and visibly restart its
  // force simulation, producing a jarring jump on every click.
  const graphData = useMemo(
    () =>
      graph
        ? {
            nodes: graph.nodes.map((n) => ({
              id: n.id,
              name: n.term,
              val: n.self_relevant ? 2 : 1,
              kind: n.kind,
              is_aspect: n.is_aspect,
            })),
            links: graph.edges.map((e) => ({ source: e.from_id, target: e.to_id, kind: e.kind, label: e.type })),
          }
        : null,
    [graph]
  );

  return (
    <div ref={containerRef} className="relative h-[560px] w-full overflow-hidden rounded-lg border border-border">
      {error && (
        <p className="p-4 text-sm text-destructive">Couldn&apos;t load the concept graph: {error}</p>
      )}
      {!error && !graph && <p className="p-4 text-sm text-muted-foreground">Loading…</p>}
      {!error && graph && graph.nodes.length === 0 && (
        <p className="p-4 text-sm text-muted-foreground">
          No concepts yet — save a highlight from a source to start building the graph.
        </p>
      )}
      {!error && graph && graphData && graph.nodes.length > 0 && dimensions.width > 0 && dimensions.height > 0 && (
        <ForceGraph2D
          width={dimensions.width}
          height={dimensions.height}
          graphData={graphData}
          nodeLabel="name"
          nodeColor={(node) =>
            nodeColorFor(
              { kind: (node as { kind?: string }).kind ?? "concept", is_aspect: (node as { is_aspect?: boolean }).is_aspect ?? false },
              isDark
            )
          }
          linkColor={(link) => edgeColorFor((link as { kind?: string }).kind ?? "concept_relation", isDark)}
          linkLabel={(link) => {
            const l = link as { kind?: string; label?: string | null };
            return l.kind === "concept_relation" && l.label ? l.label : "";
          }}
          linkWidth={1}
          onNodeClick={(node: { id?: string | number }) => {
            const full = graph.nodes.find((n) => n.id === String(node.id)) ?? null;
            onSelectNode(full);
          }}
        />
      )}
      {!error && graph && graph.nodes.length > 0 && (
        <div className="absolute bottom-2 left-2 flex flex-col gap-1 rounded-md border border-border bg-card/90 p-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: nodeColorFor({ kind: "concept", is_aspect: false }, isDark) }}
            />{" "}
            Concept
          </div>
          <div className="flex items-center gap-1">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: nodeColorFor({ kind: "source", is_aspect: false }, isDark) }}
            />{" "}
            Source
          </div>
          <div className="flex items-center gap-1">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: nodeColorFor({ kind: "wiki", is_aspect: false }, isDark) }}
            />{" "}
            Wiki page
          </div>
          <div className="flex items-center gap-1">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: nodeColorFor({ kind: "wiki", is_aspect: true }, isDark) }}
            />{" "}
            Wiki aspect
          </div>
          <div className="flex items-center gap-1">
            <span
              className="inline-block h-0.5 w-3"
              style={{ background: edgeColorFor("concept_relation", isDark) }}
            />{" "}
            Concept relation
          </div>
          <div className="flex items-center gap-1">
            <span
              className="inline-block h-0.5 w-3"
              style={{ background: edgeColorFor("source_link", isDark) }}
            />{" "}
            Source link
          </div>
          <div className="flex items-center gap-1">
            <span
              className="inline-block h-0.5 w-3"
              style={{ background: edgeColorFor("wiki_link", isDark) }}
            />{" "}
            Wiki link
          </div>
          <div className="flex items-center gap-1">
            <span
              className="inline-block h-0.5 w-3"
              style={{ background: edgeColorFor("aspect_link", isDark) }}
            />{" "}
            Aspect link
          </div>
        </div>
      )}
    </div>
  );
}
