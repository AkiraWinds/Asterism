"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { getGraph, GraphData } from "@/lib/api";

// react-force-graph-2d touches `window` at module load time, so it must be
// loaded client-side only (Next.js SSR would otherwise crash on import).
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

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
  // sibling WikiPagePanel. Measure the wrapper ourselves and pass explicit
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
            nodes: graph.nodes.map((n) => ({ id: n.id, name: n.term, val: n.self_relevant ? 2 : 1 })),
            links: graph.edges.map((e) => ({ source: e.from_id, target: e.to_id, label: e.type })),
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
          // Mirrors globals.css's --app-muted-foreground (the token this
          // app already uses for secondary/dim content) — read directly
          // from the media-query state above, since the canvas can't
          // consume CSS variables itself. Node color intentionally left at
          // the library default: differentiating nodes visually by
          // provenance tier is explicitly out of scope for this feature
          // (see docs/superpowers/specs/2026-08-19-graph-wiki-panel-design.md).
          linkColor={() => (isDark ? "#A8A2B8" : "#71717A")}
          linkWidth={1}
          onNodeClick={(node: { id?: string | number }) => {
            const full = graph.nodes.find((n) => n.id === String(node.id)) ?? null;
            onSelectNode(full);
          }}
        />
      )}
    </div>
  );
}
