"use client";

import { useEffect, useRef, useState } from "react";
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

  const graphData = graph
    ? {
        nodes: graph.nodes.map((n) => ({ id: n.id, name: n.term, val: n.self_relevant ? 2 : 1 })),
        links: graph.edges.map((e) => ({ source: e.from_id, target: e.to_id, label: e.type })),
      }
    : null;

  return (
    <div ref={containerRef} className="relative h-[70vh] w-full overflow-hidden rounded-lg border border-border">
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
          onNodeClick={(node: { id?: string | number }) => {
            const full = graph.nodes.find((n) => n.id === String(node.id)) ?? null;
            onSelectNode(full);
          }}
        />
      )}
    </div>
  );
}
