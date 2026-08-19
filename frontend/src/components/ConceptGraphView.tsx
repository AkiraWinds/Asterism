"use client";

import { useEffect, useState } from "react";
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

  useEffect(() => {
    getGraph()
      .then(setGraph)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load graph"));
  }, []);

  if (error) {
    return <p className="text-sm text-destructive">Couldn&apos;t load the concept graph: {error}</p>;
  }

  if (!graph) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  if (graph.nodes.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No concepts yet — save a highlight from a source to start building the graph.
      </p>
    );
  }

  const graphData = {
    nodes: graph.nodes.map((n) => ({ id: n.id, name: n.term, val: n.self_relevant ? 2 : 1 })),
    links: graph.edges.map((e) => ({ source: e.from_id, target: e.to_id, label: e.type })),
  };

  return (
    <div className="relative h-[70vh] w-full rounded-lg border border-border">
      <ForceGraph2D
        graphData={graphData}
        nodeLabel="name"
        onNodeClick={(node: { id?: string | number }) => {
          const full = graph.nodes.find((n) => n.id === String(node.id)) ?? null;
          onSelectNode(full);
        }}
      />
    </div>
  );
}
