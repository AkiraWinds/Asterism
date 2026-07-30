"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { getGraph, GraphData } from "@/lib/api";

// react-force-graph-2d touches `window` at module load time, so it must be
// loaded client-side only (Next.js SSR would otherwise crash on import).
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

export function ConceptGraphView() {
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphData["nodes"][number] | null>(null);

  useEffect(() => {
    getGraph()
      .then(setGraph)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load graph"));
  }, []);

  if (error) {
    return <p className="text-sm text-red-600 dark:text-red-400">Couldn&apos;t load the concept graph: {error}</p>;
  }

  if (!graph) {
    return <p className="text-sm text-neutral-500 dark:text-neutral-400">Loading…</p>;
  }

  if (graph.nodes.length === 0) {
    return (
      <p className="text-sm text-neutral-500 dark:text-neutral-400">
        No concepts yet — save a highlight from a source to start building the graph.
      </p>
    );
  }

  const graphData = {
    nodes: graph.nodes.map((n) => ({ id: n.id, name: n.term, val: n.self_relevant ? 2 : 1 })),
    links: graph.edges.map((e) => ({ source: e.from_id, target: e.to_id, label: e.type })),
  };

  return (
    <div className="relative h-[70vh] w-full rounded-lg border border-neutral-200 dark:border-neutral-800">
      <ForceGraph2D
        graphData={graphData}
        nodeLabel="name"
        onNodeClick={(node: { id?: string | number }) => {
          const full = graph.nodes.find((n) => n.id === String(node.id)) ?? null;
          setSelectedNode(full);
        }}
      />
      {selectedNode && (
        <div className="absolute bottom-3 left-3 max-w-sm rounded-md border border-neutral-200 bg-white p-3 text-sm shadow-md dark:border-neutral-700 dark:bg-neutral-800">
          <p className="font-medium text-neutral-900 dark:text-neutral-100">{selectedNode.term}</p>
          <p className="mt-1 text-neutral-600 dark:text-neutral-300">{selectedNode.definition}</p>
        </div>
      )}
    </div>
  );
}
